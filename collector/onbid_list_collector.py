import os
import sys
import sqlite3
import urllib.parse
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# 프로젝트 루트를 sys.path에 추가 (db, processor, notifier 패키지 import용)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import to_int, to_float
from db.schema_items import init_db
from processor.calc import calc_ratio
from processor.status import mark_closed
from processor.query import query_items

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
SERVICE_KEY = urllib.parse.quote(os.environ["ONBID_API_KEY"], safe="")
BASE_URL    = "https://apis.data.go.kr/B010003/OnbidRlstListSrvc2/getRlstCltrList2"
DB_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "onbid.db")

NUM_OF_ROWS = 100   # 페이지당 최대 수집 건수
MAX_PAGES   = 1000    # 그룹당 최대 페이지 수 (최대 1,000건)

# 수집 대상 지역 (시도명 기준)
# 서울, 광역시, 특별자치시, 인구 100만 이상 특례시 중심
TARGET_REGIONS = {
    "서울특별시",
    "경기도",
    "인천광역시",
    "부산광역시",
    "대구광역시",
    "광주광역시",
    "대전광역시",
    "울산광역시",
    "세종특별자치시",
}

# 수집할 용도 중분류 / 소분류 조합
# 새 카테고리 추가 시 이 리스트에만 딕셔너리 추가하면 됨
QUERY_GROUPS = [
    {
        "label": "상가용및업무용건물 > 업무시설",
        "cltrUsgMclsCtgrNm": "상가용및업무용건물",
        "cltrUsgSclsCtgrNm": "업무시설",
    },
    {
        "label": "상가용및업무용건물 > 기타상가용및업무용",
        "cltrUsgMclsCtgrNm": "상가용및업무용건물",
        "cltrUsgSclsCtgrNm": "기타상가용및업무용",
    },
    {
        "label": "용도복합용건물 > 주/상용건물",
        "cltrUsgMclsCtgrNm": "용도복합용건물",
        "cltrUsgSclsCtgrNm": "주/상용건물",
    },
    {
        "label": "용도복합용건물 > 오피스텔",
        "cltrUsgMclsCtgrNm": "용도복합용건물",
        "cltrUsgSclsCtgrNm": "오피스텔",
    },
]

