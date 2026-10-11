const USAGE_ICONS: Record<string, string> = {
  업무시설: "🏢",
  "주/상용건물": "🏠",
  오피스텔: "🏙",
};

export function usageIcon(mcls: string | null | undefined): string {
  if (!mcls) return "📋";
  return USAGE_ICONS[mcls] ?? "📋";
}
