"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
  return (
    <Link
      href={href}
      className={
        active
          ? "text-primary font-semibold"
          : "text-text-3 hover:text-text-1 transition-colors"
      }
    >
      {children}
    </Link>
  );
}

export default function TopNav() {
  return (
    <nav className="sticky top-0 z-30 bg-surface border-b border-border h-12 px-4 md:px-6 flex items-center gap-6">
      <Link href="/" className="text-sm font-bold text-primary tracking-tight">
        Onbid
      </Link>
      <div className="flex items-center gap-4 text-sm">
        <NavLink href="/">Overview</NavLink>
        <NavLink href="/analytics">Analytics</NavLink>
        <NavLink href="/bookmark">Bookmark</NavLink>
      </div>
    </nav>
  );
}
