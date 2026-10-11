"""
onbid_bid_collector.py
─────────────────────────────────────────────────────────────────────────────
BID_ITEMS(물건목록)에서 cltrMngNo + pbctCdtnNo 를 읽어
온비드 물건상세 입찰정보 조회 API(getCltrBidInf)를 호출하고
응답을 2개 서브 테이블에 저장한다.

[서브 테이블]
  BID_QUAL  - 회차별 입찰정보  (1:N)
  BID_HIST  - 이전 입찰 내역   (1:N, BID_QUAL 하위)

[실행 전략]
  - BID_ITEMS.bid_fetched_at IS NULL → 한 번도 입찰정보 조회 안 한 물건 우선
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
from db.schema_bid import init_bid_db

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
SERVICE_KEY = urllib.parse.quote(os.environ["ONBID_API_KEY"], safe="")
BID_URL     = "https://apis.data.go.kr/B010003/OnbidCltrBidDtlSrvc2/getCltrBidInf2"
DB_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "onbid.db")

SLEEP_SEC     = 0.15   # API 10 tps 제한 → 호출 간 대기(초)
BATCH_SIZE    = 50     # 중간 커밋 단위
FORCE_REFETCH = False  # True이면 이미 조회한 물건도 재조회

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("onbid_bid.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────
# API 호출
# ─────────────────────────────────────────
class RateLimitExceeded(Exception):
    """API 일일 한도(429) 초과 — 더 호출해도 모두 실패하므로 즉시 종료 신호."""


# NODATA(03) — 응답은 정상이지만 데이터 없음. fetched 갱신해야 재시도 안 됨.
# 일반 실패(타임아웃 등)와 구분하기 위한 sentinel.
NODATA_SENTINEL: dict = {}


def fetch_bid(cltr_mng_no: str, pbct_cdtn_no) -> dict | None:
    """입찰정보 조회 API 호출. 성공 시 응답 dict 반환, 실패 시 None.

    serviceKey는 이미 URL 인코딩된 값이므로 URL에 직접 포함.
    나머지 파라미터는 requests가 안전하게 인코딩하도록 params 딕셔너리 사용.
    429(Too Many Requests)는 RateLimitExceeded로 호출자에게 전파한다.
    """
    base = f"{BID_URL}?serviceKey={SERVICE_KEY}"

    params = {
        "resultType": "json",
        "numOfRows":  10,   # 회차가 여러 개일 수 있으므로 넉넉하게
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
        # 응답 구조가 두 가지:
        #   구형: { "result": { "resultCode": "00" }, ... }
        #   신형: { "header": { "resultCode": "00" }, "body": { "items": ... } }
        result_code = (
            data.get("result", {}).get("resultCode")
            or data.get("header", {}).get("resultCode")
            or "??"
        )

        if result_code == "03":
            # NODATA_ERROR — 입찰 진행 중이 아닌 물건 (종료/낙찰).
            # 정상 응답이므로 fetched 갱신해서 재시도 막아야 함 → sentinel 반환.
            return NODATA_SENTINEL
        if result_code != "00":
            log.warning(f"  [{cltr_mng_no}] 응답코드 {result_code}")
            return None

        return data

    except Exception as e:
        log.error(f"  [{cltr_mng_no}] 응답 파싱 실패: {e}")
        return None


# ─────────────────────────────────────────
# 서브 테이블 저장
# ─────────────────────────────────────────
def _clear_sub_tables(conn: sqlite3.Connection, cltr_mng_no: str):
    """재조회 전 기존 데이터 삭제."""
    # BID_HIST는 BID_QUAL의 id를 참조하므로 BID_QUAL 먼저 조회 후 삭제
    qual_ids = [
        row[0] for row in conn.execute(
            "SELECT id FROM BID_QUAL WHERE cltr_mng_no = ?", (cltr_mng_no,)
        ).fetchall()
    ]
    if qual_ids:
        placeholders = ",".join("?" * len(qual_ids))
        conn.execute(f"DELETE FROM BID_HIST WHERE bid_qual_id IN ({placeholders})", qual_ids)
    conn.execute("DELETE FROM BID_QUAL WHERE cltr_mng_no = ?", (cltr_mng_no,))


def save_bid(conn: sqlite3.Connection, cltr_mng_no: str, data: dict):
    """API 응답을 BID_QUAL에 저장.

    신형 응답(`body.items.item[]`)을 기준으로 처리한다.
      - 각 item = 현재 진행 중인 회차 (1~N건) → result_status="진행중"으로 저장
      - 첫 item의 prcnBidClgList = 과거 회차 결과 → 회차로 펼쳐서 저장
        (pbctStatNm 그대로 result_status에 보존: "유찰"/"낙찰"/"취소" 등)

    구형 응답(`prvdBidDtls`)은 사실상 운영에 없지만 호환을 위해 fallback 처리.
    """
    _clear_sub_tables(conn, cltr_mng_no)

    # 신형 응답: body.items.item[] 추출
    items_list: list[dict] = []
    if "body" in data:
        items_raw = (data.get("body") or {}).get("items", {}).get("item")
        items_list = to_list(items_raw) if items_raw else []

    # 구형 fallback: 최상위 prvdBidDtls
    if not items_list and data.get("prvdBidDtls"):
        _save_bid_legacy(conn, cltr_mng_no, data)
        return

    if not items_list:
        # 응답은 정상이지만 items가 비어있는 경우 — fetched_at만 기록
        conn.execute(
            "UPDATE BID_ITEMS SET bid_fetched_at = ? WHERE cltr_mng_no = ?",
            (now_str(), cltr_mng_no),
        )
        conn.commit()
        return

    proc_anct_nm = to_str(items_list[0].get("onbidPbancNm") or items_list[0].get("procAnctNm"))
    pbct_cdtn_no = to_int(items_list[0].get("pbctCdtnNo"))

    saved_seqs: set[int] = set()  # 회차 중복 방지

    # 1. 현재 진행 중인 회차들
    for item in items_list:
        bid_seq = to_int(item.get("pbctNsq"))
        if bid_seq is None or bid_seq in saved_seqs:
            continue
        saved_seqs.add(bid_seq)

        conn.execute("""
            INSERT INTO BID_QUAL (
                cltr_mng_no, pbct_cdtn_no, proc_anct_nm,
                bid_seq, bid_strt_dttm, bid_end_dttm, bid_opnn_dttm,
                bid_particp_lmtn_nm, bid_grnt_dcsn,
                acml_fail_cnt,
                collb_bid_possbl_yn, aprxy_bid_possbl_yn, elctrn_grnt_srv_yn,
                result_status
            ) VALUES (
                :cltr_mng_no, :pbct_cdtn_no, :proc_anct_nm,
                :bid_seq, :bid_strt_dttm, :bid_end_dttm, :bid_opnn_dttm,
                :bid_particp_lmtn_nm, :bid_grnt_dcsn,
                :acml_fail_cnt,
                :collb_bid_possbl_yn, :aprxy_bid_possbl_yn, :elctrn_grnt_srv_yn,
                :result_status
            )
        """, {
            "cltr_mng_no":          cltr_mng_no,
            "pbct_cdtn_no":         pbct_cdtn_no,
            "proc_anct_nm":         proc_anct_nm,
            "bid_seq":              bid_seq,
            "bid_strt_dttm":        to_str(item.get("cltrBidBgngDt")),
            "bid_end_dttm":         to_str(item.get("cltrBidEndDt")),
            "bid_opnn_dttm":        to_str(item.get("cltrOpbdDt")),
            "bid_particp_lmtn_nm":  to_str(item.get("qlfcLmtCdtnCont")),
            "bid_grnt_dcsn":        to_str(item.get("pbctTdpsCont")),
            "acml_fail_cnt":        to_int(item.get("usbdNft")),
            "collb_bid_possbl_yn":  to_str(item.get("collbBidPsblYn")),
            "aprxy_bid_possbl_yn":  to_str(item.get("subtBidPsblYn")),
            "elctrn_grnt_srv_yn":   to_str(item.get("eltrGrprUseYn")),
            "result_status":        "진행중",
        })

    # 2. 과거 회차들 — 첫 item의 prcnBidClgList
    prcn_list = to_list(items_list[0].get("prcnBidClgList") or [])
    for prcn in prcn_list:
        bid_seq = to_int(prcn.get("pbctNsq"))
        if bid_seq is None or bid_seq in saved_seqs:
            continue
        saved_seqs.add(bid_seq)

        conn.execute("""
            INSERT INTO BID_QUAL (
                cltr_mng_no, pbct_cdtn_no, proc_anct_nm,
                bid_seq, bid_opnn_dttm, min_bd_prc, result_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            cltr_mng_no, pbct_cdtn_no, proc_anct_nm,
            bid_seq,
            to_str(prcn.get("cltrOpbdDt")),
            to_int(prcn.get("lowstBidPrcIndctCont")),
            to_str(prcn.get("pbctStatNm")),
        ))

    # 입찰정보 조회 완료 시각 기록
    conn.execute(
        "UPDATE BID_ITEMS SET bid_fetched_at = ? WHERE cltr_mng_no = ?",
        (now_str(), cltr_mng_no),
    )
    conn.commit()


