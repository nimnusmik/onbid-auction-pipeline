// frontend/src/components/detail/TabPricing.tsx
"use client";

import { useEffect, useState } from "react";
import { fetchItemHistory } from "@/api";
import { useMarketPrice } from "@/hooks/useMarketPrice";
import type { BidItem, BidQual, MarketPriceResponse } from "@/types";
import { fmtAmt } from "@/utils/format";
import DecisionBanner, { type DecisionStatus } from "./DecisionBanner";

const STORAGE_KEY_PREFIX = "onbid_memo_";

const TIER_LABELS: Record<number, string> = {
  0: "같은 건물 (지번 완전일치)",
  1: "같은 건물 (건물명+면적)",
};

const STATUS_MSG: Record<string, { icon: string; title: string; desc: string }> = {
  no_mapping:    { icon: "🗺️", title: "법정동코드 매핑 없음",   desc: "해당 지역의 법정동코드를 찾을 수 없습니다." },
  not_supported: { icon: "🏢", title: "미지원 용도",             desc: "현재 오피스텔과 업무시설만 시세 조회를 지원합니다." },
  no_data:       { icon: "📭", title: "같은 건물 실거래 없음",   desc: "최근 6개월간 같은 건물의 실거래가 없어 시세를 표시하지 않습니다. (주변 평균가는 오차가 커 신뢰도가 낮아 제외)" },
  api_error:     { icon: "⚠️", title: "API 오류",               desc: "국토교통부 API 호출 중 오류가 발생했습니다." },
};

interface Props {
  item: BidItem;
}

export default function TabPricing({ item }: Props) {
  const [quals, setQuals] = useState<BidQual[]>([]);

  const { market, loading: marketLoading, error: marketError } = useMarketPrice(item.cltr_mng_no);

  const storageKey = `${STORAGE_KEY_PREFIX}${item.cltr_mng_no}`;
  const [memo, setMemo] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchItemHistory(item.cltr_mng_no).then(setQuals).catch(() => {});
  }, [item.cltr_mng_no]);

  useEffect(() => {
    const stored = localStorage.getItem(storageKey);
    if (stored) setMemo(stored);
  }, [storageKey]);

  function saveMemo() {
    localStorage.setItem(storageKey, memo);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  // 가격 추이: 진행중 회차는 min_bd_prc가 null일 수 있어 BID_ITEMS의 lowst_bid_prc 사용
  const pricedQuals = quals
    .filter((q) => q.min_bd_prc != null && q.min_bd_prc > 0)
    .sort((a, b) => a.bid_seq - b.bid_seq);
  const firstMin = pricedQuals.length > 0 ? Math.max(...pricedQuals.map((q) => q.min_bd_prc as number)) : null;
  const lastMin = item.lowst_bid_prc ?? (pricedQuals.length > 0 ? (pricedQuals[pricedQuals.length - 1].min_bd_prc as number) : null);
  const dropPct = firstMin && lastMin ? ((firstMin - lastMin) / firstMin) * 100 : null;
  const failCount = quals.filter((q) => q.result_status === "유찰").length;

  // DecisionBanner status 결정
  const discount = market?.comparison?.discount_from_market_pct ?? null;
  let status: DecisionStatus = "ok";
  let bannerText = `감정가의 ${item.ratio_pct.toFixed(1)}%`;
  if (discount !== null) {
    bannerText += ` · 시세 대비 ${discount > 0 ? "-" : "+"}${Math.abs(discount).toFixed(1)}% ${discount > 0 ? "저렴" : "비쌈"}`;
    if (discount > 30) status = "ok";
    else if (discount > 15) status = "warn";
    else status = "danger";
  } else if (item.ratio_pct < 60) {
    status = "ok";
  } else if (item.ratio_pct < 70) {
    status = "warn";
  } else {
    status = "danger";
  }
  if (failCount > 0) {
    bannerText = `${failCount}회차 유찰 후 ${bannerText}`;
  }

  return (
    <div className="flex flex-col gap-6">
      <DecisionBanner status={status}>{bannerText}</DecisionBanner>

      {/* === 1. 가격 추이 요약 === */}
      <div className="bg-surface shadow-card rounded-xl p-5">
        <p className="text-sm font-semibold text-text-1 mb-3">가격 추이 요약</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-[11px] text-text-4">감정평가액</p>
            <p className="text-sm font-semibold text-text-1 tabular-nums">{fmtAmt(item.apsl_evl_amt)}</p>
          </div>
          {firstMin && (
            <div>
              <p className="text-[11px] text-text-4">최초 최저입찰가</p>
              <p className="text-sm font-semibold text-text-1 tabular-nums">{fmtAmt(firstMin)}</p>
            </div>
          )}
          {lastMin && (
            <div>
              <p className="text-[11px] text-text-4">현재 최저입찰가</p>
              <p className="text-sm font-semibold text-primary tabular-nums">{fmtAmt(lastMin)}</p>
            </div>
          )}
          {dropPct !== null && dropPct > 0 && (
            <div>
              <p className="text-[11px] text-text-4">하락률</p>
              <p className="text-base font-bold text-hot-fg tabular-nums">-{dropPct.toFixed(1)}%</p>
            </div>
          )}
        </div>
      </div>

      {/* === 2. 국토부 실거래가 시세 비교 === */}
      {marketLoading ? (
        <div className="bg-surface shadow-card rounded-xl p-8 text-center">
          <div className="animate-pulse text-sm text-text-4">국토부 실거래가 조회 중...</div>
        </div>
      ) : marketError ? (
        <StatusBanner icon="⚠️" title="조회 실패" desc={marketError} />
      ) : market && market.status === "ok" ? (
        <MarketSection market={market} />
      ) : market && STATUS_MSG[market.status] ? (
        <StatusBanner {...STATUS_MSG[market.status]} extra={market.message} />
      ) : null}

      {/* === 3. 수익성 메모 === */}
      <div className="bg-surface shadow-card rounded-xl p-5">
        <p className="text-sm font-semibold text-text-1 mb-2">수익성 분석 메모</p>
        <p className="text-xs text-text-4 mb-3">인근 시세, 예상 임대수익 등 투자 판단 메모를 기록하세요 (로컬 저장)</p>
        <textarea
          value={memo}
          onChange={(e) => setMemo(e.target.value)}
          placeholder="예) 인근 오피스텔 시세 약 ○억, 월세 ○만원 예상, 수익률 약 ○%..."
          rows={6}
          className="w-full text-xs border border-border-strong rounded-lg p-3 resize-none focus:outline-none focus:border-primary"
        />
        <div className="flex items-center justify-end gap-2 mt-2">
          {saved && <span className="text-xs text-ok-fg">저장됨</span>}
          <button
            onClick={saveMemo}
            className="text-xs bg-primary text-primary-fg px-3 py-1.5 rounded font-medium hover:bg-primary-hover"
          >
            저장
          </button>
        </div>
      </div>
    </div>
  );
}

