import os
import sys
import sqlite3
from datetime import date, timedelta
from collections import defaultdict
from flask import Flask, jsonify, request, abort
from flask_cors import CORS

# 프로젝트 루트 + collector를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "onbid.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# 앱 시작 시 MOLIT 관련 테이블이 존재하도록 보장.
# /api/items가 MOLIT_MATCH를 LEFT JOIN하므로 비어있어도 테이블 자체는 있어야 한다.
try:
    from db.schema_molit import init_molit_db as _init_molit
    with sqlite3.connect(DB_PATH) as _conn:
        _init_molit(_conn)
except Exception:
    pass  # DB 미존재 등 — collector가 먼저 만들 때까지 무시


# ─────────────────────────────────────────
# GET /api/items
# 목록 + 필터 + 정렬
# 쿼리 파라미터: ratio_max, usbd_min, sd_nm, bookmarked, pvct, limit
# ─────────────────────────────────────────
@app.route("/api/items")
def get_items():
    ratio_min  = request.args.get("ratio_min",  type=float)
    ratio_max  = request.args.get("ratio_max",  type=float)
    price_min  = request.args.get("price_min",  type=int)
    price_max  = request.args.get("price_max",  type=int)
    usbd_min   = request.args.get("usbd_min",   type=int)
    sd_nm      = request.args.get("sd_nm",      type=str)
    bookmarked = request.args.get("bookmarked", type=int)
    pvct       = request.args.get("pvct",       type=str)
    usg_mcls   = request.args.get("usg_mcls",   type=str)
    usg_scls   = request.args.get("usg_scls",   type=str)
    limit      = request.args.get("limit",      type=int, default=100)

    # bookmarked=1 요청은 닫힌 물건도 포함 — 사용자가 명시적으로 찜한 이력은 상태와 무관하게 노출
    conditions = [] if bookmarked == 1 else ["status = 'active'"]
    params = []

    if ratio_min is not None:
        conditions.append("ratio_pct >= ?")
        params.append(ratio_min)
    if ratio_max is not None:
        conditions.append("ratio_pct <= ?")
        params.append(ratio_max)
    if price_min is not None:
        conditions.append("lowst_bid_prc >= ?")
        params.append(price_min)
    if price_max is not None:
        conditions.append("lowst_bid_prc <= ?")
        params.append(price_max)
    if usbd_min is not None:
        conditions.append("usbd_nft >= ?")
        params.append(usbd_min)
    if sd_nm:
        conditions.append("lctn_sd_nm = ?")
        params.append(sd_nm)
    if bookmarked is not None:
        conditions.append("is_bookmarked = ?")
        params.append(bookmarked)
    if pvct in ("Y", "N"):
        conditions.append("pvct_trgt_yn = ?")
        params.append(pvct)
    if usg_mcls:
        conditions.append("cltr_usg_mcls_nm = ?")
        params.append(usg_mcls)
    if usg_scls:
        conditions.append("cltr_usg_scls_nm = ?")
        params.append(usg_scls)

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    # 리스트 렌더링에 필요한 컬럼만 선택 (SELECT * 대비 ~65% 페이로드 감소)
    # thnl_img_url 은 BookmarkCard 에서만 쓰이므로 bookmarked 필터 시에만 포함
    cols = [
        "BID_ITEMS.cltr_mng_no AS cltr_mng_no", "onbid_cltr_nm",
        "cltr_usg_mcls_nm", "cltr_usg_scls_nm",
        "lctn_sd_nm", "lctn_sggn_nm",
        "bld_sqms",
        "apsl_evl_amt", "lowst_bid_prc", "ratio_pct",
        "pbct_nsq", "usbd_nft",
        "cltr_bid_end_dt", "pvct_trgt_yn",
        "first_collected_at",
    ]
    if bookmarked == 1:
        cols.append("thnl_img_url")
    # 시작가(BID_QUAL 의 최초 최저입찰가 = MAX) 대비 현재 lowst_bid_prc 비율.
    # 회차가 진행될수록 가격이 하락하므로 MAX 가 곧 시작가.
    cols.append(
        "ROUND(lowst_bid_prc * 100.0 / NULLIF("
        "(SELECT MAX(min_bd_prc) FROM BID_QUAL WHERE cltr_mng_no = BID_ITEMS.cltr_mng_no), 0), 2"
        ") AS start_ratio_pct"
    )
    # 실거래 매칭 캐시(MOLIT_MATCH) — 같은 건물 거래가 있는지 마크용
    cols.append("mm.match_tier AS market_match_tier")
    cols.append("mm.match_count AS market_match_count")
    select_cols = ", ".join(cols)

    conn = get_db()
    try:
        rows = conn.execute(
            f"""SELECT {select_cols}
                FROM BID_ITEMS
                LEFT JOIN MOLIT_MATCH mm
                       ON mm.cltr_mng_no = BID_ITEMS.cltr_mng_no
                WHERE {where}
                ORDER BY ratio_pct ASC LIMIT ?""",
            params,
        ).fetchall()
    finally:
        conn.close()

    return jsonify([dict(r) for r in rows])


