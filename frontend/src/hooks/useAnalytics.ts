"use client";

import { useState, useCallback } from "react";
import {
  fetchAnalyticsSummary,
  fetchAnalyticsTrends,
  fetchAnalyticsFlow,
  fetchAnalyticsDiscountByRegion,
} from "@/api/analytics";
import type {
  AnalyticsSummary,
  AnalyticsTrends,
  AnalyticsFlow,
  AnalyticsDiscount,
  TrendPeriod,
} from "@/types/analytics";

export function useSummary() {
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchAnalyticsSummary());
    } catch (e) {
      setError(e instanceof Error ? e.message : "요약 로드 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, error, load };
}

export function useTrends() {
  const [data, setData] = useState<AnalyticsTrends | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<TrendPeriod>("30d");

  const load = useCallback(async (p?: TrendPeriod) => {
    const target = p ?? period;
    setLoading(true);
    setError(null);
    setPeriod(target);
    try {
      setData(await fetchAnalyticsTrends(target));
    } catch (e) {
      setError(e instanceof Error ? e.message : "트렌드 로드 실패");
    } finally {
      setLoading(false);
    }
  }, [period]);

  return { data, loading, error, period, load };
}

export function useFlow() {
  const [data, setData] = useState<AnalyticsFlow | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<TrendPeriod>("30d");

  const load = useCallback(async (p?: TrendPeriod) => {
    const target = p ?? period;
    setLoading(true);
    setError(null);
    setPeriod(target);
    try {
      setData(await fetchAnalyticsFlow(target));
    } catch (e) {
      setError(e instanceof Error ? e.message : "유입/소진 로드 실패");
    } finally {
      setLoading(false);
    }
  }, [period]);

  return { data, loading, error, period, load };
}

export function useDiscountByRegion() {
  const [data, setData] = useState<AnalyticsDiscount | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchAnalyticsDiscountByRegion());
    } catch (e) {
      setError(e instanceof Error ? e.message : "할인율 로드 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, error, load };
}