def _save_bid_legacy(conn: sqlite3.Connection, cltr_mng_no: str, data: dict):
    """구형 응답(prvdBidDtls + prvdBidHists) 호환 처리. 신형 전환 후 거의 호출 안 됨."""
    proc_anct_nm = to_str(data.get("procAnctNm"))
    pbct_cdtn_no = to_int(data.get("pbctCdtnNo"))

    for dtl in to_list(data.get("prvdBidDtls")):
        cursor = conn.execute("""
            INSERT INTO BID_QUAL (
                cltr_mng_no, pbct_cdtn_no, proc_anct_nm,
                bid_seq, bid_strt_dttm, bid_end_dttm, bid_opnn_dttm,
                bid_mthd_nm, bid_particp_cstgr_nm, bid_particp_lmtn_nm,
                min_bd_prc, bd_prc_dcrmn_amount,
                bid_grnt_prc, bid_grnt_dcsn, bid_rsltn_mthd_nm,
                acml_fail_cnt, prv_bid_hist_rcnt,
                collb_bid_possbl_yn, aprxy_bid_possbl_yn, elctrn_grnt_srv_yn,
                result_status
            ) VALUES (
                :cltr_mng_no, :pbct_cdtn_no, :proc_anct_nm,
                :bid_seq, :bid_strt_dttm, :bid_end_dttm, :bid_opnn_dttm,
                :bid_mthd_nm, :bid_particp_cstgr_nm, :bid_particp_lmtn_nm,
                :min_bd_prc, :bd_prc_dcrmn_amount,
                :bid_grnt_prc, :bid_grnt_dcsn, :bid_rsltn_mthd_nm,
                :acml_fail_cnt, :prv_bid_hist_rcnt,
                :collb_bid_possbl_yn, :aprxy_bid_possbl_yn, :elctrn_grnt_srv_yn,
                '진행중'
            )
        """, {
            "cltr_mng_no":          cltr_mng_no,
            "pbct_cdtn_no":         pbct_cdtn_no,
            "proc_anct_nm":         proc_anct_nm,
            "bid_seq":              to_int(dtl.get("bidSeq")),
            "bid_strt_dttm":        to_str(dtl.get("bidStrtDttm")),
            "bid_end_dttm":         to_str(dtl.get("bidEndDttm")),
            "bid_opnn_dttm":        to_str(dtl.get("bidOpnnDttm")),
            "bid_mthd_nm":          to_str(dtl.get("bidMthdNm")),
            "bid_particp_cstgr_nm": to_str(dtl.get("bidParticpCstgrNm")),
            "bid_particp_lmtn_nm":  to_str(dtl.get("bidParticpLmtnCdtnNm")),
            "min_bd_prc":           to_int(dtl.get("minBdPrc")),
            "bd_prc_dcrmn_amount":  to_int(dtl.get("bdPrcDcrmnAmount")),
            "bid_grnt_prc":         to_int(dtl.get("bidGrntPrc")),
            "bid_grnt_dcsn":        to_str(dtl.get("bidGrntDcsn")),
            "bid_rsltn_mthd_nm":    to_str(dtl.get("bidRsltnMthdNm")),
            "acml_fail_cnt":        to_int(dtl.get("acmlFailCnt")),
            "prv_bid_hist_rcnt":    to_int(dtl.get("prvBidHistRcnt")),
            "collb_bid_possbl_yn":  to_str(dtl.get("collbBidPossblYn")),
            "aprxy_bid_possbl_yn":  to_str(dtl.get("aprxyBidPossblYn")),
            "elctrn_grnt_srv_yn":   to_str(dtl.get("elctrnGrntSrvYn")),
        })
        bid_qual_id = cursor.lastrowid

        for hist in to_list(dtl.get("prvdBidHists")):
            conn.execute("""
                INSERT INTO BID_HIST
                    (bid_qual_id, cltr_mng_no, prv_bid_seq, prv_bid_rslt, prv_bid_fail_cnt)
                VALUES (?, ?, ?, ?, ?)
            """, (
                bid_qual_id, cltr_mng_no,
                to_int(hist.get("prvBidSeq")),
                to_str(hist.get("prvBidRslt")),
                to_int(hist.get("prvBidFailCnt")),
            ))

    conn.execute(
        "UPDATE BID_ITEMS SET bid_fetched_at = ? WHERE cltr_mng_no = ?",
        (now_str(), cltr_mng_no),
    )
    conn.commit()


