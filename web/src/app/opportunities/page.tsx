"use client";

import { Suspense, useState, useCallback } from "react";
import { FileText, FolderOpen, Plus, X, CheckCircle, AlertTriangle } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { useResearchCases } from "@/hooks/use-research-cases";
import { useUrlState, filterPresets } from "@/hooks/use-url-state";
import { usePermissions } from "@/hooks/use-permissions";
import { commandHeaders } from "@/lib/api";
import { queryKeys } from "@/lib/api-client";

/* ------------------------------------------------------------------ */
/*  New-case form schema                                              */
/* ------------------------------------------------------------------ */
const newCaseSchema = z.object({
  title: z.string().min(3, "Título deve ter pelo menos 3 caracteres"),
  instrument: z.string().min(1, "Instrumento é obrigatório"),
  case_type: z.enum(["fundamental", "macro", "event", "technical"], {
    error: "Selecione um tipo de caso",
  }),
});

type NewCaseFormValues = z.infer<typeof newCaseSchema>;

/* ------------------------------------------------------------------ */
/*  New Case Form component                                           */
/* ------------------------------------------------------------------ */
function NewCaseForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<NewCaseFormValues>({
    defaultValues: { title: "", instrument: "", case_type: undefined },
  });

  const onSubmit = useCallback(
    async (values: NewCaseFormValues) => {
      setSubmitError(null);
      setSubmitSuccess(false);

      const idempotencyKey =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

      try {
        // Check for existing case by instrument (mock search)
        const existingCases = queryClient.getQueryData(
          queryKeys.researchCases(),
        ) as Array<Record<string, unknown>> | undefined;

        const duplicate = existingCases?.find(
          (c) =>
            String(c.instrument_id ?? "").toLowerCase() ===
            values.instrument.toLowerCase(),
        );

        if (duplicate) {
          setSubmitError(
            `Já existe um caso para o instrumento "${values.instrument}". Caso existente: ${String(duplicate.title ?? "Sem título")}`,
          );
          return;
        }

        // POST to create new case
        const response = await fetch("/api/backend/api/v1/research/cases", {
          method: "POST",
          headers: commandHeaders(idempotencyKey),
          body: JSON.stringify({
            title: values.title,
            instrument_id: values.instrument,
            case_type: values.case_type,
            priority: "medium",
            state: "open",
          }),
        });

        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(
            (body as { detail?: string }).detail ?? "Erro ao criar caso",
          );
        }

        setSubmitSuccess(true);
        queryClient.invalidateQueries({ queryKey: queryKeys.researchCases() });

        // Auto-close after brief success feedback
        setTimeout(() => {
          onClose();
          setSubmitSuccess(false);
        }, 1500);
      } catch (err) {
        setSubmitError(
          err instanceof Error ? err.message : "Erro desconhecido",
        );
      }
    },
    [queryClient, onClose],
  );

  return (
    <section
      className="card card-pad"
      style={{ marginTop: 14 }}
      aria-label="Abrir novo caso de pesquisa"
    >
      <div className="card-title">
        <h2>Novo caso de pesquisa</h2>
        <button
          onClick={onClose}
          className="icon-button"
          aria-label="Fechar formulário"
          style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}
        >
          <X size={16} />
        </button>
      </div>

      {submitSuccess ? (
        <div
          role="status"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "12px 16px",
            background: "var(--accent-soft)",
            borderRadius: 8,
            color: "var(--accent)",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          <CheckCircle size={16} />
          Caso criado com sucesso
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Title */}
            <div>
              <label
                htmlFor="case-title"
                style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}
              >
                Título <span aria-hidden="true" style={{ color: "var(--red)" }}>*</span>
              </label>
              <input
                id="case-title"
                type="text"
                aria-required="true"
                aria-invalid={!!errors.title}
                aria-describedby={errors.title ? "case-title-error" : undefined}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "var(--surface-2)",
                  border: `1px solid ${errors.title ? "var(--red)" : "var(--line)"}`,
                  borderRadius: 8,
                  color: "var(--text)",
                  fontSize: 13,
                }}
                placeholder="Ex: Valuation Petrobras PBR"
                {...register("title")}
              />
              {errors.title && (
                <p id="case-title-error" role="alert" style={{ color: "var(--red)", fontSize: 11, marginTop: 4 }}>
                  {errors.title.message}
                </p>
              )}
            </div>

            {/* Instrument */}
            <div>
              <label
                htmlFor="case-instrument"
                style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}
              >
                Instrumento <span aria-hidden="true" style={{ color: "var(--red)" }}>*</span>
              </label>
              <input
                id="case-instrument"
                type="text"
                aria-required="true"
                aria-invalid={!!errors.instrument}
                aria-describedby={errors.instrument ? "case-instrument-error" : undefined}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "var(--surface-2)",
                  border: `1px solid ${errors.instrument ? "var(--red)" : "var(--line)"}`,
                  borderRadius: 8,
                  color: "var(--text)",
                  fontSize: 13,
                }}
                placeholder="Ex: PETR4, USD/BRL"
                {...register("instrument")}
              />
              {errors.instrument && (
                <p id="case-instrument-error" role="alert" style={{ color: "var(--red)", fontSize: 11, marginTop: 4 }}>
                  {errors.instrument.message}
                </p>
              )}
            </div>

            {/* Case type */}
            <div>
              <label
                htmlFor="case-type"
                style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}
              >
                Tipo de caso <span aria-hidden="true" style={{ color: "var(--red)" }}>*</span>
              </label>
              <select
                id="case-type"
                aria-required="true"
                aria-invalid={!!errors.case_type}
                aria-describedby={errors.case_type ? "case-type-error" : undefined}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "var(--surface-2)",
                  border: `1px solid ${errors.case_type ? "var(--red)" : "var(--line)"}`,
                  borderRadius: 8,
                  color: "var(--text)",
                  fontSize: 13,
                }}
                {...register("case_type")}
              >
                <option value="">Selecione...</option>
                <option value="fundamental">Fundamental</option>
                <option value="macro">Macro</option>
                <option value="event">Evento corporativo</option>
                <option value="technical">Técnico</option>
              </select>
              {errors.case_type && (
                <p id="case-type-error" role="alert" style={{ color: "var(--red)", fontSize: 11, marginTop: 4 }}>
                  {errors.case_type.message}
                </p>
              )}
            </div>

            {/* Submit error */}
            {submitError && (
              <div
                role="alert"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 14px",
                  background: "rgb(255 133 127 / 10%)",
                  border: "1px solid rgb(255 133 127 / 30%)",
                  borderRadius: 8,
                  color: "var(--red)",
                  fontSize: 12,
                }}
              >
                <AlertTriangle size={14} />
                {submitError}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={onClose}
                className="button secondary"
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="button"
                disabled={isSubmitting}
                aria-label="Criar caso de pesquisa"
                style={{ opacity: isSubmitting ? 0.6 : 1 }}
              >
                {isSubmitting ? "Criando..." : "Criar caso"}
              </button>
            </div>
          </div>
        </form>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page content                                                 */
