"use client";

import { useEffect, useState } from "react";
import { fetchStats } from "@/api";
import type { Stats } from "@/types";

export default function StatsBar() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() => setError(true));
  }, []);

  if (error) return null;
  if (!stats) {
    return <div className="h-10 bg-surface shadow-card rounded-lg animate-pulse" />;
  }

  return (
    <div className="flex items-center gap-3 bg-surface shadow-card rounded-lg px-4 py-2 text-sm flex-wrap">
      <span className="text-text-3 text-xs">통계</span>
      <span className="inline-flex items-center gap-1 bg-hot-bg text-hot-fg rounded-full px-2 py-0.5 text-xs font-medium">
        60% 미만 <span className="font-bold">{stats.ratio_below60}</span>건
      </span>
      <span className="inline-flex items-center gap-1 bg-mid-bg text-mid-fg rounded-full px-2 py-0.5 text-xs font-medium">
        60~70% <span className="font-bold">{stats.ratio_60_70}</span>건
      </span>
      <span className="inline-flex items-center gap-1 bg-primary-subtle text-primary rounded-full px-2 py-0.5 text-xs font-medium">
        전체 <span className="font-bold">{stats.total}</span>건
      </span>
      <span className="ml-auto text-xs text-text-3">
        수의계약 가능 <span className="font-semibold text-primary">{stats.pvct_count}</span>건
      </span>
    </div>
  );
}
