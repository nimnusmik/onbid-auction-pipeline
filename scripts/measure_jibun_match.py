"""
measure_jibun_match.py
─────────────────────────────────────────────────────────────────────────────
지번 매칭 정확도/커버리지 측정.

측정 지표:
  1) extract_jibun() 파싱 성공률 (BID_ITEMS 전체)
  2) Tier 0 히트율 — 본번-only(현행) vs 본번+부번(제안)
  3) 건물명 보조 검증 효과
─────────────────────────────────────────────────────────────────────────────
"""
import os
import sys
import sqlite3
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))

from collector.molit_fetcher import extract_jibun, extract_building_name, _jibun_match

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "onbid.db")


def split_jibun(j: str | None) -> tuple[str | None, str | None]:
    """'1366-3' → ('1366', '3'), '821' → ('821', None)"""
    if not j:
        return None, None
    parts = j.split("-", 1)
    return parts[0], parts[1] if len(parts) > 1 else None


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 전체 active 물건
    items = conn.execute(
        """SELECT cltr_mng_no, onbid_cltr_nm AS cltr_nm,
                  lctn_sd_nm, lctn_sggn_nm, lctn_emd_nm,
                  cltr_usg_scls_nm AS usg_scls, zadr_nm
           FROM BID_ITEMS
           WHERE status='active'"""
    ).fetchall()

    # MOLIT 캐시 전체를 dong_nm + bonbun/bubun 인덱스로 로드
    molit_rows = conn.execute(
        """SELECT dong_nm, jibun, bldg_nm, api_type FROM MOLIT_TRADE_CACHE
           WHERE jibun IS NOT NULL AND jibun != '' AND jibun != '*' AND jibun != '**'"""
    ).fetchall()

    # dong_nm → [(bonbun, bubun, bldg_nm, api_type), ...]
    molit_idx: dict[str, list] = {}
    for r in molit_rows:
        dong = (r["dong_nm"] or "").strip()
        if not dong:
            continue
        bon, bu = split_jibun(r["jibun"])
        if not bon:
            continue
        molit_idx.setdefault(dong, []).append((bon, bu, r["bldg_nm"] or "", r["api_type"]))

    # 측정 카운터
    total = len(items)
    jibun_parsed = 0
    jibun_failed_samples = []
    bldg_parsed = 0

    tier0_bonbun_only = 0      # 현행
    tier0_full_match = 0       # 제안 (본번+부번)
    tier0_full_and_bldg = 0    # 제안 + 건물명 이중 검증
    hit_sample_size_bonbun_only = []
    hit_sample_size_full = []

    # 용도별 카운트
    by_usg = Counter()
    by_usg_parsed = Counter()
    by_usg_full_hit = Counter()

    for it in items:
        cltr_nm = it["cltr_nm"]
        dong_nm = (it["lctn_emd_nm"] or "").strip()
        usg = it["usg_scls"] or "기타"
        by_usg[usg] += 1

        jibun = extract_jibun(cltr_nm, it["zadr_nm"])
        bldg = extract_building_name(cltr_nm)

        if jibun:
            jibun_parsed += 1
            by_usg_parsed[usg] += 1
        else:
            if len(jibun_failed_samples) < 10:
                jibun_failed_samples.append(cltr_nm)

        if bldg:
            bldg_parsed += 1

        if not jibun or not dong_nm:
            continue

        bon_a, bu_a = split_jibun(jibun)
        candidates = molit_idx.get(dong_nm, [])

        # 본번 only (과거 로직 대비용)
        bon_only_hits = [c for c in candidates if c[0] == bon_a]
        # 본번+부번 완전일치 (= 현행 _jibun_match)
        full_hits = [c for c in candidates if c[0] == bon_a and (c[1] or "") == (bu_a or "")]

        if bon_only_hits:
            tier0_bonbun_only += 1
            hit_sample_size_bonbun_only.append(len(bon_only_hits))
        if full_hits:
            tier0_full_match += 1
            by_usg_full_hit[usg] += 1
            hit_sample_size_full.append(len(full_hits))

            # 건물명 이중 검증: 온비드 건물명이 MOLIT 거래 건물명 중 하나에 포함되면 OK
            if bldg:
                for c in full_hits:
                    if bldg and c[2] and (bldg in c[2] or c[2] in bldg):
                        tier0_full_and_bldg += 1
                        break

    # 리포트
    print("=" * 72)
    print(f"BID_ITEMS active 총 {total}건 기준")
    print("=" * 72)
    print(f"1. 지번 파싱 성공:        {jibun_parsed:>5} / {total} ({jibun_parsed/total*100:.1f}%)")
    print(f"   건물명 파싱 성공:      {bldg_parsed:>5} / {total} ({bldg_parsed/total*100:.1f}%)")
    print()
    print(f"2. Tier 0 히트율 (지번 파싱 성공분 기준: {jibun_parsed}건)")
    denom = jibun_parsed or 1
    print(f"   본번-only (현행):      {tier0_bonbun_only:>5} / {jibun_parsed} ({tier0_bonbun_only/denom*100:.1f}%)")
    print(f"   본번+부번 완전일치:    {tier0_full_match:>5} / {jibun_parsed} ({tier0_full_match/denom*100:.1f}%)")
    print(f"   ↳ + 건물명 검증:      {tier0_full_and_bldg:>5} / {jibun_parsed} ({tier0_full_and_bldg/denom*100:.1f}%)")
    print()
    print(f"   평균 매칭 거래 수 (본번-only): {sum(hit_sample_size_bonbun_only)/max(1,len(hit_sample_size_bonbun_only)):.1f}건")
    print(f"   평균 매칭 거래 수 (완전일치): {sum(hit_sample_size_full)/max(1,len(hit_sample_size_full)):.1f}건")
    print()
    print("3. 용도별 파싱·매칭")
    for usg, cnt in by_usg.most_common():
        p = by_usg_parsed.get(usg, 0)
        h = by_usg_full_hit.get(usg, 0)
        print(f"   {usg:<12} 총{cnt:>4}건  지번파싱 {p:>4}({p/cnt*100:4.1f}%)  완전일치 Tier0 {h:>4}({h/cnt*100:4.1f}%)")
    print()
    print("4. 지번 파싱 실패 샘플 (cltr_nm):")
    for s in jibun_failed_samples:
        print(f"   - {s}")


if __name__ == "__main__":
    main()
