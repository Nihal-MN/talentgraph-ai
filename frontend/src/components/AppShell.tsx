"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const NAV = [
  { href: "/", label: "Search", icon: "🔍" },
  { href: "/rediscovery", label: "Rediscovery", icon: "♻️" },
  { href: "/saved", label: "Saved searches", icon: "🔖" },
  { href: "/evaluation", label: "Evaluation", icon: "📊" },
  { href: "/health", label: "System health", icon: "🩺" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="px-5 py-5">
          <p className="text-base font-bold tracking-tight text-slate-900">
            Talent<span className="text-violet-600">Graph</span> AI
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Semantic talent search &amp; rediscovery
          </p>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  active
                    ? "bg-violet-50 text-violet-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                <span aria-hidden>{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-slate-100 px-5 py-4">
          <p className="text-[11px] leading-relaxed text-slate-400">
            Local demo · synthetic data only.
            <br />
            Human recruiters make decisions.
          </p>
        </div>
      </aside>
      <main className="flex-1 md:pl-60">
        <div className="mx-auto max-w-5xl px-6 py-8">{children}</div>
      </main>
    </div>
  );
}