# ─────────────────────────────────────────
# GET /api/stats
# 목록 요약 통계 바 (필터 무관 전체 active 기준)
# ─────────────────────────────────────────
@app.route("/api/stats")
def get_stats():
    conn = get_db()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM BID_ITEMS WHERE status = 'active'"
        ).fetchone()[0]

        bookmarked = conn.execute(
            "SELECT COUNT(*) FROM BID_ITEMS WHERE status = 'active' AND is_bookmarked = 1"
        ).fetchone()[0]

        ratio_row = conn.execute(
            "SELECT AVG(ratio_pct), MIN(ratio_pct) FROM BID_ITEMS WHERE status = 'active'"
        ).fetchone()

        by_region = conn.execute(
            """
            SELECT lctn_sd_nm, COUNT(*) as cnt
            FROM BID_ITEMS
            WHERE status = 'active'
            GROUP BY lctn_sd_nm
            ORDER BY cnt DESC
            """
        ).fetchall()

        pvct_count = conn.execute(
            "SELECT COUNT(*) FROM BID_ITEMS WHERE status = 'active' AND pvct_trgt_yn = 'Y'"
        ).fetchone()[0]

        ratio_below60 = conn.execute(
            "SELECT COUNT(*) FROM BID_ITEMS WHERE status = 'active' AND ratio_pct < 60"
        ).fetchone()[0]

        ratio_60_70 = conn.execute(
            "SELECT COUNT(*) FROM BID_ITEMS WHERE status = 'active' AND ratio_pct >= 60 AND ratio_pct < 70"
        ).fetchone()[0]
    finally:
        conn.close()

    return jsonify({
        "total":         total,
        "bookmarked":    bookmarked,
        "pvct_count":    pvct_count,
        "ratio_avg":     round(ratio_row[0], 1) if ratio_row[0] else None,
        "ratio_min":     ratio_row[1],
        "ratio_below60": ratio_below60,
        "ratio_60_70":   ratio_60_70,
        "by_region":     [dict(r) for r in by_region],
    })


# ─────────────────────────────────────────
# GET /api/items/<id>
# 상세 Hero 섹션 (BID_ITEMS 단건)
# ─────────────────────────────────────────
@app.route("/api/items/<item_id>")
def get_item(item_id):
    conn = get_db()
    try:
        item = conn.execute(
            "SELECT * FROM BID_ITEMS WHERE cltr_mng_no = ?", (item_id,)
        ).fetchone()
    finally:
        conn.close()

    if item is None:
        abort(404)

    d = dict(item)

    # AI 투자 점수 계산 (단건) — refresh_item 과 동일 로직 공유
    conn2 = get_db()
    try:
        attach_single_score(conn2, d, item_id)
    finally:
        conn2.close()

    return jsonify(d)


# ─────────────────────────────────────────
# GET /api/items/<id>/info
# 탭1 기본정보 — 면적·감정평가·공매재산명세서
# ─────────────────────────────────────────
@app.route("/api/items/<item_id>/info")
def get_item_info(item_id):
    conn = get_db()
    try:
        item = conn.execute(
            "SELECT cltr_mng_no FROM BID_ITEMS WHERE cltr_mng_no = ?", (item_id,)
        ).fetchone()

        if item is None:
            abort(404)

        sqms     = conn.execute("SELECT * FROM BID_SQMS     WHERE cltr_mng_no = ?", (item_id,)).fetchall()
        apsl_evl = conn.execute("SELECT * FROM BID_APSL_EVL WHERE cltr_mng_no = ?", (item_id,)).fetchall()
        paps_inf = conn.execute("SELECT * FROM BID_PAPS_INF WHERE cltr_mng_no = ?", (item_id,)).fetchone()
        crtn_lst = conn.execute("SELECT * FROM BID_CRTN_LST WHERE cltr_mng_no = ?", (item_id,)).fetchall()
        batc_cltr = conn.execute("SELECT * FROM BID_BATC_CLTR WHERE cltr_mng_no = ?", (item_id,)).fetchall()
    finally:
        conn.close()

    return jsonify({
        "sqms":      [dict(r) for r in sqms],
        "apsl_evl":  [dict(r) for r in apsl_evl],
        "paps_inf":  dict(paps_inf) if paps_inf else None,
        "crtn_lst":  [dict(r) for r in crtn_lst],
        "batc_cltr": [dict(r) for r in batc_cltr],
    })


