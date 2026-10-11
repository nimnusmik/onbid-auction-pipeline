"use client";

import { useState, useCallback } from "react";
import { fetchItems } from "@/api";
import type { BidItem, FilterState } from "@/types";

const DEFAULT_FILTER: FilterState = {
  ratio_min: 0,
  ratio_max: 100,
  price_min: null,
  price_max: null,
  usbd_min: 0,
  sd_nm: "",
  usg_mcls: "",
  usg_scls: "",
  bookmarked: null,
  pvct: null,
  sort: { key: "ratio_pct", dir: "asc" },
};

export function useItems() {
  const [items, setItems] = useState<BidItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterState>(DEFAULT_FILTER);

  const load = useCallback(async (f: FilterState) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchItems({
        ratio_min: f.ratio_min ?? undefined,
        ratio_max: f.ratio_max,
        price_min: f.price_min ?? undefined,
        price_max: f.price_max ?? undefined,
        usbd_min: f.usbd_min,
        sd_nm: f.sd_nm,
        usg_mcls: f.usg_mcls || undefined,
        usg_scls: f.usg_scls || undefined,
        bookmarked: f.bookmarked ?? undefined,
        pvct: f.pvct ?? undefined,
        limit: 9999,
      });
      setItems(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "데이터 로드 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  const sorted = [...items].sort((a, b) => {
    const dir = filter.sort.dir === "asc" ? 1 : -1;
    switch (filter.sort.key) {
      case "apsl_evl_amt":
        return dir * ((a.apsl_evl_amt ?? 0) - (b.apsl_evl_amt ?? 0));
      case "lowst_bid_prc":
        return dir * ((a.lowst_bid_prc ?? 0) - (b.lowst_bid_prc ?? 0));
      case "ratio_pct":
        return dir * (a.ratio_pct - b.ratio_pct);
      case "start_ratio_pct":
        // null 은 정렬 끝(가장 큰 값)으로 — asc 면 마지막, desc 면 처음에서 무시
        return dir * ((a.start_ratio_pct ?? 1e9) - (b.start_ratio_pct ?? 1e9));
      case "usbd_nft":
        return dir * (a.usbd_nft - b.usbd_nft);
      case "deadline":
        return dir * (new Date(a.cltr_bid_end_dt).getTime() - new Date(b.cltr_bid_end_dt).getTime());
    }
  });

  return { items: sorted, loading, error, filter, setFilter, load };
}
