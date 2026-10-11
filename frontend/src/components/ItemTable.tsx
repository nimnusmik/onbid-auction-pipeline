"use client";

import { useState, useEffect, useRef, type DragEvent, type ReactNode } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { BidItem, FilterState, SortKey } from "@/types";
import { fmtAmt, daysLeft, sqmsToPyeong } from "@/utils/format";
import { isNewToday } from "@/utils/itemFlags";
import RatioPill from "@/components/ui/RatioPill";
import DeadlineLabel from "@/components/ui/DeadlineLabel";
import ExternalSiteMenu from "@/components/ui/ExternalSiteMenu";

const PAGE_SIZE = 50;

type ColumnKey =
  | "loc"
  | "usg"
  | "evl"
  | "lowst"
  | "ratio"
  | "startRatio"
  | "round"
  | "fail"
  | "deadline";

type Align = "left" | "right" | "center";

interface ColumnDef {
  key: ColumnKey;
  label: string;
  sortKey?: SortKey;
  align?: Align;
  cell: (item: BidItem) => ReactNode;
}

const COLUMNS: Record<ColumnKey, ColumnDef> = {
  loc: {
    key: "loc",
    label: "소재지",
    align: "left",
    cell: (item) => (
      <>
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-sm text-text-1 font-medium">{item.onbid_cltr_nm}</span>
          {isNewToday(item.first_collected_at) && (
            <span className="text-[10px] bg-new text-primary-fg rounded-sm px-1.5 py-0.5 font-bold">
              NEW
            </span>
          )}
          {item.market_match_tier != null && (
            <span
              title={
                item.market_match_tier === 0
                  ? "같은 지번 실거래 매칭"
                  : "같은 건물명 실거래 매칭"
              }
              className="text-[10px] bg-ok-bg text-ok-fg rounded-sm px-1.5 py-0.5 font-bold"
            >
              실거래 {item.market_match_count ?? 0}건
            </span>
          )}
        </div>
        <div className="text-xs text-text-3 mt-0.5">
          {item.cltr_usg_scls_nm} / {sqmsToPyeong(item.bld_sqms)}
        </div>
      </>
    ),
  },
  usg: {
    key: "usg",
    label: "용도",
    align: "left",
    cell: (item) => (
      <>
        <div className="text-xs text-text-3">{item.cltr_usg_mcls_nm}</div>
        <div className="text-xs text-text-4 mt-0.5">{item.cltr_usg_scls_nm}</div>
      </>
    ),
  },
  evl: {
    key: "evl",
    label: "감정가",
    sortKey: "apsl_evl_amt",
    align: "right",
    cell: (item) => (
      <span className="text-sm text-text-2 tabular-nums">{fmtAmt(item.apsl_evl_amt)}</span>
    ),
  },
  lowst: {
    key: "lowst",
    label: "최저입찰가",
    sortKey: "lowst_bid_prc",
    align: "right",
    cell: (item) => (
      <span className="text-sm font-medium text-primary tabular-nums">
        {fmtAmt(item.lowst_bid_prc)}
      </span>
    ),
  },
  ratio: {
    key: "ratio",
    label: "감정가 대비",
    sortKey: "ratio_pct",
    align: "right",
    cell: (item) => <RatioPill ratio={item.ratio_pct} />,
  },
  startRatio: {
    key: "startRatio",
    label: "시작가 대비",
    sortKey: "start_ratio_pct",
    align: "right",
    cell: (item) =>
      item.start_ratio_pct != null ? (
        <span className="text-sm text-hot-fg font-medium tabular-nums">
          -{(100 - item.start_ratio_pct).toFixed(1)}%
        </span>
      ) : (
        <span className="text-sm text-text-4 tabular-nums">-</span>
      ),
  },
  round: {
    key: "round",
    label: "회차",
    align: "center",
    cell: (item) => (
      <span className="text-sm text-text-2 tabular-nums">{Number(item.pbct_nsq)}회차</span>
    ),
  },
  fail: {
    key: "fail",
    label: "유찰",
    sortKey: "usbd_nft",
    align: "center",
    cell: (item) =>
      item.usbd_nft > 0 ? (
        <span className="bg-mid-bg text-mid-fg rounded px-1.5 py-0.5 text-xs font-semibold">
          {item.usbd_nft}회
        </span>
      ) : (
        <span className="text-sm text-text-4">-</span>
      ),
  },
  deadline: {
    key: "deadline",
    label: "마감일",
    sortKey: "deadline",
    align: "center",
    cell: (item) => {
      const dl = daysLeft(item.cltr_bid_end_dt);
      const pvct = dl < 0 && item.pvct_trgt_yn === "Y";
      return <DeadlineLabel dt={item.cltr_bid_end_dt} pvct={pvct} />;
    },
  },
};

