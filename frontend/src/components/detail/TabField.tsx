// frontend/src/components/detail/TabField.tsx
"use client";

import { useEffect, useState } from "react";
import { fetchItemInfo } from "@/api";
import { LabeledTable, type ColDef } from "@/components/LabeledTable";
import type { BidItem, ItemInfo } from "@/types";
import { sqmsToPyeong } from "@/utils/format";
import DecisionBanner, { type DecisionStatus } from "./DecisionBanner";

const fmtSqms = (v: unknown) => {
  if (v == null || v === "") return "-";
  const s = String(v).trim();
  const n = parseFloat(s.replace(/[^0-9.]/g, ""));
  if (!isNaN(n)) return `${s} (약 ${(n * 0.3025).toFixed(1)}평)`;
  return s;
};

const SQMS_COLS: ColDef[] = [
  { key: "cland_cont", label: "종별(지목)" },
  { key: "sqms_cont", label: "면적", fmt: fmtSqms },
  { key: "purs_alc_cont", label: "지분" },
  { key: "dtl_cltr_nm", label: "비고" },
];

interface Props {
  item: BidItem;
}

export default function TabField({ item }: Props) {
  const [info, setInfo] = useState<ItemInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    fetchItemInfo(item.cltr_mng_no)
      .then(setInfo)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [item.cltr_mng_no]);

  // 서술형 정보 존재 여부
  const hasNarrative =
    !!(item.loc_vnty_pscd_cont || item.utlz_pscd_cont || item.icdl_cdtn_cont || item.cltr_etc_cont);
  const hasImage = !!item.thnl_img_url && !imgFailed;

  // DecisionBanner
  let status: DecisionStatus = "ok";
  let bannerText = "공고 원문 정보를 확인하세요";
  if (item.crtn_yn === "Y") {
    status = "warn";
    bannerText = "정정 이력 있음 — 공고 원문의 변경 내역을 확인하세요";
  } else if (!hasNarrative) {
    status = "warn";
    bannerText = "공고 원문의 서술 정보가 누락되어 있습니다. 온비드 원본을 참고하세요";
  }

  const InfoRow = ({ label, value }: { label: string; value: string }) => (
    <div className="flex gap-2 py-2 border-b border-border last:border-0">
      <span className="text-xs text-text-4 w-28 shrink-0">{label}</span>
      <span className="text-xs text-text-1 flex-1">{value}</span>
    </div>
  );

  return (
    <div className="flex flex-col gap-6">
      <DecisionBanner status={status}>{bannerText}</DecisionBanner>

      {/* === 1. 서술형 정보 (최상단 승격) === */}
      {(hasNarrative || hasImage) && (
        <div className="bg-surface shadow-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text-1 mb-3">현장 및 이용 현황</h3>
          {hasImage && (
            <div className="mb-4 w-full max-w-[640px] aspect-[4/3] rounded-lg overflow-hidden bg-surface-muted">
              <img
                src={(item.thnl_img_url as string).replace(
                  "downloadImageKind=THNL_NM",
                  "downloadImageKind=ORGN_NM",
                )}
                alt={item.onbid_cltr_nm}
                className="w-full h-full object-cover"
                onError={() => setImgFailed(true)}
              />
            </div>
          )}
          <div className="flex flex-col gap-4">
            {item.loc_vnty_pscd_cont && (
              <div>
                <p className="text-xs font-medium text-text-3 mb-1">위치 및 부근현황</p>
                <p className="text-xs text-text-1 whitespace-pre-wrap leading-relaxed">
                  {item.loc_vnty_pscd_cont}
                </p>
              </div>
            )}
            {item.utlz_pscd_cont && (
              <div>
                <p className="text-xs font-medium text-text-3 mb-1">이용현황</p>
                <p className="text-xs text-text-1 whitespace-pre-wrap leading-relaxed">
                  {item.utlz_pscd_cont}
                </p>
              </div>
            )}
            {item.icdl_cdtn_cont && (
              <div>
                <p className="text-xs font-medium text-text-3 mb-1">부대조건</p>
                <p className="text-xs text-text-1 whitespace-pre-wrap leading-relaxed">
                  {item.icdl_cdtn_cont}
                </p>
              </div>
            )}
            {item.cltr_etc_cont && (
              <div>
                <p className="text-xs font-medium text-text-3 mb-1">기타사항</p>
                <p className="text-xs text-text-3 bg-surface-muted border border-border rounded p-3 whitespace-pre-wrap leading-relaxed">
                  {item.cltr_etc_cont}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* === 2. 기본정보 그리드 === */}
      <div className="bg-surface shadow-card rounded-xl p-5">
        <h3 className="text-sm font-semibold text-text-1 mb-3">물건 기본정보</h3>
        <InfoRow label="소재지" value={`${item.lctn_sd_nm} ${item.lctn_sggn_nm} ${item.lctn_emd_nm}`} />
        {item.zadr_nm && <InfoRow label="지번" value={item.zadr_nm} />}
        {item.cltr_radr && <InfoRow label="도로명" value={item.cltr_radr} />}
        <InfoRow label="자산구분" value={item.prpt_div_nm} />
        <InfoRow label="건물용도" value={`${item.cltr_usg_mcls_nm} > ${item.cltr_usg_scls_nm}`} />
        <InfoRow label="건물면적" value={sqmsToPyeong(item.bld_sqms)} />
        <InfoRow label="토지면적" value={sqmsToPyeong(item.land_sqms)} />
        <InfoRow label="공고기관" value={item.rqst_org_nm} />
        <InfoRow label="집행기관" value={item.exct_org_nm} />
        <InfoRow label="입찰기간" value={`${item.cltr_bid_bgng_dt} ~ ${item.cltr_bid_end_dt}`} />
        <InfoRow label="수의계약" value={item.pvct_trgt_yn === "Y" ? "가능" : "불가"} />
        <InfoRow label="일괄입찰" value={item.batc_bid_yn === "Y" ? "예" : "아니오"} />
        <InfoRow label="지분물건" value={item.alc_yn === "Y" ? "예" : "아니오"} />
      </div>

      {/* === 3. 면적 상세 === */}
      {loading && <div className="text-xs text-text-4 animate-pulse">면적 정보 로딩 중...</div>}
      {error && <div className="text-xs text-hot-fg">면적 정보를 불러올 수 없습니다.</div>}
      {info && info.sqms.length > 0 && (
        <div>
          <p className="text-sm font-semibold text-text-1 mb-2">면적 상세</p>
          <LabeledTable data={info.sqms} columns={SQMS_COLS} />
        </div>
      )}
    </div>
  );
}
