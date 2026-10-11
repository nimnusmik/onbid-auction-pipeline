"""
onbid_web_history_collector.py
─────────────────────────────────────────────────────────────────────────────
온비드 웹 상세페이지(`mvmnCltrDtl.do`)를 직접 호출하여
공공데이터 OpenAPI 로 가져오지 못하는 회차별 입찰 이력을 수집한다.

[배경]
  공공데이터 OpenAPI(getCltrBidInf2)는 "활성 공매조건(pbctCdtnNo)" 일 때만
  회차 이력을 돌려준다. 수의계약 단계로 전환된 물건은 NODATA(03) 응답 →
  회차 이력 영구 누락. 온비드 웹 상세페이지에는 그 데이터가 표시되므로
  거기서 직접 스크레이핑한다.

[필요 조건]
  BID_ITEMS 에 다음 4개 식별자가 모두 채워져 있어야 한다:
    cltr_mng_no, pbct_cdtn_no, onbid_cltrno, onbid_pbanc_no, pbct_no
  (앞 3개는 detail collector 가 채워줌)

[흐름]
  1. 검색페이지 GET → 세션 쿠키 + CSRF 토큰 부트스트랩
  2. 상세페이지 POST → 회차 이력 HTML
  3. <div class="history_item"> 파싱 → BID_QUAL INSERT
  4. 호출 사이 SLEEP_SEC 대기 (NetFunnel 트리거 회피)

[주의]
  - 비공식 경로 — KAMCO 가 페이지 구조 바꾸면 파싱 깨짐
  - NetFunnel 대기열에 걸리면 응답 형태 달라짐 → 감지해서 중단
  - 한 세션이 얼마나 가는지 정확히 모르므로 N건마다 세션 재부트스트랩
─────────────────────────────────────────────────────────────────────────────
"""

import os
import re
import sys
import sqlite3
import time
import logging
from typing import Optional

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import to_int, to_str, now_str

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
DB_PATH    = os.path.join(os.path.dirname(__file__), "..", "data", "onbid.db")
SEARCH_URL = "https://www.onbid.co.kr/op/cltrpbancinf/cltr/cltrcdtnsrch/CltrCdtnSrchController/mvmnCltrCdtnSrchClg.do"
DTL_URL    = "https://www.onbid.co.kr/op/cltrpbancinf/cltrdtl/CltrDtlController/mvmnCltrDtl.do"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"

