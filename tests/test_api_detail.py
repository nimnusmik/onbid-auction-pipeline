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
import sqlite3
import requests
import logging
import time
from datetime import datetime
from utils import to_int, to_float, to_str, now_str, to_list

# ─────────────────────────────────────────
# 설정 (기존 collector.py와 동일 값 사용)
# ─────────────────────────────────────────
SERVICE_KEY = os.environ["ONBID_API_KEY"]
DETAIL_URL  = "https://apis.data.go.kr/B010003/OnbidRlstDtlSrvc/getRlstDtlInf"
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
# DB 초기화: 서브 테이블 생성 + 마이그레이션
# ─────────────────────────────────────────
def init_detail_db(conn: sqlite3.Connection):
    conn.executescript("""
        -- ── 면적정보 ────────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS BID_SQMS (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cltr_mng_no     TEXT    NOT NULL REFERENCES BID_ITEMS(cltr_mng_no),
            cland_cont      TEXT,   -- 종별(지목): 예) 건물>건물
            sqms_cont       TEXT,   -- 면적 (㎡)
            purs_alc_cont   TEXT,   -- 지분
            dtl_cltr_nm     TEXT    -- 비고 (상세 물건명/소재지)
        );
        CREATE INDEX IF NOT EXISTS idx_sqms_cltr ON BID_SQMS(cltr_mng_no);

        -- ── 감정평가정보 ─────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS BID_APSL_EVL (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cltr_mng_no     TEXT    NOT NULL REFERENCES BID_ITEMS(cltr_mng_no),
            apsl_evl_org_nm TEXT,   -- 감정평가기관명
            apsl_appr_nm    TEXT,   -- 감정평가사명
            apsl_evl_ymd    TEXT,   -- 평가일자 (yyyyMMdd)
            apsl_evl_amt    INTEGER,-- 감정평가금액 (원)
            url_adr         TEXT    -- 감정평가서 첨부파일 URL
        );
        CREATE INDEX IF NOT EXISTS idx_apsl_cltr ON BID_APSL_EVL(cltr_mng_no);

        -- ── 임대차정보 (압류재산 0007만) ─────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS BID_LEAS_INF (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cltr_mng_no     TEXT    NOT NULL REFERENCES BID_ITEMS(cltr_mng_no),
            irst_div_nm     TEXT,   -- 임대차 내용 구분명
            cltr_inpr_nm    TEXT,   -- 임차인 성명
            bid_grtee_amt   INTEGER,-- 보증금액 (원)
            mthr_amt        REAL,   -- 차임/월세금액 (원)
            conv_grtee_amt  REAL,   -- 환산보증금액 (원)
            cfmtn_ymd       TEXT,   -- 확정(설정)일자 (yyyyMMdd)
            mvin_ymd        TEXT    -- 전입일자 (yyyyMMdd)
        );
        CREATE INDEX IF NOT EXISTS idx_leas_cltr ON BID_LEAS_INF(cltr_mng_no);

        -- ── 등기사항증명서 주요정보 (압류재산 0007만) ────────────────────────────
        CREATE TABLE IF NOT EXISTS BID_RGST_PRMR (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cltr_mng_no     TEXT    NOT NULL REFERENCES BID_ITEMS(cltr_mng_no),
            irst_div_nm     TEXT,   -- 권리종류명
            cltr_inpr_nm    TEXT,   -- 권리자명
            rgst_ymd        TEXT,   -- 등기설정일자 (yyyyMMdd)
            inpr_stng_amt   INTEGER -- 설정금액 (원)
        );
        CREATE INDEX IF NOT EXISTS idx_rgst_cltr ON BID_RGST_PRMR(cltr_mng_no);

        -- ── 배분요구사항 (압류재산 0007만) ──────────────────────────────────────
        CREATE TABLE IF NOT EXISTS BID_DTBT_RQR (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cltr_mng_no     TEXT    NOT NULL REFERENCES BID_ITEMS(cltr_mng_no),
            rgt_rel_cd_nm   TEXT,   -- 권리종류
            acpm_prpt_nm    TEXT,   -- 권리자명
            stng_ymd        TEXT,   -- 설정일자 (yyyyMMdd)
            bond_stng_amt   INTEGER,-- 설정금액 (원)
            dtbt_rqr_yn     TEXT,   -- 배분요구여부 (Y/N)
            dtbt_rqr_ymd    TEXT,   -- 배분요구일자 (yyyyMMdd)
            dtbt_rqr_amt    INTEGER,-- 배분요구채권금액 (원)
            ersr_psbl_yn    TEXT,   -- 말소가능여부 (Y/N)
            etc_cont        TEXT    -- 기타내용
        );
        CREATE INDEX IF NOT EXISTS idx_dtbt_cltr ON BID_DTBT_RQR(cltr_mng_no);

        -- ── 점유관계 (압류재산 0007만) ───────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS BID_OCPY_REL (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cltr_mng_no     TEXT    NOT NULL REFERENCES BID_ITEMS(cltr_mng_no),
            ocpy_rel_cd_nm  TEXT,   -- 점유관계 구분명
            ocpy_irps_nm    TEXT,   -- 점유관계인 성명
            ctrt_ymd        TEXT,   -- 계약일자 (yyyyMMdd)
            mvin_ymd        TEXT,   -- 전입일자 (yyyyMMdd, 사업자등록신청일)
            cfmtn_ymd       TEXT,   -- 확정일자 (yyyyMMdd)
            acpm_grtee_amt  INTEGER,-- 보증금액 (원)
            rnt_amt         REAL,   -- 차임금액 (원)
            lsd_part_cont   TEXT    -- 임차부분 내용
        );
        CREATE INDEX IF NOT EXISTS idx_ocpy_cltr ON BID_OCPY_REL(cltr_mng_no);

        -- ── 일괄입찰물건목록 ─────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS BID_BATC_CLTR (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cltr_mng_no     TEXT    NOT NULL REFERENCES BID_ITEMS(cltr_mng_no),
            sub_cltr_mng_no TEXT,   -- 일괄묶음 내 개별 물건관리번호
            prpt_div_nm     TEXT,   -- 재산유형명
            dsps_mthod_nm   TEXT,   -- 처분방식명
            cltr_usg_mcls_nm TEXT,  -- 용도중분류명
            cltr_usg_scls_nm TEXT,  -- 용도소분류명
            onbid_cltr_nm   TEXT,   -- 물건명
            usbd_nft        INTEGER,-- 유찰횟수
            land_sqms       REAL,   -- 토지면적 (㎡)
            bld_sqms        REAL,   -- 건물면적 (㎡)
            apsl_evl_amt    INTEGER -- 감정평가금액 (원)
        );
        CREATE INDEX IF NOT EXISTS idx_batc_cltr ON BID_BATC_CLTR(cltr_mng_no);

        -- ── 정정내역 ─────────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS BID_CRTN_LST (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cltr_mng_no     TEXT    NOT NULL REFERENCES BID_ITEMS(cltr_mng_no),
            crtn_ymd        TEXT,   -- 정정일자 (yyyyMMdd)
            crtn_item_cont  TEXT,   -- 변경항목명
            bfmdf_lst_cont  TEXT,   -- 변경 전 내용
            afmdf_lst_cont  TEXT    -- 변경 후 내용
        );
        CREATE INDEX IF NOT EXISTS idx_crtn_cltr ON BID_CRTN_LST(cltr_mng_no);

        -- ── 공매재산명세서 (1:1) ─────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS BID_PAPS_INF (
            cltr_mng_no         TEXT    PRIMARY KEY REFERENCES BID_ITEMS(cltr_mng_no),
            dlgt_org_nm         TEXT,   -- 처분청
            mng_no              TEXT,   -- 관리번호
            pbanc_ymd           TEXT,   -- 공매공고일자 (yyyyMMdd)
            dtbt_rqr_edtm_ymd   TEXT,   -- 배분요구 종기일자 (yyyyMMdd)
            pbct_tdps           TEXT,   -- 공매보증금
            zadr                TEXT,   -- 지번주소
            alc_cont            TEXT,   -- 지분내용
            pbct_espc           TEXT,   -- 공매(매각)예정가격
            bid_perd            TEXT,   -- 입찰서 제출기간
            opbd_ymd            TEXT,   -- 개찰일자
            dodis_p_dudt        TEXT,   -- 매각결정기일
            ersr_excl_rgt_cont  TEXT,   -- 말소제외권리내용
            stty_ebr_vld_cont   TEXT,   -- 법정지상권 유효내용
            pytn_mtrs_cont      TEXT,   -- 유의사항내용
            prcv_ymd            TEXT,   -- 현황조사일자
            etc_smry_cont       TEXT,   -- 기타요약내용
            szr_prpt_indct_cont TEXT    -- 압류재산 표시내용
        );
    """)

    # BID_ITEMS에 상세 조회 추적 컬럼 추가 (마이그레이션)
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(BID_ITEMS)")}
    if "detail_fetched_at" not in existing_cols:
        conn.execute("ALTER TABLE BID_ITEMS ADD COLUMN detail_fetched_at TEXT")
        log.info("마이그레이션: BID_ITEMS.detail_fetched_at 컬럼 추가")

    conn.commit()
    log.info("상세 DB 초기화 완료")


