"""대시보드용 물건 조회 헬퍼."""

import sqlite3


def get_onbid_url(cltr_mng_no: str) -> str:
    """물건관리번호로 온비드 상세 페이지 URL 생성. DB에 저장하지 않고 조회 시 동적으로 생성."""
    return (
        f"https://www.onbid.co.kr/op/cta/cltrdtl/retrieveCltrDetail.do"
        f"?cltrMngNo={cltr_mng_no}"
    )


def query_items(
    conn: sqlite3.Connection,
    ratio_max: float = 100.0,   # 감정가 대비 비율 상한 (%)
    usbd_min: int = 0,          # 최소 유찰 횟수
    sd_nm: str = None,          # 시도명 필터 (None이면 전체)
    limit: int = 100,
) -> list[dict]:
    """대시보드용 물건 조회. active 상태인 물건만 반환.
    is_new는 오늘 날짜와 collected_at을 비교해 계산 (별도 컬럼 없음).
    """
    sql = """
        SELECT
            cltr_mng_no, onbid_cltr_nm,
            lctn_sd_nm, lctn_sggn_nm, lctn_emd_nm,
            apsl_evl_amt, lowst_bid_prc, ratio_pct,
            usbd_nft, pbct_nsq,
            pvct_trgt_yn, batc_bid_yn, alc_yn,
            cltr_bid_end_dt, thnl_img_url, pbct_cdtn_no,
            (DATE(collected_at) = DATE('now', 'localtime')) AS is_new  -- 오늘 수집된 신규 물건 여부
        FROM BID_ITEMS
        WHERE status    = 'active'   -- 낙찰/취소된 물건 제외
          AND ratio_pct <= ?
          AND usbd_nft  >= ?
    """
    params = [ratio_max, usbd_min]

    if sd_nm:
        sql += " AND lctn_sd_nm = ?"
        params.append(sd_nm)

    sql += " ORDER BY ratio_pct ASC LIMIT ?"
    params.append(limit)

    cursor = conn.execute(sql, params)
    cols = [d[0] for d in cursor.description]
    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]

    # 온비드 URL 동적 조합 (DB 저장 없이 런타임 생성)
    for row in rows:
        row["onbid_url"] = get_onbid_url(row["cltr_mng_no"])

    return rows