SLEEP_SEC          = 1.0    # 호출 간 대기 — NetFunnel 트리거 회피
SESSION_REFRESH_N  = 50     # N건마다 세션 재부트스트랩
HTTP_TIMEOUT       = 20

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("onbid_web_history.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────
# 세션 부트스트랩
# ─────────────────────────────────────────
class SessionExpired(Exception):
    """세션 만료 또는 NetFunnel 차단 — 재부트스트랩 필요."""


def bootstrap_session() -> tuple[requests.Session, str]:
    """검색페이지 GET 으로 JSESSIONIDOP + WMONID 쿠키 + CSRF 토큰 획득."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    r = s.get(SEARCH_URL, timeout=HTTP_TIMEOUT)
    r.raise_for_status()

    m = re.search(r'<meta[^>]*name=["\']_csrf["\'][^>]*content=["\']([^"\']+)', r.text)
    if not m:
        m = re.search(r'_csrf[^a-z0-9][^"\']*["\']([0-9a-f-]{30,40})["\']', r.text, re.I)
    if not m:
        raise RuntimeError("CSRF 토큰 추출 실패 — 페이지 구조가 바뀌었을 수 있음")

    csrf = m.group(1)
    if "JSESSIONIDOP" not in {c.name for c in s.cookies}:
        raise RuntimeError("JSESSIONIDOP 쿠키 미수신")

    return s, csrf


# ─────────────────────────────────────────
# 상세페이지 호출
# ─────────────────────────────────────────
def fetch_detail_html(
    session: requests.Session,
    csrf: str,
    cltr_mng_no: str,
    pbct_cdtn_no: int,
    onbid_cltrno: int,
    onbid_pbanc_no: int,
    pbct_no: int,
) -> str:
    """상세페이지 POST → HTML 본문 반환."""
    payload = {
        "_csrf":          csrf,
        "cltrMngNo":      cltr_mng_no,
        "pbctCdtnNo":     str(pbct_cdtn_no),
        "onbidCltrno":    str(onbid_cltrno),
        "onbidPbancNo":   str(onbid_pbanc_no),
        "pbctNo":         str(pbct_no),
        "cltrPrptDivCd":  "0005",   # 부동산
        "cltrScrnGrpCd":  "0001",
    }
    r = session.post(DTL_URL, data=payload, headers={
        "Origin": "https://www.onbid.co.kr",
        "Referer": SEARCH_URL,
        "Content-Type": "application/x-www-form-urlencoded",
    }, timeout=HTTP_TIMEOUT)

    if r.status_code in (401, 403):
        raise SessionExpired(f"HTTP {r.status_code}")
    if r.status_code >= 500:
        raise RuntimeError(f"서버 에러 HTTP {r.status_code}")
    r.raise_for_status()

    if "NetFunnel" in r.text or "netfunnel" in r.text and len(r.text) < 5000:
        raise SessionExpired("NetFunnel 대기열 응답")

    return r.text


# ─────────────────────────────────────────
# HTML 파싱
# ─────────────────────────────────────────
_RE_HISTORY_ITEM = re.compile(
    r'<div class="history_item[^"]*">(.*?)<div class="history_item|<div class="history_item[^"]*">(.*?)</?(?:section|main|footer|/div class="bid_history)',
    re.DOTALL,
)
_RE_HISTORY_BLOCK = re.compile(
    r'<div class="history_item(?: hidden)?">(.*?)(?=<div class="history_item(?: hidden)?">|</div>\s*</div>\s*<div class="btn_box|</div>\s*</div>\s*<script)',
    re.DOTALL,
)
_RE_STAT          = re.compile(r'<span class="stat_txt01">\s*([^<]+?)\s*</span>')
_RE_DATE          = re.compile(r'<span class="history_stat_date">[^<]*?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})')
_RE_LI_TEXT       = re.compile(
    r'<li>\s*<span class="tit01">\s*([^<]+?)\s*</span>\s*'
    r'<span class="(txt01|txt02)">\s*([^<]+?)\s*</span>',
    re.DOTALL,
)
_RE_GO_BID_HIS    = re.compile(
    r'fn_goBidHisDetail\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)'
)


def parse_history_items(html: str) -> list[dict]:
    """HTML 응답에서 회차별 이력 추출.

    각 회차 블록 = <div class="history_item"> 또는 <div class="history_item hidden">
    각 블록 내부:
      stat_txt01           : "유찰" / "낙찰" / "취소"
      history_stat_date    : "개찰일시 : 2025-09-10 09:00"
      <li> 회차 / 최저입찰가격 / 낙찰금액
      fn_goBidHisDetail(pbctNo, pbctCdtnNo, onbidCltrno, onbidPbancNo)

    페이지에 데스크톱(tbl_toggle) / 모바일(tbl_toggle_mo) 두 버전이 같은 데이터를
    중복 렌더링하므로, 첫 번째 컨테이너(tbl_toggle)만 추출 후 그 안에서 파싱.

    표준 라이브러리만으로 정규식 파싱 (bs4 의존성 제거).
    """
    rows: list[dict] = []

    # 첫 번째 bid_history_box01 컨테이너 추출 (데스크톱 버전)
    container_match = re.search(
        r'<div class="bid_history_box01"[^>]*id="tbl_toggle"[^>]*>(.*?)(?=<div class="bid_history_box01"|</section|</main)',
        html, re.DOTALL,
    )
    target_html = container_match.group(1) if container_match else html

    for m in _RE_HISTORY_BLOCK.finditer(target_html):
        block = m.group(1)

        # 결과 상태
        result_status = None
        sm = _RE_STAT.search(block)
        if sm:
            result_status = sm.group(1).strip()

        # 개찰일시
        opbd_dt = None
        dm = _RE_DATE.search(block)
        if dm:
            opbd_dt = dm.group(1)

        # li 들에서 라벨별 값 추출
        labels: dict[str, str] = {}
        for lm in _RE_LI_TEXT.finditer(block):
            label = re.sub(r"\s+", "", lm.group(1))
            value = lm.group(3).strip()
            labels[label] = value

        # 회차 번호 — "7/1" 형태에서 앞 = 회차, 뒤 = 차수
        bid_seq = None
        bid_round = None  # 차수 (pbctsn 대응)
        seq_text = labels.get("회차", "")
        sm2 = re.match(r"(\d+)\s*/\s*(\d+)", seq_text)
        if sm2:
            bid_seq = int(sm2.group(1))
            bid_round = int(sm2.group(2))
        else:
            sm3 = re.match(r"(\d+)", seq_text)
            if sm3:
                bid_seq = int(sm3.group(1))

        # 최저입찰가격
        min_bd_prc = None
        for k in ("최저입찰가격", "최저입찰가"):
            if k in labels:
                digits = re.sub(r"[^\d]", "", labels[k])
                if digits:
                    min_bd_prc = int(digits)
                break

        # 낙찰금액 — "-" 면 None
        winning_amt = None
        won_text = labels.get("낙찰금액", "").strip()
        if won_text and won_text != "-":
            digits = re.sub(r"[^\d]", "", won_text)
            if digits:
                winning_amt = int(digits)

        # 회차별 식별자 (fn_goBidHisDetail 인자)
        round_pbct_no = None
        round_pbct_cdtn_no = None
        gm = _RE_GO_BID_HIS.search(block)
        if gm:
            round_pbct_no = int(gm.group(1))
            round_pbct_cdtn_no = int(gm.group(2))

        if bid_seq is None and result_status is None and opbd_dt is None:
            continue  # 빈 블록 스킵

        rows.append({
            "bid_seq":            bid_seq,
            "bid_round":          bid_round,
            "result_status":      result_status,
            "bid_opnn_dttm":      opbd_dt,
            "min_bd_prc":         min_bd_prc,
            "winning_amt":        winning_amt,
            "round_pbct_no":      round_pbct_no,
            "round_pbct_cdtn_no": round_pbct_cdtn_no,
        })

    return rows


# ─────────────────────────────────────────
# DB 저장
# ─────────────────────────────────────────
def save_rows(conn: sqlite3.Connection, cltr_mng_no: str, pbct_cdtn_no: int, rows: list[dict]) -> int:
    """파싱된 회차 행들을 BID_QUAL 에 저장. 기존 데이터는 삭제 후 재삽입."""
    # 기존 행 삭제 (BID_HIST 는 신형 응답에서 안 쓰지만 일관성 위해 같이)
    qual_ids = [r[0] for r in conn.execute(
        "SELECT id FROM BID_QUAL WHERE cltr_mng_no = ?", (cltr_mng_no,)
    ).fetchall()]
    if qual_ids:
        ph = ",".join("?" * len(qual_ids))
        conn.execute(f"DELETE FROM BID_HIST WHERE bid_qual_id IN ({ph})", qual_ids)
    conn.execute("DELETE FROM BID_QUAL WHERE cltr_mng_no = ?", (cltr_mng_no,))

    saved = 0
    for r in rows:
        if r["bid_seq"] is None:
            continue
        conn.execute("""
            INSERT INTO BID_QUAL (
                cltr_mng_no, pbct_cdtn_no,
                bid_seq, bid_round, bid_opnn_dttm, min_bd_prc,
                winning_amt, result_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cltr_mng_no,
            r["round_pbct_cdtn_no"] or pbct_cdtn_no,
            r["bid_seq"],
            r["bid_round"],
            r["bid_opnn_dttm"],
            r["min_bd_prc"],
            r["winning_amt"],
            r["result_status"],
        ))
        saved += 1

    conn.execute(
        "UPDATE BID_ITEMS SET bid_fetched_at = ? WHERE cltr_mng_no = ?",
        (now_str(), cltr_mng_no),
    )
    conn.commit()
    return saved


