"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { AnalyticsDiscount } from "@/types/analytics";

interface Props {
  data: AnalyticsDiscount | null;
  highlightRegions?: string[];
}

export default function DiscountByRegionChart({ data, highlightRegions }: Props) {
  const rows = (data?.data ?? []).filter((r) => r.discount_pct !== null);

  if (rows.length === 0) {
    return (
      <div className="bg-surface shadow-card rounded-lg p-4">
        <h3 className="text-sm font-semibold mb-3">지역별 시세 대비 할인율</h3>
        <div className="h-64 flex items-center justify-center text-text-4">
          할인율 데이터를 계산할 수 있는 지역이 없습니다.
        </div>
      </div>
    );
  }

  return (
    <div className="bg-surface shadow-card rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-3">지역별 시세 대비 할인율</h3>
      <p className="text-xs text-text-4 mb-3">
        BID 평균 m²당 최저입찰가 ÷ MOLIT 평균 단가. 음수는 시세보다 비쌈.
      </p>
      <ResponsiveContainer width="100%" height={Math.max(200, rows.length * 36)}>
        <BarChart data={rows} layout="vertical" margin={{ left: 60 }}>
          <XAxis type="number" unit="%" tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="region" width={70} tick={{ fontSize: 12 }} />
          <Tooltip
            formatter={(value, name, props) => {
              const row = props.payload;
              return [
                `-${value}% (표본: BID ${row.bid_item_count}건 / MOLIT ${row.molit_deal_count}건)`,
                "할인율",
              ];
            }}
          />
          <Bar dataKey="discount_pct" radius={[0, 4, 4, 0]}>
            {rows.map((r, i) => {
              const isHighlight =
                !highlightRegions || highlightRegions.length === 0
                  ? true
                  : highlightRegions.includes(r.region);
              return (
                <Cell
                  key={i}
                  fill={isHighlight ? "var(--color-ok-fg)" : "var(--color-border-strong)"}
                />
              );
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
