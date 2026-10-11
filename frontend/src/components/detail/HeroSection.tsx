// frontend/src/components/detail/HeroSection.tsx
"use client";

import { useEffect, useState } from "react";
import { fetchItemInfo } from "@/api";
import { fmtKRW, sqmsToPyeong, dLabel, daysLeft } from "@/utils/format";
import { useMarketPrice } from "@/hooks/useMarketPrice";
import type { BidItem } from "@/types";
import HeroMap from "./HeroMap";

interface Props {
  item: BidItem;
  onBookmark: () => void;
  onRefresh: () => void;
  refreshing?: boolean;
}

function DeadlinePill({ dt }: { dt: string }) {
  const dl = daysLeft(dt);
  const cls =
    dl < 0
      ? "bg-border text-text-4"
      : dl <= 3
      ? "bg-hot-bg text-hot-fg"
      : "bg-primary-subtle text-primary";
  return (
    <span className={`text-xs rounded-full px-2.5 py-0.5 font-medium ${cls}`}>
      {dLabel(dt)}
    </span>
  );
}

function RatioText({ r }: { r: number }) {
  const cls = r < 60 ? "text-hot-fg" : r < 70 ? "text-mid-fg" : "text-ok-fg";
  return <span className={`text-base font-bold ${cls} tabular-nums`}>{r.toFixed(1)}%</span>;
}

function DiscountText({ discount }: { discount: number | null | undefined }) {
  if (discount == null) return <span className="text-base text-text-4">-</span>;
  const cls =
    discount > 30 ? "text-hot-fg" : discount > 15 ? "text-mid-fg" : "text-ok-fg";
  return (
    <span className={`text-base font-bold ${cls} tabular-nums`}>
      -{discount.toFixed(1)}%
    </span>
  );
}

const ONBID_SEARCH_URL =
  "https://www.onbid.co.kr/op/cltrpbancinf/cltr/cltrcdtnsrch/CltrCdtnSrchController/mvmnCltrCdtnSrchClg.do";

async function openOnbidWithClipboard(cltrMngNo: string) {
  try {
    await navigator.clipboard.writeText(cltrMngNo);
  } catch {
    // clipboard unavailable (insecure context or denied permission) — open anyway
  }
  window.open(ONBID_SEARCH_URL, "_blank", "noopener,noreferrer");
}

