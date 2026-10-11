"use client";

import type { AnalyticsSummary, AnalyticsDiscount } from "@/types/analytics";
import type { AnalyticsFilterState } from "./AnalyticsFilters";
import RegionCountChart from "./RegionCountChart";
import UsageDonutChart from "./UsageDonutChart";
import RatioDistributionChart from "./RatioDistributionChart";
import DiscountByRegionChart from "./DiscountByRegionChart";

interface Props {
  filter: AnalyticsFilterState;
  summary: AnalyticsSummary | null;
  discount: AnalyticsDiscount | null;
}

export default function SegmentExplorer({ filter, summary, discount }: Props) {
  if (!summary) {
    return (
      <section className="space-y-4">
        <h2 className="text-lg font-bold">세부 분포</h2>
        <div className="h-32 flex items-center justify-center text-text-4">로딩 중...</div>
      </section>
    );
  }

  // 필터 적용
  const byRegion =
    filter.regions.length > 0
      ? summary.by_region.filter((r) => filter.regions.includes(r.region))
      : summary.by_region;
  const byUsage =
    filter.usageTypes.length > 0
      ? summary.by_usage_type.filter((u) => filter.usageTypes.includes(u.usage_type))
      : summary.by_usage_type;

  return (
    <section className="space-y-6">
      <h2 className="text-lg font-bold">세부 분포</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <RegionCountChart data={byRegion} />
        <RatioDistributionChart data={summary.ratio_distribution} />
        <UsageDonutChart data={byUsage} />
      </div>

      <DiscountByRegionChart data={discount} highlightRegions={filter.regions} />
    </section>
  );
}
