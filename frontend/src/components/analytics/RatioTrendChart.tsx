"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { AnalyticsTrends } from "@/types/analytics";

interface Props {
  data: AnalyticsTrends | null;
  loading: boolean;
}

export default function RatioTrendChart({ data, loading }: Props) {
  const chartData = data?.data ?? [];

  return (
    <div className="bg-surface shadow-card rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-3">평균 감정가율 추이</h3>
      {loading ? (
        <div className="h-64 flex items-center justify-center text-text-4">로딩 중...</div>
      ) : chartData.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-text-4">
          데이터가 아직 충분하지 않습니다.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-strong)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickFormatter={(d) => String(d).slice(5)}
            />
            <YAxis domain={["auto", "auto"]} unit="%" tick={{ fontSize: 11 }} />
            <Tooltip
              labelFormatter={(d) => String(d)}
              formatter={(value) => [`${value}%`, "평균 감정가율"]}
            />
            <Line
              type="monotone"
              dataKey="avg_ratio"
              stroke="var(--color-hot-fg)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
