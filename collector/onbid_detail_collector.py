"""
onbid_detail_collector.py
─────────────────────────────────────────────────────────────────────────────
BID_ITEMS(물건목록)에서 cltrMngNo + pbctCdtnNo 를 읽어
온비드 부동산 물건상세 조회 API(getRlstDtlInf)를 호출하고
응답을 9개 서브 테이블에 저장한다.

[서브 테이블]
  BID_SQMS        - 면적정보          (1:N)
  BID_APSL_EVL    - 감정평가정보       (1:N)
  BID_LEAS_INF    - 임대차정보         (1:N, 압류재산만)
  BID_RGST_PRMR   - 등기사항증명서     (1:N, 압류재산만)
  BID_DTBT_RQR    - 배분요구사항       (1:N, 압류재산만)
  BID_OCPY_REL    - 점유관계           (1:N, 압류재산만)
  BID_BATC_CLTR   - 일괄입찰물건목록   (1:N)
  BID_CRTN_LST    - 정정내역           (1:N)
  BID_PAPS_INF    - 공매재산명세서     (1:1)

[실행 전략]
  - BID_ITEMS.detail_fetched_at IS NULL  → 한 번도 상세 조회 안 한 물건 우선 처리
  - BID_ITEMS.crtn_yn = 'Y'             → 정정 이력 있으면 재조회
  - status = 'active' 인 물건만 대상
  - API 초당 10 tps 제한 → 호출마다 0.15초 대기
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import sqlite3
import urllib.parse
import requests
import logging
import time
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import to_int, to_float, to_str, now_str, to_list
from db.schema_detail import init_detail_db

# ─────────────────────────────────────────
# 설정 (기존 collector.py와 동일 값 사용)
# ─────────────────────────────────────────
SERVICE_KEY = urllib.parse.quote(os.environ["ONBID_API_KEY"], safe="")
DETAIL_URL  = "https://apis.data.go.kr/B010003/OnbidRlstDtlSrvc2/getRlstDtlInf2"
DB_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "onbid.db")

SLEEP_SEC       = 0.15   # API 10 tps 제한 → 호출 간 대기(초)
BATCH_SIZE      = 50     # 한 번에 처리할 물건 수 (메모리 절약)
FORCE_REFETCH   = False  # True 이면 이미 조회한 물건도 재조회

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("onbid_detail.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────
# API 호출
# ─────────────────────────────────────────
class RateLimitExceeded(Exception):
    """API 일일 한도(429) 초과 — 더 호출해도 모두 실패하므로 즉시 종료 신호."""


def fetch_detail(cltr_mng_no: str, pbct_cdtn_no) -> dict | None:
    """물건상세 조회 API 호출. 성공 시 item dict 반환, 실패 시 None.

    serviceKey는 이미 URL 인코딩된 값이므로 params 딕셔너리에 넣지 않고
    URL에 직접 포함시킨다. (params 딕셔너리 방식은 이중 인코딩 발생)
    429(Too Many Requests)는 RateLimitExceeded로 호출자에게 전파한다.
    """
    # serviceKey → URL에 직접 삽입 (이중 인코딩 방지)
    # 나머지 파라미터는 requests가 안전하게 인코딩하도록 params 딕셔너리 사용
    base = f"{DETAIL_URL}?serviceKey={SERVICE_KEY}"

    params = {
        "resultType": "json",
        "numOfRows":  1,
        "pageNo":     1,
        "cltrMngNo":  cltr_mng_no,
    }
    if pbct_cdtn_no:
        params["pbctCdtnNo"] = pbct_cdtn_no

    try:
        res = requests.get(base, params=params, timeout=15)
        if res.status_code == 429:
            raise RateLimitExceeded(f"[{cltr_mng_no}] 429 Too Many Requests")
        res.raise_for_status()
        data = res.json()
    except RateLimitExceeded:
        raise
    except Exception as e:
        log.error(f"  [{cltr_mng_no}] API 요청 실패: {e}")
        return None

    try:
        body = data.get("body", {})
        result_code = data.get("header", {}).get("resultCode", "??")

        if result_code != "00":
            log.warning(f"  [{cltr_mng_no}] 응답코드 {result_code}")
            return None

        items = body.get("items") or {}
        item  = items.get("item")

        if not item:
            log.warning(f"  [{cltr_mng_no}] item 없음 (총건수={body.get('totalCount', 0)})")
            return None

        # 단건이면 dict, 복수면 list → 첫 번째만 사용
        if isinstance(item, list):
            item = item[0]

        return item

    except Exception as e:
        log.error(f"  [{cltr_mng_no}] 응답 파싱 실패: {e}")
        return None


# ─────────────────────────────────────────
# 서브 테이블 저장
# ─────────────────────────────────────────
def _clear_sub_tables(conn: sqlite3.Connection, cltr_mng_no: str):
    """재조회 전 기존 서브 테이블 데이터 삭제 (1:N 관계 초기화)."""
    tables = [
        "BID_SQMS", "BID_APSL_EVL", "BID_LEAS_INF",
        "BID_RGST_PRMR", "BID_DTBT_RQR", "BID_OCPY_REL",
        "BID_BATC_CLTR", "BID_CRTN_LST",
    ]
    for tbl in tables:
        conn.execute(f"DELETE FROM {tbl} WHERE cltr_mng_no = ?", (cltr_mng_no,))
    # BID_PAPS_INF는 1:1이라 REPLACE로 처리 (아래 save에서 처리)


def save_sqms(conn, cltr_mng_no, rows):
    """면적정보 저장."""
    for r in rows:
        conn.execute("""
            INSERT INTO BID_SQMS
                (cltr_mng_no, cland_cont, sqms_cont, purs_alc_cont, dtl_cltr_nm)
            VALUES (?, ?, ?, ?, ?)
        """, (
            cltr_mng_no,
            to_str(r.get("clandCont")),
            to_str(r.get("sqmsCont")),
            to_str(r.get("pursAlcCont")),
            to_str(r.get("dtlCltrNm")),
        ))


def save_apsl_evl(conn, cltr_mng_no, rows):
    """감정평가정보 저장."""
    for r in rows:
        conn.execute("""
            INSERT INTO BID_APSL_EVL
                (cltr_mng_no, apsl_evl_org_nm, apsl_appr_nm, apsl_evl_ymd,
                 apsl_evl_amt, url_adr)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            cltr_mng_no,
            to_str(r.get("apslEvlOrgNm")),
            to_str(r.get("apslApprNm")),
            to_str(r.get("apslEvlYmd")),
            to_int(r.get("apslEvlAmt")),
            to_str(r.get("urlAdr")),
        ))


