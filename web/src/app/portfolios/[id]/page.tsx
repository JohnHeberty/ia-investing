"use client";

import { useParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { AlertTriangle, Shield, Clock, FileText, TrendingUp, TrendingDown, Scale, Activity, Zap, AlertCircle, CheckCircle2, XCircle } from "lucide-react";

import { AsOfIndicator, Badge, DomainTabs, Metric, StatePanel } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { ConfidenceBar, EvidenceTag, FreshnessPill } from "@/components/evidence-tags";
import {
  PortfolioDiff,
  ScenarioWaterfall,
  ApprovalCard,
  type DiffEntry,
  type ScenarioEntry,
} from "@/components/decision-components";
import { usePortfolio } from "@/hooks/use-portfolios";
import { useUrlState, filterPresets } from "@/hooks/use-url-state";

// --- Mock data for demonstration (would come from API in production) ---
const mockTheses = [
  {
    id: "t1",
    title: "Expansão infraestrutura verde",
    kind: "recommendation" as const,
    confidence: 85,
    summary: "Investimento em energias renováveis apresenta retorno superior ao CDI no horizonte de 24 meses.",
    author: "Analyst Alpha",
    date: "2026-07-15",
  },
  {
    id: "t2",
    title: "Risco de juros nos EUA",
    kind: "inference" as const,
    confidence: 72,
    summary: "Projeção de alta de 50bps na próxima reunião Fed impacta ativosEmergentes.",
    author: "Agent Beta",
    date: "2026-07-14",
  },
  {
    id: "t3",
    title: "PIB Brasil Q2 2026",
    kind: "fact" as const,
    confidence: 98,
    summary: "PIB cresceu 0.4% no trimestre, acima da mediana de mercado de 0.3%.",
    author: "Fonte oficial",
    date: "2026-07-10",
  },
];

const mockAuditTrail = [
  { id: "a1", action: "Rebalanceamento aprovado", user: "Committee", timestamp: "2026-07-18T14:30:00Z", details: "Alocação VALE3 ajustada de 5% para 7%" },
  { id: "a2", action: "Limite de concentração ajustado", user: "Risk Manager", timestamp: "2026-07-17T10:15:00Z", details: "Teto de Setor aumentado de 25% para 30%" },
  { id: "a3", action: "Snapshot publicado", user: "System", timestamp: "2026-07-16T09:00:00Z", details: "Versão lock 42 criada automaticamente" },
  { id: "a4", action: "Mandato revisado", user: "Compliance", timestamp: "2026-07-15T16:45:00Z", details: "Novo limite de alavancagem: 1.2x" },
];

const mockRiskLimits = [
  { id: "r1", name: "Concentração por ativo", limit: 10, current: 7.2, unit: "%", status: "ok" as const },
  { id: "r2", name: "Concentração por setor", limit: 30, current: 28.5, unit: "%", status: "warning" as const },
  { id: "r3", name: "Alavancagem máxima", limit: 1.2, current: 1.15, unit: "x", status: "ok" as const },
  { id: "r4", name: "Drawdown máximo", limit: 15, current: 12.3, unit: "%", status: "ok" as const },
  { id: "r5", name: "Exposição Moody", limit: 20, current: 22.1, unit: "%", status: "breach" as const },
];

const mockBreaches = [
  { id: "b1", limit: "Exposição Moody", type: "hard" as const, date: "2026-07-18T11:00:00Z", value: 22.1, threshold: 20 },
  { id: "b2", limit: "Concentração setor", type: "soft" as const, date: "2026-07-17T09:30:00Z", value: 28.5, threshold: 30 },
];

const mockExposures = [
  { name: "Ações BR", value: 45.2 },
  { name: "Renda Fixa", value: 32.1 },
  { name: "Ações EUA", value: 12.3 },
  { name: "Alternativos", value: 6.8 },
  { name: "Caixa", value: 3.6 },
];

const mockStressScenarios: ScenarioEntry[] = [
  { name: "Crise 2008", impact: -0.18, cumulative: -0.18 },
  { name: "COVID Crash", impact: -0.12, cumulative: -0.30 },
  { name: "Alta juros +500bps", impact: -0.08, cumulative: -0.38 },
  { name: "Default soberania", impact: -0.22, cumulative: -0.60 },
  { name: "Rally tech", impact: 0.15, cumulative: -0.45 },
];

const mockDiffEntries: DiffEntry[] = [
  { ticker: "PETR4", name: "Petrobras PN", currentWeight: 5.0, targetWeight: 7.0, action: "buy" },
  { ticker: "VALE3", name: "Vale ON", currentWeight: 8.0, targetWeight: 6.5, action: "sell" },
  { ticker: "ITUB4", name: "Itaú Unibanco PN", currentWeight: 4.5, targetWeight: 4.5, action: "hold" },
  { ticker: "WEGE3", name: "WEG ON", currentWeight: 0, targetWeight: 3.0, action: "new" },
  { ticker: "ABEV3", name: "Ambev ON", currentWeight: 3.5, targetWeight: 0, action: "exit" },
];

const mockConstraints = [
  { name: "Concentração máxima por ativo", limit: "10%", current: "7.2%", passed: true },
  { name: "Concentração máxima por setor", limit: "30%", current: "28.5%", passed: true },
  { name: "Número mínimo de ativos", limit: "15", current: "18", passed: true },
  { name: "Alavancagem máxima", limit: "1.2x", current: "1.15x", passed: true },
];

export function PortfolioContent({ id }: { id: string }) {
  const { portfolio, isLoading, isError, dataState } = usePortfolio(id);
  const [urlState, setUrlState] = useUrlState(filterPresets.portfolio);
  const [actionState, setActionState] = useState<"idle" | "stress-requested" | "waiver-requested">("idle");

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Portfolio 360</div>
            <h1>Carregando…</h1>
          </div>
        </div>
        <section className="grid grid-4">
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
        </section>
      </>
    );
  }

  if (isError || !portfolio) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Portfolio 360</div>
            <h1>Carteira não encontrada</h1>
          </div>
        </div>
        <DataStatePanel
          state={dataState}
          title="Erro ao carregar carteira"
          detail="Não foi possível acessar os dados desta carteira. Verifique o ID ou tente novamente."
        />
      </>
    );
  }

  const name = String(portfolio.name ?? "Carteira");
  const state = String(portfolio.state ?? "");
  const currency = String(portfolio.base_currency ?? "BRL");
  const environment = String(portfolio.environment ?? "");
  const updatedAt = String(portfolio.updated_at ?? portfolio.created_at ?? "");
  const mandateId = String(portfolio.mandate_id ?? "");
  const lockVersion = String(portfolio.lock_version ?? "0");
  const ownerTeamId = String(portfolio.owner_team_id ?? "");
  const organizationId = String(portfolio.organization_id ?? "");
  const createdAt = String(portfolio.created_at ?? "");
  const benchmark = String(portfolio.benchmark ?? "Ibovespa");
  const navReconciled = portfolio.nav_reconciled !== false;
  const methodology = String(portfolio.methodology ?? "nav-v1");

  const stateTone =
    state === "active" ? "good" : state === "draft" ? "warn" : "neutral";
  const stateLabel =
    state === "active" ? "Ativa" : state === "draft" ? "Rascunho" : state;

  // Calculate risk metrics
  const hardBreaches = mockBreaches.filter((b) => b.type === "hard").length;
  const softBreaches = mockBreaches.filter((b) => b.type === "soft").length;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Portfolio 360</div>
          <h1>{name}</h1>
          <p className="subtitle">
            Carteira-modelo · {currency} · ambiente {environment} · mandato {mandateId.slice(0, 8) || "—"}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Badge tone={stateTone}>{stateLabel}</Badge>
          {updatedAt && <FreshnessPill retrievedAt={updatedAt} maxAgeHours={1} />}
          <AsOfIndicator
            value={updatedAt ? new Date(updatedAt).toLocaleString("pt-BR") : "—"}
            freshness={dataState === "stale" ? "Desatualizado" : "Atual"}
          />
        </div>
      </div>

      {dataState === "stale" && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning lastUpdated={updatedAt} source="model-portfolios" />
        </div>
      )}

      <section className="grid grid-4">
        <Metric label="Moeda base" value={currency} note={`Código: ${currency}`} />
        <Metric
          label="Estado"
          value={stateLabel}
          note={`Ambiente: ${environment}`}
          tone={stateTone}
        />
        <Metric
          label="Benchmark"
          value={benchmark}
          note="Índice de referência"
        />
        <Metric
          label="NAV Reconciliado"
          value={navReconciled ? "Sim" : "Não"}
          note={navReconciled ? "Conferido automaticamente" : "Pendente de conciliação"}
          tone={navReconciled ? "positive" : "warning"}
        />
      </section>

      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Mandato</h2>
            <Badge tone="neutral">v{mandateId.slice(0, 8) || "—"}</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Mandato vinculado: {mandateId || "Não definido"}.
            A carteira opera sob as restrições e limites definidos pelo mandato.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Ownership</h2>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Time responsável: {ownerTeamId || "Não atribuído"}.
            Organização: {organizationId || "—"}.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Temporalidade</h2>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Criado em: {createdAt ? new Date(createdAt).toLocaleString("pt-BR") : "—"}.
            Atualizado em: {updatedAt ? new Date(updatedAt).toLocaleString("pt-BR") : "—"}.
          </p>
        </article>
      </section>

      <DomainTabs
        label="Detalhes da carteira"
        tabs={[
          {
            id: "positions",
            label: "Posições",
            content: (
              <StatePanel
                title="Posições"
                detail="Snapshot point-in-time reconciliado. As posições são resolvidas pelo instrumento e preço no cutoff."
              />
            ),
          },
          {
            id: "performance",
            label: "Performance",
            content: (
              <div>
                <div className="card card-pad" style={{ marginBottom: 14 }}>
                  <div className="card-title">
                    <h2>NAV e benchmark</h2>
                    <Badge tone="neutral">{methodology}</Badge>
                  </div>
                  <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
                    Metodologia: {methodology}, mesma moeda e mesmo cutoff.
                    Benchmark: {benchmark}.
                  </p>
                  <div style={{ marginTop: 12 }}>
                    <ConfidenceBar value={navReconciled ? 100 : 0} label="Conciliação" />
                  </div>
                </div>
                <StatePanel
                  title="Curva de performance"
                  detail="Gráfico de rendimento acumulado versus benchmark será exibido aqui."
                />
              </div>
            ),
          },
          {
            id: "risk",
            label: "Risco",
            content: (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {/* Risk Limits Table */}
                <div className="card card-pad">
                  <div className="card-title">
                    <h2>Limites de risco</h2>
                    <div style={{ display: "flex", gap: 6 }}>
                      <Badge tone="good">{mockRiskLimits.filter((l) => l.status === "ok").length} OK</Badge>
                      <Badge tone="warn">{mockRiskLimits.filter((l) => l.status === "warning").length} Alerta</Badge>
                      <Badge tone="bad">{mockRiskLimits.filter((l) => l.status === "breach").length} Violação</Badge>
                    </div>
                  </div>
                  <div className="table-wrap">
                    <table className="table" role="table" aria-label="Limites de risco">
                      <thead>
                        <tr>
                          <th scope="col">Limite</th>
                          <th scope="col" className="numeric">Limite</th>
                          <th scope="col" className="numeric">Atual</th>
                          <th scope="col">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {mockRiskLimits.map((limit) => (
                          <tr key={limit.id}>
                            <td>{limit.name}</td>
                            <td className="numeric" style={{ fontFamily: "var(--font-mono)" }}>
                              {limit.limit}{limit.unit}
                            </td>
                            <td className="numeric" style={{ fontFamily: "var(--font-mono)" }}>
                              {limit.current}{limit.unit}
                            </td>
                            <td>
                              <Badge
                                tone={
                                  limit.status === "ok"
                                    ? "good"
                                    : limit.status === "warning"
                                      ? "warn"
                                      : "bad"
                                }
                              >
                                {limit.status === "ok"
                                  ? "Dentro"
                                  : limit.status === "warning"
                                    ? "Próximo"
                                    : "Violação"}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Breach History */}
                {mockBreaches.length > 0 && (
                  <div className="card card-pad">
                    <div className="card-title">
                      <h2>Histórico de violações</h2>
                      <Badge tone={hardBreaches > 0 ? "bad" : "warn"}>
                        {hardBreaches} hard · {softBreaches} soft
                      </Badge>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {mockBreaches.map((breach) => (
                        <div
                          key={breach.id}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            padding: "8px 12px",
                            background: "var(--surface-2)",
                            borderRadius: 6,
                            fontSize: 12,
                          }}
                        >
                          {breach.type === "hard" ? (
                            <XCircle size={14} style={{ color: "var(--red)" }} />
                          ) : (
                            <AlertCircle size={14} style={{ color: "var(--amber)" }} />
                          )}
                          <div style={{ flex: 1 }}>
                            <strong>{breach.limit}</strong>
                            <span style={{ color: "var(--muted)", marginLeft: 8 }}>
                              {breach.value}{breach.threshold < 10 ? "x" : "%"} / {breach.threshold}{breach.threshold < 10 ? "x" : "%"}
                            </span>
                          </div>
                          <Badge tone={breach.type === "hard" ? "bad" : "warn"}>
                            {breach.type === "hard" ? "Hard" : "Soft"}
                          </Badge>
                          <time style={{ color: "var(--muted)" }}>
                            {new Date(breach.date).toLocaleString("pt-BR")}
                          </time>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Concentration Exposures */}
                <div className="card card-pad">
                  <div className="card-title">
                    <h2>Exposções por classe</h2>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {mockExposures.map((exp) => (
                      <div key={exp.name} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
                        <span style={{ minWidth: 120, color: "var(--muted)" }}>{exp.name}</span>
                        <div style={{ flex: 1 }}>
                          <ConfidenceBar value={exp.value} showPercent={false} />
                        </div>
                        <span style={{ fontFamily: "var(--font-mono)", minWidth: 40, textAlign: "right" }}>
                          {exp.value}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Stress Scenarios */}
                <ScenarioWaterfall scenarios={mockStressScenarios} />

                {/* Authorized Actions */}
                <div className="card card-pad">
                  <div className="card-title">
                    <h2>Ações autorizadas</h2>
                  </div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button
                      className="btn"
                      onClick={() => setActionState("stress-requested")}
                      disabled={actionState === "stress-requested"}
                      aria-label="Solicitar stress adicional"
                    >
                      <Zap size={14} />
                      Solicitar stress adicional
                    </button>
                    <button
                      className="btn"
                      onClick={() => setActionState("waiver-requested")}
                      disabled={actionState === "waiver-requested"}
                      aria-label="Waiver temporário"
                    >
                      <Scale size={14} />
                      Waiver temporário
                    </button>
                  </div>

                  {actionState === "stress-requested" && (
                    <div style={{ marginTop: 12 }}>
                      <ApprovalCard
                        title="Stress adicional solicitado"
                        description="Solicitação de cenário de stress personalizado para esta carteira."
                        status="pending"
                        requestedBy="Portfolio Manager"
                        requestedAt={new Date().toLocaleString("pt-BR")}
                      />
                    </div>
                  )}

                  {actionState === "waiver-requested" && (
                    <div style={{ marginTop: 12 }}>
                      <ApprovalCard
                        title="Waiver temporário"
                        description="Solicitação de suspensão temporária do limite de concentração Moody."
                        status="pending"
                        requestedBy="Risk Manager"
                        requestedAt={new Date().toLocaleString("pt-BR")}
                        conditions={["Revisão em 30 dias", "Cobertura de hedge obrigatória"]}
                      />
                    </div>
                  )}
                </div>
              </div>
            ),
          },
          {
            id: "theses",
            label: "Teses",
            content: (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div className="card card-pad">
                  <div className="card-title">
                    <h2>Teses e propostas</h2>
                    <span>{mockTheses.length} vinculadas</span>
                  </div>
                  <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65, marginBottom: 12 }}>
                    Teses e propostas vinculadas a esta carteira. Nova proposta pode estar bloqueada até revisão independente.
                  </p>
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {mockTheses.map((thesis) => (
                      <article
                        key={thesis.id}
                        style={{
                          padding: "12px 14px",
                          background: "var(--surface-2)",
                          borderRadius: 8,
                          borderLeft: `3px solid ${
                            thesis.kind === "fact"
                              ? "var(--accent)"
                              : thesis.kind === "inference"
                                ? "var(--amber)"
                                : "var(--blue)"
                          }`,
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                          <strong style={{ fontSize: 13 }}>{thesis.title}</strong>
                          <EvidenceTag kind={thesis.kind}>{thesis.kind === "fact" ? "Dado verificado" : thesis.kind === "inference" ? "Dedução" : "Sugestão"}</EvidenceTag>
                        </div>
                        <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.6, margin: "0 0 8px 0" }}>
                          {thesis.summary}
                        </p>
                        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 11 }}>
                          <ConfidenceBar value={thesis.confidence} label="Confiança" />
                          <span style={{ color: "var(--muted)" }}>·</span>
                          <span style={{ color: "var(--muted)" }}>{thesis.author}</span>
                          <span style={{ color: "var(--muted)" }}>·</span>
                          <time style={{ color: "var(--muted)" }}>{thesis.date}</time>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              </div>
            ),
          },
          {
            id: "audit",
            label: "Auditoria",
            content: (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div className="card card-pad">
                  <div className="card-title">
                    <h2>Trilha de auditoria</h2>
                    <span>{mockAuditTrail.length} eventos</span>
                  </div>
                  <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65, marginBottom: 12 }}>
                    Mandato, snapshots, decisão e publicação vinculados. Rastreabilidade completa preservada.
                  </p>
                  <div className="timeline" role="list" aria-label="Histórico de auditoria">
                    {mockAuditTrail.map((entry) => (
                      <div key={entry.id} className="event" role="listitem">
                        <div className="event-icon">
                          {entry.action.includes("aprovado") ? (
                            <CheckCircle2 size={12} />
                          ) : entry.action.includes("ajustado") ? (
                            <Activity size={12} />
                          ) : entry.action.includes("publicado") ? (
                            <FileText size={12} />
                          ) : (
                            <Clock size={12} />
                          )}
                        </div>
                        <div>
                          <strong>{entry.action}</strong>
                          <p>{entry.details}</p>
                        </div>
                        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
                          <time>
                            {new Date(entry.timestamp).toLocaleString("pt-BR")}
                          </time>
                          <span style={{ fontSize: 10, color: "var(--muted)" }}>{entry.user}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ),
          },
        ]}
      />

      {/* Rebalance Section */}
      <section style={{ marginTop: 14 }}>
        <PortfolioDiff entries={mockDiffEntries} />

        {/* Constraint Compliance */}
        <div className="card card-pad" style={{ marginTop: 14 }}>
          <div className="card-title">
            <h2>Conformidade de restrições</h2>
            <Badge tone={mockConstraints.every((c) => c.passed) ? "good" : "bad"}>
              {mockConstraints.every((c) => c.passed) ? "Todos passam" : "Violação detectada"}
            </Badge>
          </div>
          <div className="table-wrap">
            <table className="table" role="table" aria-label="Conformidade de restrições">
              <thead>
                <tr>
                  <th scope="col">Restrição</th>
                  <th scope="col" className="numeric">Limite</th>
                  <th scope="col" className="numeric">Proposto</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {mockConstraints.map((constraint, i) => (
                  <tr key={i}>
                    <td>{constraint.name}</td>
                    <td className="numeric" style={{ fontFamily: "var(--font-mono)" }}>
                      {constraint.limit}
                    </td>
                    <td className="numeric" style={{ fontFamily: "var(--font-mono)" }}>
                      {constraint.current}
                    </td>
                    <td>
                      <Badge tone={constraint.passed ? "good" : "bad"}>
                        {constraint.passed ? "Conforme" : "Violação"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Methodology Footer */}
      <footer style={{ marginTop: 14, padding: "12px 0", borderTop: "1px solid var(--line-soft)", fontSize: 11, color: "var(--muted)" }}>
        <p>
          <strong>Metodologia:</strong> {methodology} · 
          <strong> Benchmark:</strong> {benchmark} · 
          <strong> Moeda:</strong> {currency} · 
          <strong> As of:</strong> {updatedAt ? new Date(updatedAt).toLocaleString("pt-BR") : "—"} · 
          <strong> Lock:</strong> v{lockVersion}
        </p>
        <p style={{ marginTop: 4 }}>
          Dados reconciliados automaticamente. Última conciliação: {updatedAt ? new Date(updatedAt).toLocaleString("pt-BR") : "—"}.
          Para dúvidas, contacte o time de Risk.
        </p>
      </footer>
    </>
  );
}

export default function PortfolioPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";

  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Portfolio 360</div>
              <h1>Carregando…</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <PortfolioContent id={id} />
    </Suspense>
  );
}