export default function HeroSection({ item, onBookmark, onRefresh, refreshing }: Props) {
  const address = `${item.lctn_sd_nm} ${item.lctn_sggn_nm} ${item.lctn_emd_nm}`;
  const { market } = useMarketPrice(item.cltr_mng_no);
  const discount = market?.comparison?.discount_from_market_pct ?? null;
  const [copied, setCopied] = useState(false);
  const [apslPdfUrl, setApslPdfUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchItemInfo(item.cltr_mng_no)
      .then((info) => {
        if (cancelled) return;
        const records = info.apsl_evl
          .filter((r) => {
            const u = r.url_adr;
            return typeof u === "string" && u.trim().length > 0;
          })
          .sort((a, b) =>
            String(b.apsl_evl_ymd ?? "").localeCompare(String(a.apsl_evl_ymd ?? "")),
          );
        if (records.length > 0) setApslPdfUrl(String(records[0].url_adr));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [item.cltr_mng_no]);

  async function handleOnbidClick() {
    await openOnbidWithClipboard(item.cltr_mng_no);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  function handleApslPdfClick() {
    if (!apslPdfUrl) return;
    window.open(apslPdfUrl, "_blank", "noopener,noreferrer");
  }

  return (
    <div className="bg-surface shadow-card rounded-xl p-5 md:p-6">
      <div className="flex flex-col md:flex-row gap-5 md:gap-6">
        {/* 좌: 지도 */}
        <div className="w-full md:w-60 h-48 md:h-auto md:self-stretch shrink-0 rounded-lg overflow-hidden bg-surface-muted">
          <HeroMap address={address} labelSggn={item.lctn_sggn_nm} className="w-full h-full" />
        </div>

        {/* 중: 정보 */}
        <div className="flex-1 flex flex-col gap-3 min-w-0">
          {/* 배지 */}
          <div className="flex flex-wrap gap-1.5">
            {item.ratio_pct < 60 && (
              <span className="text-xs bg-hot-bg text-hot-fg rounded-full px-2 py-0.5 font-medium">
                60% 미만 알림
              </span>
            )}
            {item.pvct_trgt_yn === "Y" && (
              <span className="text-xs bg-primary-subtle text-primary rounded-full px-2 py-0.5 font-medium">
                수의계약
              </span>
            )}
            {item.alc_yn === "Y" && (
              <span className="text-xs bg-border text-text-3 rounded-full px-2 py-0.5">
                지분물건
              </span>
            )}
            <span className="text-xs bg-border text-text-3 rounded-full px-2 py-0.5">
              {item.prpt_div_nm}
            </span>
            <DeadlinePill dt={item.cltr_bid_end_dt} />
          </div>

          {/* 물건명/주소 */}
          <div>
            <p className="text-xs text-text-3 font-mono">{item.cltr_mng_no}</p>
            <h1 className="text-xl md:text-2xl font-bold text-text-1 tracking-tight mt-0.5">
              {item.onbid_cltr_nm}
            </h1>
            <p className="text-sm text-text-2 mt-1">{address}</p>
            <p className="text-xs text-text-4 mt-0.5">
              건물 {sqmsToPyeong(item.bld_sqms)}
              {item.land_sqms != null && ` / 토지 ${sqmsToPyeong(item.land_sqms)}`}
            </p>
          </div>

          {/* 가격 */}
          <div className="flex items-baseline gap-3 flex-wrap">
            <span className="text-sm text-text-4 line-through tabular-nums">
              {fmtKRW(item.apsl_evl_amt)}
            </span>
            <span className="text-2xl font-bold text-primary tabular-nums tracking-tight">
              {fmtKRW(item.lowst_bid_prc)}
            </span>
          </div>

          {/* 게이지바 (가격 바로 아래) */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-4 w-6">0%</span>
            <div className="flex-1 h-2 bg-border rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  item.ratio_pct < 60 ? "bg-hot-fg" : item.ratio_pct < 70 ? "bg-mid-fg" : "bg-ok-fg"
                }`}
                style={{ width: `${Math.min(item.ratio_pct, 100)}%` }}
              />
            </div>
            <span className="text-xs text-text-4 w-8">100%</span>
          </div>

          {/* 핵심 4수치 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div className="bg-surface-muted rounded-lg px-3 py-2 text-center">
              <p className="text-xs text-text-4 mb-1">감정가 대비</p>
              <RatioText r={item.ratio_pct} />
            </div>
            <div className="bg-surface-muted rounded-lg px-3 py-2 text-center">
              <p className="text-xs text-text-4 mb-1">시세 대비</p>
              <DiscountText discount={discount} />
            </div>
            <div className="bg-surface-muted rounded-lg px-3 py-2 text-center">
              <p className="text-xs text-text-4 mb-1">유찰 횟수</p>
              <p className="text-base font-bold text-text-1 tabular-nums">{item.usbd_nft}회</p>
            </div>
            <div className="bg-primary-subtle rounded-lg px-3 py-2 text-center">
              <p className="text-xs text-primary mb-1">AI 점수</p>
              {item.score != null ? (
                <>
                  <p
                    className={`text-base font-bold tabular-nums ${
                      item.score >= 70 ? "text-primary-hover" : item.score >= 50 ? "text-primary" : "text-text-4"
                    }`}
                  >
                    {item.score}점
                  </p>
                  {item.score_breakdown && (
                    <div className="flex justify-center gap-1.5 mt-1">
                      <span className="text-[10px] text-primary">가격 {item.score_breakdown.price}</span>
                      <span className="text-[10px] text-primary">입지 {item.score_breakdown.location}</span>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-base text-text-4">-</p>
              )}
            </div>
          </div>
        </div>

        {/* 우: 액션 */}
        <div className="flex md:flex-col gap-2 shrink-0">
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className="flex-1 md:flex-none px-4 py-2 rounded-md text-sm font-medium border border-ok-fg/30 bg-ok-bg text-ok-fg hover:opacity-80 transition-opacity disabled:opacity-50"
          >
            {refreshing ? "갱신 중..." : "↻ 새로고침"}
          </button>
          <button
            onClick={onBookmark}
            className={`flex-1 md:flex-none px-4 py-2 rounded-md text-sm font-medium border transition-colors ${
              item.is_bookmarked
                ? "bg-mid-bg text-mid-fg border-mid-fg/30"
                : "bg-surface text-text-2 border-border-strong hover:border-primary"
            }`}
          >
            {item.is_bookmarked ? "★ 관심 해제" : "☆ 관심 등록"}
          </button>
          <button
            type="button"
            onClick={handleApslPdfClick}
            disabled={!apslPdfUrl}
            title={apslPdfUrl ? "감정평가서 PDF 다운로드" : "감정평가서 PDF가 없습니다"}
            className="flex-1 md:flex-none px-4 py-2 rounded-md text-sm font-medium bg-primary text-primary-fg hover:bg-primary-hover transition-colors text-center disabled:opacity-50 disabled:cursor-not-allowed"
          >
            📄 감정평가서
          </button>
          <button
            type="button"
            onClick={handleOnbidClick}
            title={`물건번호 복사 + 온비드 조건검색 열기 (${item.cltr_mng_no})`}
            className="flex-1 md:flex-none px-4 py-2 rounded-md text-sm font-medium bg-surface text-primary border border-primary/30 hover:bg-primary-subtle transition-colors text-center"
          >
            {copied ? "물건번호 복사됨 · 붙여넣기" : "온비드 →"}
          </button>
        </div>
      </div>
    </div>
  );
}
