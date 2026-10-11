"""
backfill_molit_cache.py
─────────────────────────────────────────────────────────────────────────────
active BID_ITEMS의 모든 (lawd_cd, api_type) × 24개월 MOLIT 거래를 캐시에 적재.

기존 캐시는 fetch_and_cache() 내부의 MOLIT_FETCH_LOG로 자동 스킵된다.
예상 소요: ~10분 (신규 호출 약 2,900건).
─────────────────────────────────────────────────────────────────────────────
"""
import os
import sys
import sqlite3
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))

from collector.molit_fetcher import (
    fetch_and_cache, get_deal_months, USG_TO_PRIMARY, ALL_API_TYPES, SLEEP_SEC
)
from collector.lawd_code import get_lawd_cd
from db.schema_molit import init_molit_db

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "onbid.db")


def main():
    conn = sqlite3.connect(DB_PATH)
    init_molit_db(conn)

    # active 물건의 unique (lawd_cd, api_type) 수집
    rows = conn.execute(
        """SELECT DISTINCT lctn_sd_nm, lctn_sggn_nm, cltr_usg_scls_nm
           FROM BID_ITEMS WHERE status='active'"""
    ).fetchall()

    combos: set[tuple[str, str]] = set()
    for sd, sggn, usg in rows:
        cd = get_lawd_cd(sd, sggn)
        if not cd:
            continue
        # 화이트리스트가 아니라 PRIMARY(=실제 조회 시도 대상) 기준
        for api_type in USG_TO_PRIMARY.get(usg, ["officetel", "commercial"]):
            combos.add((cd, api_type))

    months = get_deal_months()
    total = len(combos) * len(months)
    print(f"대상 (lawd_cd × api_type): {len(combos)}")
    print(f"조회 개월: {len(months)}")
    print(f"총 시도 수: {total:,} (캐시 히트는 스킵)")
    print("=" * 60)

    done = 0
    fetched = 0
    skipped = 0
    errors = 0
    t0 = time.time()

    for (lawd_cd, api_type) in sorted(combos):
        for ym in months:
            try:
                cnt = fetch_and_cache(conn, lawd_cd, ym, api_type)
                if cnt == -1:
                    skipped += 1
                elif cnt >= 0:
                    fetched += 1
                    conn.commit()
                    time.sleep(SLEEP_SEC)
            except Exception as e:
                errors += 1
                print(f"  ERROR {lawd_cd}/{ym}/{api_type}: {e}")
            done += 1

            if done % 200 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed else 0
                eta = (total - done) / rate if rate else 0
                print(f"  [{done:>5}/{total}] fetched={fetched} skipped={skipped} errors={errors} "
                      f"({rate:.1f}/s, ETA {eta/60:.1f}min)")

    conn.close()
    print("=" * 60)
    print(f"완료: fetched={fetched} skipped={skipped} errors={errors}")
    print(f"소요: {(time.time()-t0)/60:.1f}분")


if __name__ == "__main__":
    main()