# ─────────────────────────────────────────
# GET /api/items/<id>/history
# 탭2 유찰내역 — 회차별 입찰정보 + 이전 입찰 내역
# ─────────────────────────────────────────
@app.route("/api/items/<item_id>/history")
def get_item_history(item_id):
    conn = get_db()
    try:
        item = conn.execute(
            "SELECT cltr_mng_no FROM BID_ITEMS WHERE cltr_mng_no = ?", (item_id,)
        ).fetchone()

        if item is None:
            abort(404)

        quals = conn.execute(
            "SELECT * FROM BID_QUAL WHERE cltr_mng_no = ? ORDER BY bid_seq ASC",
            (item_id,),
        ).fetchall()

        result = []
        for q in quals:
            hists = conn.execute(
                "SELECT * FROM BID_HIST WHERE bid_qual_id = ?",
                (q["id"],),
            ).fetchall()
            result.append({**dict(q), "hist": [dict(h) for h in hists]})
    finally:
        conn.close()

    return jsonify(result)


# ─────────────────────────────────────────
# GET /api/items/<id>/tenant
# 탭4 임차인 정보 — 임대차·점유관계·등기사항·배분요구
# ─────────────────────────────────────────
@app.route("/api/items/<item_id>/tenant")
def get_item_tenant(item_id):
    conn = get_db()
    try:
        item = conn.execute(
            "SELECT cltr_mng_no FROM BID_ITEMS WHERE cltr_mng_no = ?", (item_id,)
        ).fetchone()

        if item is None:
            abort(404)

        leas_inf  = conn.execute("SELECT * FROM BID_LEAS_INF  WHERE cltr_mng_no = ?", (item_id,)).fetchall()
        ocpy_rel  = conn.execute("SELECT * FROM BID_OCPY_REL  WHERE cltr_mng_no = ?", (item_id,)).fetchall()
        rgst_prmr = conn.execute("SELECT * FROM BID_RGST_PRMR WHERE cltr_mng_no = ?", (item_id,)).fetchall()
        dtbt_rqr  = conn.execute("SELECT * FROM BID_DTBT_RQR  WHERE cltr_mng_no = ?", (item_id,)).fetchall()
    finally:
        conn.close()

    return jsonify({
        "leas_inf":  [dict(r) for r in leas_inf],
        "ocpy_rel":  [dict(r) for r in ocpy_rel],
        "rgst_prmr": [dict(r) for r in rgst_prmr],
        "dtbt_rqr":  [dict(r) for r in dtbt_rqr],
    })


# ─────────────────────────────────────────
# POST /api/items/<id>/bookmark
# 관심물건 토글
# ─────────────────────────────────────────
@app.route("/api/items/<item_id>/bookmark", methods=["POST"])
def toggle_bookmark(item_id):
    conn = get_db()
    try:
        item = conn.execute(
            "SELECT cltr_mng_no, is_bookmarked FROM BID_ITEMS WHERE cltr_mng_no = ?",
            (item_id,),
        ).fetchone()

        if item is None:
            abort(404)

        new_value = 0 if item["is_bookmarked"] else 1
        conn.execute(
            "UPDATE BID_ITEMS SET is_bookmarked = ? WHERE cltr_mng_no = ?",
            (new_value, item_id),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"cltr_mng_no": item_id, "is_bookmarked": new_value})



# ─────────────────────────────────────────
# GET /api/items/<id>/check
# 온비드 API에 물건이 아직 유효한지 확인
# ─────────────────────────────────────────
@app.route("/api/items/<item_id>/check")
def check_item(item_id):
    from onbid_bid_collector import fetch_bid

    conn = get_db()
    try:
        item = conn.execute(
            "SELECT cltr_mng_no, pbct_cdtn_no, status FROM BID_ITEMS WHERE cltr_mng_no = ?",
            (item_id,),
        ).fetchone()
    finally:
        conn.close()

    if item is None:
        abort(404)

    data = fetch_bid(item["cltr_mng_no"], item["pbct_cdtn_no"])

    if data is None:
        # API가 NODATA → 종료된 물건. DB 상태 업데이트
        conn2 = sqlite3.connect(DB_PATH)
        try:
            conn2.execute(
                "UPDATE BID_ITEMS SET status = 'closed' WHERE cltr_mng_no = ?",
                (item_id,),
            )
            conn2.commit()
        finally:
            conn2.close()
        return jsonify({"alive": False, "status": "closed"})

    return jsonify({"alive": True, "status": "active"})


