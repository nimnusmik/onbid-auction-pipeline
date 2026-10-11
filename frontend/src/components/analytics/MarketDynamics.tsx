"use client";

import type {
  AnalyticsFlow,
  AnalyticsTrends,
  TrendPeriod,
} from "@/types/analytics";

const PERIODS: { value: TrendPeriod; label: string }[] = [
  { value: "7d", label: "7일" },
  { value: "30d", label: "30일" },
  { value: "90d", label: "90일" },
];

interface Props {
  flow: AnalyticsFlow | null;
  trends: AnalyticsTrends | null;
  period: TrendPeriod;
  flowLoading: boolean;
  trendsLoading: boolean;
  onPeriodChange: (p: TrendPeriod) => void;
}

export default function MarketDynamics({
  period,
  onPeriodChange,
}: Props) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">시장 동향</h2>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => onPeriodChange(p.value)}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                period === p.value
                  ? "bg-primary text-primary-fg"
                  : "bg-surface-muted text-text-2 hover:bg-border"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
