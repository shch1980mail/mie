"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

const LINKS = [
  { href: "/", label: "Дашборд" },
  { href: "/scanner", label: "Сканер" },
  { href: "/calendar", label: "Календарь" },
];

export default function Nav() {
  const path = usePathname() ?? "";
  const router = useRouter();
  const [q, setQ] = useState("");

  const go = (e: FormEvent) => {
    e.preventDefault();
    const s = q.trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
    if (s) {
      router.push(`/chart/${s}`);
      setQ("");
    }
  };

  return (
    <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5">
        <Link href="/" className="text-base font-bold tracking-tight text-sky-400">
          MIE<span className="ml-1 hidden font-normal text-slate-500 sm:inline">Market Intelligence</span>
        </Link>
        <nav className="flex gap-1">
          {LINKS.map((l) => {
            const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`rounded-lg px-3 py-1.5 text-sm transition ${
                  active ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <form onSubmit={go} className="ml-auto flex w-full gap-2 sm:w-auto">
          <input
            className="input sm:w-44"
            placeholder="Символ: EURUSD, BTCUSDT"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Открыть символ"
          />
          <button type="submit" className="btn btn-primary">
            Открыть
          </button>
        </form>
      </div>
    </header>
  );
}
