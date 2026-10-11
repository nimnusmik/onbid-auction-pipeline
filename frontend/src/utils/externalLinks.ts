import type { BidItem } from "@/types";

export type ExternalSite =
  | "naver"
  | "valueupmap"
  | "disco"
  | "hogangnono"
  | "zigbang";

export const EXTERNAL_SITES: {
  id: ExternalSite;
  label: string;
  short: string;
  note?: string;
}[] = [
  { id: "naver", label: "네이버 부동산", short: "N" },
  { id: "valueupmap", label: "밸류맵 (공매/토지)", short: "V" },
  { id: "disco", label: "디스코 (실거래)", short: "D", note: "구글 경유" },
  { id: "hogangnono", label: "호갱노노", short: "호" },
  { id: "zigbang", label: "직방", short: "직" },
];

/** 지번 → 도로명 → 시군구읍면동 순으로 검색 쿼리 생성 */
export function buildAddressQuery(item: BidItem): string {
  const zadr = item.zadr_nm?.trim();
  if (zadr) return zadr;
  const radr = item.cltr_radr?.trim();
  if (radr) return radr;
  return [item.lctn_sd_nm, item.lctn_sggn_nm, item.lctn_emd_nm]
    .filter((s) => s && s.trim().length > 0)
    .join(" ");
}

/**
 * 단지명 없는 케이스용 짧은 폴백 주소: "시도(축약) 시군구 읍면동 지번".
 * 호수/층/필지/주건축물 등 노이즈를 잘라내어 외부 사이트 지번 매칭률을 높인다.
 */
export function buildShortAddressQuery(item: BidItem): string {
  const sido = (item.lctn_sd_nm ?? "")
    .replace(/특별자치도|특별자치시|특별시|광역시/g, "")
    .replace(/도$/, "")
    .trim();
  const parts = [sido, item.lctn_sggn_nm, item.lctn_emd_nm]
    .map((s) => (s ?? "").trim())
    .filter((s) => s.length > 0);
  const zadr = item.zadr_nm ?? "";
  const jibunMatch = zadr.match(/(\d+(?:-\d+)?)/);
  if (jibunMatch) parts.push(jibunMatch[1]);
  return parts.join(" ");
}

/**
 * cltr_radr 끝 괄호 안 "(동, 건물명)" 에서 건물/단지명 추출.
 * 예) "...(부평동, e편한세상시티부평역)" → "e편한세상시티부평역"
 */
export function extractBuildingName(item: BidItem): string | null {
  const radr = item.cltr_radr ?? "";
  const m = radr.match(/\(([^,()]+),\s*([^()]+)\)\s*$/);
  if (!m) return null;
  const name = m[2].trim();
  if (!name || name.length < 2) return null;
  return name;
}

const NOISE_PATTERNS: RegExp[] = [
  /^\d+(-\d+)*외?\d*$/,
  /^외\d*$/,
  /^\d+필지$/,
  /^제?\d+층$/,
  /^제?\d+호$/,
  /^제?\d+동$/,
  /^제[가-힣]+동$/,
  /^제?\d+층제?\d+호$/,
  /^외\d+호실?$/,
  /^[가-힣]{1,4}(특별시|광역시|특별자치시|특별자치도|도|시|군|구|읍|면|동|리)$/,
  /^.+(대로|번길)$/,
  /^[가-힣A-Za-z\d]+로$/,
  /^오피스텔$|^아파트$|^업무시설$|^주상복합$|^주차장호?$|^상가$|^사무소$|^지식산업센터$/,
  /^일괄매각$|^개별매각$|^개별$|^매각$|^일부$|^주건축물$|^주건물$|^부속건물$/,
];

/**
 * zadr_nm / onbid_cltr_nm 같은 자유 텍스트에서 토큰 단위로 노이즈를 제거해
 * 단지/건물명 후보를 추려낸다.
 */
export function extractBuildingFromText(
  text: string | null | undefined,
  item: BidItem,
): string | null {
  if (!text) return null;
  const normalized = text
    .replace(/특별자치도|특별자치시|특별시|광역시/g, "")
    .replace(/[()[\]]/g, " ")
    .replace(/\s*,\s*/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const sido = (item.lctn_sd_nm ?? "")
    .replace(/특별자치도|특별자치시|특별시|광역시/g, "")
    .trim();
  const sgn = (item.lctn_sggn_nm ?? "").trim();
  const emd = (item.lctn_emd_nm ?? "").trim();

  const kept: string[] = [];
  for (const t of normalized.split(/\s+/)) {
    if (!t) continue;
    if (t === sido || t === sgn || t === emd) continue;
    if (NOISE_PATTERNS.some((p) => p.test(t))) continue;
    kept.push(t);
  }
  if (kept.length === 0) return null;
  return kept.join(" ");
}

/**
 * 단지/건물 상세페이지 매칭을 위한 검색어: "시군구 + 건물명".
 * 추출 우선순위:
 *   1) cltr_radr 끝 괄호 "(동, 건물명)"
 *   2) zadr_nm 토큰 정제
 *   3) onbid_cltr_nm 토큰 정제
 * 모두 실패 시 null → 호출측에서 주소로 폴백.
 */
export function buildBuildingQuery(item: BidItem): string | null {
  const name =
    extractBuildingName(item) ??
    extractBuildingFromText(item.zadr_nm, item) ??
    extractBuildingFromText(item.onbid_cltr_nm, item);
  if (!name) return null;
  const sggn = item.lctn_sggn_nm?.trim();
  return sggn ? `${sggn} ${name}` : name;
}

/** 네이버 부동산 검색 매칭률을 위해 주소 정규화 */
export function normalizeForNaver(query: string): string {
  return query
    .replace(/\s*\([^)]*\)/g, "")
    .replace(/특별자치도/g, "")
    .replace(/특별자치시/g, "")
    .replace(/특별시/g, "")
    .replace(/광역시/g, "")
    .replace(/\s+외\s+\d+필지/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export async function openExternalSite(
  site: ExternalSite,
  item: BidItem,
): Promise<{ copied: boolean; query: string }> {
  const buildingQuery = buildBuildingQuery(item);
  const shortAddress = buildShortAddressQuery(item);
  let query = "";
  let url = "";

  switch (site) {
    case "naver": {
      query = buildingQuery ?? shortAddress;
      url = `https://m.land.naver.com/search/result/${encodeURIComponent(query)}`;
      break;
    }
    case "valueupmap": {
      query = buildingQuery ?? shortAddress;
      url = `https://www.valueupmap.com/search?keyword=${encodeURIComponent(query)}`;
      break;
    }
    case "disco": {
      query = buildingQuery ?? shortAddress;
      url = `https://www.google.com/search?q=${encodeURIComponent(`${query} site:disco.re`)}`;
      break;
    }
    case "hogangnono": {
      query = buildingQuery ?? shortAddress;
      url = `https://hogangnono.com/search?q=${encodeURIComponent(query)}`;
      break;
    }
    case "zigbang": {
      query = buildingQuery ?? shortAddress;
      url = `https://www.zigbang.com/search?q=${encodeURIComponent(query)}`;
      break;
    }
  }

  const copied = await copyToClipboard(query);
  window.open(url, "_blank", "noopener,noreferrer");
  return { copied, query };
}
