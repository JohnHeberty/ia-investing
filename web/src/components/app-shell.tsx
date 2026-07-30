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
  LogOut,
  Moon,
  Radar,
  RefreshCw,
  TrendingUp,
  Search,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React, { useCallback, useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/components/auth-provider";
import { usePermissions } from "@/hooks/use-permissions";

type NavItem = readonly [string, string, LucideIcon, string | null];

const primary: NavItem[] = [
  ["/", "Missão", CircleGauge, null],
  ["/portfolios", "Carteiras", BriefcaseBusiness, "portfolio:read"],
  ["/opportunities", "Oportunidades", Radar, "research_cases:read"],
  ["/opportunities/candidates", "Candidatos", Search, null],
  ["/opportunities/exploration", "Exploração", Radar, null],
  ["/risk", "Risco", ShieldCheck, null],
  ["/committee", "Comitê", Landmark, "committee:*"],
];

const operations: NavItem[] = [
  ["/policy", "Política", Gavel, "policy:read"],
  ["/macro", "Macro", TrendingUp, "macro:read"],
  ["/paper", "Paper trading", BriefcaseBusiness, "portfolio:read"],
  ["/rebalance", "Rebalance", RefreshCw, "rebalance:*"],
  ["/agents", "Agents", Activity, "agent_runs:read"],
  ["/data-quality", "Qualidade", Database, "quality_incidents:manage"],
  ["/backtests", "Backtests", ChartNoAxesCombined, null],
  ["/audit", "Auditoria", FileCheck2, "audit:read"],
];

const NavGroup = React.memo(function NavGroup({ label, items }: { label: string; items: NavItem[] }) {
  const pathname = usePathname();
  const { can } = usePermissions();

  const visible = items.filter(([, , , permission]) => !permission || can(permission));
  if (visible.length === 0) return null;

  return (
    <div className="nav-group">
      <div className="nav-label">{label}</div>
      {visible.map(([href, labelText, Icon]) => (
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
});

function getInitialTheme(): string {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem("ia-theme");
  return stored === "light" || stored === "dark" ? stored : "dark";
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [theme] = useState(getInitialTheme);
  const isLoginPage = pathname === "/login";

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    if (!loading && !user && !isLoginPage) {
      router.replace("/login");
    }
  }, [loading, user, isLoginPage, router]);

  const toggleTheme = useCallback(() => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    window.localStorage.setItem("ia-theme", next);
  }, []);

  const handleLogout = useCallback(() => {
    logout();
  }, [logout]);

  const handleSearch = useCallback(() => {
    router.push("/opportunities/candidates");
  }, [router]);

  const handleNotifications = useCallback(() => {
    router.push("/audit");
  }, [router]);

  // Login page: minimal layout without sidebar/topbar
  if (isLoginPage) {
    return (
      <main
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          background: "var(--bg)",
        }}
      >
        {children}
      </main>
    );
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
            {user ? (
              <>
                <span style={{ fontWeight: 600, fontSize: 12 }}>{user.name ?? user.subject}</span>
                {(user.roles?.length ?? 0) > 0 && (
                  <span style={{ fontSize: 11, color: "var(--muted)", display: "block" }}>
                    {user.roles.join(", ")}
                  </span>
                )}
              </>
            ) : (
              <>
                Equipe de Investimentos
                <br />
                São Paulo · BRT
              </>
            )}
          </div>
          {user && (
            <button
              className="nav-link"
              onClick={handleLogout}
              type="button"
              aria-label="Sair"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                border: "none",
                background: "none",
                cursor: "pointer",
                width: "100%",
                fontSize: 12,
                color: "var(--muted)",
                padding: "8px 12px",
              }}
            >
              <LogOut size={14} strokeWidth={1.7} />
              <span>Sair</span>
            </button>
          )}
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
            <button className="icon-button" aria-label="Pesquisar" onClick={handleSearch} type="button">
              <Search size={15} />
            </button>
            <button className="icon-button" aria-label="Notificações" onClick={handleNotifications} type="button">
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