# ─────────────────────────────────────────
# 조회 대상 물건 목록
# ─────────────────────────────────────────
def get_pending_items(conn: sqlite3.Connection, force: bool = False) -> list[tuple]:
    """입찰정보 조회가 필요한 물건 목록 반환.

    조건:
      - status = 'active' (closed + pvct_trgt_yn='Y' 누적분 65건 등을 제외)
      - force=False: 다음 중 하나
          a) bid_fetched_at IS NULL (미조회)
          b) bid_fetched_at 이 2일 이상 경과 (단순 안전망)
          c) BID_QUAL 의 진행중 회차 마감일이 이미 지났음 (새 회차 등장 가능성)
      - force=True:  전체 active 물건 재조회
    """
    if force:
        sql = """
            SELECT cltr_mng_no, pbct_cdtn_no
            FROM BID_ITEMS
            WHERE status = 'active'
              AND cltr_bid_bgng_dt <= datetime('now', 'localtime')
            ORDER BY ratio_pct ASC
        """
    else:
        sql = """
            SELECT cltr_mng_no, pbct_cdtn_no
            FROM BID_ITEMS
            WHERE status = 'active'
              AND cltr_bid_bgng_dt <= datetime('now', 'localtime')
              AND (
                   bid_fetched_at IS NULL
                OR bid_fetched_at < datetime('now', 'localtime', '-2 days')
                OR EXISTS (
                     SELECT 1 FROM BID_QUAL q
                     WHERE q.cltr_mng_no = BID_ITEMS.cltr_mng_no
                       AND q.result_status = '진행중'
                       AND q.bid_end_dttm < datetime('now', 'localtime')
                   )
              )
            ORDER BY ratio_pct ASC
        """
    return conn.execute(sql).fetchall()


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────
def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        init_bid_db(conn)

        pending = get_pending_items(conn, force=FORCE_REFETCH)
        total   = len(pending)

        if total == 0:
            log.info("입찰정보 조회 대상 물건 없음 (모두 최신 상태)")
            return

        log.info(f"입찰정보 조회 대상: {total}건 시작")
        log.info("=" * 55)

        success = 0
        nodata  = 0
        fail    = 0
        aborted = False

        for idx, (cltr_mng_no, pbct_cdtn_no) in enumerate(pending, 1):
            log.info(f"[{idx}/{total}] {cltr_mng_no} (공매조건번호={pbct_cdtn_no})")

            try:
                data = fetch_bid(cltr_mng_no, pbct_cdtn_no)
            except RateLimitExceeded as e:
                log.error(f"  ⛔ API 일일 한도 초과 → 처리 중단 ({e})")
                log.error(f"  지금까지: 성공 {success} / NODATA {nodata} / 일시실패 {fail} / 미처리 {total - idx + 1}")
                aborted = True
                break

            if data is NODATA_SENTINEL:
                # 입찰 진행 중 아님(종료/낙찰) — 갱신해서 재시도 막음
                conn.execute(
                    "UPDATE BID_ITEMS SET bid_fetched_at = ? WHERE cltr_mng_no = ?",
                    (now_str(), cltr_mng_no),
                )
                conn.commit()
                nodata += 1
            elif data:
                save_bid(conn, cltr_mng_no, data)

                qual_cnt = conn.execute(
                    "SELECT COUNT(*) FROM BID_QUAL WHERE cltr_mng_no=?", (cltr_mng_no,)
                ).fetchone()[0]
                ongoing_cnt = conn.execute(
                    "SELECT COUNT(*) FROM BID_QUAL WHERE cltr_mng_no=? AND result_status='진행중'",
                    (cltr_mng_no,),
                ).fetchone()[0]

                log.info(f"  → 저장 완료 | 회차:{qual_cnt} (진행중 {ongoing_cnt})")
                success += 1
            else:
                # 일시 실패(타임아웃, 알 수 없는 에러 코드) — fetched 갱신 X.
                # 다음 cron에서 재시도되도록 NULL 유지.
                fail += 1

            time.sleep(SLEEP_SEC)

            if idx % BATCH_SIZE == 0:
                conn.commit()
                log.info(f"  ── 중간 저장 ({idx}/{total}건 처리됨) ──")

        conn.commit()

        log.info("=" * 55)
        status = "중단됨" if aborted else "완료"
        log.info(f"입찰정보 조회 {status} | 성공:{success} / NODATA:{nodata} / 일시실패:{fail} / 전체:{total}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
