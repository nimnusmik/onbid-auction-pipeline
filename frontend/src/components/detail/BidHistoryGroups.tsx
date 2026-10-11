// frontend/src/components/detail/BidHistoryGroups.tsx
"use client";

import type { BidQual } from "@/types";
import { fmtAmt } from "@/utils/format";

// 회차 묶음을 시간순 정렬 후 bid_seq=1 마다 새 그룹으로 분리.
// 같은 cltr_mng_no 안에 공매조건(pbct_cdtn_no)이 여러 번 새로 만들어지는 경우
// (수의계약 단계의 가격 인하 재공매 등) bid_seq 가 1로 다시 시작되므로
// 이를 경계로 그룹화한다. 결과는 최신 그룹부터 반환.
export function groupByCdtn(quals: BidQual[]): BidQual[][] {
  if (quals.length === 0) return [];
  const sorted = [...quals].sort((a, b) => {
    const ta = a.bid_opnn_dttm ?? "";
    const tb = b.bid_opnn_dttm ?? "";
    if (ta && tb && ta !== tb) return ta.localeCompare(tb);
    return a.bid_seq - b.bid_seq;
  });
  const groups: BidQual[][] = [];
  let current: BidQual[] = [];
  for (const q of sorted) {
    if (q.bid_seq === 1 && current.length > 0) {
      groups.push(current);
      current = [];
    }
    current.push(q);
  }
  if (current.length > 0) groups.push(current);
  return groups.reverse();
}

export default function BidHistoryGroups({ quals }: { quals: BidQual[] }) {
  const groups = groupByCdtn(quals);
  const total = groups.length;

  return (
    <div className="flex flex-col gap-3">
      {groups.map((group, idx) => {
        const order = total - idx;
        const start = group[0].bid_opnn_dttm?.slice(0, 7) ?? "-";
        const end   = group[group.length - 1].bid_opnn_dttm?.slice(0, 7) ?? null;
        const periodLabel = end && end !== start ? `${start} ~ ${end}` : start;

        const failCnt    = group.filter(q => q.result_status === "유찰").length;
        const wonCnt     = group.filter(q => q.result_status === "낙찰").length;
        const cancelCnt  = group.filter(q => q.result_status === "취소").length;
        const ongoingCnt = group.filter(q => q.result_status === "진행중").length;

        const summaryParts: string[] = [];
        if (ongoingCnt > 0) summaryParts.push(`${ongoingCnt}회 진행중`);
        if (wonCnt > 0)     summaryParts.push(`${wonCnt}회 낙찰`);
        if (failCnt > 0)    summaryParts.push(`${failCnt}회 유찰`);
        if (cancelCnt > 0)  summaryParts.push(`${cancelCnt}회 취소`);
        const summary = summaryParts.join(" · ") || "회차 없음";

        const sortedRows = [...group].sort((a, b) => b.bid_seq - a.bid_seq);

        return (
          <div key={group[0].id} className="bg-surface shadow-card rounded-lg overflow-hidden">
            <div className="flex items-baseline justify-between px-3 py-2 bg-surface-muted border-b border-border">
              <p className="text-xs font-semibold text-text-1">
                {order}차 공매
                <span className="ml-2 text-text-3 font-normal">{periodLabel}</span>
              </p>
              <p className="text-[11px] text-text-3">{summary}</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left px-3 py-2 text-text-3 font-semibold">회차</th>
                    <th className="text-left px-3 py-2 text-text-3 font-semibold">입찰기간</th>
                    <th className="text-right px-3 py-2 text-text-3 font-semibold">최저가</th>
                    <th className="text-right px-3 py-2 text-text-3 font-semibold">보증금</th>
                    <th className="text-center px-3 py-2 text-text-3 font-semibold">결과</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map(q => {
                    const status = q.result_status;
                    const badgeClass =
                      status === "진행중" ? "bg-ok-bg text-ok-fg" :
                      status === "낙찰"   ? "bg-primary/10 text-primary" :
                      status === "유찰"   ? "bg-mid-bg text-mid-fg" :
                      status === "취소"   ? "bg-surface-muted text-text-4" :
                      "bg-surface-muted text-text-4";
                    const period = q.bid_strt_dttm && q.bid_end_dttm
                      ? `${q.bid_strt_dttm} ~ ${q.bid_end_dttm}`
                      : (q.bid_opnn_dttm ?? "-");
                    return (
                      <tr key={q.id} className="border-b border-border last:border-0 hover:bg-surface-muted">
                        <td className="px-3 py-2 text-text-1 font-medium">{q.bid_seq}회차</td>
                        <td className="px-3 py-2 text-text-3 whitespace-nowrap">{period}</td>
                        <td className="px-3 py-2 text-right text-primary font-medium tabular-nums">
                          {q.min_bd_prc != null ? fmtAmt(q.min_bd_prc) : "-"}
                        </td>
                        <td className="px-3 py-2 text-right text-text-3 tabular-nums">
                          {q.bid_grnt_prc != null ? fmtAmt(q.bid_grnt_prc) : "-"}
                        </td>
                        <td className="px-3 py-2 text-center">
                          {status ? (
                            <span className={`${badgeClass} rounded px-2 py-0.5`}>{status}</span>
                          ) : (
                            <span className="text-text-4">-</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}