const DEFAULT_COLUMN_ORDER: ColumnKey[] = [
  "loc",
  "usg",
  "evl",
  "lowst",
  "ratio",
  "startRatio",
  "round",
  "fail",
  "deadline",
];
const COLUMN_ORDER_KEY = "onbid:list-column-order";

function loadColumnOrder(): ColumnKey[] {
  if (typeof window === "undefined") return DEFAULT_COLUMN_ORDER;
  try {
    const raw = localStorage.getItem(COLUMN_ORDER_KEY);
    if (!raw) return DEFAULT_COLUMN_ORDER;
    const parsed = JSON.parse(raw) as ColumnKey[];
    const valid =
      Array.isArray(parsed) &&
      parsed.length === DEFAULT_COLUMN_ORDER.length &&
      DEFAULT_COLUMN_ORDER.every((k) => parsed.includes(k));
    return valid ? parsed : DEFAULT_COLUMN_ORDER;
  } catch {
    return DEFAULT_COLUMN_ORDER;
  }
}

function alignClass(align: Align | undefined): string {
  switch (align) {
    case "left":
      return "text-left";
    case "center":
      return "text-center";
    default:
      return "text-right";
  }
}

interface Props {
  items: BidItem[];
  filter: FilterState;
  onSortChange: (sort: FilterState["sort"]) => void;
}

