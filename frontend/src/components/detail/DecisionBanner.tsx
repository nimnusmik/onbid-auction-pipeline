// frontend/src/components/detail/DecisionBanner.tsx
"use client";

import type { ReactNode } from "react";

export type DecisionStatus = "ok" | "warn" | "danger";

interface Props {
  status: DecisionStatus;
  icon?: ReactNode;
  children: ReactNode;
}

const STYLE: Record<DecisionStatus, string> = {
  ok: "bg-ok-bg text-ok-fg",
  warn: "bg-mid-bg text-mid-fg",
  danger: "bg-hot-bg text-hot-fg",
};

const DEFAULT_ICON: Record<DecisionStatus, string> = {
  ok: "✓",
  warn: "!",
  danger: "⚠",
};

export default function DecisionBanner({ status, icon, children }: Props) {
  return (
    <div
      className={`rounded-lg px-4 py-2.5 text-sm font-medium flex items-center gap-2 ${STYLE[status]}`}
      role="status"
    >
      <span className="font-bold shrink-0">{icon ?? DEFAULT_ICON[status]}</span>
      <span className="flex-1">{children}</span>
    </div>
  );
}
