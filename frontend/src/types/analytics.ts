export interface AnalyticsSummary {
  total_items: number;
  total_delta: number | null;
  avg_ratio_pct: number | null;
  by_region: { region: string; count: number; avg_ratio: number }[];
  by_usage_type: { usage_type: string; count: number; avg_ratio: number }[];
  ratio_distribution: { bucket: string; count: number }[];
  top_scored: {
    cltr_mng_no: string;
    name: string;
    score: number;
    ratio_pct: number;
    region: string;
  }[];
}

export interface TrendDataPoint {
  date: string;
  total_count: number;
  avg_ratio: number | null;
  by_region: {
    region: string;
    usage_type: string;
    count: number;
    avg_ratio: number | null;
  }[];
}

export interface AnalyticsTrends {
  period: string;
  data: TrendDataPoint[];
}

export interface FlowDataPoint {
  date: string;
  new_count: number;
  closed_count: number;
  total_count: number;
}

export interface AnalyticsFlow {
  period: string;
  data: FlowDataPoint[];
}

export interface DiscountByRegion {
  region: string;
  bid_item_count: number;
  molit_deal_count: number;
  bid_avg_per_sqm: number | null;
  molit_avg_per_sqm: number | null;
  discount_pct: number | null;
}

export interface AnalyticsDiscount {
  data: DiscountByRegion[];
}

export type TrendPeriod = "7d" | "30d" | "90d";