def save_leas_inf(conn, cltr_mng_no, rows):
    """임대차정보 저장 (압류재산 0007만 데이터 존재)."""
    for r in rows:
        conn.execute("""
            INSERT INTO BID_LEAS_INF
                (cltr_mng_no, irst_div_nm, cltr_inpr_nm, bid_grtee_amt,
                 mthr_amt, conv_grtee_amt, cfmtn_ymd, mvin_ymd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cltr_mng_no,
            to_str(r.get("irstDivNm")),
            to_str(r.get("cltrInprNm")),
            to_int(r.get("bidGrteeAmt")),
            to_float(r.get("mthrAmt")),
            to_float(r.get("convGrteeAmt")),
            to_str(r.get("cfmtnYmd")),
            to_str(r.get("mvinYmd")),
        ))


def save_rgst_prmr(conn, cltr_mng_no, rows):
    """등기사항증명서 주요정보 저장 (압류재산 0007만)."""
    for r in rows:
        conn.execute("""
            INSERT INTO BID_RGST_PRMR
                (cltr_mng_no, irst_div_nm, cltr_inpr_nm, rgst_ymd, inpr_stng_amt)
            VALUES (?, ?, ?, ?, ?)
        """, (
            cltr_mng_no,
            to_str(r.get("irstDivNm")),
            to_str(r.get("cltrInprNm")),
            to_str(r.get("rgstYmd")),
            to_int(r.get("inprStngAmt")),
        ))


def save_dtbt_rqr(conn, cltr_mng_no, rows):
    """배분요구사항목록 저장 (압류재산 0007만)."""
    for r in rows:
        conn.execute("""
            INSERT INTO BID_DTBT_RQR
                (cltr_mng_no, rgt_rel_cd_nm, acpm_prpt_nm, stng_ymd,
                 bond_stng_amt, dtbt_rqr_yn, dtbt_rqr_ymd,
                 dtbt_rqr_amt, ersr_psbl_yn, etc_cont)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cltr_mng_no,
            to_str(r.get("rgtRelCdNm")),
            to_str(r.get("acpmPrptBondDclFlnm")),
            to_str(r.get("stngYmd")),
            to_int(r.get("bondDclrStngAmt")),
            to_str(r.get("dtbtRqrYn")),
            to_str(r.get("dtbtRqrYmd")),
            to_int(r.get("dtbtRqrAmt")),
            to_str(r.get("ersrPsblYn")),
            to_str(r.get("etcCont")),
        ))