# ─────────────────────────────────────────
# POST /api/items/<id>/refresh
# 단건 새로고침 — 온비드 API에서 상세+입찰 정보 재수집
# ─────────────────────────────────────────
@app.route("/api/items/<item_id>/refresh", methods=["POST"])
def refresh_item(item_id):
    from onbid_detail_collector import fetch_detail, save_detail
    from onbid_bid_collector import fetch_bid, save_bid
    from db.schema_detail import init_detail_db
    from db.schema_bid import init_bid_db

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row

        item = conn.execute(
            "SELECT cltr_mng_no, pbct_cdtn_no FROM BID_ITEMS WHERE cltr_mng_no = ?",
            (item_id,),
        ).fetchone()

        if item is None:
            abort(404)

        cltr_mng_no = item["cltr_mng_no"]
        pbct_cdtn_no = item["pbct_cdtn_no"]
        results = {"detail": False, "bid": False}

        # 상세 정보 재수집
        try:
            init_detail_db(conn)
            detail_data = fetch_detail(cltr_mng_no, pbct_cdtn_no)
            if detail_data:
                save_detail(conn, cltr_mng_no, detail_data)
                results["detail"] = True
        except Exception:
            pass

        # 입찰 정보 재수집
        try:
            init_bid_db(conn)
            bid_data = fetch_bid(cltr_mng_no, pbct_cdtn_no)
            if bid_data:
                save_bid(conn, cltr_mng_no, bid_data)
                results["bid"] = True

                # 원본 API 응답에서 현재 회차 데이터 직접 추출
                raw = bid_data
                if "body" in bid_data:
                    items_raw = (bid_data.get("body") or {}).get("items", {}).get("item")
                    if isinstance(items_raw, list):
                        raw = items_raw[0]
                    elif isinstance(items_raw, dict):
                        raw = items_raw

                usbd = raw.get("usbdNft")
                cur_price = raw.get("prcnNsqLowstBidPrc") or raw.get("lowstBidPrc")

                if usbd is not None or cur_price is not None:
                    apsl = conn.execute(
                        "SELECT apsl_evl_amt FROM BID_ITEMS WHERE cltr_mng_no = ?",
                        (cltr_mng_no,),
                    ).fetchone()
                    updates = {}
                    if usbd is not None:
                        updates["usbd_nft"] = int(usbd)
                    if cur_price is not None:
                        price = int(float(cur_price))
                        updates["lowst_bid_prc"] = price
                        if apsl and apsl["apsl_evl_amt"]:
                            updates["ratio_pct"] = round(price / apsl["apsl_evl_amt"] * 100, 2)
                    if updates:
                        set_clause = ", ".join(f"{k} = ?" for k in updates)
                        conn.execute(
                            f"UPDATE BID_ITEMS SET {set_clause} WHERE cltr_mng_no = ?",
                            (*updates.values(), cltr_mng_no),
                        )
                        conn.commit()
        except Exception:
            pass

        # 갱신된 데이터 반환 — get_item 과 동일하게 AI 점수 부착
        conn.row_factory = sqlite3.Row
        updated = conn.execute(
            "SELECT * FROM BID_ITEMS WHERE cltr_mng_no = ?", (item_id,)
        ).fetchone()
        d = dict(updated)
        attach_single_score(conn, d, item_id)

        return jsonify({"item": d, "refreshed": results})
    finally:
        conn.close()


# ─────────────────────────────────────────
# GET /api/items/<id>/market-price
# 탭3 수익성 분석 — 국토부 실거래가 기반 시세 조회
# ─────────────────────────────────────────
@app.route("/api/items/<item_id>/market-price")
def get_market_price(item_id):
    from molit_fetcher import get_market_price as fetch_market
    from db.schema_molit import init_molit_db

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        item = conn.execute(
            """SELECT cltr_mng_no, lctn_sd_nm, lctn_sggn_nm, lctn_emd_nm,
                      cltr_usg_scls_nm, bld_sqms, onbid_cltr_nm, zadr_nm,
                      lowst_bid_prc, apsl_evl_amt
               FROM BID_ITEMS WHERE cltr_mng_no = ?""",
            (item_id,),
        ).fetchone()

        if item is None:
            abort(404)

        init_molit_db(conn)

        result = fetch_market(
            conn,
            sd_nm=item["lctn_sd_nm"],
            sggn_nm=item["lctn_sggn_nm"],
            emd_nm=item["lctn_emd_nm"],
            usg_scls=item["cltr_usg_scls_nm"],
            bld_sqms=item["bld_sqms"],
            cltr_nm=item["onbid_cltr_nm"],
            zadr_nm=item["zadr_nm"],
        )

        # 시세 vs 입찰가 비교 추가
        if result.get("status") == "ok" and result.get("summary"):
            est = result["summary"].get("estimated_market_price_won")
            bid = item["lowst_bid_prc"]
            if est and bid:
                result["comparison"] = {
                    "market_vs_bid_pct": round(bid / est * 100, 1),
                    "discount_from_market_pct": round((1 - bid / est) * 100, 1),
                }

        return jsonify(result)
    finally:
        conn.close()


# ─────────────────────────────────────────
# 투자 스코어링
# ─────────────────────────────────────────
LOCATION_PREMIUM = {
    "서울특별시 강남구": 100, "서울특별시 서초구": 100, "서울특별시 송파구": 95,
    "서울특별시 마포구": 90, "서울특별시 영등포구": 90, "서울특별시 용산구": 90,
    "서울특별시 성동구": 85, "서울특별시 광진구": 85, "서울특별시 종로구": 85,
    "서울특별시": 80,
    "경기도 성남시": 85, "경기도 과천시": 85, "경기도 하남시": 80,
    "경기도 수원시": 75, "경기도 용인시": 75, "경기도 화성시": 70,
    "경기도": 65,
    "인천광역시": 60, "부산광역시": 60, "대구광역시": 55, "광주광역시": 55,
    "대전광역시": 55, "울산광역시": 50, "세종특별자치시": 50,
}


