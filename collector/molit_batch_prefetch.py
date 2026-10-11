"""
molit_batch_prefetch.py
─────────────────────────────────────────────────────────────────────────────
활성 온비드 물건이 분포한 모든 시군구에 대해
국토교통부 실거래가 데이터를 사전 수집한다.

기존 문제:
  get_market_price()가 on-demand(상세 페이지 조회 시)로만 동작하여,
  아직 조회되지 않은 시군구(80개 중 63개)는 MOLIT 캐시가 비어 있었다.

해결:
  파이프라인 4단계로 편입하여, 매 수집 주기마다
  active 물건의 시군구 × 용도별 우선 api_type을 일괄 수집한다.
  fetch_and_cache()의 캐시 로직(30일 TTL)을 그대로 활용하므로
  이미 수집된 조합은 자동 스킵된다.

실행:
  python molit_batch_prefetch.py          # 단독 실행
  run_pipeline.py에서 4단계로 호출됨      # 파이프라인 통합
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import sqlite3
import logging
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lawd_code import get_lawd_cd
from db.schema_molit import init_molit_db
from molit_fetcher import (
    fetch_and_cache,
    get_deal_months,
    USG_TO_PRIMARY,
    SLEEP_SEC,
    LOOKBACK_MONTHS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "onbid.db")

# on-demand(get_market_price)와 동일하게 24개월.
# 공매 물건은 비인기 건물이 많아 거래 빈도가 낮으므로 기간을 넉넉히 잡는다.
# 캐시 TTL(30일) 덕분에 이미 수집된 조합은 자동 스킵되어 재실행 부담이 적다.
BATCH_LOOKBACK_MONTHS = 24


def get_target_districts(conn: sqlite3.Connection) -> list[dict]:
    """active 물건에서 (시도, 시군구, 용도소분류) 조합을 추출한다.

    같은 시군구에 여러 용도가 있으면 각각의 api_type을 모두 수집해야 하므로
    용도별로 분리하여 반환한다.
    """
    rows = conn.execute("""
        SELECT DISTINCT lctn_sd_nm, lctn_sggn_nm, cltr_usg_scls_nm
        FROM BID_ITEMS
        WHERE status = 'active'
          AND lctn_sd_nm IS NOT NULL
          AND lctn_sggn_nm IS NOT NULL
    """).fetchall()

    targets = []
    for sd, sggn, usg in rows:
        lawd_cd = get_lawd_cd(sd, sggn)
        if not lawd_cd:
            log.warning(f"LAWD_CD 매핑 없음: {sd} {sggn}")
            continue
        targets.append({
            "sd_nm": sd,
            "sggn_nm": sggn,
            "lawd_cd": lawd_cd,
            "usg_scls": usg,
        })
    return targets


def prefetch(conn: sqlite3.Connection) -> dict:
    """전체 시군구 × 용도별 우선 api_type을 사전 수집.

    Returns:
        {"districts": 시군구 수, "api_calls": API 호출 수, "new_trades": 신규 거래 수}
    """
    targets = get_target_districts(conn)

    # lawd_cd 기준으로 필요한 api_type 합산 (중복 제거)
    # 예: 미추홀구에 오피스텔+업무시설이 있으면 officetel+commercial 모두 수집
    lawd_types: dict[str, set[str]] = {}
    for t in targets:
        lc = t["lawd_cd"]
        if lc not in lawd_types:
            lawd_types[lc] = set()
        primary = USG_TO_PRIMARY.get(t["usg_scls"], ["officetel", "commercial"])
        lawd_types[lc].update(primary)

    months = get_deal_months(BATCH_LOOKBACK_MONTHS)

    total_districts = len(lawd_types)
    total_api_calls = 0
    total_new_trades = 0
    total_skipped = 0

    log.info(f"사전 수집 시작: {total_districts}개 시군구, "
             f"{len(months)}개월, API 타입 합산 {sum(len(v) for v in lawd_types.values())}종")

    for i, (lawd_cd, api_types) in enumerate(sorted(lawd_types.items()), 1):
        for ym in months:
            for api_type in sorted(api_types):
                cnt = fetch_and_cache(conn, lawd_cd, ym, api_type)
                if cnt == -1:
                    total_skipped += 1
                else:
                    total_api_calls += 1
                    total_new_trades += cnt
                    time.sleep(SLEEP_SEC)

        if i % 10 == 0 or i == total_districts:
            log.info(f"진행: {i}/{total_districts} 시군구 완료 "
                     f"(API {total_api_calls}콜, 신규 {total_new_trades}건, "
                     f"캐시 히트 {total_skipped}건)")

    stats = {
        "districts": total_districts,
        "api_calls": total_api_calls,
        "new_trades": total_new_trades,
        "cache_hits": total_skipped,
    }
    log.info(f"사전 수집 완료: {stats}")
    return stats


def main():
    if not os.path.exists(DB_PATH):
        log.error(f"DB 파일 없음: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    try:
        init_molit_db(conn)
        stats = prefetch(conn)
        log.info(
            f"결과: {stats['districts']}개 시군구, "
            f"API {stats['api_calls']}콜, "
            f"신규 거래 {stats['new_trades']}건 수집, "
            f"캐시 히트 {stats['cache_hits']}건 스킵"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
