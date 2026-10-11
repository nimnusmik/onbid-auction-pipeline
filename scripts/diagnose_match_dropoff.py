"""
diagnose_match_dropoff.py
─────────────────────────────────────────────────────────────────────────────
Tier 0 매칭이 9.1%에 그치는 원인을 단계별로 분해한다.

단계별 탈락 측정:
  0) 지번 파싱 성공 (baseline)
  1) lawd_cd 매핑 존재
  2) 해당 lawd_cd에 MOLIT 거래가 하나라도 있음 (기간 무관)
  3) 6개월 내 거래 존재
  4) 같은 읍면동명 거래 존재
  5) 같은 본번 거래 존재
  6) 같은 본번+부번 거래 존재 ← 최종

추가: lookback 확장(6→12→24개월) 시 Tier 0 히트율 변화.
─────────────────────────────────────────────────────────────────────────────
"""
import os
import sys
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))

from collector.molit_fetcher import extract_jibun, USG_TO_ALLOWED_TYPES
from collector.lawd_code import get_lawd_cd

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "onbid.db")


def split_jibun(j: str | None):
    if not j:
        return None, ""
    parts = j.split("-", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


def months_back(n: int) -> list[str]:
    now = datetime.now()
    result = []
    for i in range(n):
        dt = now - timedelta(days=30 * i)
        ym = dt.strftime("%Y%m")
        if ym not in result:
            result.append(ym)
    return result


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    items = conn.execute(
        """SELECT cltr_mng_no, onbid_cltr_nm, lctn_sd_nm, lctn_sggn_nm, lctn_emd_nm,
                  cltr_usg_scls_nm, zadr_nm
           FROM BID_ITEMS WHERE status='active'"""
    ).fetchall()
    total = len(items)

    # 단계별 카운터
    c_parsed = 0
    c_lawd_ok = 0
    c_trade_any = 0         # 기간 무관 lawd_cd에 거래 존재
    c_trade_6mo = 0         # 6개월 내 거래
    c_dong_match = 0        # 같은 읍면동
    c_bonbun_match = 0      # 본번 일치
    c_full_match = 0        # 본번+부번 완전일치

    # lookback 비교
    lookback_hits = {6: 0, 12: 0, 24: 0, 60: 0}

    # MOLIT 통계
    conn.execute("CREATE INDEX IF NOT EXISTS idx_molit_lawd ON MOLIT_TRADE_CACHE(lawd_cd)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_molit_lawd_ymd ON MOLIT_TRADE_CACHE(lawd_cd, deal_ymd)")

    months_6 = set(months_back(6))
    months_12 = set(months_back(12))
    months_24 = set(months_back(24))

    # 읍면동 포맷 불일치 샘플
    dong_mismatch_samples = []

    for it in items:
        jibun = extract_jibun(it["onbid_cltr_nm"], it["zadr_nm"])
        if not jibun:
            continue
        c_parsed += 1

        lawd_cd = get_lawd_cd(it["lctn_sd_nm"], it["lctn_sggn_nm"])
        if not lawd_cd:
            continue
        c_lawd_ok += 1

        # api_type 화이트리스트
        usg = it["cltr_usg_scls_nm"] or ""
        allowed_types = USG_TO_ALLOWED_TYPES.get(usg, ["officetel", "commercial"])
        api_filter = "(" + ",".join("?" for _ in allowed_types) + ")"

        trades = conn.execute(
            f"""SELECT dong_nm, jibun, deal_ymd FROM MOLIT_TRADE_CACHE
                WHERE lawd_cd=? AND api_type IN {api_filter}""",
            (lawd_cd, *allowed_types),
        ).fetchall()

        if not trades:
            continue
        c_trade_any += 1

        # 기간 필터
        trades_6 = [t for t in trades if t["deal_ymd"] in months_6]
        trades_12 = [t for t in trades if t["deal_ymd"] in months_12]
        trades_24 = [t for t in trades if t["deal_ymd"] in months_24]
        trades_60 = trades  # 캐시 전체

        if trades_6:
            c_trade_6mo += 1

        dong_nm = (it["lctn_emd_nm"] or "").strip()
        bon_a, bu_a = split_jibun(jibun)

        def hit(trade_list):
            dong_hits = [t for t in trade_list if (t["dong_nm"] or "").strip() == dong_nm]
            if not dong_hits:
                return "dong_miss"
            bon_hits = [t for t in dong_hits if (t["jibun"] or "").split("-", 1)[0] == bon_a]
            if not bon_hits:
                return "bonbun_miss"
            full_hits = [
                t for t in bon_hits
                if ((t["jibun"] or "").split("-", 1)[1] if "-" in (t["jibun"] or "") else "") == bu_a
            ]
            if not full_hits:
                return "bubun_miss"
            return "full_hit"

        # 6개월 기준 단계 측정
        result = hit(trades_6)
        if result in ("bonbun_miss", "bubun_miss", "full_hit"):
            c_dong_match += 1
        if result in ("bubun_miss", "full_hit"):
            c_bonbun_match += 1
        if result == "full_hit":
            c_full_match += 1

        # 읍면동 불일치 샘플 수집
        if result == "dong_miss" and trades_6 and len(dong_mismatch_samples) < 8:
            molit_dongs = sorted({(t["dong_nm"] or "").strip() for t in trades_6})
            dong_mismatch_samples.append({
                "onbid_dong": dong_nm,
                "molit_dongs": molit_dongs[:5],
                "sggn": it["lctn_sggn_nm"],
            })

        # Lookback 확장 효과
        for mo, tl in [(6, trades_6), (12, trades_12), (24, trades_24), (60, trades_60)]:
            if hit(tl) == "full_hit":
                lookback_hits[mo] += 1

    # 리포트
    print("=" * 72)
    print(f"BID_ITEMS active 총 {total}건 — 단계별 탈락 분석")
    print("=" * 72)
    print(f"0) 지번 파싱 성공:                  {c_parsed:>5} ({c_parsed/total*100:.1f}%)")
    print(f"1) lawd_cd 매핑 성공:              {c_lawd_ok:>5} ({c_lawd_ok/total*100:.1f}%)")
    print(f"2) lawd_cd에 거래 존재 (기간무관):  {c_trade_any:>5} ({c_trade_any/total*100:.1f}%)")
    print(f"3) 6개월 내 거래 존재:             {c_trade_6mo:>5} ({c_trade_6mo/total*100:.1f}%)")
    print(f"4) 같은 읍면동 거래 존재:          {c_dong_match:>5} ({c_dong_match/total*100:.1f}%)")
    print(f"5) 같은 본번 거래 존재:            {c_bonbun_match:>5} ({c_bonbun_match/total*100:.1f}%)")
    print(f"6) 본번+부번 완전일치 (최종):       {c_full_match:>5} ({c_full_match/total*100:.1f}%)")
    print()
    print("Lookback 확장 효과 (완전일치 Tier 0 기준)")
    for mo, cnt in lookback_hits.items():
        print(f"   {mo:>3}개월: {cnt:>5}건 ({cnt/total*100:4.1f}%)")
    print()
    if dong_mismatch_samples:
        print("읍면동 불일치 샘플 (거래는 있는데 dong_nm 안 맞음):")
        for s in dong_mismatch_samples:
            print(f"   온비드 '{s['onbid_dong']}' ({s['sggn']})")
            print(f"     ↳ MOLIT dongs: {s['molit_dongs']}")


if __name__ == "__main__":
    main()
