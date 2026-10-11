"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useSummary } from "@/hooks/useAnalytics";

export default function SummaryStrip() {
  const { data, loading, load } = useSummary();

  useEffect(() => {
    load();
  }, [load]);

  if (loading || !data) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4 animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-20 bg-border-strong rounded-lg" />
        ))}
      </div>
    );
  }

  const topRegion = data.by_region[0];
  const topScored = data.top_scored[0];

  const avgRatio =
    data.by_region.length > 0
      ? (
          data.by_region.reduce((s, r) => s + r.avg_ratio * r.count, 0) /
          data.by_region.reduce((s, r) => s + r.count, 0)
        ).toFixed(1)
      : "-";

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
      <div className="bg-surface shadow-card rounded-lg p-4">
        <p className="text-xs text-text-3 mb-1">전체 물건</p>
        <p className="text-2xl font-bold text-text-1 tracking-tight tabular-nums">
          {data.total_items.toLocaleString()}
          {data.total_delta != null && (
            <span
              className={`text-sm ml-2 font-semibold ${
                data.total_delta >= 0 ? "text-urgent" : "text-primary"
              }`}
            >
              {data.total_delta >= 0 ? "▲" : "▼"}
              {Math.abs(data.total_delta)}
            </span>
          )}
        </p>
      </div>

      <div className="bg-surface shadow-card rounded-lg p-4">
        <p className="text-xs text-text-3 mb-1">평균 감정가율</p>
        <p className="text-2xl font-bold text-text-1 tracking-tight tabular-nums">
          {avgRatio}%
        </p>
      </div>

      <div className="bg-surface shadow-card rounded-lg p-4">
        <p className="text-xs text-text-3 mb-1">최다 지역</p>
        <p className="text-lg font-bold text-text-1">
          {topRegion ? topRegion.region : "-"}
        </p>
        {topRegion && (
          <p className="text-xs text-text-4 mt-0.5">{topRegion.count}건</p>
        )}
      </div>

      <div className="bg-surface shadow-card rounded-lg p-4">
        <p className="text-xs text-text-3 mb-1">투자 1순위</p>
        {topScored ? (
          <Link
            href={`/items/${topScored.cltr_mng_no}`}
            className="text-sm font-bold text-primary hover:underline line-clamp-1"
          >
            {topScored.name}
          </Link>
        ) : (
          <p className="text-lg font-bold text-text-4">-</p>
        )}
        {topScored && (
          <p className="text-xs text-text-4 mt-0.5">
            점수 {topScored.score} · {topScored.ratio_pct}%
          </p>
        )}
      </div>
    </div>
  );
}
