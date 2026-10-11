"""BID_ITEMS, COLLECTION_LOG, ALERT_LOG 테이블 스키마 및 마이그레이션."""

import sqlite3
import logging

log = logging.getLogger(__name__)


def init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS BID_ITEMS (
            cltr_mng_no         TEXT        PRIMARY KEY,   -- 물건관리번호 (고유 식별자)
            pbct_cdtn_no        INTEGER,                   -- 공매조건번호 (상세 API 호출 시 cltr_mng_no와 함께 필수)
            onbid_cltr_nm       TEXT,                      -- 물건명
            prpt_div_nm         TEXT,                      -- 재산유형 (예: 기타일반재산)
            cltr_usg_mcls_nm    TEXT,                      -- 용도 중분류 (예: 상가용및업무용건물)
            cltr_usg_scls_nm    TEXT,                      -- 용도 소분류 (예: 업무시설)
            lctn_sd_nm          TEXT,                      -- 소재지 시도
            lctn_sggn_nm        TEXT,                      -- 소재지 시군구
            lctn_emd_nm         TEXT,                      -- 소재지 읍면동
            land_sqms           REAL,                      -- 토지면적 (㎡)
            bld_sqms            REAL,                      -- 건물면적 (㎡)
            apsl_evl_amt        INTEGER,                   -- 감정평가금액 (원)
            lowst_bid_prc       INTEGER,                   -- 현재 회차 최저입찰가 (원)
            ratio_pct           REAL,                      -- 감정가 대비 최저입찰가 비율 (%)
            frst_ratio_pct      REAL,                      -- 최초 최저입찰가 대비 현재 비율 (%) - 하락폭 파악용
            usbd_nft            INTEGER,                   -- 유찰 횟수
            pbct_nsq            TEXT,                      -- 현재 공매 회차
            pvct_trgt_yn        TEXT,                      -- 수의계약 대상 여부 (Y/N)
            batc_bid_yn         TEXT,                      -- 일괄입찰 여부 (Y: 여러 물건 묶음)
            alc_yn              TEXT,                      -- 지분물건 여부 (Y: 일부 지분만 매각)
            crtn_yn             TEXT,                      -- 정정 이력 여부 (Y: 상세 조회 시 정정내역 확인 권장)
            rqst_org_nm         TEXT,                      -- 공고기관명
            exct_org_nm         TEXT,                      -- 집행기관명
            cltr_bid_bgng_dt    TEXT,                      -- 입찰 시작일시 (YYYY-MM-DD HH:MM)
            cltr_bid_end_dt     TEXT,                      -- 입찰 마감일시 (YYYY-MM-DD HH:MM)
            thnl_img_url        TEXT,                      -- 썸네일 이미지 URL
            status              TEXT        DEFAULT 'active',              -- 물건 상태 (active: 진행중 / closed: 낙찰·취소로 API에서 사라짐)
            is_bookmarked       INTEGER     DEFAULT 0,                     -- 관심목록 등록 여부 (0: 미등록 / 1: 등록). 수집과 무관하게 사용자가 직접 설정
            first_collected_at  TEXT,                                      -- 최초 수집 일시 (INSERT 시에만 기록, 이후 변경 없음)
            collected_at        TEXT        DEFAULT (datetime('now', 'localtime'))  -- 마지막 수집 일시 (매 수집마다 갱신)
        );

        -- 대시보드 필터 쿼리 성능을 위한 인덱스
        CREATE INDEX IF NOT EXISTS idx_ratio     ON BID_ITEMS (ratio_pct);       -- 감정가 비율 필터
        CREATE INDEX IF NOT EXISTS idx_end_dt    ON BID_ITEMS (cltr_bid_end_dt); -- 마감일 정렬/필터
        CREATE INDEX IF NOT EXISTS idx_region    ON BID_ITEMS (lctn_sd_nm, lctn_sggn_nm); -- 지역 필터
        CREATE INDEX IF NOT EXISTS idx_usbd      ON BID_ITEMS (usbd_nft);        -- 유찰 횟수 필터

        -- 수집 실행 이력 (그룹별 성공/실패, 신규/변경 건수 기록)
        CREATE TABLE IF NOT EXISTS COLLECTION_LOG (
            id              INTEGER     PRIMARY KEY AUTOINCREMENT,
            run_at          TEXT        DEFAULT (datetime('now', 'localtime')),
            query_label     TEXT,       -- 수집 그룹 레이블
            total_count     INTEGER,    -- 수집된 전체 건수
            new_count       INTEGER,    -- 신규 저장 건수
            updated_count   INTEGER,    -- 기존 업데이트 건수
            status          TEXT,       -- 'success' / 'fail'
            error_msg       TEXT        -- 실패 시 오류 메시지
        );

        -- 알림 발송 이력 (중복 발송 방지 및 발송 상태 추적)
        CREATE TABLE IF NOT EXISTS ALERT_LOG (
            id                  INTEGER     PRIMARY KEY AUTOINCREMENT,
            cltr_mng_no         TEXT        REFERENCES BID_ITEMS(cltr_mng_no),
            triggered_ratio     REAL,       -- 알림을 트리거한 시점의 비율값
            alert_type          TEXT,       -- AlertType: ratio / deadline / pvct
            sent_at             TEXT        DEFAULT (datetime('now', 'localtime')),
            status              TEXT        -- AlertStatus: success / fail / skip
        );

        -- 일일 스냅샷 (분석 트렌드 차트용, 파이프라인 실행 시 집계)
        CREATE TABLE IF NOT EXISTS DAILY_SNAPSHOT (
            id                  INTEGER     PRIMARY KEY AUTOINCREMENT,
            snapshot_date       TEXT        NOT NULL,           -- YYYY-MM-DD
            region              TEXT        NOT NULL,           -- 시/도
            usage_type          TEXT        NOT NULL,           -- 용도
            total_count         INTEGER     NOT NULL DEFAULT 0, -- 활성 물건 수
            avg_ratio_pct       REAL,                           -- 평균 감정가율
            min_ratio_pct       REAL,                           -- 최소 감정가율
            avg_apsl_unt_prc    REAL,                           -- 평균 감정가
            avg_min_bid         REAL,                           -- 평균 최저입찰가
            fail_count_avg      REAL,                           -- 평균 유찰횟수
            created_at          TEXT        DEFAULT (datetime('now', 'localtime')),
            UNIQUE(snapshot_date, region, usage_type)
        );

        CREATE INDEX IF NOT EXISTS idx_snapshot_date ON DAILY_SNAPSHOT(snapshot_date);
    """)

    # 기존 DB 마이그레이션: 신규 컬럼이 없으면 추가 (스키마 변경 시 DB 재생성 없이 적용)
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(BID_ITEMS)")}
    if "status" not in existing_cols:
        conn.execute("ALTER TABLE BID_ITEMS ADD COLUMN status TEXT DEFAULT 'active'")
        log.info("마이그레이션: status 컬럼 추가")
    if "first_collected_at" not in existing_cols:
        conn.execute("ALTER TABLE BID_ITEMS ADD COLUMN first_collected_at TEXT")
        log.info("마이그레이션: first_collected_at 컬럼 추가")
    if "is_bookmarked" not in existing_cols:
        conn.execute("ALTER TABLE BID_ITEMS ADD COLUMN is_bookmarked INTEGER DEFAULT 0")
        log.info("마이그레이션: is_bookmarked 컬럼 추가")

    conn.commit()
    log.info("DB 초기화 완료")
