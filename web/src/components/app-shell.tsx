"use client";

import {
  Activity,
  Bell,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  CircleGauge,
  Database,
  FileCheck2,
  Gavel,
  Landmark,
  Moon,
  Radar,
  TrendingUp,
  Search,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, type ReactNode } from "react";

type NavItem = readonly [string, string, LucideIcon];

const primary = [
  ["/", "Missão", CircleGauge],
  ["/portfolios/demo", "Carteiras", BriefcaseBusiness],
  ["/opportunities", "Oportunidades", Radar],
  ["/risk", "Risco", ShieldCheck],
  ["/committee", "Comitê", Landmark],
] as const satisfies readonly NavItem[];
const operations = [
  ["/policy", "Política", Gavel],
  ["/macro", "Macro", TrendingUp],
  ["/paper", "Paper trading", BriefcaseBusiness],
  ["/agents", "Agents", Activity],
  ["/data-quality", "Qualidade", Database],
  ["/backtests", "Backtests", ChartNoAxesCombined],
  ["/audit", "Auditoria", FileCheck2],
] as const satisfies readonly NavItem[];

function NavGroup({ label, items }: { label: string; items: readonly NavItem[] }) {
  const pathname = usePathname();
  return (
    <div className="nav-group">
      <div className="nav-label">{label}</div>
      {items.map(([href, labelText, Icon]) => (
        <Link
          aria-current={
            pathname === href || (href !== "/" && pathname.startsWith(href.split("/demo")[0]))
              ? "page"
              : undefined
          }
          aria-label={labelText}
          className="nav-link"
          data-active={
            pathname === href || (href !== "/" && pathname.startsWith(href.split("/demo")[0]))
          }
          href={href as Route}
          key={href}
        >
          <Icon size={16} strokeWidth={1.7} aria-hidden="true" />
          <span>{labelText}</span>
        </Link>
      ))}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  useEffect(() => {
    const stored = window.localStorage.getItem("ia-theme");
    const initial = stored === "light" || stored === "dark" ? stored : "dark";
    document.documentElement.dataset.theme = initial;
  }, []);

  function toggleTheme() {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    window.localStorage.setItem("ia-theme", next);
  }

  return (
    <div className="shell">
      <aside className="sidebar" aria-label="Navegação principal">
        <Link href="/" className="brand">
          <div className="brand-mark">IA</div>
          <div className="brand-copy">
            <strong>INVESTING OS</strong>
            <span>institutional research</span>
          </div>
        </Link>
        <NavGroup label="Decisão" items={primary} />
        <NavGroup label="Operações" items={operations} />
        <div className="sidebar-foot">
          <div className="environment">● Paper environment</div>
          <div className="identity">
            Equipe de Investimentos
            <br />
            São Paulo · BRT
          </div>
        </div>
      </aside>
      <main className="main">
        {process.env.NEXT_PUBLIC_ENABLE_DEMO_DATA === "true" && (
          <div className="demo-banner">Dados de demonstração — nenhuma decisão ou ordem real</div>
        )}
        <header className="topbar">
          <div className="breadcrumb">
            Organização / <strong>Brasil Long Only</strong>
          </div>
          <div className="top-actions">
            <button className="icon-button" aria-label="Pesquisar">
              <Search size={15} />
            </button>
            <button className="icon-button" aria-label="Notificações">
              <Bell size={15} />
            </button>
            <button
              className="icon-button"
              aria-label="Alternar tema claro ou escuro"
              onClick={toggleTheme}
              type="button"
            >
              <Moon size={15} />
            </button>
          </div>
        </header>
        <div className="content">{children}</div>
      </main>
    </div>
  );
}