/* ------------------------------------------------------------------ */
function OpportunitiesContent() {
  const [urlState, setUrlState] = useUrlState(filterPresets.opportunities);
  const {
    cases,
    openCases,
    researchCases,
    readyForCommittee,
    isLoading,
    isError,
    dataState,
    count,
  } = useResearchCases();
  const { can } = usePermissions();
  const canCreateCase = can("research_cases:create");
  const [showNewCaseForm, setShowNewCaseForm] = useState(false);

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Research funnel</div>
            <h1>Oportunidades</h1>
            <p className="subtitle">
              Triagem auditável por origem, materialidade e evidência disponível.
            </p>
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

  if (isError) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Research funnel</div>
            <h1>Oportunidades</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar oportunidades"
          detail="Não foi possível acessar os casos de pesquisa. Verifique a conexão com a API."
        />
      </>
    );
  }

  const conversionRate =
    count > 0 ? Math.round((readyForCommittee / count) * 100) : 0;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Research funnel</div>
          <h1>Oportunidades</h1>
          <p className="subtitle">
            Triagem auditável por origem, materialidade e evidência disponível.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <AsOfIndicator
            freshness={dataState === "stale" ? "Desatualizado" : "Atual"}
          />
          {canCreateCase ? (
            <button
              className="button"
              onClick={() => setShowNewCaseForm((prev) => !prev)}
              aria-label="Abrir novo caso de pesquisa"
              aria-expanded={showNewCaseForm}
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Plus size={14} />
                Abrir novo caso
              </span>
            </button>
          ) : (
            <Badge tone="neutral">Sem permissão</Badge>
          )}
        </div>
      </div>

      {showNewCaseForm && canCreateCase && (
        <NewCaseForm onClose={() => setShowNewCaseForm(false)} />
      )}

      {dataState === "stale" && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning lastUpdated={new Date().toISOString()} source="research/cases" />
        </div>
      )}

      <section className="grid grid-4" aria-label="Indicadores de oportunidades">
        <Metric
          label="Novas"
          value={String(openCases)}
          note="abertas ou triadas"
        />
        <Metric
          label="Em pesquisa"
          value={String(researchCases)}
          note="análise ativa"
          tone={researchCases > 5 ? "warning" : undefined}
        />
        <Metric
          label="Prontas para comitê"
          value={String(readyForCommittee)}
          note="aguardando decisão"
        />
        <Metric
          label="Convertidas"
          value={`${conversionRate}%`}
          note="janela de 30 dias"
        />
      </section>

      {count === 0 ? (
        <div style={{ marginTop: 14 }}>
          <DataStatePanel
            state="empty"
            title="Nenhum caso de pesquisa encontrado"
            detail="Não existem oportunidades registradas no sistema. Casos são criados automaticamente a partir de sinais fundamentais, eventos corporativos e macro."
            action={
              canCreateCase ? (
                <button
                  className="button"
                  onClick={() => setShowNewCaseForm(true)}
                  aria-label="Abrir primeiro caso de pesquisa"
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <Plus size={14} />
                    Abrir primeiro caso
                  </span>
                </button>
              ) : (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "8px 12px",
                    background: "var(--surface-2)",
                    borderRadius: 6,
                    fontSize: 12,
                    color: "var(--muted)",
                  }}
                >
                  <FolderOpen size={14} />
                  <span>Aguardando sinais para abertura de casos</span>
                </div>
              )
            }
          />
        </div>
      ) : (
        <>
          {/* Research funnel stages */}
          <section className="card card-pad" style={{ marginTop: 14 }}>
            <div className="card-title">
              <h2>Funil de pesquisa</h2>
              <span>{count} caso{count !== 1 ? "s" : ""} total</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <FunnelRow label="Abertos / Triados" value={openCases} total={count} tone="neutral" />
              <FunnelRow label="Em pesquisa" value={researchCases} total={count} tone="warn" />
              <FunnelRow label="Prontos para comitê" value={readyForCommittee} total={count} tone="good" />
            </div>
          </section>

          {/* Cases table */}
          <section className="card card-pad" style={{ marginTop: 14 }}>
            <div className="card-title">
              <h2>Casos de pesquisa</h2>
              <span>{count} registro{count !== 1 ? "s" : ""}</span>
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Título</th>
                    <th>Tipo</th>
                    <th>Prioridade</th>
                    <th>Estado</th>
                    <th>Criado por</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.slice(0, 12).map((c) => (
                    <tr key={c.id}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <FileText size={12} style={{ color: "var(--muted)" }} />
                          <span style={{ fontWeight: 600 }}>{c.title || "Sem título"}</span>
                        </div>
                      </td>
                      <td>
                        <Badge tone="neutral">{c.case_type || "—"}</Badge>
                      </td>
                      <td>
                        <Badge
                          tone={
                            c.priority === "high"
                              ? "bad"
                              : c.priority === "medium"
                                ? "warn"
                                : "neutral"
                          }
                        >
                          {c.priority === "high"
                            ? "Alta"
                            : c.priority === "medium"
                              ? "Média"
                              : c.priority === "low"
                                ? "Baixa"
                                : c.priority || "—"}
                        </Badge>
                      </td>
                      <td>
                        <Badge
                          tone={
                            c.state === "ready_for_committee"
                              ? "good"
                              : c.state === "in_research"
                                ? "warn"
                                : "neutral"
                          }
                        >
                          {c.state === "open"
                            ? "Aberto"
                            : c.state === "triaged"
                              ? "Triado"
                              : c.state === "in_research"
                                ? "Em pesquisa"
                                : c.state === "ready_for_committee"
                                  ? "Pronto"
                                  : c.state}
                        </Badge>
                      </td>
                      <td style={{ color: "var(--muted)", fontSize: 12 }}>
                        {c.created_by || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Info sections */}
          <section className="grid grid-3" style={{ marginTop: 14 }}>
            <article className="card card-pad">
              <div className="card-title">
                <h2>Sinais fundamentais</h2>
                <Badge tone="good">Saudável</Badge>
              </div>
              <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
                Mudanças de métricas e valuation são calculadas sobre dados point-in-time.
              </p>
            </article>
            <article className="card card-pad">
              <div className="card-title">
                <h2>Eventos corporativos</h2>
                <Badge tone="warn">Atenção</Badge>
              </div>
              <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
                Fatos relevantes são deduplicados e classificados antes da abertura de caso.
              </p>
            </article>
            <article className="card card-pad">
              <div className="card-title">
                <h2>Macro e política</h2>
                <Badge tone="good">Saudável</Badge>
              </div>
              <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
                Impactos mostram mecanismo, horizonte, confidence e fontes oficiais.
              </p>
            </article>
          </section>
        </>
      )}
    </>
  );
}

function FunnelRow({
  label,
  value,
  total,
  tone,
}: {
  label: string;
  value: number;
  total: number;
  tone: "neutral" | "warn" | "good";
}) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "8px 0",
        borderTop: "1px solid var(--line-soft)",
        fontSize: 12,
      }}
    >
      <span style={{ minWidth: 160, color: "var(--muted)" }}>{label}</span>
      <div style={{ flex: 1, height: 8, background: "var(--surface-2)", borderRadius: 4, overflow: "hidden" }}>
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background:
              tone === "good" ? "var(--accent)" : tone === "warn" ? "var(--amber)" : "var(--muted-2)",
            borderRadius: 4,
          }}
        />
      </div>
      <span style={{ fontFamily: "var(--font-mono)", minWidth: 32, textAlign: "right" }}>
        {value}
      </span>
    </div>
  );
}

export default function OpportunitiesPage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Research funnel</div>
              <h1>Oportunidades</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <OpportunitiesContent />
    </Suspense>
  );
}