# 로그: 파일(onbid_collector.log) + 콘솔 동시 출력
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("onbid_collector.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────
def format_dt(dt_str: str) -> str:
    """표시용 날짜 포맷 변환. 날짜 없거나 9999년이면 '미정' 반환."""
    if not dt_str or dt_str[:4] >= "2999":
        return "미정"
    try:
        return f"{dt_str[0:4]}-{dt_str[4:6]}-{dt_str[6:8]} {dt_str[8:10]}:{dt_str[10:12]}"
    except Exception:
        return "미정"


def parse_dt(dt_str: str) -> str | None:
    """DB 저장용 날짜 포맷 변환. SQLite 정렬·비교 가능한 ISO 형식으로 변환. 날짜 없으면 None."""
    if not dt_str or dt_str[:4] >= "2999":
        return None
    try:
        return f"{dt_str[0:4]}-{dt_str[4:6]}-{dt_str[6:8]} {dt_str[8:10]}:{dt_str[10:12]}"
    except Exception:
        return None


# ─────────────────────────────────────────
# 예외
# ─────────────────────────────────────────
class PageFetchError(Exception):
    """목록 페이지 수집 중 일시적 실패. 호출자에 전파해 부분 데이터로
    mark_closed 가 활성 물건을 잘못 closed 마킹하는 것을 막는다."""


# ─────────────────────────────────────────
# API 호출
# ─────────────────────────────────────────
def fetch_pages(mclass: str, sclass: str, label: str) -> list[dict]:
    """수의계약 불가(N) / 가능(Y) 물건을 각각 수집해 합쳐 반환.
    pvct 서브쿼리 중 하나라도 실패하면 PageFetchError 가 그대로 전파된다.
    """
    items: list[dict] = []
    for pvct_yn in ("N", "Y"):
        items.extend(_fetch_pages_by_pvct(mclass, sclass, label, pvct_yn))
    return items


def _fetch_pages_by_pvct(mclass: str, sclass: str, label: str, pvct_yn: str) -> list[dict]:
    """특정 pvctTrgtYn 값으로 목록 API를 페이지 단위 호출해 결과 반환.
    NODATA_ERROR(resultCode 03)는 정상적인 빈 결과로 간주.
    네트워크/응답 구조 실패는 PageFetchError 로 전파한다.
    """
    items = []
    sub_label = f"{label}|pvct={pvct_yn}"
    for page_no in range(1, MAX_PAGES + 1):
        url = (
            f"{BASE_URL}"
            f"?serviceKey={SERVICE_KEY}"                           # 인증키
            f"&pageNo={page_no}"                                   # 페이지 번호
            f"&numOfRows={NUM_OF_ROWS}"                            # 페이지당 건수
            "&resultType=json"                                     # 응답 형식
            "&prptDivCd=0007,0010,0005,0002,0003,0006,0008,0011"   # 재산종류 코드 (다중)
            f"&pvctTrgtYn={pvct_yn}"                               # v2 필수 — 수의계약 가능여부
            "&dspsMthodCd=0001"                                    # 매각만
            "&bidDivCd=0001"                                       # 인터넷 입찰만
            "&cltrUsgLclsCtgrNm=부동산"                              # 부동산만
            f"&cltrUsgMclsCtgrNm={mclass}"                         # 용도 중분류
            f"&cltrUsgSclsCtgrNm={sclass}"                         # 용도 소분류
            "&bldSqmsStart=30"                                     # 건물면적 최소 (㎡)
            "&bldSqmsEnd=200"                                      # 건물면적 최대 (㎡)
        )
        try:
            res = requests.get(url, timeout=10)
            data = res.json()
        except Exception as e:
            raise PageFetchError(
                f"[{sub_label}] 페이지 {page_no} 요청 실패: {e}"
            ) from e

        # NODATA_ERROR: 조건 매칭 물건 0건 — 에러 아님
        result_code = data.get("result", {}).get("resultCode") if isinstance(data.get("result"), dict) else None
        if result_code == "03":
            log.info(f"  [{sub_label}] 데이터 없음")
            break

        if "body" not in data:
            raise PageFetchError(f"[{sub_label}] 응답 구조 오류: {data}")

        total_count = data["body"].get("totalCount", 0)
        raw_items   = data["body"].get("items") or {}
        page_items  = raw_items.get("item", [])

        # API가 단건일 때 dict로 반환하는 경우 리스트로 통일
        if isinstance(page_items, dict):
            page_items = [page_items]
        if not page_items:
            break

        items.extend(page_items)
        log.info(f"  [{sub_label}] 페이지 {page_no} → {len(page_items)}건 (누적 {len(items)}/{total_count})")

        # 전체 건수 도달 시 조기 종료
        if len(items) >= total_count:
            break

    return items


# ─────────────────────────────────────────
# DB 저장 (UPSERT)
# ─────────────────────────────────────────
def upsert_items(conn: sqlite3.Connection, items: list[dict]) -> tuple[int, int, set]:
    """수집된 물건 목록을 DB에 저장.
    - 신규 물건: INSERT (first_collected_at, collected_at 모두 현재 시각)
    - 기존 물건: UPDATE (collected_at만 갱신, first_collected_at은 유지)
    - 반환: (신규 건수, 업데이트 건수, 수집된 물건번호 셋)
    """
    new_count     = 0
    updated_count = 0
    collected_ids = set()  # 이번 수집에서 확인된 물건번호 (mark_closed에서 사용)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in items:
        cltr_mng_no = item.get("cltrMngNo")
        if not cltr_mng_no:
            continue

        # 대상 지역 외 물건 제외
        if item.get("lctnSdnm") not in TARGET_REGIONS:
            continue

        collected_ids.add(cltr_mng_no)

        # 기존 레코드 존재 여부 확인 (INSERT vs UPDATE 분기)
        existing = conn.execute(
            "SELECT cltr_mng_no FROM BID_ITEMS WHERE cltr_mng_no = ?",
            (cltr_mng_no,)
        ).fetchone()

        # API 필드명 → DB 컬럼명 매핑 및 타입 변환
        fields = {
            "pbct_cdtn_no":     to_int(item.get("pbctCdtnNo")),
            "onbid_cltr_nm":    item.get("onbidCltrNm"),
            "prpt_div_nm":      item.get("prptDivNm"),
            "cltr_usg_mcls_nm": item.get("cltrUsgMclsCtgrNm"),
            "cltr_usg_scls_nm": item.get("cltrUsgSclsCtgrNm"),
            "lctn_sd_nm":       item.get("lctnSdnm"),
            "lctn_sggn_nm":     item.get("lctnSggnm"),
            "lctn_emd_nm":      item.get("lctnEmdNm"),
            "land_sqms":        to_float(item.get("landSqms")),
            "bld_sqms":         to_float(item.get("bldSqms")),
            "apsl_evl_amt":     to_int(item.get("apslEvlAmt")),
            "lowst_bid_prc":    to_int(item.get("lowstBidPrcIndctCont")),
            "ratio_pct":        calc_ratio(item),
            "frst_ratio_pct":   to_float(item.get("frstCtrsLowstBidPrcRto")),
            "usbd_nft":         to_int(item.get("usbdNft")),
            "pbct_nsq":         item.get("pbctNsq"),
            "pvct_trgt_yn":     item.get("pvctTrgtYn"),
            "batc_bid_yn":      item.get("batcBidYn"),
            "alc_yn":           item.get("alcYn"),
            "crtn_yn":          item.get("crtnYn"),
            "rqst_org_nm":      item.get("rqstOrgNm"),
            "exct_org_nm":      item.get("exctOrgNm"),
            "cltr_bid_bgng_dt": parse_dt(item.get("cltrBidBgngDt")),
            "cltr_bid_end_dt":  parse_dt(item.get("cltrBidEndDt")),
            "thnl_img_url":     item.get("thnlImgUrlAdr"),
        }

        if not existing:
            # 신규 물건: first_collected_at과 collected_at 모두 현재 시각으로 세팅
            conn.execute("""
                INSERT INTO BID_ITEMS (
                    cltr_mng_no, pbct_cdtn_no, onbid_cltr_nm, prpt_div_nm,
                    cltr_usg_mcls_nm, cltr_usg_scls_nm,
                    lctn_sd_nm, lctn_sggn_nm, lctn_emd_nm,
                    land_sqms, bld_sqms,
                    apsl_evl_amt, lowst_bid_prc, ratio_pct, frst_ratio_pct,
                    usbd_nft, pbct_nsq,
                    pvct_trgt_yn, batc_bid_yn, alc_yn, crtn_yn,
                    rqst_org_nm, exct_org_nm,
                    cltr_bid_bgng_dt, cltr_bid_end_dt,
                    thnl_img_url, first_collected_at, collected_at
                ) VALUES (
                    :cltr_mng_no, :pbct_cdtn_no, :onbid_cltr_nm, :prpt_div_nm,
                    :cltr_usg_mcls_nm, :cltr_usg_scls_nm,
                    :lctn_sd_nm, :lctn_sggn_nm, :lctn_emd_nm,
                    :land_sqms, :bld_sqms,
                    :apsl_evl_amt, :lowst_bid_prc, :ratio_pct, :frst_ratio_pct,
                    :usbd_nft, :pbct_nsq,
                    :pvct_trgt_yn, :batc_bid_yn, :alc_yn, :crtn_yn,
                    :rqst_org_nm, :exct_org_nm,
                    :cltr_bid_bgng_dt, :cltr_bid_end_dt,
                    :thnl_img_url, :now, :now
                )
            """, {**fields, "cltr_mng_no": cltr_mng_no, "now": now})
            new_count += 1
        else:
            # 기존 물건: 최신 정보로 업데이트. first_collected_at은 건드리지 않음
            conn.execute("""
                UPDATE BID_ITEMS SET
                    pbct_cdtn_no=:pbct_cdtn_no, onbid_cltr_nm=:onbid_cltr_nm, prpt_div_nm=:prpt_div_nm,
                    cltr_usg_mcls_nm=:cltr_usg_mcls_nm, cltr_usg_scls_nm=:cltr_usg_scls_nm,
                    lctn_sd_nm=:lctn_sd_nm, lctn_sggn_nm=:lctn_sggn_nm, lctn_emd_nm=:lctn_emd_nm,
                    land_sqms=:land_sqms, bld_sqms=:bld_sqms,
                    apsl_evl_amt=:apsl_evl_amt, lowst_bid_prc=:lowst_bid_prc,
                    ratio_pct=:ratio_pct, frst_ratio_pct=:frst_ratio_pct,
                    usbd_nft=:usbd_nft, pbct_nsq=:pbct_nsq,
                    pvct_trgt_yn=:pvct_trgt_yn, batc_bid_yn=:batc_bid_yn,
                    alc_yn=:alc_yn, crtn_yn=:crtn_yn,
                    rqst_org_nm=:rqst_org_nm, exct_org_nm=:exct_org_nm,
                    cltr_bid_bgng_dt=:cltr_bid_bgng_dt, cltr_bid_end_dt=:cltr_bid_end_dt,
                    thnl_img_url=:thnl_img_url, collected_at=:collected_at
                WHERE cltr_mng_no=:cltr_mng_no
            """, {**fields, "cltr_mng_no": cltr_mng_no, "collected_at": now})
            updated_count += 1

    conn.commit()
    return new_count, updated_count, collected_ids


# ─────────────────────────────────────────
# 수집 로그 저장
# ─────────────────────────────────────────
def save_log(
    conn: sqlite3.Connection,
    label: str,
    total: int,
    new: int,
    updated: int,
    status: str,
    error_msg: str = None,
):
    """그룹별 수집 결과를 COLLECTION_LOG에 기록."""
    conn.execute("""
        INSERT INTO COLLECTION_LOG (query_label, total_count, new_count, updated_count, status, error_msg)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (label, total, new, updated, status, error_msg))
    conn.commit()


# ─────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────
def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)

        all_collected_ids: set = set()  # 성공한 그룹의 수집 ID 합산
        succeeded_groups: list[tuple[str, str]] = []  # (mclass, sclass) — 실패 그룹 mark_closed 보호용

        for group in QUERY_GROUPS:
            label  = group["label"]
            mclass = group["cltrUsgMclsCtgrNm"]
            sclass = group["cltrUsgSclsCtgrNm"]

            log.info(f"{'='*50}")
            log.info(f"[{label}] 수집 시작")

            try:
                items = fetch_pages(mclass, sclass, label)
                new_cnt, upd_cnt, ids = upsert_items(conn, items)
                all_collected_ids |= ids
                succeeded_groups.append((mclass, sclass))
                save_log(conn, label, len(items), new_cnt, upd_cnt, "success")
                log.info(f"[{label}] 완료 → 전체 {len(items)}건 / 신규 {new_cnt}건 / 변경 {upd_cnt}건")

            except Exception as e:
                # 부분 실패 그룹은 succeeded_groups 에 들어가지 않으므로
                # mark_closed 가 그 그룹의 물건을 건드리지 않는다.
                save_log(conn, label, 0, 0, 0, "fail", str(e))
                log.error(f"[{label}] 실패: {e}")

        # 성공한 그룹의 물건만 mark_closed 대상. 실패 그룹은 보존.
        closed_cnt = mark_closed(conn, all_collected_ids, succeeded_groups)
        if closed_cnt:
            log.info(f"[종료 감지] {closed_cnt}건 → status=closed (낙찰/취소 추정)")

        # 수집 결과 확인 (감정가 대비 75% 이하, 유찰 1회 이상)
        log.info("\n[결과 미리보기 - 감정가 75% 이하 / 유찰 1회 이상]")
        results = query_items(conn, ratio_max=75.0, usbd_min=1, limit=10)
        for r in results:
            log.info(
                f"  {r['cltr_mng_no']} | {r['lctn_sd_nm']} {r['lctn_sggn_nm']} | "
                f"감정가비율 {r['ratio_pct']}% | 유찰 {r['usbd_nft']}회 | "
                f"{'[신규]' if r['is_new'] else ''} "
                f"URL: {r['onbid_url']}"
            )

        log.info("수집 완료")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
