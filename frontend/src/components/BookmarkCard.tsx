"use client";

import { useState } from "react";
import Link from "next/link";
import type { BidItem } from "@/types";
import { fmtAmt, daysLeft } from "@/utils/format";
import { isNewToday } from "@/utils/itemFlags";
import { usageIcon } from "@/utils/usageIcons";
import RatioPill from "@/components/ui/RatioPill";
import DeadlineLabel from "@/components/ui/DeadlineLabel";

export default function BookmarkCard({ item }: { item: BidItem }) {
  const [imgFailed, setImgFailed] = useState(false);
  const dl = daysLeft(item.cltr_bid_end_dt);
  const pvct = dl < 0 && item.pvct_trgt_yn === "Y";
  const hasImg = !!item.thnl_img_url && !imgFailed;
  const isNew = isNewToday(item.first_collected_at);

  return (
    <Link
      href={`/items/${item.cltr_mng_no}`}
      className="group bg-surface shadow-card rounded-xl overflow-hidden flex flex-col hover:shadow-card-hover hover:-translate-y-0.5 transition-all"
    >
      {/* 썸네일 영역 */}
      <div className="relative aspect-[4/3] bg-surface-muted">
        {hasImg ? (
          <img
            src={item.thnl_img_url as string}
            alt={item.onbid_cltr_nm}
            className="w-full h-full object-cover"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-text-4">
            <span className="text-5xl" aria-hidden>
              {usageIcon(item.cltr_usg_mcls_nm)}
            </span>
            <span className="text-xs">{item.cltr_usg_mcls_nm}</span>
          </div>
        )}

        {/* 좌상단: NEW or 수의계약 */}
        <div className="absolute top-2 left-2 flex gap-1">
          {pvct && (
            <span className="text-[10px] bg-mid-bg/95 text-mid-fg rounded px-1.5 py-0.5 font-semibold backdrop-blur-sm">
              수의계약
            </span>
          )}
          {!pvct && isNew && (
            <span className="text-[10px] bg-new/95 text-primary-fg rounded px-1.5 py-0.5 font-bold backdrop-blur-sm">
              NEW
            </span>
          )}
        </div>

        {/* 우상단: ratio */}
        <div className="absolute top-2 right-2 bg-surface/90 backdrop-blur-sm rounded-full">
          <RatioPill ratio={item.ratio_pct} />
        </div>
      </div>

      {/* 정보 영역 */}
      <div className="p-3 flex flex-col gap-1.5 flex-1">
        <div className="text-sm font-semibold text-text-1 line-clamp-2">
          {item.onbid_cltr_nm}
        </div>
        <div className="text-xs text-text-3">
          {item.lctn_sd_nm} {item.lctn_sggn_nm} · {item.cltr_usg_scls_nm}
        </div>
        <div className="flex items-end justify-between mt-auto pt-1">
          <div className="text-base font-bold text-primary tabular-nums">
            {fmtAmt(item.lowst_bid_prc)}
          </div>
          <DeadlineLabel dt={item.cltr_bid_end_dt} pvct={pvct} />
        </div>
        <div className="flex items-center gap-1.5 text-xs">
          {item.usbd_nft > 0 && (
            <span className="bg-mid-bg text-mid-fg rounded px-1.5 py-0.5 font-semibold">
              유찰 {item.usbd_nft}회
            </span>
          )}
          <span className="text-text-4 tabular-nums">
            {Number(item.pbct_nsq)}회차
          </span>
        </div>
      </div>
    </Link>
  );
}
