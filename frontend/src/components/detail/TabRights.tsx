// frontend/src/components/detail/TabRights.tsx
"use client";

import { useEffect, useState } from "react";
import { fetchItemHistory, fetchItemTenant } from "@/api";
import { LabeledTable, type ColDef } from "@/components/LabeledTable";
import type { BidItem, BidQual, TenantInfo } from "@/types";
import BidHistoryGroups from "./BidHistoryGroups";
import DecisionBanner, { type DecisionStatus } from "./DecisionBanner";

interface Props {
  item: BidItem;
}

const fmtAmt = (v: unknown) => {
  if (v == null) return "-";
  const n = Number(v);
  if (isNaN(n)) return String(v);
  return n.toLocaleString("ko-KR") + " 원";
};

const fmtDate = (v: unknown) => {
  if (v == null || v === "") return "-";
  const s = String(v);
  if (s.length === 8) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
  return s;
};

const SECTION_COLS: Record<string, ColDef[]> = {
  leas_inf: [
    { key: "irst_div_nm", label: "구분" },
    { key: "cltr_inpr_nm", label: "임차인" },
    { key: "bid_grtee_amt", label: "보증금", fmt: fmtAmt },
    { key: "mthr_amt", label: "월세", fmt: fmtAmt },
    { key: "conv_grtee_amt", label: "환산보증금", fmt: fmtAmt },
    { key: "cfmtn_ymd", label: "확정일자", fmt: fmtDate },
    { key: "mvin_ymd", label: "전입일자", fmt: fmtDate },
  ],
  ocpy_rel: [
    { key: "ocpy_rel_cd_nm", label: "점유관계" },
    { key: "ocpy_irps_nm", label: "점유자" },
    { key: "ctrt_ymd", label: "계약일자", fmt: fmtDate },
    { key: "mvin_ymd", label: "전입일자", fmt: fmtDate },
    { key: "cfmtn_ymd", label: "확정일자", fmt: fmtDate },
    { key: "acpm_grtee_amt", label: "보증금", fmt: fmtAmt },
    { key: "rnt_amt", label: "차임", fmt: fmtAmt },
    { key: "lsd_part_cont", label: "임차부분" },
  ],
  rgst_prmr: [
    { key: "irst_div_nm", label: "권리종류" },
    { key: "cltr_inpr_nm", label: "권리자" },
    { key: "rgst_ymd", label: "등기설정일", fmt: fmtDate },
    { key: "inpr_stng_amt", label: "설정금액", fmt: fmtAmt },
  ],
  dtbt_rqr: [
    { key: "rgt_rel_cd_nm", label: "권리종류" },
    { key: "acpm_prpt_nm", label: "권리자" },
    { key: "stng_ymd", label: "설정일자", fmt: fmtDate },
    { key: "bond_stng_amt", label: "설정금액", fmt: fmtAmt },
    { key: "dtbt_rqr_yn", label: "배분요구" },
    { key: "dtbt_rqr_ymd", label: "배분요구일", fmt: fmtDate },
    { key: "dtbt_rqr_amt", label: "배분요구액", fmt: fmtAmt },
    { key: "ersr_psbl_yn", label: "말소가능" },
    { key: "etc_cont", label: "기타" },
  ],
};

type RiskStatus = "ok" | "warn" | "unknown";

interface RiskItem {
  label: string;
  status: RiskStatus;
  description: string;
}

function StatusPill({ status }: { status: RiskStatus }) {
  if (status === "ok")
    return <span className="text-xs bg-ok-bg text-ok-fg rounded-full px-2 py-0.5 font-medium">양호</span>;
  if (status === "warn")
    return <span className="text-xs bg-mid-bg text-mid-fg rounded-full px-2 py-0.5 font-medium">주의</span>;
  return <span className="text-xs bg-border text-text-3 rounded-full px-2 py-0.5">확인 필요</span>;
}

