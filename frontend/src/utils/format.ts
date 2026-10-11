/** 원화 포맷: 1,234,000,000 원 */
export function fmtKRW(n: number | null | undefined): string {
  if (n == null) return "-";
  return n.toLocaleString("ko-KR") + " 원";
}

/** 억/만 단위 축약: 39.5억 */
export function fmtAmt(n: number | null | undefined): string {
  if (n == null) return "-";
  if (n >= 100_000_000) return (n / 100_000_000).toFixed(1) + "억";
  if (n >= 10_000) return (n / 10_000).toFixed(0) + "만";
  return String(n);
}

/** ratio_pct 기반 색상 클래스 */
export function ratioColor(r: number): "red" | "warn" | "green" {
  if (r < 60) return "red";
  if (r < 70) return "warn";
  return "green";
}

/** 마감까지 남은 일수 */
export function daysLeft(endDt: string): number {
  const end = new Date(endDt);
  const now = new Date();
  return Math.ceil((end.getTime() - now.getTime()) / 86400000);
}

/** D-n 표시 */
export function dLabel(endDt: string): string {
  const d = daysLeft(endDt);
  if (d < 0) return "종료";
  if (d === 0) return "D-0";
  return `D-${d}`;
}

/** 면적 ㎡ → 평 */
export function sqmsToPyeong(sqms: number | null): string {
  if (sqms == null) return "-";
  return `${sqms.toFixed(1)}㎡ (약 ${(sqms * 0.3025).toFixed(1)}평)`;
}
