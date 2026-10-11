"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { PieLabelRenderProps } from "recharts";
import type { AnalyticsSummary } from "@/types/analytics";

const COLORS = [
  "var(--color-primary)",
  "var(--color-primary-hover)",
  "var(--color-ok-fg)",
  "var(--color-mid-fg)",
  "var(--color-hot-fg)",
  "#8b5cf6",
  "#14b8a6",
  "#ec4899",
];

interface Props {
  data: AnalyticsSummary["by_usage_type"];
}

export default function UsageDonutChart({ data }: Props) {
  return (
    <div className="bg-surface shadow-card rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-3">용도별 비율</h3>
      <ResponsiveContainer width="100%" height={250}>
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="usage_type"
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={90}
            label={(props: PieLabelRenderProps) => {
              const name = (props as PieLabelRenderProps & { usage_type?: string }).usage_type ?? "";
              const pct = typeof props.percent === "number" ? props.percent : 0;
              return `${name} ${(pct * 100).toFixed(0)}%`;
            }}
            labelLine={false}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(value, name) => [`${value}건`, name]} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
