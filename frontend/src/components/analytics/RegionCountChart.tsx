"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { AnalyticsSummary } from "@/types/analytics";

interface Props {
  data: AnalyticsSummary["by_region"];
}

export default function RegionCountChart({ data }: Props) {
  return (
    <div className="bg-surface shadow-card rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-3">지역별 물건 수</h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} layout="vertical" margin={{ left: 40 }}>
          <XAxis type="number" />
          <YAxis type="category" dataKey="region" width={50} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value) => [`${value}건`, "물건 수"]} />
          <Bar dataKey="count" fill="var(--color-primary)" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
