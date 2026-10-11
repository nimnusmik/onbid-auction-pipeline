"use client";

import { Suspense, useEffect } from "react";
import FilterPanel from "@/components/FilterPanel";
import SummaryStrip from "@/components/SummaryStrip";
import ItemTable from "@/components/ItemTable";
import PageWithSidebar from "@/components/layout/PageWithSidebar";
import { useItems } from "@/hooks/useItems";

export default function HomePage() {
  const { items, loading, error, filter, setFilter, load } = useItems();

  useEffect(() => {
    load(filter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSearch(f: typeof filter) {
    setFilter(f);
    load(f);
  }

  return (
    <PageWithSidebar
      sidebar={<FilterPanel filter={filter} onSearch={handleSearch} />}
    >
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-text-1">온비드 공매 대시보드</h1>
          <p className="text-xs text-text-4 mt-0.5">한국자산관리공사 공매 물건 투자 분석</p>
        </div>
      </div>

      <SummaryStrip />

      {/* 에러 */}
      {error && (
        <div className="bg-hot-bg rounded-lg px-4 py-3 text-sm text-hot-fg">
          데이터를 불러오지 못했습니다: {error}
        </div>
      )}

      {/* 로딩 */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-text-4">물건 목록을 불러오는 중...</p>
          </div>
        </div>
      ) : (
        <Suspense>
          <ItemTable
            items={items}
            filter={filter}
            onSortChange={(sort) => setFilter({ ...filter, sort })}
          />
        </Suspense>
      )}
    </PageWithSidebar>
  );
}