def save_ocpy_rel(conn, cltr_mng_no, rows):
    """점유관계목록 저장 (압류재산 0007만)."""
    for r in rows:
        conn.execute("""
            INSERT INTO BID_OCPY_REL
                (cltr_mng_no, ocpy_rel_cd_nm, ocpy_irps_nm, ctrt_ymd,
                 mvin_ymd, cfmtn_ymd, acpm_grtee_amt, rnt_amt, lsd_part_cont)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cltr_mng_no,
            to_str(r.get("ocpyRelCdNm")),
            to_str(r.get("acpmPrptOcpyIrpsFlnm")),
            to_str(r.get("ctrtYmd")),
            to_str(r.get("mvinYmd")),
            to_str(r.get("cfmtnYmd")),
            to_int(r.get("acpmGrteeAmt")),
            to_float(r.get("rntAmt")),
            to_str(r.get("lsdPartCont")),
        ))


def save_batc_cltr(conn, cltr_mng_no, rows):
    """일괄입찰물건목록 저장."""
    for r in rows:
        conn.execute("""
            INSERT INTO BID_BATC_CLTR
                (cltr_mng_no, sub_cltr_mng_no, prpt_div_nm, dsps_mthod_nm,
                 cltr_usg_mcls_nm, cltr_usg_scls_nm, onbid_cltr_nm,
                 usbd_nft, land_sqms, bld_sqms, apsl_evl_amt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cltr_mng_no,
            to_str(r.get("cltrMngNo")),       # 묶음 내 개별 물건번호
            to_str(r.get("prptDivNm")),
            to_str(r.get("dspsMthodNm")),
            to_str(r.get("cltrUsgMclsCtgrNm")),
            to_str(r.get("cltrUsgSclsCtgrNm")),
            to_str(r.get("onbidCltrNm")),
            to_int(r.get("usbdNft")),
            to_float(r.get("landSqms")),
            to_float(r.get("bldSqms")),
            to_int(r.get("apslEvlAmt")),
        ))


def save_crtn_lst(conn, cltr_mng_no, rows):
    """정정내역 저장."""
    for r in rows:
        conn.execute("""
            INSERT INTO BID_CRTN_LST
                (cltr_mng_no, crtn_ymd, crtn_item_cont,
                 bfmdf_lst_cont, afmdf_lst_cont)
            VALUES (?, ?, ?, ?, ?)
        """, (
            cltr_mng_no,
            to_str(r.get("crtnYmd")),
            to_str(r.get("crtnItemCont")),
            to_str(r.get("bfmdfLstCont")),
            to_str(r.get("afmdfLstCont")),
        ))