def get_location_score(sd_nm: str, sggn_nm: str) -> float:
    specific = f"{sd_nm} {sggn_nm}" if sggn_nm else sd_nm
    if specific in LOCATION_PREMIUM:
        return LOCATION_PREMIUM[specific]
    if sd_nm in LOCATION_PREMIUM:
        return LOCATION_PREMIUM[sd_nm]
    return 30


# price_ratio 정규화 시 상한 클립(winsorize) 분위.
# 시세 추정 오류로 가끔 비정상적으로 큰 비율(예: 100배)이 섞이는데,
# 순수 min-max 로는 이 단일 이상치가 분모를 키워 거의 모든 물건의 가격점수를
# 만점으로 뭉개버린다. p95 에서 상한을 잘라 가격 차원의 변별력을 보존한다.
WINSOR_Q = 0.95


def _price_ratio(start_price, market_price):
    """시작가 / 시세가 비율. 한쪽이라도 없으면(0 포함) 1.0(중립)으로 처리.

    시작가 없으면 시세가로, 시세가 없으면 시작가로 대체 → 어느 쪽이든 비율 1.0.
    """
    if start_price and market_price:
        return start_price / market_price
    return 1.0


def _percentile(sorted_vals, q):
    """오름차순 정렬된 리스트의 q 분위값 (0<=q<=1). 빈 리스트면 None."""
    if not sorted_vals:
        return None
    idx = min(int(len(sorted_vals) * q), len(sorted_vals) - 1)
    return sorted_vals[idx]


def _price_bounds(price_ratios):
    """price_ratio 리스트에서 정규화 기준 (pr_min, pr_cap) 산출.

    pr_cap 은 p95 winsorize 상한. 비면 (None, None).
    """
    if not price_ratios:
        return None, None
    prs = sorted(price_ratios)
    return prs[0], _percentile(prs, WINSOR_Q)


def _score_item(it, pr_min, pr_cap, w_price=0.7, w_location=0.3):
    """단일 물건의 AI 투자 점수를 계산해 it에 score/score_breakdown을 채운다.

    price_ratio(시작가/시세가) 정규화 기준(pr_min, pr_cap=p95 상한)은 호출부에서 결정한다.
    - 단건 조회: active 물건 전체 풀 기준
    - 목록: 전달된 items 기준
    비율이 낮을수록(시세 대비 싸게 시작) 높은 점수. pr_cap 초과분은 상한으로 클립.
    """
    pr = it.get("price_ratio")
    if pr is None:
        pr = 1.0
    pr = min(pr, pr_cap)  # winsorize: 이상치 상한 클립
    pr_range = pr_cap - pr_min if pr_cap != pr_min else 1
    price_score = 100 * (1 - (pr - pr_min) / pr_range)
    loc_score = get_location_score(it.get("lctn_sd_nm", ""), it.get("lctn_sggn_nm", ""))

    total = w_price * price_score + w_location * loc_score
    it["score"] = round(total, 1)
    it["score_breakdown"] = {
        "price": round(w_price * price_score, 1),
        "location": round(w_location * loc_score, 1),
    }
    return it


def compute_scores(items: list, w_price=0.7, w_location=0.3) -> list:
    if not items:
        return items
    for it in items:
        it["price_ratio"] = _price_ratio(it.get("start_price"), it.get("market_price"))

    pr_min, pr_cap = _price_bounds([it["price_ratio"] for it in items])

    for it in items:
        _score_item(it, pr_min, pr_cap, w_price, w_location)

    return sorted(items, key=lambda x: x["score"], reverse=True)


def attach_single_score(conn, d, item_id):
    """단건 물건 dict d 에 AI 투자 점수(score/score_breakdown)를 채운다.

    시작가(MAX min_bd_prc)·시세가(estimated_market_price_won)를 조회하고
    active 풀 전체 price_ratio 기준(p95 winsorize)으로 정규화한다.
    get_item / refresh_item 이 동일한 점수를 반환하도록 공통으로 사용.
    conn 은 row_factory=sqlite3.Row 여야 한다.
    """
    d["start_price"] = conn.execute(
        "SELECT MAX(min_bd_prc) FROM BID_QUAL WHERE cltr_mng_no = ?", (item_id,)
    ).fetchone()[0]
    mp = conn.execute(
        "SELECT estimated_market_price_won FROM MOLIT_MATCH WHERE cltr_mng_no = ?", (item_id,)
    ).fetchone()
    d["market_price"] = mp[0] if mp else None

    pool = conn.execute(
        """
        SELECT (SELECT MAX(min_bd_prc) FROM BID_QUAL q WHERE q.cltr_mng_no = b.cltr_mng_no) AS sp,
               mm.estimated_market_price_won AS mp
        FROM BID_ITEMS b
        LEFT JOIN MOLIT_MATCH mm ON mm.cltr_mng_no = b.cltr_mng_no
        WHERE b.status = 'active'
        """
    ).fetchall()

    pr_min, pr_cap = _price_bounds([_price_ratio(r["sp"], r["mp"]) for r in pool])
    if pr_min is not None:
        d["price_ratio"] = _price_ratio(d["start_price"], d["market_price"])
        _score_item(d, pr_min, pr_cap)
    return d


