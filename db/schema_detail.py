"""상세 서브 테이블 9개 스키마 및 마이그레이션."""

import sqlite3
import logging

log = logging.getLogger(__name__)


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

    # 위치 및 이용현황 컬럼 마이그레이션
    migrate_cols = {
        "loc_vnty_pscd_cont": "TEXT",    # 위치 및 부근 현황
        "utlz_pscd_cont":     "TEXT",    # 이용현황
        "cltr_etc_cont":      "TEXT",    # 기타사항
        "icdl_cdtn_cont":     "TEXT",    # 부대조건
        "zadr_nm":            "TEXT",    # 지번주소(전체)
        "cltr_radr":          "TEXT",    # 도로명주소(전체)
        # 온비드 웹 상세페이지 호출 시 필요한 보조 식별자 (cltrMngNo+pbctCdtnNo만으로는 500 에러)
        "onbid_cltrno":       "INTEGER", # 온비드 물건번호
        "onbid_pbanc_no":     "INTEGER", # 온비드 공고번호
        "pbct_no":            "INTEGER", # 공매번호
    }
    for col, dtype in migrate_cols.items():
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE BID_ITEMS ADD COLUMN {col} {dtype}")
            log.info(f"마이그레이션: BID_ITEMS.{col} 컬럼 추가")

    conn.commit()
    log.info("상세 DB 초기화 완료")
