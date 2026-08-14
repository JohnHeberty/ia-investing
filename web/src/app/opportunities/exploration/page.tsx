"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Radar, RefreshCw } from "lucide-react";
import {
  createExplorationRun,
  createExplorationSchedule,
  dismissExplorationSuggestion,
  getExplorationRun,
  listExplorationRuns,
  promoteExplorationSuggestion,
} from "@/lib/candidate-api";
import styles from "@/components/candidates/candidate-intelligence.module.css";
import { ExplorationForm } from "@/components/exploration/ExplorationForm";
import { ScheduleForm } from "@/components/exploration/ScheduleForm";
import { SuggestionCard } from "@/components/exploration/SuggestionCard";
import { DismissDialog } from "@/components/exploration/DismissDialog";

export default function ExplorationPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [workingSuggestion, setWorkingSuggestion] = useState<string | null>(null);
  const [dismissTarget, setDismissTarget] = useState<string | null>(null);
  const [dismissReason, setDismissReason] = useState("");

  const runsQuery = useQuery({
    queryKey: ["exploration-runs"],
    queryFn: () => listExplorationRuns(),
    staleTime: 30_000,
  });

  const runs = runsQuery.data ?? [];
  const effectiveSelectedId = selectedId ?? runs[0]?.id ?? null;

  const selectedQuery = useQuery({
    queryKey: ["exploration-run", effectiveSelectedId],
    queryFn: () => getExplorationRun(effectiveSelectedId!),
    staleTime: 30_000,
    enabled: !!effectiveSelectedId,
  });

  const selected = selectedQuery.data ?? null;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    const form = new FormData(event.currentTarget);
    const strategies = form.getAll("strategy").map(String);
    if (!strategies.length) {
      setError("Selecione ao menos uma estratégia.");
      setSubmitting(false);
      return;
    }
    try {
      const run = await createExplorationRun({
        strategy_codes: strategies,
        minimum_liquidity: String(form.get("minimum_liquidity") || "5000000"),
        maximum_suggestions: Number(form.get("maximum_suggestions") || 20),
      });
      setSuccess(
        `Exploração ${run.id} enfileirada. Nenhuma sugestão entra diretamente em carteira.`,
      );
      setSelectedId(run.id);
      await queryClient.invalidateQueries({ queryKey: ["exploration-runs"] });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao iniciar exploração");
    } finally {
      setSubmitting(false);
    }
  }

  async function createSchedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    const form = new FormData(event.currentTarget);
    const strategies = form.getAll("schedule_strategy").map(String);
    if (!strategies.length) {
      setError("Selecione ao menos uma estratégia para o agendamento.");
      setSubmitting(false);
      return;
    }
    try {
      const schedule = await createExplorationSchedule({
        name: String(form.get("schedule_name") || "weekly-discovery"),
        strategy_codes: strategies,
        minimum_liquidity: String(form.get("schedule_minimum_liquidity") || "5000000"),
        maximum_suggestions: Number(form.get("schedule_maximum_suggestions") || 20),
        interval_hours: Number(form.get("schedule_interval_hours") || 168),
        paused: false,
      });
      setSuccess(
        `Agendamento ${schedule.schedule_id} criado a cada ${schedule.interval_hours} horas.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao criar agendamento");
    } finally {
      setSubmitting(false);
    }
  }

  async function promote(id: string) {
    setWorkingSuggestion(id);
    setError(null);
    try {
      const candidate = await promoteExplorationSuggestion(id);
      setSuccess(
        `${candidate.ticker} foi promovida para candidato e entrou no fluxo completo de investigação.`,
      );
      await queryClient.invalidateQueries({ queryKey: ["exploration-runs"] });
      await queryClient.invalidateQueries({ queryKey: ["exploration-run", effectiveSelectedId] });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao promover sugestão");
    } finally {
      setWorkingSuggestion(null);
    }
  }

  function dismiss(id: string) {
    setDismissTarget(id);
    setDismissReason("");
  }

  async function confirmDismiss() {
    if (!dismissTarget || !dismissReason.trim()) return;
    setWorkingSuggestion(dismissTarget);
    setError(null);
    try {
      await dismissExplorationSuggestion(dismissTarget, dismissReason.trim());
      setSuccess("Sugestão dispensada com justificativa registrada.");
      await queryClient.invalidateQueries({ queryKey: ["exploration-runs"] });
      await queryClient.invalidateQueries({ queryKey: ["exploration-run", effectiveSelectedId] });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao dispensar sugestão");
    } finally {
      setWorkingSuggestion(null);
      setDismissTarget(null);
      setDismissReason("");
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <Link className="breadcrumb" href="/opportunities/candidates">
            <ArrowLeft size={13} /> Voltar para candidatos
          </Link>
          <div className="eyebrow mt-12">Autonomous discovery</div>
          <h1>Exploração de novas ações</h1>
          <p className="subtitle">
            O universo, liquidez, restricted list e cobertura são filtrados em código. O agent
            investiga apenas a shortlist e cria sugestões para o mesmo processo de aprovação.
          </p>
        </div>
        <Radar size={34} />
      </header>

      {error && (
        <div className={styles.error} role="alert">
          {error}
        </div>
      )}
      {success && <div className={styles.success}>{success}</div>}

      <ExplorationForm onSubmit={submit} submitting={submitting} />
      <ScheduleForm onSubmit={createSchedule} submitting={submitting} />

      <section className="card card-pad section-gap">
        <div className="card-title">
          <h2>Execuções e sugestões</h2>
          <button
            className="button secondary"
            type="button"
            onClick={() => void queryClient.invalidateQueries({ queryKey: ["exploration-runs"] })}
            disabled={runsQuery.isFetching}
          >
            <RefreshCw size={14} /> Atualizar
          </button>
        </div>
        {runsQuery.isLoading && <p className="subtitle">Carregando execuções...</p>}
        {!runsQuery.isLoading && !runs.length && <p className="subtitle">Nenhuma exploração executada.</p>}
        {!!runs.length && (
          <div className={styles.toolbar}>
            <label className={styles.field}>
              <span>Execução</span>
              <select
                value={effectiveSelectedId ?? ""}
                onChange={(event) => setSelectedId(event.target.value)}
              >
                {runs.map((run) => (
                  <option key={run.id} value={run.id}>
                    {new Date(run.created_at).toLocaleString("pt-BR")} · {run.status} ·{" "}
                    {run.strategy_codes.join(", ")}
                  </option>
                ))}
              </select>
            </label>
            {selected && (
              <span className="subtitle">
                Universo {selected.run.universe_size} · elegíveis {selected.run.eligible_size} ·
                sugestões {selected.suggestions.length}
              </span>
            )}
          </div>
        )}

        {selected?.run.error_detail && (
          <div className={styles.error}>{selected.run.error_detail}</div>
        )}
        {selected && !selected.suggestions.length && (
          <p className="subtitle">
            A execução ainda não produziu sugestões ou nenhuma ação passou pelos filtros.
          </p>
        )}
        {selected && !!selected.suggestions.length && (
          <div className={`${styles.sourceList} mt-12`}>
            {selected.suggestions.map((item) => (
              <SuggestionCard
                key={item.id}
                item={item}
                workingSuggestion={workingSuggestion}
                onPromote={promote}
                onDismiss={dismiss}
              />
            ))}
          </div>
        )}
      </section>

      <DismissDialog
        open={dismissTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDismissTarget(null);
            setDismissReason("");
          }
        }}
        dismissReason={dismissReason}
        onDismissReasonChange={setDismissReason}
        onConfirm={() => void confirmDismiss()}
      />
    </>
  );
}
