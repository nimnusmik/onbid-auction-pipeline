"use client";

import { useEffect } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

export default function FilterDrawer({ open, onClose, children }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <>
      <div
        className={`md:hidden fixed inset-0 z-40 bg-text-1/50 transition-opacity ${
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-hidden={!open}
        className={`md:hidden fixed top-0 left-0 bottom-0 z-50 w-72 bg-surface shadow-drawer p-4 transition-transform ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-text-1">필터</h2>
          <button
            onClick={onClose}
            className="text-text-3 hover:text-text-1 text-lg"
            aria-label="닫기"
          >
            ✕
          </button>
        </div>
        <div className="overflow-y-auto max-h-[calc(100vh-4rem)]">
          {children}
        </div>
      </aside>
    </>
  );
}
