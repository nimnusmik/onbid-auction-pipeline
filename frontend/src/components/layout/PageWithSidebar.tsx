"use client";

import { useEffect, useState } from "react";
import FilterDrawer from "./FilterDrawer";

const STORAGE_KEY = "onbid_sidebar_open";

interface Props {
  sidebar: React.ReactNode;
  children: React.ReactNode;
}

export default function PageWithSidebar({ sidebar, children }: Props) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [desktopOpen, setDesktopOpen] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved != null) setDesktopOpen(saved === "1");
  }, []);

  function toggleDesktop() {
    setDesktopOpen((prev) => {
      const next = !prev;
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }

  return (
    <div className="flex">
      <aside
        className={`relative hidden md:block shrink-0 bg-surface min-h-[calc(100vh-48px)] border-r border-border transition-[width] duration-200 ease-out ${
          desktopOpen ? "w-60" : "w-6"
        }`}
      >
        <button
          onClick={toggleDesktop}
          aria-label={desktopOpen ? "필터 접기" : "필터 펼치기"}
          title={desktopOpen ? "필터 접기" : "필터 펼치기"}
          className="absolute top-3 right-1 w-5 h-5 flex items-center justify-center text-xs text-text-3 hover:text-primary rounded z-10"
        >
          <span aria-hidden>{desktopOpen ? "◀" : "▶"}</span>
        </button>
        <div className={`w-60 ${desktopOpen ? "block" : "hidden"}`}>{sidebar}</div>
      </aside>
      <FilterDrawer open={mobileOpen} onClose={() => setMobileOpen(false)}>
        {sidebar}
      </FilterDrawer>
      <main className="flex-1 min-w-0 p-4 md:p-6">
        <button
          onClick={() => setMobileOpen(true)}
          className="md:hidden mb-3 inline-flex items-center gap-2 px-3 py-1.5 text-sm bg-surface shadow-card rounded-md text-text-2"
          aria-label="필터 열기"
        >
          <span aria-hidden>☰</span> 필터
        </button>
        {children}
      </main>
    </div>
  );
}
