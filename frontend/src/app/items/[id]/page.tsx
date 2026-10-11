// frontend/src/app/items/[id]/page.tsx
"use client";

import { use, useEffect, useState, type DragEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { fetchItem, toggleBookmark, refreshItem, checkItem } from "@/api";
import type { BidItem } from "@/types";
import HeroSection from "@/components/detail/HeroSection";
import TabPricing from "@/components/detail/TabPricing";
import TabRights from "@/components/detail/TabRights";
import TabField from "@/components/detail/TabField";

type TabKey = "pricing" | "rights" | "field";

const TAB_LABELS: Record<TabKey, string> = {
  rights: "⚖️ 유찰내역 & 권리 분석",
  pricing: "💰 가격 분석",
  field: "📍 현장 정보",
};
const DEFAULT_TAB_ORDER: TabKey[] = ["rights", "pricing", "field"];
const TAB_ORDER_KEY = "onbid:item-tab-order";

function loadTabOrder(): TabKey[] {
  if (typeof window === "undefined") return DEFAULT_TAB_ORDER;
  try {
    const raw = localStorage.getItem(TAB_ORDER_KEY);
    if (!raw) return DEFAULT_TAB_ORDER;
    const parsed = JSON.parse(raw) as TabKey[];
    const valid =
      Array.isArray(parsed) &&
      parsed.length === DEFAULT_TAB_ORDER.length &&
      DEFAULT_TAB_ORDER.every((k) => parsed.includes(k));
    return valid ? parsed : DEFAULT_TAB_ORDER;
  } catch {
    return DEFAULT_TAB_ORDER;
  }
}

export default function ItemDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const [item, setItem] = useState<BidItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [tabOrder, setTabOrder] = useState<TabKey[]>(DEFAULT_TAB_ORDER);
  const [activeTab, setActiveTab] = useState<TabKey>(DEFAULT_TAB_ORDER[0]);
  const [draggingTab, setDraggingTab] = useState<TabKey | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [closed, setClosed] = useState(false);

  useEffect(() => {
    // 1) 캐시된 DB 데이터 즉시 표시 (빠름)
    fetchItem(id)
      .then((data) => {
        setItem(data);
        checkItem(id)
          .then((res) => {
            if (!res.alive) setClosed(true);
          })
          .catch(() => {});
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));

    // 2) 백그라운드에서 온비드 API 호출해 fresh 데이터로 갱신
    //    detail/bid 서브테이블이 cron 으로는 거의 갱신되지 않아
    //    페이지 진입 시점에 한 번 더 호출하는 게 맞다.
    setRefreshing(true);
    refreshItem(id)
      .then((res) => setItem(res.item))
      .catch(() => {})
      .finally(() => setRefreshing(false));
  }, [id]);

  useEffect(() => {
    const stored = loadTabOrder();
    setTabOrder(stored);
    setActiveTab(stored[0]);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem(TAB_ORDER_KEY, JSON.stringify(tabOrder));
  }, [tabOrder]);

  function handleTabDragStart(e: DragEvent<HTMLDivElement>, key: TabKey) {
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", key);
    setDraggingTab(key);
  }

  function handleTabDragOver(e: DragEvent<HTMLDivElement>, overKey: TabKey) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (!draggingTab || draggingTab === overKey) return;
    setTabOrder((prev) => {
      const fromIdx = prev.indexOf(draggingTab);
      const toIdx = prev.indexOf(overKey);
      if (fromIdx < 0 || toIdx < 0) return prev;
      const next = [...prev];
      next.splice(fromIdx, 1);
      next.splice(toIdx, 0, draggingTab);
      return next;
    });
  }

  function handleTabDragEnd() {
    setDraggingTab(null);
  }

  async function handleBookmark() {
    if (!item) return;
    try {
      const res = await toggleBookmark(item.cltr_mng_no);
      setItem({ ...item, is_bookmarked: res.is_bookmarked });
    } catch {
      // ignore
    }
  }

  async function handleRefresh() {
    if (!item || refreshing) return;
    setRefreshing(true);
    try {
      const res = await refreshItem(item.cltr_mng_no);
      setItem(res.item);
    } catch {
      // ignore
    } finally {
      setRefreshing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-48px)]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-text-3">물건 정보를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (error || !item) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-48px)]">
        <div className="text-center">
          <p className="text-lg font-semibold text-text-1 mb-2">물건을 찾을 수 없습니다</p>
          <Link href="/" className="text-sm text-primary underline">
            목록으로 돌아가기
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-bg">
      {/* 상세 서브 네브 (루트 TopNav 아래) */}
      <div className="sticky top-12 z-20 bg-surface border-b border-border px-4 md:px-6 h-10 flex items-center gap-3">
        <button
          onClick={() => router.back()}
          className="text-sm text-primary hover:underline flex items-center gap-1"
        >
          ← 목록
        </button>
        <span className="text-border-strong">/</span>
        <span className="text-sm text-text-3 truncate flex-1 min-w-0">{item.onbid_cltr_nm}</span>
      </div>

      <div className="max-w-5xl mx-auto px-4 md:px-6 py-4 md:py-6 flex flex-col gap-4 md:gap-6">
        {/* 종료 / 수의계약 배너 */}
        {closed && item.pvct_trgt_yn === "Y" && (
          <div className="bg-primary-subtle border border-primary/20 rounded-lg px-5 py-3 flex items-center gap-3">
            <span className="text-lg">📋</span>
            <div>
              <p className="text-sm font-semibold text-primary-hover">수의계약 가능 물건입니다</p>
              <p className="text-xs text-primary mt-0.5">정규 입찰은 종료되었으나, 수의계약으로 매수할 수 있습니다.</p>
            </div>
          </div>
        )}
        {closed && item.pvct_trgt_yn !== "Y" && (
          <div className="bg-hot-bg border border-hot-fg/20 rounded-lg px-5 py-3 flex items-center gap-3">
            <span className="text-lg">⚠️</span>
            <div>
              <p className="text-sm font-semibold text-hot-fg">이 물건은 종료되었습니다</p>
              <p className="text-xs text-hot-fg/80 mt-0.5">온비드에서 낙찰·취소 처리되어 더 이상 입찰할 수 없습니다.</p>
            </div>
          </div>
        )}

        {/* Hero */}
        <HeroSection item={item} onBookmark={handleBookmark} onRefresh={handleRefresh} refreshing={refreshing} />

        {/* 탭 */}
        <div className="bg-surface shadow-card rounded-xl overflow-hidden">
          <div className="flex border-b border-border">
            {tabOrder.map((key) => {
              const isActive = activeTab === key;
              const isDragging = draggingTab === key;
              return (
                <div
                  key={key}
                  role="tab"
                  tabIndex={0}
                  aria-selected={isActive}
                  draggable
                  onDragStart={(e) => handleTabDragStart(e, key)}
                  onDragOver={(e) => handleTabDragOver(e, key)}
                  onDragEnd={handleTabDragEnd}
                  onClick={() => setActiveTab(key)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setActiveTab(key);
                    }
                  }}
                  title="드래그하여 탭 순서를 바꿀 수 있습니다"
                  className={`flex-1 px-3 py-3 text-sm text-center whitespace-nowrap transition-colors cursor-grab active:cursor-grabbing select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                    isActive
                      ? "border-b-2 border-primary text-primary font-semibold"
                      : "text-text-3 hover:text-text-1 hover:bg-surface-muted"
                  } ${isDragging ? "opacity-50" : ""}`}
                >
                  {TAB_LABELS[key]}
                </div>
              );
            })}
          </div>

          <div className="p-4 md:p-6">
            {activeTab === "pricing" && <TabPricing item={item} />}
            {activeTab === "rights" && <TabRights item={item} />}
            {activeTab === "field" && <TabField item={item} />}
          </div>
        </div>
      </div>
    </div>
  );
}
