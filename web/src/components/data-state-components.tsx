"use client";

import { AlertTriangle, Clock, Database, ShieldAlert, WifiOff, XCircle } from "lucide-react";
import type { ReactNode } from "react";

import type { DataState } from "@/components/domain";

/**
 * Data state configuration with icons, messages, and actions.
 */
const stateConfig: Record<
  DataState,
  {
    icon: ReactNode;
    title: string;
    detail: string;
    variant: "warning" | "error" | "info";
  }
> = {
  empty: {
    icon: <Database size={20} />,
    title: "Sem dados disponíveis",
    detail: "Nenhum registro encontrado para os filtros selecionados.",
    variant: "info",
  },
  missing: {
    icon: <XCircle size={20} />,
    title: "Dado ausente",
    detail: "Este dado nunca foi coletado ou processado. Zero não substitui dado faltante.",
    variant: "info",
  },
  stale: {
    icon: <Clock size={20} />,
    title: "Dados desatualizados",
    detail: "A fonte ultrapassou a janela de freshness. O dado pode não refletir o estado atual.",
    variant: "warning",
  },
  partial: {
    icon: <AlertTriangle size={20} />,
    title: "Dados parciais",
    detail: "Apenas parte do conjunto de dados está disponível. Resultados podem estar incompletos.",
    variant: "warning",
  },
  quarantined: {
    icon: <ShieldAlert size={20} />,
    title: "Dados em quarentena",
    detail: "Este dado foi sinalizado como potencialmente inconsistente e está sob investigação.",
    variant: "warning",
  },
  forbidden: {
    icon: <ShieldAlert size={20} />,
    title: "Sem permissão",
    detail: "Você não tem acesso a estes dados. Solicite acesso ao administrador.",
    variant: "error",
  },
  error: {
    icon: <WifiOff size={20} />,
    title: "Erro ao carregar",
    detail: "Não foi possível acessar o dado. Tente novamente ou entre em contato com suporte.",
    variant: "error",
  },
};

/**
 * Full-page or section data state display.
 * Shows appropriate icon, message, and optional action for each state.
 */
export function DataStatePanel({
  state,
  title,
  detail,
  action,
}: {
  state: DataState;
  title?: string;
  detail?: string;
  action?: ReactNode;
}) {
  const config = stateConfig[state];
  const bgColor =
    config.variant === "error"
      ? "var(--red)"
      : config.variant === "warning"
        ? "var(--amber)"
        : "var(--blue)";
  return (
    <div
      className="state-panel"
      data-state={state}
      role={config.variant === "error" ? "alert" : "status"}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        textAlign: "center",
        padding: "32px 24px",
        gap: 12,
      }}
    >
      <div style={{ color: bgColor, opacity: 0.8 }}>{config.icon}</div>
      <strong style={{ fontSize: 14 }}>{title ?? config.title}</strong>
      <span style={{ color: "var(--muted)", fontSize: 12, maxWidth: 400, lineHeight: 1.6 }}>
        {detail ?? config.detail}
      </span>
      {action && <div style={{ marginTop: 8 }}>{action}</div>}
    </div>
  );
}

/**
 * Inline loading skeleton with shimmer effect.
 */
export function LoadingSkeleton({
  lines = 3,
  style,
}: {
  lines?: number;
  style?: React.CSSProperties;
}) {
  return (
    <div
      role="status"
      aria-label="Carregando"
      style={{ display: "flex", flexDirection: "column", gap: 8, ...style }}
    >
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          style={{
            height: 12,
            background: "var(--surface-2)",
            borderRadius: 6,
            width: `${70 + (i % 3) * 10}%`,
            animation: "pulse 1.5s ease-in-out infinite",
          }}
        />
      ))}
      <span className="sr-only">Carregando conteúdo...</span>
    </div>
  );
}

/**
 * Stale data warning banner.
 */
export function StaleWarning({
  lastUpdated,
  source,
}: {
  lastUpdated: string;
  source?: string;
}) {
  return (
    <div
      role="alert"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 12px",
        background: "var(--amber)",
        color: "var(--bg)",
        borderRadius: 6,
        fontSize: 12,
        fontWeight: 500,
      }}
    >
      <Clock size={14} />
      <span>
        Dados desatualizados desde {new Date(lastUpdated).toLocaleString("pt-BR")}
        {source && ` (fonte: ${source})`}
      </span>
    </div>
  );
}

/**
 * Partial data indicator with coverage info.
 */
export function PartialDataIndicator({
  coverage,
  missingFields,
}: {
  coverage: number;
  missingFields?: string[];
}) {
  return (
    <div
      role="status"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 12px",
        background: "var(--amber)",
        color: "var(--bg)",
        borderRadius: 6,
        fontSize: 12,
      }}
    >
      <AlertTriangle size={14} />
      <span>
        Dados parciais — {Math.round(coverage)}% de cobertura
        {missingFields && missingFields.length > 0 && (
          <> · Ausentes: {missingFields.join(", ")}</>
        )}
      </span>
    </div>
  );
}
