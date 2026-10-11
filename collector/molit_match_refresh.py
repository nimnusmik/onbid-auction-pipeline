"""
molit_match_refresh.py
─────────────────────────────────────────────────────────────────────────────
active BID_ITEMS 각각에 대해 MOLIT_TRADE_CACHE를 조회하여
같은 건물 실거래 매칭 결과를 MOLIT_MATCH 테이블에 캐싱한다.

외부 API 호출 없음 — 캐시(MOLIT_TRADE_CACHE)에 이미 있는 데이터만 사용.
molit_batch_prefetch가 먼저 돌아 캐시를 채워둔 뒤 실행되어야 한다.

목록(/api/items) 응답에 "실거래 매칭 있음/없음"을 표시하기 위한
사전 계산. 매번 100건마다 match_trades를 호출하면 응답이 느려지므로
파이프라인 단계에서 한 번에 갱신한다.

실행:
  python molit_match_refresh.py     # 단독
  run_pipeline.py 5단계로 호출됨
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import sqlite3
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.schema_molit import init_molit_db
from molit_fetcher import (
    get_market_price,
    extract_building_name, extract_jibun, match_trades,
)
from lawd_code import get_lawd_cd

# molit_fetcher.USG_TO_ALLOWED_TYPES 가 모듈 레벨에 정의되어 있으면 import
try:
    from molit_fetcher import USG_TO_ALLOWED_TYPES  # type: ignore
except ImportError:
    USG_TO_ALLOWED_TYPES = {}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "onbid.db")


def refresh_one(conn: sqlite3.Connection, item: sqlite3.Row) -> dict:
    """단일 BID_ITEM에 대해 캐시만으로 매칭 시도. API 호출 없음."""
    lawd_cd = get_lawd_cd(item["lctn_sd_nm"], item["lctn_sggn_nm"])
    if not lawd_cd:
        return {"tier": None, "count": 0, "avg_up": None, "est": None}

    usg_scls = item["cltr_usg_scls_nm"]
    bldg_name = extract_building_name(item["onbid_cltr_nm"])
    jibun = extract_jibun(item["onbid_cltr_nm"], item["zadr_nm"])
    allowed_types = USG_TO_ALLOWED_TYPES.get(usg_scls) if USG_TO_ALLOWED_TYPES else None

    result = match_trades(
        conn, lawd_cd, item["lctn_emd_nm"], bldg_name, item["bld_sqms"],
        jibun, api_types=allowed_types,
    )

    if result.get("status") != "ok":
        return {"tier": None, "count": 0, "avg_up": None, "est": None}

    summary = result.get("summary") or {}
    return {
        "tier":   result.get("match_tier"),
        "count":  result.get("match_count") or 0,
        "avg_up": summary.get("avg_unit_price"),
        "est":    summary.get("estimated_market_price_won"),
    }


def refresh_all(conn: sqlite3.Connection) -> dict:
    """active 물건 전체 갱신. 매칭 성공 / 실패 / 스킵 카운트 반환."""
    conn.row_factory = sqlite3.Row
    items = conn.execute("""
        SELECT cltr_mng_no, onbid_cltr_nm, zadr_nm,
               lctn_sd_nm, lctn_sggn_nm, lctn_emd_nm,
               cltr_usg_scls_nm, bld_sqms
        FROM BID_ITEMS
        WHERE status = 'active'
    """).fetchall()

    matched = 0
    no_data = 0
    for it in items:
        r = refresh_one(conn, it)
        conn.execute("""
            INSERT INTO MOLIT_MATCH
                (cltr_mng_no, match_tier, match_count,
                 avg_unit_price, estimated_market_price_won,
                 matched_at)
            VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))
            ON CONFLICT(cltr_mng_no) DO UPDATE SET
                match_tier                  = excluded.match_tier,
                match_count                 = excluded.match_count,
                avg_unit_price              = excluded.avg_unit_price,
                estimated_market_price_won  = excluded.estimated_market_price_won,
                matched_at                  = excluded.matched_at
        """, (it["cltr_mng_no"], r["tier"], r["count"],
              r["avg_up"], r["est"]))
        if r["tier"] is not None:
            matched += 1
        else:
            no_data += 1

    conn.commit()
    stats = {"total": len(items), "matched": matched, "no_data": no_data}
    log.info(f"매칭 갱신 완료: {stats}")
    return stats


def main():
    if not os.path.exists(DB_PATH):
        log.error(f"DB 파일 없음: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    try:
        init_molit_db(conn)
        refresh_all(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