# ─────────────────────────────────────────
# API 호출
# ─────────────────────────────────────────
def fetch_detail(cltr_mng_no: str, pbct_cdtn_no) -> dict | None:
    """물건상세 조회 API 호출. 성공 시 item dict 반환, 실패 시 None."""
    params = {
        "serviceKey": SERVICE_KEY,
        "resultType": "json",
        "numOfRows":  1,
        "pageNo":     1,
        "cltrMngNo":  cltr_mng_no,
    }
    if pbct_cdtn_no:
        params["pbctCdtnNo"] = pbct_cdtn_no

    try:
        res = requests.get(DETAIL_URL, params=params, timeout=15)
        res.raise_for_status()
        data = res.json()
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


def save_paps_inf(conn, cltr_mng_no, paps: dict | None):
    """공매재산명세서 저장 (1:1, REPLACE)."""
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

    # 상세 조회 완료 시각 기록
    conn.execute(
        "UPDATE BID_ITEMS SET detail_fetched_at = ? WHERE cltr_mng_no = ?",
        (now_str(), cltr_mng_no),
    )
    conn.commit()


# ─────────────────────────────────────────
# 조회 대상 물건 목록 가져오기
# ─────────────────────────────────────────
def get_pending_items(conn: sqlite3.Connection, force: bool = False) -> list[tuple]:
    """상세 조회가 필요한 물건 목록 반환.

    조건:
      - status = 'active' (낙찰/취소 제외)
      - force=False: detail_fetched_at IS NULL (미조회) OR crtn_yn = 'Y' (정정 있음)
      - force=True:  전체 active 물건 재조회
    """
    if force:
        sql = """
            SELECT cltr_mng_no, pbct_cdtn_no
            FROM BID_ITEMS
            WHERE status = 'active'
            ORDER BY ratio_pct ASC  -- 낮은 비율(유망 물건) 먼저
        """
    else:
        sql = """
            SELECT cltr_mng_no, pbct_cdtn_no
            FROM BID_ITEMS
            WHERE status = 'active'
              AND (
                detail_fetched_at IS NULL   -- 한 번도 조회 안 한 물건
                OR crtn_yn = 'Y'            -- 정정 이력 있는 물건 (재조회)
              )
            ORDER BY
                detail_fetched_at IS NULL DESC,  -- 미조회 먼저
                ratio_pct ASC                    -- 같은 우선순위라면 감정가비율 낮은 것 먼저
        """
    return conn.execute(sql).fetchall()


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────
def main():
    conn = sqlite3.connect(DB_PATH)
    init_detail_db(conn)

    pending = get_pending_items(conn, force=FORCE_REFETCH)
    total   = len(pending)

    if total == 0:
        log.info("상세 조회 대상 물건 없음 (모두 최신 상태)")
        conn.close()
        return

    log.info(f"상세 조회 대상: {total}건 시작")
    log.info("=" * 55)

    success = 0
    fail    = 0

    for idx, (cltr_mng_no, pbct_cdtn_no) in enumerate(pending, 1):
        log.info(f"[{idx}/{total}] {cltr_mng_no} (공매조건번호={pbct_cdtn_no})")

        item = fetch_detail(cltr_mng_no, pbct_cdtn_no)

        if item:
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
        else:
            fail += 1

        # API 10 tps 제한 준수
        time.sleep(SLEEP_SEC)

        # BATCH_SIZE 단위로 중간 커밋 (이미 save_detail 내부에서 commit하지만 명시적 보장)
        if idx % BATCH_SIZE == 0:
            conn.commit()
            log.info(f"  ── 중간 저장 ({idx}/{total}건 처리됨) ──")

    conn.commit()
    conn.close()

    log.info("=" * 55)
    log.info(f"상세 조회 완료 | 성공: {success}건 / 실패: {fail}건 / 전체: {total}건")


if __name__ == "__main__":
    main()