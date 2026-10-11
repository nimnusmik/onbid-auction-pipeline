"use client";

import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { AnalyticsFlow } from "@/types/analytics";

interface Props {
  data: AnalyticsFlow | null;
  loading: boolean;
}

export default function FlowChart({ data, loading }: Props) {
  const chartData = data?.data ?? [];

  return (
    <div className="bg-surface shadow-card rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-3">유입/소진 추이</h3>
      {loading ? (
        <div className="h-64 flex items-center justify-center text-text-4">로딩 중...</div>
      ) : chartData.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-text-4">
          데이터가 아직 충분하지 않습니다.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={250}>
          <ComposedChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-strong)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickFormatter={(d) => String(d).slice(5)}
            />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
              labelFormatter={(d) => String(d)}
              formatter={(value, name) => [`${value}건`, name]}
            />
            <Legend wrapperStyle={{ fontSize: "12px" }} />
            <Bar dataKey="new_count" name="신규 유입" fill="var(--color-primary)" radius={[3, 3, 0, 0]} />
            <Bar dataKey="closed_count" name="마감 소진" fill="var(--color-mid-fg)" radius={[3, 3, 0, 0]} />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
