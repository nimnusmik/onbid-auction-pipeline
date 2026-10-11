"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useItems } from "@/hooks/useItems";
import BookmarkCard from "@/components/BookmarkCard";

export default function BookmarkPage() {
  const { items, loading, error, filter, setFilter, load } = useItems();

  useEffect(() => {
    const bookmarkFilter = { ...filter, bookmarked: 1 };
    setFilter(bookmarkFilter);
    load(bookmarkFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="max-w-7xl mx-auto px-4 md:px-6 py-6">
      {/* 헤더 */}
      <div className="flex items-end justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-text-1">관심 물건</h1>
          <p className="text-xs text-text-4 mt-0.5">찜해둔 물건을 한눈에</p>
        </div>
        {!loading && !error && (
          <span className="text-sm text-text-3 tabular-nums">
            {items.length}건
          </span>
        )}
      </div>

      {/* 에러 */}
      {error && (
        <div className="bg-hot-bg rounded-lg px-4 py-3 text-sm text-hot-fg">
          데이터를 불러오지 못했습니다: {error}
        </div>
      )}

      {/* 로딩 */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-text-4">관심 물건을 불러오는 중...</p>
          </div>
        </div>
      )}

      {/* 빈 상태 */}
      {!loading && !error && items.length === 0 && (
        <div className="bg-surface shadow-card rounded-xl py-16 px-6 flex flex-col items-center gap-3 text-center">
          <span className="text-5xl" aria-hidden>⭐</span>
          <div className="text-base font-semibold text-text-1">
            아직 찜한 물건이 없습니다
          </div>
          <div className="text-sm text-text-4">
            물건 상세 페이지에서 별 아이콘을 눌러 관심 물건을 추가해보세요
          </div>
          <Link
            href="/"
            className="mt-2 inline-block bg-primary text-primary-fg rounded-md px-4 py-2 text-sm font-medium hover:opacity-90"
          >
            Overview로 이동
          </Link>
        </div>
      )}

      {/* 카드 그리드 */}
      {!loading && !error && items.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {items.map((item) => (
            <BookmarkCard key={item.cltr_mng_no} item={item} />
          ))}
        </div>
      )}
    </main>
  );
}