# ─────────────────────────────────────────
# GET /api/analytics/summary
# 홈페이지 요약 스트립용 집계 데이터
# ─────────────────────────────────────────
@app.route("/api/analytics/summary")
def analytics_summary():
    conn = get_db()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM BID_ITEMS WHERE status = 'active'"
        ).fetchone()[0]

        avg_ratio = conn.execute(
            "SELECT ROUND(AVG(ratio_pct), 1) FROM BID_ITEMS WHERE status = 'active' AND ratio_pct IS NOT NULL"
        ).fetchone()[0]

        by_region = conn.execute("""
            SELECT lctn_sd_nm AS region, COUNT(*) AS count,
                   ROUND(AVG(ratio_pct), 1) AS avg_ratio
            FROM BID_ITEMS WHERE status = 'active' AND lctn_sd_nm IS NOT NULL
            GROUP BY lctn_sd_nm ORDER BY count DESC
        """).fetchall()

        by_usage = conn.execute("""
            SELECT cltr_usg_mcls_nm AS usage_type, COUNT(*) AS count,
                   ROUND(AVG(ratio_pct), 1) AS avg_ratio
            FROM BID_ITEMS WHERE status = 'active' AND cltr_usg_mcls_nm IS NOT NULL
            GROUP BY cltr_usg_mcls_nm ORDER BY count DESC
        """).fetchall()

        ratio_dist = conn.execute("""
            SELECT
                CAST(CAST(ratio_pct / 10 AS INTEGER) * 10 AS TEXT) || '-' ||
                CAST(CAST(ratio_pct / 10 AS INTEGER) * 10 + 10 AS TEXT) || '%' AS bucket,
                COUNT(*) AS count
            FROM BID_ITEMS WHERE status = 'active' AND ratio_pct IS NOT NULL
            GROUP BY CAST(ratio_pct / 10 AS INTEGER)
            ORDER BY CAST(ratio_pct / 10 AS INTEGER)
        """).fetchall()

        top_rows = conn.execute("""
            SELECT BID_ITEMS.cltr_mng_no AS cltr_mng_no, onbid_cltr_nm, ratio_pct, usbd_nft,
                   lctn_sd_nm, lctn_sggn_nm,
                   (SELECT MAX(min_bd_prc) FROM BID_QUAL q
                     WHERE q.cltr_mng_no = BID_ITEMS.cltr_mng_no) AS start_price,
                   mm.estimated_market_price_won AS market_price
            FROM BID_ITEMS
            LEFT JOIN MOLIT_MATCH mm ON mm.cltr_mng_no = BID_ITEMS.cltr_mng_no
            WHERE status = 'active'
        """).fetchall()
        top_items = compute_scores([dict(r) for r in top_rows])[:5]

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        yesterday_total = conn.execute(
            "SELECT SUM(total_count) FROM DAILY_SNAPSHOT WHERE snapshot_date = ?",
            (yesterday,),
        ).fetchone()[0]

        return jsonify({
            "total_items": total,
            "total_delta": total - yesterday_total if yesterday_total is not None else None,
            "avg_ratio_pct": avg_ratio,
            "by_region": [dict(r) for r in by_region],
            "by_usage_type": [dict(r) for r in by_usage],
            "ratio_distribution": [dict(r) for r in ratio_dist],
            "top_scored": [{
                "cltr_mng_no": it["cltr_mng_no"],
                "name": it["onbid_cltr_nm"],
                "score": it["score"],
                "ratio_pct": it["ratio_pct"],
                "region": it["lctn_sd_nm"],
            } for it in top_items],
        })
    finally:
        conn.close()


