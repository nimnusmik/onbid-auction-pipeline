"use client";

import { type MouseEvent } from "react";
import type { BidItem } from "@/types";
import { openExternalSite } from "@/utils/externalLinks";

export default function ExternalSiteMenu({ item }: { item: BidItem }) {
  function handleClick(e: MouseEvent) {
    e.stopPropagation();
    void openExternalSite("hogangnono", item);
  }

  return (
    <button
      onClick={handleClick}
      className="text-xs text-primary hover:bg-primary-subtle border border-border-strong hover:border-primary rounded-md px-2 py-1 whitespace-nowrap transition-colors"
    >
      호갱노노 ↗
    </button>
  );
}