export default function TabRights({ item }: Props) {
  const [tenant, setTenant] = useState<TenantInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const [quals, setQuals] = useState<BidQual[]>([]);
  const [histLoading, setHistLoading] = useState(true);
  const [histError, setHistError] = useState(false);

  const isArrested = item.prpt_div_nm === "압류재산";

  useEffect(() => {
    if (!isArrested) {
      setLoading(false);
      return;
    }
    fetchItemTenant(item.cltr_mng_no)
      .then(setTenant)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [item.cltr_mng_no, isArrested]);

  useEffect(() => {
    fetchItemHistory(item.cltr_mng_no)
      .then(setQuals)
      .catch(() => setHistError(true))
      .finally(() => setHistLoading(false));
  }, [item.cltr_mng_no]);

  // 구조적 리스크 4항목
  const risks: RiskItem[] = [
    {
      label: "지분물건 여부",
      status: item.alc_yn === "Y" ? "warn" : "ok",
      description:
        item.alc_yn === "Y"
          ? "지분물건 — 공유자 우선매수권 및 명도 복잡성 주의"
          : "단독 물건",
    },
    {
      label: "수의계약 가능",
      status: item.pvct_trgt_yn === "Y" ? "ok" : "unknown",
      description:
        item.pvct_trgt_yn === "Y"
          ? "수의계약 가능 — 낙찰 실패 시 협의 매수 가능"
          : "수의계약 불가",
    },
    {
      label: "정정 이력",
      status: item.crtn_yn === "Y" ? "warn" : "ok",
      description:
        item.crtn_yn === "Y"
          ? "정정 이력 있음 — 공고 내용 변경 여부 확인 필요"
          : "정정 이력 없음",
    },
    {
      label: "일괄입찰",
      status: item.batc_bid_yn === "Y" ? "warn" : "ok",
      description:
        item.batc_bid_yn === "Y"
          ? "일괄입찰 물건 — 여러 물건을 함께 낙찰받아야 함"
          : "단독 입찰",
    },
  ];

  const warnCount = risks.filter((r) => r.status === "warn").length;

  // DecisionBanner
  let bannerStatus: DecisionStatus = "ok";
  let bannerText = "";
  if (isArrested) {
    bannerText = `압류재산 — 임차인·등기 정보 확인 필수`;
    bannerStatus = warnCount >= 2 ? "danger" : warnCount >= 1 ? "warn" : "warn";
  } else {
    bannerText = `${item.prpt_div_nm} — 임차인 정보는 제공되지 않음. 구조적 리스크 ${warnCount}건`;
    bannerStatus = warnCount >= 2 ? "danger" : warnCount >= 1 ? "warn" : "ok";
  }

  return (
    <div className="flex flex-col gap-6">
      {/* 유찰 회차 내역 */}
      <div>
        <p className="text-sm font-semibold text-text-1 mb-3">유찰 회차 내역</p>
        {histLoading ? (
          <div className="text-sm text-text-4 animate-pulse py-8 text-center">로딩 중...</div>
        ) : histError ? (
          <div className="text-sm text-hot-fg py-8 text-center">입찰 이력을 불러올 수 없습니다.</div>
        ) : quals.length === 0 ? (
          <div className="rounded-lg bg-surface shadow-card text-center py-8 text-xs text-text-4">
            입찰 회차 정보가 없습니다
          </div>
        ) : (
          <BidHistoryGroups quals={quals} />
        )}
      </div>

      <DecisionBanner status={bannerStatus}>{bannerText}</DecisionBanner>

      {/* 임차인 섹션 */}
      {isArrested ? (
        loading ? (
          <div className="text-sm text-text-4 animate-pulse py-8 text-center">로딩 중...</div>
        ) : error || !tenant ? (
          <div className="text-sm text-hot-fg py-8 text-center">임차인 정보를 불러올 수 없습니다.</div>
        ) : (
          <div className="flex flex-col gap-6">
            <Section title="임대차 정보" sectionKey="leas_inf" data={tenant.leas_inf} />
            <Section title="점유 관계" sectionKey="ocpy_rel" data={tenant.ocpy_rel} />
            <Section title="등기사항 주요 정보" sectionKey="rgst_prmr" data={tenant.rgst_prmr} />
            <Section title="배분요구 사항" sectionKey="dtbt_rqr" data={tenant.dtbt_rqr} />
          </div>
        )
      ) : (
        <div className="bg-mid-bg rounded-xl p-6 text-center">
          <p className="text-sm font-semibold text-mid-fg mb-1">임차인 정보 미제공</p>
          <p className="text-xs text-mid-fg/80">
            신탁재산 / 기타일반재산은 온비드 API에서 임차인 정보를 제공하지 않습니다.
          </p>
          <p className="text-xs text-mid-fg/70 mt-1">현재 자산 구분: {item.prpt_div_nm}</p>
        </div>
      )}

      {/* 구조적 리스크 */}
      <div>
        <p className="text-sm font-semibold text-text-1 mb-3">구조적 리스크</p>
        <div className="bg-surface shadow-card rounded-xl divide-y divide-border">
          {risks.map((risk) => (
            <div key={risk.label} className="flex items-center gap-4 px-5 py-3.5">
              <StatusPill status={risk.status} />
              <div className="flex-1">
                <p className="text-sm font-medium text-text-1">{risk.label}</p>
                <p className="text-xs text-text-3 mt-0.5">{risk.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Section({ title, sectionKey, data }: { title: string; sectionKey: string; data: Record<string, unknown>[] }) {
  return (
    <div>
      <p className="text-sm font-semibold text-text-1 mb-2">{title}</p>
      <LabeledTable data={data} columns={SECTION_COLS[sectionKey] ?? []} />
    </div>
  );
}
