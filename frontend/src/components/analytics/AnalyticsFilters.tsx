"use client";

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
const USAGE_TYPES = ["용도복합용건물", "상가용및업무용건물"];

export interface AnalyticsFilterState {
  regions: string[];
  usageTypes: string[];
}

interface Props {
  filter: AnalyticsFilterState;
  onChange: (f: AnalyticsFilterState) => void;
}

export default function AnalyticsFilters({ filter, onChange }: Props) {
  function toggleRegion(r: string) {
    const next = filter.regions.includes(r)
      ? filter.regions.filter((x) => x !== r)
      : [...filter.regions, r];
    onChange({ ...filter, regions: next });
  }

  function toggleUsage(u: string) {
    const next = filter.usageTypes.includes(u)
      ? filter.usageTypes.filter((x) => x !== u)
      : [...filter.usageTypes, u];
    onChange({ ...filter, usageTypes: next });
  }

  function clearAll() {
    onChange({ regions: [], usageTypes: [] });
  }

  const hasFilter = filter.regions.length > 0 || filter.usageTypes.length > 0;

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="hidden md:block text-sm font-semibold text-text-1">필터</h3>
        {hasFilter && (
          <button
            onClick={clearAll}
            className="text-xs text-text-4 hover:text-text-2 ml-auto"
          >
            초기화
          </button>
        )}
      </div>

      <div>
        <p className="text-xs text-text-3 mb-2">지역</p>
        <div className="flex flex-wrap gap-1.5">
          {REGIONS.map((r) => (
            <button
              key={r}
              onClick={() => toggleRegion(r)}
              className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                filter.regions.includes(r)
                  ? "bg-primary text-primary-fg"
                  : "bg-surface-muted text-text-2 hover:bg-border"
              }`}
            >
              {r.replace(/특별시|광역시|특별자치시|도$/, "")}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs text-text-3 mb-2">용도</p>
        <div className="flex flex-wrap gap-1.5">
          {USAGE_TYPES.map((u) => (
            <button
              key={u}
              onClick={() => toggleUsage(u)}
              className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                filter.usageTypes.includes(u)
                  ? "bg-primary text-primary-fg"
                  : "bg-surface-muted text-text-2 hover:bg-border"
              }`}
            >
              {u}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
