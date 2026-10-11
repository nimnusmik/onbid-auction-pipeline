import { API_BASE } from "@/utils/api";
import type { BidItem, Stats, ItemInfo, BidQual, TenantInfo, MarketPriceResponse } from "@/types";

export async function fetchItems(params: {
  ratio_min?: number;
  ratio_max?: number;
  price_min?: number;
  price_max?: number;
  usbd_min?: number;
  sd_nm?: string;
  usg_mcls?: string;
  usg_scls?: string;
  bookmarked?: number;
  pvct?: string;
  limit?: number;
}): Promise<BidItem[]> {
  const q = new URLSearchParams();
  if (params.ratio_min !== undefined) q.set("ratio_min", String(params.ratio_min));
  if (params.ratio_max !== undefined) q.set("ratio_max", String(params.ratio_max));
  if (params.price_min !== undefined) q.set("price_min", String(params.price_min));
  if (params.price_max !== undefined) q.set("price_max", String(params.price_max));
  if (params.usbd_min !== undefined && params.usbd_min > 0) q.set("usbd_min", String(params.usbd_min));
  if (params.sd_nm) q.set("sd_nm", params.sd_nm);
  if (params.usg_mcls) q.set("usg_mcls", params.usg_mcls);
  if (params.usg_scls) q.set("usg_scls", params.usg_scls);
  if (params.bookmarked !== null && params.bookmarked !== undefined) q.set("bookmarked", String(params.bookmarked));
  if (params.pvct) q.set("pvct", params.pvct);
  q.set("limit", String(params.limit ?? 200));
  const res = await fetch(`${API_BASE}/api/items?${q}`);
  if (!res.ok) throw new Error("items fetch failed");
  return res.json();
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) throw new Error("stats fetch failed");
  return res.json();
}

export async function fetchItem(id: string): Promise<BidItem> {
  const res = await fetch(`${API_BASE}/api/items/${id}`);
  if (!res.ok) throw new Error("item fetch failed");
  return res.json();
}

export async function fetchItemInfo(id: string): Promise<ItemInfo> {
  const res = await fetch(`${API_BASE}/api/items/${id}/info`);
  if (!res.ok) throw new Error("item info fetch failed");
  return res.json();
}

export async function fetchItemHistory(id: string): Promise<BidQual[]> {
  const res = await fetch(`${API_BASE}/api/items/${id}/history`);
  if (!res.ok) throw new Error("item history fetch failed");
  return res.json();
}

export async function fetchItemTenant(id: string): Promise<TenantInfo> {
  const res = await fetch(`${API_BASE}/api/items/${id}/tenant`);
  if (!res.ok) throw new Error("item tenant fetch failed");
  return res.json();
}

export async function toggleBookmark(id: string): Promise<{ cltr_mng_no: string; is_bookmarked: number }> {
  const res = await fetch(`${API_BASE}/api/items/${id}/bookmark`, { method: "POST" });
  if (!res.ok) throw new Error("bookmark toggle failed");
  return res.json();
}

export async function checkItem(id: string): Promise<{ alive: boolean; status: string }> {
  const res = await fetch(`${API_BASE}/api/items/${id}/check`);
  if (!res.ok) throw new Error("check failed");
  return res.json();
}

export async function refreshItem(id: string): Promise<{ item: BidItem; refreshed: { detail: boolean; bid: boolean } }> {
  const res = await fetch(`${API_BASE}/api/items/${id}/refresh`, { method: "POST" });
  if (!res.ok) throw new Error("refresh failed");
  return res.json();
}

export async function fetchMarketPrice(id: string): Promise<MarketPriceResponse> {
  const res = await fetch(`${API_BASE}/api/items/${id}/market-price`);
  if (!res.ok) throw new Error("market price fetch failed");
  return res.json();
}