def save_paps_inf(conn, cltr_mng_no, paps: dict | list | None):
    """공매재산명세서 저장 (1:1, REPLACE)."""
    if isinstance(paps, list):
        paps = paps[0] if paps else None
    if not paps:
        return
    conn.execute("""
        INSERT OR REPLACE INTO BID_PAPS_INF (
            cltr_mng_no, dlgt_org_nm, mng_no, pbanc_ymd,
            dtbt_rqr_edtm_ymd, pbct_tdps, zadr, alc_cont,
            pbct_espc, bid_perd, opbd_ymd, dodis_p_dudt,
            ersr_excl_rgt_cont, stty_ebr_vld_cont, pytn_mtrs_cont,
            prcv_ymd, etc_smry_cont, szr_prpt_indct_cont
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        cltr_mng_no,
        to_str(paps.get("dlgtOrgNm")),
        to_str(paps.get("mngNo")),
        to_str(paps.get("pbancYmd")),
        to_str(paps.get("dtbtRqrEdtmYmd")),
        to_str(paps.get("pbctTdps")),
        to_str(paps.get("zadr")),
        to_str(paps.get("alcCont")),
        to_str(paps.get("pbctEspc")),
        to_str(paps.get("bidPerd")),
        to_str(paps.get("opbdYmd")),
        to_str(paps.get("dodispDudt")),
        to_str(paps.get("ersrExclRgtCont")),
        to_str(paps.get("sttyEbrVldCont")),
        to_str(paps.get("pytnMtrsCont")),
        to_str(paps.get("prcvYmd")),
        to_str(paps.get("etcSmryCont")),
        to_str(paps.get("szrPrptIndctCont")),
    ))


# ─────────────────────────────────────────
# 단일 물건 상세 저장 통합
# ─────────────────────────────────────────
def save_detail(conn: sqlite3.Connection, cltr_mng_no: str, item: dict):
    """API 응답 item 하나를 받아 모든 서브 테이블에 저장.

    흐름:
      1. 기존 서브 테이블 데이터 삭제 (재조회 시 중복 방지)
      2. 각 서브 배열 파싱 → INSERT
      3. BID_ITEMS.detail_fetched_at 갱신
    """
    _clear_sub_tables(conn, cltr_mng_no)

    save_sqms       (conn, cltr_mng_no, to_list(item.get("sqmsList")))
    save_apsl_evl   (conn, cltr_mng_no, to_list(item.get("apslEvlClgList")))
    save_leas_inf   (conn, cltr_mng_no, to_list(item.get("leasInfList")))
    save_rgst_prmr  (conn, cltr_mng_no, to_list(item.get("rgstPrmrInfList")))
    save_dtbt_rqr   (conn, cltr_mng_no, to_list(item.get("dtbtRqrMtrsList")))
    save_ocpy_rel   (conn, cltr_mng_no, to_list(item.get("ocpyRelList")))
    save_batc_cltr  (conn, cltr_mng_no, to_list(item.get("batcBidCltrClgList")))
    save_crtn_lst   (conn, cltr_mng_no, to_list(item.get("crtnLstClgList")))
    save_paps_inf   (conn, cltr_mng_no, item.get("papsInf"))

    # 위치 및 이용현황 + 웹 호출용 보조 식별자 저장
    conn.execute("""
        UPDATE BID_ITEMS SET
            loc_vnty_pscd_cont = ?,
            utlz_pscd_cont     = ?,
            cltr_etc_cont      = ?,
            icdl_cdtn_cont     = ?,
            zadr_nm            = ?,
            cltr_radr          = ?,
            onbid_cltrno       = ?,
            onbid_pbanc_no     = ?,
            pbct_no            = ?,
            detail_fetched_at  = ?
        WHERE cltr_mng_no = ?
    """, (
        to_str(item.get("locVntyPscdCont")),
        to_str(item.get("utlzPscdCont")),
        to_str(item.get("cltrEtcCont")),
        to_str(item.get("icdlCdtnCont")),
        to_str(item.get("zadrNm")),
        to_str(item.get("cltrRadr")),
        to_int(item.get("onbidCltrno")),
        to_int(item.get("onbidPbancNo")),
        to_int(item.get("pbctNo")),
        now_str(),
        cltr_mng_no,
    ))
    conn.commit()


# ─────────────────────────────────────────
# 조회 대상 물건 목록 가져오기
# ─────────────────────────────────────────
def get_pending_items(conn: sqlite3.Connection, force: bool = False) -> list[tuple]:
    """상세 조회가 필요한 물건 목록 반환.

    조건:
      - status = 'active' (낙찰/취소 제외)
      - force=False: detail_fetched_at IS NULL (신규 물건만 1회 수집)
      - force=True:  전체 active 물건 재조회

    detail 데이터의 사후 갱신은 detail 페이지 진입 시 frontend 가
    /api/items/<id>/refresh 로 트리거하므로(stale-while-revalidate),
    cron 단계에서는 신규 물건 backfill 만 담당한다.
    """
    if force:
        sql = """
            SELECT cltr_mng_no, pbct_cdtn_no
            FROM BID_ITEMS
            WHERE status = 'active'
            ORDER BY ratio_pct ASC
        """
    else:
        sql = """
            SELECT cltr_mng_no, pbct_cdtn_no
            FROM BID_ITEMS
            WHERE status = 'active'
              AND detail_fetched_at IS NULL
            ORDER BY ratio_pct ASC
        """
    return conn.execute(sql).fetchall()


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────
def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        init_detail_db(conn)

        pending = get_pending_items(conn, force=FORCE_REFETCH)
        total   = len(pending)

        if total == 0:
            log.info("상세 조회 대상 물건 없음 (모두 최신 상태)")
            return

        log.info(f"상세 조회 대상: {total}건 시작")
        log.info("=" * 55)

        success = 0
        fail    = 0
        aborted = False

        for idx, (cltr_mng_no, pbct_cdtn_no) in enumerate(pending, 1):
            log.info(f"[{idx}/{total}] {cltr_mng_no} (공매조건번호={pbct_cdtn_no})")

            try:
                item = fetch_detail(cltr_mng_no, pbct_cdtn_no)
            except RateLimitExceeded as e:
                log.error(f"  ⛔ API 일일 한도 초과 → 처리 중단 ({e})")
                log.error(f"  지금까지: 성공 {success} / 실패 {fail} / 미처리 {total - idx + 1}")
                aborted = True
                break

            if item:
                try:
                    save_detail(conn, cltr_mng_no, item)

                    # 저장 건수 요약 로그
                    sqms_cnt  = conn.execute("SELECT COUNT(*) FROM BID_SQMS     WHERE cltr_mng_no=?", (cltr_mng_no,)).fetchone()[0]
                    apsl_cnt  = conn.execute("SELECT COUNT(*) FROM BID_APSL_EVL WHERE cltr_mng_no=?", (cltr_mng_no,)).fetchone()[0]
                    leas_cnt  = conn.execute("SELECT COUNT(*) FROM BID_LEAS_INF WHERE cltr_mng_no=?", (cltr_mng_no,)).fetchone()[0]
                    rgst_cnt  = conn.execute("SELECT COUNT(*) FROM BID_RGST_PRMR WHERE cltr_mng_no=?", (cltr_mng_no,)).fetchone()[0]
                    dtbt_cnt  = conn.execute("SELECT COUNT(*) FROM BID_DTBT_RQR WHERE cltr_mng_no=?", (cltr_mng_no,)).fetchone()[0]
                    ocpy_cnt  = conn.execute("SELECT COUNT(*) FROM BID_OCPY_REL WHERE cltr_mng_no=?", (cltr_mng_no,)).fetchone()[0]

                    log.info(
                        f"  → 저장 완료 | 면적:{sqms_cnt} 감정:{apsl_cnt} "
                        f"임대차:{leas_cnt} 등기:{rgst_cnt} 배분:{dtbt_cnt} 점유:{ocpy_cnt}"
                    )
                    success += 1
                except Exception as e:
                    conn.rollback()
                    log.error(f"  → 저장 실패 [{cltr_mng_no}]: {e}")
                    fail += 1
            else:
                fail += 1

            # API 10 tps 제한 준수
            time.sleep(SLEEP_SEC)

            # BATCH_SIZE 단위로 중간 커밋 (이미 save_detail 내부에서 commit하지만 명시적 보장)
            if idx % BATCH_SIZE == 0:
                conn.commit()
                log.info(f"  ── 중간 저장 ({idx}/{total}건 처리됨) ──")

        conn.commit()

        log.info("=" * 55)
        status = "중단됨" if aborted else "완료"
        log.info(f"상세 조회 {status} | 성공: {success}건 / 실패: {fail}건 / 전체: {total}건")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
