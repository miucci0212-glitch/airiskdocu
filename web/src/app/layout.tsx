import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 위험성평가 도우미",
  description: "불시 · 단발성 작업용 위험성평가서 자동 작성",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