# ─────────────────────────────────────────
# GET /api/analytics/trends?period=30d
# 트렌드 차트용 스냅샷 데이터
# ─────────────────────────────────────────
@app.route("/api/analytics/trends")
def analytics_trends():
    period = request.args.get("period", "30d")
    days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)

    conn = get_db()
    try:
        start_date = (date.today() - timedelta(days=days)).isoformat()

        rows = conn.execute("""
            SELECT snapshot_date, region, usage_type, total_count,
                   avg_ratio_pct, min_ratio_pct, fail_count_avg
            FROM DAILY_SNAPSHOT
            WHERE snapshot_date >= ?
            ORDER BY snapshot_date
        """, (start_date,)).fetchall()

        by_date = defaultdict(lambda: {"total_count": 0, "ratio_sum": 0, "ratio_n": 0, "by_region": []})
        for r in rows:
            d = dict(r)
            entry = by_date[d["snapshot_date"]]
            entry["total_count"] += d["total_count"]
            if d["avg_ratio_pct"] is not None:
                entry["ratio_sum"] += d["avg_ratio_pct"] * d["total_count"]
                entry["ratio_n"] += d["total_count"]
            entry["by_region"].append({
                "region": d["region"],
                "usage_type": d["usage_type"],
                "count": d["total_count"],
                "avg_ratio": d["avg_ratio_pct"],
            })

        data = []
        for dt in sorted(by_date.keys()):
            entry = by_date[dt]
            avg_ratio = round(entry["ratio_sum"] / entry["ratio_n"], 1) if entry["ratio_n"] > 0 else None
            data.append({
                "date": dt,
                "total_count": entry["total_count"],
                "avg_ratio": avg_ratio,
                "by_region": entry["by_region"],
            })

        return jsonify({"period": period, "data": data})
    finally:
        conn.close()


