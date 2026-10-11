"use client";

import { useState } from "react";
import type { FilterState } from "@/types";

const USG_TREE: Record<string, string[]> = {
  "상가용및업무용건물": ["업무시설", "기타상가용및업무용"],
  "용도복합용건물": ["오피스텔", "주/상용건물"],
};

const REGIONS = [
  "서울특별시",
  "경기도",
  "인천광역시",
  "부산광역시",
  "대구광역시",
  "광주광역시",
  "대전광역시",
  "울산광역시",
  "세종특별자치시",
];

function ratioLabel(v: number): { text: string; color: string } {
  if (v < 50) return { text: "최우선 검토", color: "text-hot-fg" };
  if (v < 60) return { text: "우선 검토", color: "text-hot-fg" };
  if (v < 70) return { text: "적극 검토", color: "text-mid-fg" };
  if (v < 80) return { text: "일반 관심", color: "text-mid-fg" };
  return { text: "관심 낮음", color: "text-text-4" };
}

interface Props {
  filter: FilterState;
  onSearch: (f: FilterState) => void;
}

export default function FilterPanel({ filter, onSearch }: Props) {
  const [local, setLocal] = useState<FilterState>(filter);

  const label = ratioLabel(local.ratio_max);

  function reset() {
    const def: FilterState = {
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
      sort: local.sort,
    };
    setLocal(def);
  }

  const sclsOptions = local.usg_mcls ? USG_TREE[local.usg_mcls] ?? [] : [];

  const numInput =
    "text-xs border border-border-strong rounded-md px-2 py-1 bg-surface text-text-1 focus:outline-none focus:border-primary";
  const selInput =
    "text-xs border border-border-strong rounded-md px-2 py-1.5 bg-surface text-text-1 focus:outline-none focus:border-primary disabled:opacity-40";

  return (
    <div className="p-4 flex flex-col gap-5">
      <h2 className="hidden md:block text-sm font-semibold text-text-1 border-b border-border pb-2">
        필터
      </h2>

      {/* 감정가 대비 비율 */}
      <div className="flex flex-col gap-2">
        <label className="text-xs font-medium text-text-2">감정가 대비 비율</label>
        <div className="flex items-center gap-1.5 flex-wrap">
          <input
            type="number"
            min={0}
            max={100}
            step={5}
            value={local.ratio_min}
            onChange={(e) => {
              const v = Number(e.target.value);
              setLocal({ ...local, ratio_min: Math.min(v, local.ratio_max) });
            }}
            className={`${numInput} w-16 text-center`}
          />
          <span className="text-xs text-text-3">~</span>
          <input
            type="number"
            min={0}
            max={100}
            step={5}
            value={local.ratio_max}
            onChange={(e) => {
              const v = Number(e.target.value);
              setLocal({ ...local, ratio_max: Math.max(v, local.ratio_min) });
            }}
            className={`${numInput} w-16 text-center`}
          />
          <span className="text-xs text-text-3">%</span>
        </div>
        <input
          type="range"
          min={0}
          max={100}
          step={5}
          value={local.ratio_max}
          onChange={(e) => {
            const v = Number(e.target.value);
            setLocal({ ...local, ratio_max: Math.max(v, local.ratio_min) });
          }}
          className="w-full accent-primary"
        />
        <span className={`text-xs font-medium ${label.color}`}>{label.text}</span>
      </div>

      {/* 최저입찰가 범위 */}
      <div className="flex flex-col gap-2">
        <label className="text-xs font-medium text-text-2">최저입찰가</label>
        <div className="flex items-center gap-1.5 flex-wrap">
          <input
            type="number"
            min={0}
            step={1000}
            placeholder="하한"
            value={local.price_min != null ? local.price_min / 10000 : ""}
            onChange={(e) => {
              const raw = e.target.value;
              setLocal({ ...local, price_min: raw === "" ? null : Number(raw) * 10000 });
            }}
            className={`${numInput} w-[84px] text-right`}
          />
          <span className="text-xs text-text-3">~</span>
          <input
            type="number"
            min={0}
            step={1000}
            placeholder="상한"
            value={local.price_max != null ? local.price_max / 10000 : ""}
            onChange={(e) => {
              const raw = e.target.value;
              setLocal({ ...local, price_max: raw === "" ? null : Number(raw) * 10000 });
            }}
            className={`${numInput} w-[84px] text-right`}
          />
          <span className="text-xs text-text-3 shrink-0">만원</span>
        </div>
      </div>

      {/* 유찰 횟수 최소 */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-text-2">유찰 횟수 최소</label>
        <select
          value={local.usbd_min}
          onChange={(e) => setLocal({ ...local, usbd_min: Number(e.target.value) })}
          className={selInput}
        >
          <option value={0}>전체</option>
          <option value={1}>1회 이상</option>
          <option value={2}>2회 이상</option>
          <option value={3}>3회 이상</option>
          <option value={5}>5회 이상</option>
        </select>
      </div>

      {/* 용도 */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-text-2">용도</label>
        <select
          value={local.usg_mcls}
          onChange={(e) => setLocal({ ...local, usg_mcls: e.target.value, usg_scls: "" })}
          className={selInput}
        >
          <option value="">중분류 전체</option>
          {Object.keys(USG_TREE).map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <select
          value={local.usg_scls}
          onChange={(e) => setLocal({ ...local, usg_scls: e.target.value })}
          disabled={!local.usg_mcls}
          className={selInput}
        >
          <option value="">소분류 전체</option>
          {sclsOptions.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* 지역 */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-text-2">지역</label>
        <select
          value={local.sd_nm}
          onChange={(e) => setLocal({ ...local, sd_nm: e.target.value })}
          className={selInput}
        >
          <option value="">전체</option>
          {REGIONS.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </div>

      {/* 수의계약 */}
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-text-2">수의계약</label>
        <div className="flex gap-2">
          {([null, "Y", "N"] as const).map((val) => (
            <button
              key={String(val)}
              onClick={() => setLocal({ ...local, pvct: val })}
              className={`flex-1 text-xs py-1.5 rounded-md border transition-colors ${
                local.pvct === val
                  ? "bg-primary text-primary-fg border-primary"
                  : "bg-surface text-text-2 border-border-strong hover:border-primary hover:text-primary"
              }`}
            >
              {val === null ? "전체" : val === "Y" ? "가능" : "불가능"}
            </button>
          ))}
        </div>
      </div>

      {/* 관심물건만 */}
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="bookmarked"
          checked={local.bookmarked === 1}
          onChange={(e) => setLocal({ ...local, bookmarked: e.target.checked ? 1 : null })}
          className="accent-primary"
        />
        <label htmlFor="bookmarked" className="text-xs text-text-2 cursor-pointer">
          관심 물건만
        </label>
      </div>

      {/* 버튼 */}
      <div className="flex flex-col gap-2 mt-2">
        <button
          onClick={() => onSearch(local)}
          className="w-full bg-primary text-primary-fg text-sm py-2 rounded-md font-medium hover:bg-primary-hover transition-colors"
        >
          검색
        </button>
        <button
          onClick={reset}
          className="w-full bg-surface border border-border-strong text-text-2 text-sm py-2 rounded-md hover:bg-surface-muted transition-colors"
        >
          초기화
        </button>
      </div>
    </div>
  );
}
