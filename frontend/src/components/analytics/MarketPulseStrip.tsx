"use client";

import Link from "next/link";
import type {
  AnalyticsSummary,
  AnalyticsFlow,
  AnalyticsDiscount,
} from "@/types/analytics";
import type { AnalyticsFilterState } from "./AnalyticsFilters";

interface Props {
  filter: AnalyticsFilterState;
  summary: AnalyticsSummary | null;
  flow: AnalyticsFlow | null;
  discount: AnalyticsDiscount | null;
}

export default function MarketPulseStrip({ filter, summary, flow, discount }: Props) {
  // 필터 적용 헬퍼: 지역/용도 필터에 따라 summary/discount의 일부 값만 노출
  // 현재 스펙: 필터 적용 시 Pulse 카드는 **필터 지역의 평균**을 반영 (프론트 재계산)

  // 1. 신규 유입 (최근 7일) — flow.data 마지막 7개 new_count 합산
  const last7 = flow?.data.slice(-7) ?? [];
  const newInflow = last7.reduce((s, d) => s + d.new_count, 0);
  const prev7 = flow?.data.slice(-14, -7) ?? [];
  const prevInflow = prev7.reduce((s, d) => s + d.new_count, 0);
  const inflowDelta = newInflow - prevInflow;

  // 2. 마감 임박 — summary에서는 직접 계산 어려움. 일단 "-"로 placeholder
  //    향후 홈 items API 재사용 or 백엔드 추가 엔드포인트 필요
  const upcomingDeadline: number | null = null;

  // 3. 평균 감정가율 (필터 적용)
  let avgRatio: number | null = summary?.avg_ratio_pct ?? null;
  if (filter.regions.length > 0 && summary?.by_region) {
    const rows = summary.by_region.filter((r) => filter.regions.includes(r.region));
    if (rows.length > 0) {
      const weighted = rows.reduce((s, r) => s + r.avg_ratio * r.count, 0);
      const totalCount = rows.reduce((s, r) => s + r.count, 0);
      avgRatio = totalCount > 0 ? Math.round((weighted / totalCount) * 10) / 10 : null;
    }
  }

  // 4. 시세 대비 평균 할인율 (필터 적용)
  let avgDiscount: number | null = null;
  let discountSample = 0;
  if (discount?.data) {
    let rows = discount.data.filter((d) => d.discount_pct !== null);
    if (filter.regions.length > 0) {
      rows = rows.filter((d) => filter.regions.includes(d.region));
    }
    if (rows.length > 0) {
      const weighted = rows.reduce((s, r) => s + (r.discount_pct ?? 0) * r.bid_item_count, 0);
      const totalCount = rows.reduce((s, r) => s + r.bid_item_count, 0);
      avgDiscount = totalCount > 0 ? Math.round((weighted / totalCount) * 10) / 10 : null;
      discountSample = totalCount;
    }
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <PulseCard
        icon="📥"
        label="신규 유입"
        sub="최근 7일"
        value={`${newInflow}건`}
        delta={inflowDelta === 0 ? null : `${inflowDelta > 0 ? "▲" : "▼"} ${Math.abs(inflowDelta)} (전주 대비)`}
        deltaClass={inflowDelta > 0 ? "text-ok-fg" : inflowDelta < 0 ? "text-hot-fg" : ""}
        href="/?sort=newest"
      />
      <PulseCard
        icon="⏰"
        label="마감 임박"
        sub="D-7 이내"
        value={upcomingDeadline !== null ? `${upcomingDeadline}건` : "-"}
        delta={null}
        href="/?sort=deadline"
      />
      <PulseCard
        icon="💰"
        label="평균 감정가율"
        sub={filter.regions.length > 0 ? "선택 지역" : "활성 물건 전체"}
        value={avgRatio !== null ? `${avgRatio}%` : "-"}
        delta={null}
      />
      <PulseCard
        icon="📊"
        label="시세 대비 평균 할인율"
        sub={discountSample > 0 ? `표본 ${discountSample}건` : "-"}
        value={avgDiscount !== null ? `-${avgDiscount}%` : "-"}
        delta={null}
      />
    </div>
  );
}

function PulseCard({
  icon,
  label,
  sub,
  value,
  delta,
  deltaClass,
  href,
}: {
  icon: string;
  label: string;
  sub: string;
  value: string;
  delta: string | null;
  deltaClass?: string;
  href?: string;
}) {
  const content = (
    <div className="bg-surface shadow-card rounded-xl p-4 h-full hover:shadow-card-hover transition-shadow">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">{icon}</span>
        <div>
          <p className="text-xs font-semibold text-text-2">{label}</p>
          <p className="text-[10px] text-text-4">{sub}</p>
        </div>
      </div>
      <p className="text-2xl font-bold text-text-1 tabular-nums tracking-tight">{value}</p>
      {delta && <p className={`text-[11px] mt-1 tabular-nums ${deltaClass ?? "text-text-3"}`}>{delta}</p>}
    </div>
  );
  return href ? <Link href={href}>{content}</Link> : content;
}