export default function ItemTable({ items, filter, onSortChange }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [page, setPage] = useState(() => Number(searchParams.get("page")) || 1);
  const prevSort = useRef(filter.sort);

  const [columnOrder, setColumnOrder] = useState<ColumnKey[]>(DEFAULT_COLUMN_ORDER);
  const [draggingCol, setDraggingCol] = useState<ColumnKey | null>(null);

  useEffect(() => {
    setColumnOrder(loadColumnOrder());
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem(COLUMN_ORDER_KEY, JSON.stringify(columnOrder));
  }, [columnOrder]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlPage = Number(params.get("page")) || 1;
    if (urlPage === page) return;
    if (page <= 1) params.delete("page");
    else params.set("page", String(page));
    const qs = params.toString();
    router.replace(qs ? `?${qs}` : "/", { scroll: false });
  }, [page, router]);

  useEffect(() => {
    if (prevSort.current !== filter.sort) {
      prevSort.current = filter.sort;
      setPage(1);
    }
  }, [filter.sort]);

  // 마감 지나고 수의계약도 아닌 물건은 숨김
  const visibleItems = items.filter((item) => {
    const dl = daysLeft(item.cltr_bid_end_dt);
    return !(dl < 0 && item.pvct_trgt_yn !== "Y");
  });

  const totalPages = Math.ceil(visibleItems.length / PAGE_SIZE);
  const pageItems = visibleItems.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const toggleSort = (key: SortKey) => {
    const nextDir = filter.sort.key === key && filter.sort.dir === "asc" ? "desc" : "asc";
    onSortChange({ key, dir: nextDir });
  };

  function handleColDragStart(e: DragEvent<HTMLTableCellElement>, key: ColumnKey) {
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", key);
    setDraggingCol(key);
  }

  function handleColDragOver(e: DragEvent<HTMLTableCellElement>, overKey: ColumnKey) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (!draggingCol || draggingCol === overKey) return;
    setColumnOrder((prev) => {
      const fromIdx = prev.indexOf(draggingCol);
      const toIdx = prev.indexOf(overKey);
      if (fromIdx < 0 || toIdx < 0) return prev;
      const next = [...prev];
      next.splice(fromIdx, 1);
      next.splice(toIdx, 0, draggingCol);
      return next;
    });
  }

  function handleColDragEnd() {
    setDraggingCol(null);
  }

  return (
    <div className="flex flex-col gap-3">
      {/* 결과 카운트 */}
      <div className="flex items-center justify-end">
        <span className="text-xs text-text-4 tabular-nums">
          {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, visibleItems.length)} / 총 {visibleItems.length}건
        </span>
      </div>

      {/* 빈 상태 */}
      {visibleItems.length === 0 && (
        <div className="bg-surface shadow-card rounded-lg py-12 text-center text-sm text-text-4">
          조건에 맞는 물건이 없습니다
        </div>
      )}

      {/* 데스크톱: 테이블 */}
      {visibleItems.length > 0 && (
        <div className="hidden md:block overflow-x-auto bg-surface shadow-card rounded-xl">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-surface-muted border-b border-border">
                {columnOrder.map((key) => {
                  const col = COLUMNS[key];
                  const align = alignClass(col.align);
                  const isDragging = draggingCol === key;
                  const dragCls = `cursor-grab active:cursor-grabbing select-none ${
                    isDragging ? "opacity-50" : ""
                  }`;
                  if (col.sortKey) {
                    const active = filter.sort.key === col.sortKey;
                    const arrow = !active ? "↕" : filter.sort.dir === "asc" ? "↑" : "↓";
                    return (
                      <th
                        key={key}
                        draggable
                        onDragStart={(e) => handleColDragStart(e, key)}
                        onDragOver={(e) => handleColDragOver(e, key)}
                        onDragEnd={handleColDragEnd}
                        onClick={() => col.sortKey && toggleSort(col.sortKey)}
                        title="드래그하여 컬럼 순서를 바꿀 수 있습니다"
                        className={`px-3 py-2.5 text-xs font-semibold whitespace-nowrap hover:text-primary ${
                          active ? "text-primary" : "text-text-3"
                        } ${align} ${dragCls}`}
                      >
                        {col.label} <span className={active ? "" : "opacity-30"}>{arrow}</span>
                      </th>
                    );
                  }
                  return (
                    <th
                      key={key}
                      draggable
                      onDragStart={(e) => handleColDragStart(e, key)}
                      onDragOver={(e) => handleColDragOver(e, key)}
                      onDragEnd={handleColDragEnd}
                      title="드래그하여 컬럼 순서를 바꿀 수 있습니다"
                      className={`px-3 py-2.5 text-xs font-semibold text-text-3 whitespace-nowrap ${align} ${dragCls}`}
                    >
                      {col.label}
                    </th>
                  );
                })}
                <th className="px-3 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {pageItems.map((item) => {
                const dl = daysLeft(item.cltr_bid_end_dt);
                const pvct = dl < 0 && item.pvct_trgt_yn === "Y";
                return (
                  <tr
                    key={item.cltr_mng_no}
                    className={`border-b border-border cursor-pointer transition-colors ${
                      pvct ? "bg-surface hover:bg-surface-muted" : "bg-primary-subtle/60 hover:bg-primary-subtle"
                    }`}
                    onClick={() => router.push(`/items/${item.cltr_mng_no}`)}
                  >
                    {columnOrder.map((key) => {
                      const col = COLUMNS[key];
                      const align = alignClass(col.align);
                      return (
                        <td key={key} className={`px-3 py-2.5 ${align}`}>
                          {col.cell(item)}
                        </td>
                      );
                    })}
                    <td className="px-2 py-2.5 text-right w-px whitespace-nowrap">
                      <ExternalSiteMenu item={item} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 모바일: 카드 리스트 */}
      {visibleItems.length > 0 && (
        <div className="md:hidden flex flex-col gap-2">
          {pageItems.map((item) => {
            const dl = daysLeft(item.cltr_bid_end_dt);
            const pvct = dl < 0 && item.pvct_trgt_yn === "Y";
            return (
              <div
                key={item.cltr_mng_no}
                role="button"
                tabIndex={0}
                onClick={() => router.push(`/items/${item.cltr_mng_no}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    router.push(`/items/${item.cltr_mng_no}`);
                  }
                }}
                className="text-left bg-surface shadow-card rounded-lg p-3 flex flex-col gap-1 cursor-pointer"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="text-sm font-medium text-text-1 flex-1">
                    {item.onbid_cltr_nm}
                  </div>
                  <RatioPill ratio={item.ratio_pct} />
                </div>
                <div className="flex items-center gap-1.5 text-xs text-text-3 flex-wrap">
                  {isNewToday(item.first_collected_at) && (
                    <span className="text-[10px] bg-new text-primary-fg rounded-sm px-1.5 py-0.5 font-bold">
                      NEW
                    </span>
                  )}
                  {item.market_match_tier != null && (
                    <span className="text-[10px] bg-ok-bg text-ok-fg rounded-sm px-1.5 py-0.5 font-bold">
                      실거래 {item.market_match_count ?? 0}건
                    </span>
                  )}
                  <span>{item.cltr_usg_scls_nm} / {sqmsToPyeong(item.bld_sqms)}</span>
                </div>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-sm font-semibold text-primary tabular-nums">
                    {fmtAmt(item.lowst_bid_prc)}
                  </span>
                  <DeadlineLabel dt={item.cltr_bid_end_dt} pvct={pvct} />
                </div>
                <div className="flex items-center justify-end mt-1">
                  <ExternalSiteMenu item={item} />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 페이지네이션 */}
      <div className="flex md:items-center md:justify-end gap-2 px-1">
        {totalPages > 1 && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(1)}
              disabled={page === 1}
              className="px-2 py-1 text-xs rounded-md border border-border-strong disabled:opacity-30 hover:border-primary hover:text-primary transition-colors"
            >
              «
            </button>
            <button
              onClick={() => setPage((p) => p - 1)}
              disabled={page === 1}
              className="px-2 py-1 text-xs rounded-md border border-border-strong disabled:opacity-30 hover:border-primary hover:text-primary transition-colors"
            >
              ‹
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 2)
              .reduce<(number | "…")[]>((acc, p, idx, arr) => {
                if (idx > 0 && p - (arr[idx - 1] as number) > 1) acc.push("…");
                acc.push(p);
                return acc;
              }, [])
              .map((p, idx) =>
                p === "…" ? (
                  <span key={`ellipsis-${idx}`} className="px-1 text-xs text-text-4">…</span>
                ) : (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`px-2.5 py-1 text-xs rounded-md border transition-colors tabular-nums ${
                      page === p
                        ? "bg-primary text-primary-fg border-primary"
                        : "border-border-strong hover:border-primary hover:text-primary"
                    }`}
                  >
                    {p}
                  </button>
                )
              )}
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page === totalPages}
              className="px-2 py-1 text-xs rounded-md border border-border-strong disabled:opacity-30 hover:border-primary hover:text-primary transition-colors"
            >
              ›
            </button>
            <button
              onClick={() => setPage(totalPages)}
              disabled={page === totalPages}
              className="px-2 py-1 text-xs rounded-md border border-border-strong disabled:opacity-30 hover:border-primary hover:text-primary transition-colors"
            >
              »
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
