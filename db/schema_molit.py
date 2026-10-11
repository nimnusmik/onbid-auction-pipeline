"""MOLIT_TRADE_CACHE, MOLIT_FETCH_LOG 테이블 스키마.

국토교통부 실거래가 API 응답을 캐싱하기 위한 테이블.
"""

import sqlite3
import logging

log = logging.getLogger(__name__)


def init_molit_db(conn: sqlite3.Connection):
    conn.executescript("""
        -- 실거래 데이터 캐시 (API 응답 1건 = 1행)
        CREATE TABLE IF NOT EXISTS MOLIT_TRADE_CACHE (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            lawd_cd         TEXT    NOT NULL,        -- 법정동코드 5자리 (시군구)
            deal_ymd        TEXT    NOT NULL,        -- 조회 계약년월 YYYYMM
            api_type        TEXT    NOT NULL,        -- 'officetel' | 'commercial'

            dong_nm         TEXT,                    -- 법정동명 (읍면동)
            jibun           TEXT,                    -- 지번 (예: 302-8)
            bldg_nm         TEXT,                    -- 단지명/건물명
            exclu_use_ar    REAL,                    -- 전용면적 (㎡)
            deal_amount     INTEGER,                 -- 거래금액 (만원)
            floor           TEXT,                    -- 층
            build_year      TEXT,                    -- 건축년도
            deal_day        TEXT,                    -- 계약일 (일)

            unit_price      REAL,                    -- ㎡당 단가 (만원/㎡)

            fetched_at      TEXT DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_molit_cache_lookup
            ON MOLIT_TRADE_CACHE(lawd_cd, deal_ymd, api_type);
        CREATE INDEX IF NOT EXISTS idx_molit_cache_dong
            ON MOLIT_TRADE_CACHE(lawd_cd, deal_ymd, dong_nm);

        -- 조회 이력 (중복 API 호출 방지)
        CREATE TABLE IF NOT EXISTS MOLIT_FETCH_LOG (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            lawd_cd     TEXT    NOT NULL,
            deal_ymd    TEXT    NOT NULL,
            api_type    TEXT    NOT NULL,
            total_count INTEGER DEFAULT 0,
            fetched_at  TEXT DEFAULT (datetime('now', 'localtime')),

            UNIQUE(lawd_cd, deal_ymd, api_type)
        );

        -- 물건별 시세 매칭 결과 캐시.
        -- 파이프라인 5단계(molit_match_refresh)가 active 물건에 대해 일괄 갱신.
        -- 행이 존재하고 match_tier IS NOT NULL → 같은 건물 실거래 매칭 성공.
        -- 행이 존재하고 match_tier IS NULL → 매칭 시도했으나 실패(no_data).
        -- 행이 없으면 → 아직 매칭 시도하지 않음.
        CREATE TABLE IF NOT EXISTS MOLIT_MATCH (
            cltr_mng_no                 TEXT PRIMARY KEY,
            match_tier                  INTEGER,      -- 0=같은 지번, 1=같은 건물명, NULL=no_data
            match_count                 INTEGER,
            avg_unit_price              REAL,         -- 만원/㎡
            estimated_market_price_won  INTEGER,
            matched_at                  TEXT DEFAULT (datetime('now', 'localtime'))
        );
    """)
    # 기존 DB 마이그레이션: jibun 컬럼 추가
    try:
        conn.execute("ALTER TABLE MOLIT_TRADE_CACHE ADD COLUMN jibun TEXT")
        log.info("MOLIT_TRADE_CACHE에 jibun 컬럼 추가 완료")
    except sqlite3.OperationalError:
        pass  # 이미 존재

    conn.commit()
    log.info("국토교통부 실거래가 캐시 DB 초기화 완료")
