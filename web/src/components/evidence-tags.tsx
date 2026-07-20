import type { ReactNode } from "react";

/**
 * Fact / Inference / Recommendation tag.
 * Semantically separates what is known from what is inferred or suggested.
 */
export function EvidenceTag({
  kind,
  children,
}: {
  kind: "fact" | "inference" | "recommendation";
  children: ReactNode;
}) {
  const config = {
    fact: { label: "Fato", tone: "good" as const },
    inference: { label: "Inferência", tone: "warn" as const },
    recommendation: { label: "Recomendação", tone: "neutral" as const },
  };
  const { label, tone } = config[kind];
  return (
    <span
      className="badge"
      data-tone={tone}
      title={kind === "fact" ? "Dado verificado e citável" : kind === "inference" ? "Dedução do agent" : "Sugestão de ação"}
    >
      {label}: {children}
    </span>
  );
}

/**
 * Confidence bar with percentage and visual indicator.
 */
export function ConfidenceBar({
  value,
  label,
  showPercent = true,
}: {
  value: number;
  label?: string;
  showPercent?: boolean;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const tone = clamped >= 80 ? "good" : clamped >= 50 ? "warn" : "bad";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
      {label && <span style={{ color: "var(--muted)", minWidth: 80 }}>{label}</span>}
      <div className="bar" style={{ flex: 1 }}>
        <span
          style={{
            width: `${clamped}%`,
            background: tone === "good" ? "var(--accent)" : tone === "warn" ? "var(--amber)" : "var(--red)",
          }}
        />
      </div>
      {showPercent && (
        <span style={{ fontFamily: "var(--font-mono)", minWidth: 32, textAlign: "right" }}>
          {clamped}%
        </span>
      )}
    </div>
  );
}

/**
 * Freshness pill showing data age with semantic color.
 */
export function FreshnessPill({
  retrievedAt,
  maxAgeHours = 24,
}: {
  retrievedAt: string;
  maxAgeHours?: number;
}) {
  const age = Date.now() - new Date(retrievedAt).getTime();
  const hours = age / (1000 * 60 * 60);
  const label =
    hours < 1
      ? "Atual"
      : hours < maxAgeHours
        ? `${Math.round(hours)}h`
        : hours < maxAgeHours * 7
          ? `${Math.round(hours / 24)}d`
          : "Stale";
  const tone = hours < maxAgeHours ? "good" : hours < maxAgeHours * 3 ? "warn" : "bad";
  return (
    <span
      className="badge"
      data-tone={tone}
      title={`Última atualização: ${new Date(retrievedAt).toLocaleString("pt-BR")}`}
    >
      {label}
    </span>
  );
}

/**
 * Mandate badge showing portfolio mandate status.
 */
export function MandateBadge({
  status,
}: {
  status: "approved" | "paper_live" | "committee" | "simulated" | "ineligible";
}) {
  const config = {
    approved: { label: "Aprovada", tone: "good" as const },
    paper_live: { label: "Paper live", tone: "good" as const },
    committee: { label: "Comitê", tone: "warn" as const },
    simulated: { label: "Simulada", tone: "neutral" as const },
    ineligible: { label: "Inelegível", tone: "bad" as const },
  };
  const { label, tone } = config[status];
  return (
    <span className="badge" data-tone={tone}>
      {label}
    </span>
  );
}

/**
 * Quality indicator showing data quality score with visual feedback.
 */
export function QualityIndicator({
  score,
  label = "Qualidade",
}: {
  score: number;
  label?: string;
}) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const tone = clamped >= 90 ? "good" : clamped >= 70 ? "warn" : "bad";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
      <span style={{ color: "var(--muted)" }}>{label}</span>
      <span
        className="badge"
        data-tone={tone}
        style={{ fontFamily: "var(--font-mono)" }}
      >
        {clamped}%
      </span>
    </div>
  );
}
