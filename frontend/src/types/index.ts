export interface BidItem {
  cltr_mng_no: string;
  pbct_cdtn_no: number;
  onbid_cltr_nm: string;
  prpt_div_nm: string;
  cltr_usg_mcls_nm: string;
  cltr_usg_scls_nm: string;
  lctn_sd_nm: string;
  lctn_sggn_nm: string;
  lctn_emd_nm: string;
  land_sqms: number | null;
  bld_sqms: number | null;
  apsl_evl_amt: number;
  lowst_bid_prc: number;
  ratio_pct: number;
  frst_ratio_pct: number | null;
  start_ratio_pct: number | null;  // BID_QUAL 의 최초(=최대) 최저입찰가 대비 현재가 비율
  usbd_nft: number;
  pbct_nsq: string;
  pvct_trgt_yn: string;
  batc_bid_yn: string;
  alc_yn: string;
  crtn_yn: string;
  rqst_org_nm: string;
  exct_org_nm: string;
  cltr_bid_bgng_dt: string;
  cltr_bid_end_dt: string;
  thnl_img_url: string | null;
  status: "active" | "closed";
  is_bookmarked: number;
  first_collected_at: string;
  collected_at: string;
  detail_fetched_at: string | null;
  bid_fetched_at: string | null;
  loc_vnty_pscd_cont: string | null;
  utlz_pscd_cont: string | null;
  cltr_etc_cont: string | null;
  icdl_cdtn_cont: string | null;
  zadr_nm: string | null;
  cltr_radr: string | null;
  // 실거래 매칭 캐시(MOLIT_MATCH). null = 아직 갱신 안 됨, 매칭 실패도 null로 옴
  market_match_tier?: number | null;     // 0=같은 지번, 1=같은 건물명
  market_match_count?: number | null;
  score?: number;
  score_breakdown?: {
    price: number;
    location: number;
  };
}

export interface Stats {
  total: number;
  bookmarked: number;
  pvct_count: number;
  ratio_avg: number | null;
  ratio_min: number | null;
  ratio_below60: number;
  ratio_60_70: number;
  by_region: { lctn_sd_nm: string; cnt: number }[];
}

export interface ItemInfo {
  sqms: Record<string, unknown>[];
  apsl_evl: Record<string, unknown>[];
  paps_inf: Record<string, unknown> | null;
  crtn_lst: Record<string, unknown>[];
  batc_cltr: Record<string, unknown>[];
}

export interface BidHist {
  id: number;
  bid_qual_id: number;
  cltr_mng_no: string;
  prv_bid_seq: number;
  prv_bid_rslt: string;
  prv_bid_fail_cnt: number;
}

export interface BidQual {
  id: number;
  cltr_mng_no: string;
  pbct_cdtn_no: number;
  bid_seq: number;
  bid_round: number | null;       // 차수 (web 출처)
  bid_strt_dttm: string | null;
  bid_end_dttm: string | null;
  bid_opnn_dttm: string | null;
  min_bd_prc: number | null;
  bid_grnt_prc: number | null;
  winning_amt: number | null;     // 낙찰금액 (web 출처)
  acml_fail_cnt: number | null;
  result_status: string | null;   // "진행중" / "유찰" / "낙찰" / "취소"
  hist: BidHist[];
}

export interface TenantInfo {
  leas_inf: Record<string, unknown>[];
  ocpy_rel: Record<string, unknown>[];
  rgst_prmr: Record<string, unknown>[];
  dtbt_rqr: Record<string, unknown>[];
}

export interface MarketTransaction {
  dong_nm: string;
  bldg_nm: string;
  exclu_use_ar: number | null;
  deal_amount: number | null;
  floor: string;
  deal_date: string;
  unit_price: number | null;
}

export interface MarketPriceResponse {
  status: "ok" | "no_data" | "no_mapping" | "not_supported" | "api_error";
  message?: string;
  match_tier: number | null;
  match_tier_label?: string;
  match_count?: number;
  transactions: MarketTransaction[];
  summary: {
    avg_unit_price: number | null;
    estimated_market_price_won: number | null;
    latest_deal: string | null;
    area_sqm?: number | null;
  } | null;
  comparison: {
    market_vs_bid_pct: number;
    discount_from_market_pct: number;
  } | null;
}

export type SortKey =
  | "apsl_evl_amt"
  | "lowst_bid_prc"
  | "ratio_pct"
  | "start_ratio_pct"
  | "usbd_nft"
  | "deadline";

export interface SortState {
  key: SortKey;
  dir: "asc" | "desc";
}

export interface FilterState {
  ratio_min: number;
  ratio_max: number;
  price_min: number | null;
  price_max: number | null;
  usbd_min: number;
  sd_nm: string;
  usg_mcls: string;
  usg_scls: string;
  bookmarked: number | null;
  pvct: "Y" | "N" | null;
  sort: SortState;
}
