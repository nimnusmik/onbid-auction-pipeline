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
  data: AnalyticsSummary["ratio_distribution"];
}

export default function RatioDistributionChart({ data }: Props) {
  return (
    <div className="bg-surface shadow-card rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-3">감정가율 분포</h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data}>
          <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
          <YAxis />
          <Tooltip formatter={(value) => [`${value}건`, "물건 수"]} />
          <Bar dataKey="count" fill="var(--color-primary-hover)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
