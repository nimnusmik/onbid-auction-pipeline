"""
run_pipeline.py
─────────────────────────────────────────────────────────────────────────────
온비드 수집 파이프라인 오케스트레이터

실행 순서:
  1단계: onbid_list_collector.py      — 물건 목록 수집
  2단계: onbid_detail_collector.py    — 물건 상세 수집
  3단계: onbid_bid_collector.py       — 입찰정보 수집
  4단계: molit_batch_prefetch.py      — 실거래가 사전 수집
  5단계: molit_match_refresh.py       — 물건별 시세 매칭 캐시 갱신

중단 조건:
  - 1단계 실행 후 COLLECTION_LOG에 오늘 성공한 그룹이 하나도 없으면 중단
    (API 장애, 네트워크 오류 등으로 전체 실패한 경우 stale 데이터 기준으로
     2·3단계가 도는 것을 방지)

cron 등록 예시:
  0 6 * * * cd /path/to/onbid-dashboard/collector && python run_pipeline.py
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sqlite3
import subprocess
import logging
import sys
from datetime import datetime, date

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
DB_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "onbid.db")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
CRON_LOG    = os.path.join(SCRIPTS_DIR, "cron_history.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("onbid_pipeline.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def write_cron_log(status: str, detail: str = ""):
    """cron 실행 이력을 한 줄씩 기록한다."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {status}"
    if detail:
        line += f" | {detail}"
    with open(CRON_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_step(script_name: str) -> bool:
    """스크립트를 실행하고 성공 여부를 반환한다."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    log.info(f"[{script_name}] 시작")
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=SCRIPTS_DIR,
    )
    if result.returncode != 0:
        log.error(f"[{script_name}] 비정상 종료 (exit code {result.returncode})")
        return False
    log.info(f"[{script_name}] 완료")
    return True


def check_step1_success() -> bool:
    """오늘 1단계 수집에서 성공한 그룹이 하나라도 있는지 확인한다."""
    if not os.path.exists(DB_PATH):
        log.error(f"DB 파일 없음: {DB_PATH}")
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM COLLECTION_LOG
            WHERE status = 'success'
              AND run_at >= ?
            """,
            (today,),
        ).fetchone()
        success_count = row[0] if row else 0
    finally:
        conn.close()

    if success_count == 0:
        log.error(
            "1단계 수집 결과 없음 — 오늘 성공한 그룹이 없습니다. "
            "2·3단계 실행을 중단합니다."
        )
        return False

    log.info(f"1단계 수집 확인: 오늘 성공한 그룹 {success_count}개")
    return True


def write_daily_snapshot():
    """활성 BID_ITEMS를 (지역, 용도)별로 집계하여 DAILY_SNAPSHOT에 UPSERT."""
    log.info("일일 스냅샷 기록 시작")
    try:
        conn = sqlite3.connect(DB_PATH)
        today = date.today().isoformat()

        rows = conn.execute("""
            SELECT
                lctn_sd_nm AS region,
                cltr_usg_mcls_nm AS usage_type,
                COUNT(*) AS total_count,
                AVG(ratio_pct) AS avg_ratio_pct,
                MIN(ratio_pct) AS min_ratio_pct,
                AVG(apsl_evl_amt) AS avg_apsl_unt_prc,
                AVG(lowst_bid_prc) AS avg_min_bid,
                AVG(usbd_nft) AS fail_count_avg
            FROM BID_ITEMS
            WHERE status = 'active'
              AND lctn_sd_nm IS NOT NULL
              AND cltr_usg_mcls_nm IS NOT NULL
            GROUP BY lctn_sd_nm, cltr_usg_mcls_nm
        """).fetchall()

        for row in rows:
            conn.execute("""
                INSERT INTO DAILY_SNAPSHOT
                    (snapshot_date, region, usage_type, total_count,
                     avg_ratio_pct, min_ratio_pct, avg_apsl_unt_prc,
                     avg_min_bid, fail_count_avg)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_date, region, usage_type)
                DO UPDATE SET
                    total_count = excluded.total_count,
                    avg_ratio_pct = excluded.avg_ratio_pct,
                    min_ratio_pct = excluded.min_ratio_pct,
                    avg_apsl_unt_prc = excluded.avg_apsl_unt_prc,
                    avg_min_bid = excluded.avg_min_bid,
                    fail_count_avg = excluded.fail_count_avg,
                    created_at = datetime('now', 'localtime')
            """, (today, row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]))

        conn.commit()
        log.info(f"일일 스냅샷 기록 완료: {len(rows)}개 그룹")

        conn.execute("""
            INSERT INTO COLLECTION_LOG (query_label, total_count, new_count, updated_count, status)
            VALUES ('daily_snapshot', ?, ?, 0, 'success')
        """, (len(rows), len(rows)))
        conn.commit()
        conn.close()

    except Exception as e:
        log.error(f"스냅샷 기록 실패: {e}")


def main():
    started_at = datetime.now()
    write_cron_log("STARTED")
    log.info("=" * 55)
    log.info("온비드 수집 파이프라인 시작")
    log.info("=" * 55)

    try:
        # 1단계: 목록 수집
        run_step("onbid_list_collector.py")

        # 1단계 성공 여부 검증 — 실패 시 중단
        if not check_step1_success():
            log.error("파이프라인 중단")
            elapsed = datetime.now() - started_at
            write_cron_log("FAILED", f"1단계 검증 실패 | 소요 {elapsed}")
            sys.exit(1)

        # 2단계: 물건 상세 수집
        run_step("onbid_detail_collector.py")

        # 3단계: 입찰정보 수집
        run_step("onbid_bid_collector.py")

        # 4단계: 국토교통부 실거래가 사전 수집
        run_step("molit_batch_prefetch.py")

        # 5단계: 물건별 시세 매칭 캐시 갱신 (목록의 실거래 마크 표시용)
        run_step("molit_match_refresh.py")

        # 일일 스냅샷 기록 (분석 트렌드용)
        write_daily_snapshot()

        elapsed = datetime.now() - started_at
        write_cron_log("SUCCESS", f"소요 {elapsed}")
        log.info("=" * 55)
        log.info("온비드 수집 파이프라인 완료")
        log.info("=" * 55)

    except Exception as e:
        elapsed = datetime.now() - started_at
        write_cron_log("ERROR", f"{e} | 소요 {elapsed}")
        log.exception("파이프라인 예외 발생")
        sys.exit(1)


if __name__ == "__main__":
    main()