function StatusBanner({ icon, title, desc, extra }: { icon: string; title: string; desc: string; extra?: string }) {
  return (
    <div className="bg-mid-bg rounded-xl p-5">
      <div className="flex items-start gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <p className="text-sm font-semibold text-mid-fg">{title}</p>
          <p className="text-xs text-mid-fg/90 mt-1">{desc}</p>
          {extra && <p className="text-xs text-mid-fg/70 mt-1">{extra}</p>}
        </div>
      </div>
    </div>
  );
}

function MarketSection({ market }: { market: MarketPriceResponse }) {
  const { summary, transactions, match_tier, match_count, comparison } = market;

  const unitPrices = transactions
    .map((tx) => tx.unit_price)
    .filter((p): p is number => p != null && p > 0);
  const minUnit = unitPrices.length > 0 ? Math.min(...unitPrices) : null;
  const maxUnit = unitPrices.length > 0 ? Math.max(...unitPrices) : null;

  const SQM_PER_PYEONG = 3.3058;
  const estimated = summary?.estimated_market_price_won ?? null;
  const avgUnitSqm = summary?.avg_unit_price ?? null;             // 만원/㎡
  const areaSqm = summary?.area_sqm ?? null;                      // ㎡ (온비드 bld_sqms)
  const avgUnitPyeong = avgUnitSqm != null ? avgUnitSqm * SQM_PER_PYEONG : null;
  const areaPyeong = areaSqm != null ? areaSqm / SQM_PER_PYEONG : null;
  const discountPct = comparison?.discount_from_market_pct ?? null;

  return (
    <>
      {estimated != null && (
        <div className="bg-primary/10 border border-primary/30 rounded-xl p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-semibold text-primary">실거래 기반 추정 시세</p>
            <span className="text-[10px] text-text-4 bg-surface px-2 py-0.5 rounded-full">
              {TIER_LABELS[match_tier ?? 0] ?? ""} / {match_count}건
            </span>
          </div>
          <p className="text-3xl font-bold text-primary tabular-nums">{fmtAmt(estimated)}</p>
          {avgUnitPyeong != null && areaPyeong != null && areaSqm != null && (
            <p className="text-xs text-text-3 mt-2 tabular-nums">
              평당 {avgUnitPyeong.toFixed(0)}만원 × {areaPyeong.toFixed(1)}평 ({areaSqm.toFixed(1)}㎡)
            </p>
          )}
          {discountPct != null && (
            <p className={`text-xs mt-1 font-medium tabular-nums ${discountPct > 0 ? "text-ok-fg" : "text-hot-fg"}`}>
              현재 최저입찰가는 추정 시세 대비 {discountPct > 0 ? "-" : "+"}{Math.abs(discountPct).toFixed(1)}% {discountPct > 0 ? "저렴" : "비쌈"}
            </p>
          )}
          <p className="text-[10px] text-text-4 mt-2">
            * 면적이 다른 같은 건물 거래는 평당가 기준으로 이 물건 면적에 맞춰 환산
          </p>
        </div>
      )}

      <div className="bg-surface shadow-card rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm font-semibold text-text-1">실거래 단가 통계</p>
          <span className="text-[10px] text-text-4 bg-surface-muted px-2 py-0.5 rounded-full">
            {TIER_LABELS[match_tier ?? 0] ?? ""} / {match_count}건
          </span>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="text-center">
            <p className="text-[11px] text-text-4">최저 평당가</p>
            <p className="text-base font-bold text-text-1 mt-0.5 tabular-nums">
              {minUnit != null ? `${minUnit.toFixed(1)}만/㎡` : "-"}
            </p>
          </div>
          <div className="text-center border-x border-border">
            <p className="text-[11px] text-text-4">평균 평당가</p>
            <p className="text-base font-bold text-primary mt-0.5 tabular-nums">
              {summary?.avg_unit_price != null ? `${summary.avg_unit_price.toFixed(1)}만/㎡` : "-"}
            </p>
          </div>
          <div className="text-center">
            <p className="text-[11px] text-text-4">최고 평당가</p>
            <p className="text-base font-bold text-text-1 mt-0.5 tabular-nums">
              {maxUnit != null ? `${maxUnit.toFixed(1)}만/㎡` : "-"}
            </p>
          </div>
        </div>

        {summary?.latest_deal && (
          <div className="mt-3 pt-3 border-t border-border">
            <p className="text-[10px] text-text-4">최근 거래: {summary.latest_deal}</p>
          </div>
        )}
      </div>

      {transactions.length > 0 && (
        <div className="bg-surface shadow-card rounded-xl p-5">
          <p className="text-sm font-semibold text-text-1 mb-3">인근 실거래 내역</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-4 border-b border-border">
                  <th className="text-left py-2 font-medium">계약일</th>
                  <th className="text-left py-2 font-medium">건물명</th>
                  <th className="text-right py-2 font-medium">전용면적</th>
                  <th className="text-right py-2 font-medium">거래금액</th>
                  <th className="text-right py-2 font-medium">층</th>
                  <th className="text-right py-2 font-medium">단가</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="py-2 text-text-3">{tx.deal_date}</td>
                    <td className="py-2 text-text-1 max-w-[120px] truncate">{tx.bldg_nm || "-"}</td>
                    <td className="py-2 text-right text-text-3 tabular-nums">
                      {tx.exclu_use_ar ? `${tx.exclu_use_ar.toFixed(1)}㎡` : "-"}
                    </td>
                    <td className="py-2 text-right font-medium text-text-1 tabular-nums">
                      {tx.deal_amount ? `${tx.deal_amount.toLocaleString()}만` : "-"}
                    </td>
                    <td className="py-2 text-right text-text-3 tabular-nums">{tx.floor || "-"}</td>
                    <td className="py-2 text-right text-text-4 tabular-nums">
                      {tx.unit_price ? `${tx.unit_price.toFixed(1)}` : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
