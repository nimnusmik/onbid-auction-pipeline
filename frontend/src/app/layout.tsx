import type { Metadata } from "next";
import AppShell from "@/components/layout/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "온비드 공매 대시보드",
  description: "한국자산관리공사 온비드 공매 물건 투자 분석 대시보드",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full">
      <body className="min-h-full bg-bg">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