# ─────────────────────────────────────────
# GET /api/analytics/scores
# 투자 스코어보드
# ─────────────────────────────────────────
@app.route("/api/analytics/scores")
def analytics_scores():
    w_price = float(request.args.get("w_price", 0.7))
    w_location = float(request.args.get("w_location", 0.3))
    limit = int(request.args.get("limit", 50))

    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT BID_ITEMS.cltr_mng_no AS cltr_mng_no, onbid_cltr_nm,
                   lctn_sd_nm, lctn_sggn_nm,
                   cltr_usg_mcls_nm, ratio_pct, usbd_nft, lowst_bid_prc,
                   apsl_evl_amt, cltr_bid_end_dt,
                   (SELECT MAX(min_bd_prc) FROM BID_QUAL q
                     WHERE q.cltr_mng_no = BID_ITEMS.cltr_mng_no) AS start_price,
                   mm.estimated_market_price_won AS market_price
            FROM BID_ITEMS
            LEFT JOIN MOLIT_MATCH mm ON mm.cltr_mng_no = BID_ITEMS.cltr_mng_no
            WHERE status = 'active'
        """).fetchall()

        items = compute_scores([dict(r) for r in rows], w_price, w_location)

        pr_min, pr_cap = _price_bounds(
            [it["price_ratio"] for it in items if it.get("price_ratio") is not None]
        )
        return jsonify({
            "weights": {"price": w_price, "location": w_location},
            "normalization": {
                "price_min": pr_min,
                "price_cap": pr_cap,  # p95 winsorize 상한 (정규화 분모 = cap - min)
            },
            "items": [{
                "cltr_mng_no": it["cltr_mng_no"],
                "name": it["onbid_cltr_nm"],
                "region": f"{it['lctn_sd_nm']} {it.get('lctn_sggn_nm', '')}".strip(),
                "usage_type": it.get("cltr_usg_mcls_nm", ""),
                "ratio_pct": it["ratio_pct"],
                "fail_count": it.get("usbd_nft", 0),
                "lowst_bid_prc": it.get("lowst_bid_prc"),
                "apsl_evl_amt": it.get("apsl_evl_amt"),
                "start_price": it.get("start_price"),
                "market_price": it.get("market_price"),
                "price_ratio": it.get("price_ratio"),
                "cltr_bid_end_dt": it.get("cltr_bid_end_dt"),
                "score": it["score"],
                "score_breakdown": it["score_breakdown"],
            } for it in items[:limit]],
        })
    finally:
        conn.close()


# ─────────────────────────────────────────
# GET /api/analytics/flow?period=30d
# 일별 유입/소진 추이
# - new_count: BID_ITEMS.first_collected_at 기준
# - closed_count: DAILY_SNAPSHOT total_count 델타 역산 (근사)
# ─────────────────────────────────────────
@app.route("/api/analytics/flow")
def analytics_flow():
    period = request.args.get("period", "30d")
    days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)

    conn = get_db()
    try:
        start_date = (date.today() - timedelta(days=days)).isoformat()

        # new_count: BID_ITEMS.first_collected_at 기준
        new_rows = conn.execute("""
            SELECT date(first_collected_at) AS date, COUNT(*) AS new_count
            FROM BID_ITEMS
            WHERE date(first_collected_at) >= ?
            GROUP BY date(first_collected_at)
        """, (start_date,)).fetchall()
        new_by_date = {r["date"]: r["new_count"] for r in new_rows}

        # total_count: DAILY_SNAPSHOT 합산
        total_rows = conn.execute("""
            SELECT snapshot_date AS date, SUM(total_count) AS total_count
            FROM DAILY_SNAPSHOT
            WHERE snapshot_date >= ?
            GROUP BY snapshot_date
            ORDER BY snapshot_date
        """, (start_date,)).fetchall()

        # closed_count 역산: delta = total(t) - total(t-1); closed = new(t) - delta → max(0, ...)
        data = []
        prev_total = None
        for r in total_rows:
            d = r["date"]
            total = r["total_count"] or 0
            new_c = new_by_date.get(d, 0)
            if prev_total is None:
                closed_c = 0  # 시작일은 델타 계산 불가
            else:
                delta = total - prev_total
                closed_c = max(0, new_c - delta)
            data.append({
                "date": d,
                "new_count": new_c,
                "closed_count": closed_c,
                "total_count": total,
            })
            prev_total = total

        return jsonify({"period": period, "data": data})
    finally:
        conn.close()


# ─────────────────────────────────────────
# GET /api/analytics/discount-by-region
# 지역별 시세 대비 평균 할인율 (근사)
#  - BID 평균 단가: 활성 BID_ITEMS의 lowst_bid_prc / bld_sqms 평균 (원/㎡)
#  - MOLIT 평균 단가: 최근 6개월 MOLIT_TRADE_CACHE.unit_price 평균 (만원/㎡)
#  - discount_pct = (1 - bid/molit_won) * 100
# ─────────────────────────────────────────
@app.route("/api/analytics/discount-by-region")
def analytics_discount_by_region():
    # 시도 코드 → 시도명
    SIDO_CODE_MAP = {
        "11": "서울특별시", "26": "부산광역시", "27": "대구광역시",
        "28": "인천광역시", "29": "광주광역시", "30": "대전광역시",
        "31": "울산광역시", "36": "세종특별자치시", "41": "경기도",
    }

    conn = get_db()
    try:
        # BID 지역별 평균 단가 (원/㎡)
        bid_rows = conn.execute("""
            SELECT lctn_sd_nm AS region,
                   COUNT(*) AS bid_item_count,
                   AVG(CASE WHEN bld_sqms > 0 THEN lowst_bid_prc * 1.0 / bld_sqms END) AS bid_avg_per_sqm
            FROM BID_ITEMS
            WHERE status = 'active' AND bld_sqms IS NOT NULL AND bld_sqms > 0
              AND lowst_bid_prc IS NOT NULL
            GROUP BY lctn_sd_nm
        """).fetchall()
        bid_by_region = {r["region"]: dict(r) for r in bid_rows}

        # MOLIT 지역별 평균 단가 (만원/㎡), 최근 6개월
        # MOLIT_TRADE_CACHE.deal_ymd = YYYYMM, lawd_cd 앞 2자리 = 시도
        from datetime import datetime
        today = datetime.today()
        # 6개월 전 YYYYMM 계산
        y, m = today.year, today.month - 6
        while m <= 0:
            y -= 1
            m += 12
        start_ymd = f"{y}{m:02d}"

        molit_rows = conn.execute("""
            SELECT substr(lawd_cd, 1, 2) AS sido_cd,
                   COUNT(*) AS molit_deal_count,
                   AVG(unit_price) AS molit_avg_per_sqm_manwon
            FROM MOLIT_TRADE_CACHE
            WHERE deal_ymd >= ? AND unit_price IS NOT NULL AND unit_price > 0
            GROUP BY substr(lawd_cd, 1, 2)
        """, (start_ymd,)).fetchall()

        molit_by_region = {}
        for r in molit_rows:
            sido = SIDO_CODE_MAP.get(r["sido_cd"])
            if sido:
                molit_by_region[sido] = {
                    "molit_deal_count": r["molit_deal_count"],
                    "molit_avg_per_sqm": r["molit_avg_per_sqm_manwon"] * 10000,  # 만원 → 원
                }

        # 병합 및 할인율 계산
        data = []
        for region, bid in bid_by_region.items():
            molit = molit_by_region.get(region)
            bid_avg = bid["bid_avg_per_sqm"]
            if molit and molit["molit_avg_per_sqm"] and molit["molit_avg_per_sqm"] > 0 and bid_avg is not None:
                discount_pct = round((1 - bid_avg / molit["molit_avg_per_sqm"]) * 100, 1)
            else:
                discount_pct = None
            data.append({
                "region": region,
                "bid_item_count": bid["bid_item_count"],
                "molit_deal_count": molit["molit_deal_count"] if molit else 0,
                "bid_avg_per_sqm": round(bid_avg) if bid_avg else None,
                "molit_avg_per_sqm": round(molit["molit_avg_per_sqm"]) if molit else None,
                "discount_pct": discount_pct,
            })

        # 할인율 높은 순 정렬 (None은 뒤로)
        data.sort(key=lambda x: (x["discount_pct"] is None, -(x["discount_pct"] or 0)))

        return jsonify({"data": data})
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
