import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "Market Intelligence Engine",
  description: "Анализ рынка: свечи, технический и фундаментальный анализ, мультитаймфрейм",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#020617",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <Nav />
        <main className="mx-auto max-w-7xl px-4 py-5">{children}</main>
        <footer className="mx-auto max-w-7xl px-4 pb-8 pt-2 text-center text-[11px] leading-snug text-slate-600">
          Информационный инструмент. Не является инвестиционной рекомендацией. Вероятности и E[R] оценочные и не
          учитывают спред, комиссии и проскальзывание. Торговля связана с риском потери капитала.
        </footer>
      </body>
    </html>
  );
}