# ─────────────────────────────────────────
# 조회 대상 선정
# ─────────────────────────────────────────
def get_pending_items(conn: sqlite3.Connection, limit: Optional[int] = None) -> list[tuple]:
    """웹 스크레이핑 대상 물건 목록.

    조건:
      - status = 'active'
      - 4개 식별자(pbct_cdtn_no, onbid_cltrno, onbid_pbanc_no, pbct_no) 모두 NOT NULL
      - BID_QUAL 이 비어있는 물건 우선 (수의계약 단계로 의심되는 케이스)
    """
    sql = """
        SELECT cltr_mng_no, pbct_cdtn_no, onbid_cltrno, onbid_pbanc_no, pbct_no
        FROM BID_ITEMS
        WHERE status = 'active'
          AND pbct_cdtn_no   IS NOT NULL
          AND onbid_cltrno   IS NOT NULL
          AND onbid_pbanc_no IS NOT NULL
          AND pbct_no        IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM BID_QUAL q WHERE q.cltr_mng_no = BID_ITEMS.cltr_mng_no
          )
        ORDER BY ratio_pct ASC NULLS LAST
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql).fetchall()


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────
def main(limit: Optional[int] = None, dry_run: bool = False):
    conn = sqlite3.connect(DB_PATH)
    try:
        pending = get_pending_items(conn, limit=limit)
        total = len(pending)
        if total == 0:
            log.info("웹 회차이력 수집 대상 없음")
            return

        log.info(f"웹 회차이력 수집 대상: {total}건 (dry_run={dry_run})")

        session, csrf = bootstrap_session()
        log.info(f"세션 부트스트랩 OK — CSRF={csrf[:8]}...")

        success = 0
        empty   = 0
        fail    = 0

        for idx, (cltr_mng_no, pbct_cdtn_no, onbid_cltrno, onbid_pbanc_no, pbct_no) in enumerate(pending, 1):
            log.info(f"[{idx}/{total}] {cltr_mng_no}")

            # 세션 주기 갱신
            if idx > 1 and (idx - 1) % SESSION_REFRESH_N == 0:
                session, csrf = bootstrap_session()
                log.info(f"  세션 재부트스트랩")

            try:
                html = fetch_detail_html(session, csrf, cltr_mng_no,
                                         pbct_cdtn_no, onbid_cltrno, onbid_pbanc_no, pbct_no)
            except SessionExpired as e:
                log.warning(f"  세션 만료/차단 ({e}) — 재부트스트랩 후 재시도")
                session, csrf = bootstrap_session()
                try:
                    html = fetch_detail_html(session, csrf, cltr_mng_no,
                                             pbct_cdtn_no, onbid_cltrno, onbid_pbanc_no, pbct_no)
                except Exception as e2:
                    log.error(f"  재시도 실패: {e2}")
                    fail += 1
                    time.sleep(SLEEP_SEC)
                    continue
            except Exception as e:
                log.error(f"  호출 실패: {e}")
                fail += 1
                time.sleep(SLEEP_SEC)
                continue

            rows = parse_history_items(html)
            if not rows:
                log.warning(f"  → 회차 0건 (페이지 구조 의심 또는 정말 이력 없음)")
                empty += 1
            else:
                if dry_run:
                    log.info(f"  → DRY-RUN: {len(rows)}건 파싱됨 — DB 저장 생략")
                    for r in rows[:3]:
                        log.info(f"     {r['bid_seq']}회차 {r['result_status']} {r['bid_opnn_dttm']} 최저가={r['min_bd_prc']}")
                else:
                    saved = save_rows(conn, cltr_mng_no, pbct_cdtn_no, rows)
                    log.info(f"  → 저장 {saved}건")
                success += 1

            time.sleep(SLEEP_SEC)

        log.info("=" * 55)
        log.info(f"완료 | 성공:{success} / 빈응답:{empty} / 실패:{fail} / 전체:{total}")
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None, help="처리할 최대 건수")
    p.add_argument("--dry-run", action="store_true", help="DB 저장 안 하고 파싱만")
    args = p.parse_args()
    main(limit=args.limit, dry_run=args.dry_run)
