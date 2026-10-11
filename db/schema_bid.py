"""BID_QUAL, BID_HIST 테이블 스키마 및 마이그레이션."""

import sqlite3
import logging

log = logging.getLogger(__name__)


def init_bid_db(conn: sqlite3.Connection):
    conn.executescript("""
        -- ── 회차별 입찰정보 ──────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS BID_QUAL (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            cltr_mng_no             TEXT    NOT NULL REFERENCES BID_ITEMS(cltr_mng_no),
            pbct_cdtn_no            INTEGER,                -- 공매조건번호
            proc_anct_nm            TEXT,                   -- 공고명
            bid_seq                 INTEGER,                -- 입찰 회차 번호
            bid_strt_dttm           TEXT,                   -- 입찰 시작 일시
            bid_end_dttm            TEXT,                   -- 입찰 마감 일시
            bid_opnn_dttm           TEXT,                   -- 개찰 일시
            bid_mthd_nm             TEXT,                   -- 입찰 방법명 (온라인/오프라인/혼합)
            bid_particp_cstgr_nm    TEXT,                   -- 입찰 참여 범주명 (개인/법인/기관)
            bid_particp_lmtn_nm     TEXT,                   -- 입찰 참여 제한 조건명
            min_bd_prc              INTEGER,                -- 최소 입찰가 (원)
            bd_prc_dcrmn_amount     INTEGER,                -- 입찰가 감소액 (원, 회차마다 내려가는 금액)
            bid_grnt_prc            INTEGER,                -- 입찰 보증금 (원)
            bid_grnt_dcsn           TEXT,                   -- 보증금 결정 방식 (예: 정가의 10%)
            bid_rsltn_mthd_nm       TEXT,                   -- 낙찰 방법명 (최고가 우선/최저가 우선/복합평가)
            acml_fail_cnt           INTEGER,                -- 유찰 누적 횟수
            prv_bid_hist_rcnt       INTEGER,                -- 이전 입찰 내역 건수
            collb_bid_possbl_yn     TEXT,                   -- 공동입찰 가능여부 (Y/N)
            aprxy_bid_possbl_yn     TEXT,                   -- 대리입찰 가능여부 (Y/N)
            elctrn_grnt_srv_yn      TEXT,                   -- 전자보증서 가능여부 (Y/N)
            result_status           TEXT                    -- 회차 결과 (진행중/유찰/낙찰/취소)
        );
        CREATE INDEX IF NOT EXISTS idx_qual_cltr ON BID_QUAL(cltr_mng_no);

        -- ── 이전 입찰 내역 (BID_QUAL 하위) ──────────────────────────────────────
        CREATE TABLE IF NOT EXISTS BID_HIST (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            bid_qual_id     INTEGER NOT NULL REFERENCES BID_QUAL(id),
            cltr_mng_no     TEXT    NOT NULL,               -- 물건관리번호 (조회 편의용)
            prv_bid_seq     INTEGER,                        -- 이전 입찰 회차
            prv_bid_rslt    TEXT,                           -- 이전 입찰 결과 (유찰/낙찰/취소)
            prv_bid_fail_cnt INTEGER                        -- 해당 회차 실패 횟수
        );
        CREATE INDEX IF NOT EXISTS idx_hist_qual ON BID_HIST(bid_qual_id);
        CREATE INDEX IF NOT EXISTS idx_hist_cltr ON BID_HIST(cltr_mng_no);
    """)

    # BID_ITEMS에 입찰정보 조회 추적 컬럼 추가 (마이그레이션)
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(BID_ITEMS)")}
    if "bid_fetched_at" not in existing_cols:
        conn.execute("ALTER TABLE BID_ITEMS ADD COLUMN bid_fetched_at TEXT")
        log.info("마이그레이션: BID_ITEMS.bid_fetched_at 컬럼 추가")

    # BID_QUAL 마이그레이션
    qual_cols = {row[1] for row in conn.execute("PRAGMA table_info(BID_QUAL)")}
    qual_migrate = {
        "result_status": "TEXT",     # 진행중/유찰/낙찰/취소
        "bid_round":     "INTEGER",  # 차수 (회차/차수 의 뒤 숫자, 웹 스크레이핑 결과)
        "winning_amt":   "INTEGER",  # 낙찰금액 (웹 스크레이핑 결과)
    }
    for col, dtype in qual_migrate.items():
        if col not in qual_cols:
            conn.execute(f"ALTER TABLE BID_QUAL ADD COLUMN {col} {dtype}")
            log.info(f"마이그레이션: BID_QUAL.{col} 컬럼 추가")

    conn.commit()
    log.info("입찰정보 DB 초기화 완료")
