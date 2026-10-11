import { API_BASE } from "@/utils/api";
import type {
  AnalyticsSummary,
  AnalyticsTrends,
  AnalyticsFlow,
  AnalyticsDiscount,
  TrendPeriod,
} from "@/types/analytics";

export async function fetchAnalyticsSummary(): Promise<AnalyticsSummary> {
  const res = await fetch(`${API_BASE}/api/analytics/summary`);
  if (!res.ok) throw new Error("분석 요약 데이터 로드 실패");
  return res.json();
}

export async function fetchAnalyticsTrends(
  period: TrendPeriod = "30d"
): Promise<AnalyticsTrends> {
  const res = await fetch(`${API_BASE}/api/analytics/trends?period=${period}`);
  if (!res.ok) throw new Error("트렌드 데이터 로드 실패");
  return res.json();
}

export async function fetchAnalyticsFlow(
  period: TrendPeriod = "30d"
): Promise<AnalyticsFlow> {
  const res = await fetch(`${API_BASE}/api/analytics/flow?period=${period}`);
  if (!res.ok) throw new Error("유입/소진 데이터 로드 실패");
  return res.json();
}

export async function fetchAnalyticsDiscountByRegion(): Promise<AnalyticsDiscount> {
  const res = await fetch(`${API_BASE}/api/analytics/discount-by-region`);
  if (!res.ok) throw new Error("지역별 할인율 데이터 로드 실패");
  return res.json();
}
