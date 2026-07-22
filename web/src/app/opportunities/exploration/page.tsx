"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, CheckCircle2, Radar, RefreshCw, ShieldAlert, XCircle } from "lucide-react";
import {
  createExplorationRun,
  createExplorationSchedule,
  dismissExplorationSuggestion,
  getExplorationRun,
  listExplorationRuns,
  promoteExplorationSuggestion,
  type ExplorationDetail,
  type ExplorationRun,
} from "@/lib/candidate-api";
import styles from "@/components/candidates/candidate-intelligence.module.css";

function score(value: string): string {
  return `${(Number(value) * 100).toFixed(0)}%`;
}

export default function ExplorationPage() {
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [runs, setRuns] = useState<ExplorationRun[]>([]);
  const [selected, setSelected] = useState<ExplorationDetail | null>(null);
  const [workingSuggestion, setWorkingSuggestion] = useState<string | null>(null);

  const refresh = useCallback(async (preferredId?: string) => {
    setLoading(true);
    setError(null);
    try {
      const nextRuns = await listExplorationRuns();
      setRuns(nextRuns);
      const runId = preferredId ?? nextRuns[0]?.id;
      if (runId) setSelected(await getExplorationRun(runId));
      else setSelected(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao consultar explorações");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

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
        minimum_liquidity: String(form.get("minimum_liquidity") ?? "5000000"),
        maximum_suggestions: Number(form.get("maximum_suggestions") ?? 20),
      });
      setSuccess(`Exploração ${run.id} enfileirada. Nenhuma sugestão entra diretamente em carteira.`);
      await refresh(run.id);
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
        name: String(form.get("schedule_name") ?? "weekly-discovery"),
        strategy_codes: strategies,
        minimum_liquidity: String(form.get("schedule_minimum_liquidity") ?? "5000000"),
        maximum_suggestions: Number(form.get("schedule_maximum_suggestions") ?? 20),
        interval_hours: Number(form.get("schedule_interval_hours") ?? 168),
        paused: false,
      });
      setSuccess(`Agendamento ${schedule.schedule_id} criado a cada ${schedule.interval_hours} horas.`);
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
      setSuccess(`${candidate.ticker} foi promovida para candidato e entrou no fluxo completo de investigação.`);
      await refresh(selected?.run.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao promover sugestão");
    } finally {
      setWorkingSuggestion(null);
    }
  }

  async function dismiss(id: string) {
    const reason = window.prompt("Motivo da dispensa desta sugestão:");
    if (!reason?.trim()) return;
    setWorkingSuggestion(id);
    setError(null);
    try {
      await dismissExplorationSuggestion(id, reason.trim());
      setSuccess("Sugestão dispensada com justificativa registrada.");
      await refresh(selected?.run.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Falha ao dispensar sugestão");
    } finally {
      setWorkingSuggestion(null);
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <Link className="breadcrumb" href="/opportunities/candidates"><ArrowLeft size={13} /> Voltar para candidatos</Link>
          <div className="eyebrow" style={{ marginTop: 12 }}>Autonomous discovery</div>
          <h1>Exploração de novas ações</h1>
          <p className="subtitle">O universo, liquidez, restricted list e cobertura são filtrados em código. O agent investiga apenas a shortlist e cria sugestões para o mesmo processo de aprovação.</p>
        </div>
        <Radar size={34} />
      </header>

      {error && <div className={styles.error} role="alert">{error}</div>}
      {success && <div className={styles.success}>{success}</div>}

      <div className="split">
        <form className={`card card-pad ${styles.layout}`} onSubmit={submit}>
          <div className="card-title"><h2>Nova exploração</h2><span>paper research</span></div>
          <fieldset className={styles.field}>
            <legend>Estratégias</legend>
            <label><input type="checkbox" name="strategy" value="quality" defaultChecked /> Qualidade</label>
            <label><input type="checkbox" name="strategy" value="value" defaultChecked /> Value</label>
            <label><input type="checkbox" name="strategy" value="growth" /> Crescimento</label>
            <label><input type="checkbox" name="strategy" value="dividend" /> Dividendos</label>
            <label><input type="checkbox" name="strategy" value="event_driven" /> Eventos</label>
          </fieldset>
          <div className={styles.formGrid}>
            <div className={styles.field}>
              <label htmlFor="minimum_liquidity">Liquidez média diária mínima (R$)</label>
              <input id="minimum_liquidity" name="minimum_liquidity" inputMode="decimal" defaultValue="5000000" />
            </div>
            <div className={styles.field}>
              <label htmlFor="maximum_suggestions">Máximo de sugestões</label>
              <input id="maximum_suggestions" name="maximum_suggestions" type="number" min={1} max={100} defaultValue={20} />
            </div>
          </div>
          <button className="button" disabled={submitting}>{submitting ? "Iniciando..." : "Iniciar exploração"}</button>
        </form>

        <aside className="card card-pad">
          <div className="card-title"><h2>Controles obrigatórios</h2><span>sem compra autônoma</span></div>
          <div className={styles.gapList}>
            <div className={styles.gap}><strong>Shortlist determinística</strong><p className="subtitle">O agent não pode introduzir ticker fora do universo filtrado.</p></div>
            <div className={styles.gap}><strong>Deduplicação</strong><p className="subtitle">Ativos já cobertos, bloqueados ou em cooldown são excluídos.</p></div>
            <div className={styles.gap}><strong>Promoção explícita</strong><p className="subtitle">Uma sugestão vira candidato; depois passa por identidade, fontes, dados, análise, risco e comitê.</p></div>
            <div className={styles.gap}><strong>Nenhuma ordem</strong><p className="subtitle">A exploração não altera carteiras e não acessa credenciais de corretora.</p></div>
          </div>
        </aside>
      </div>

      <section className="card card-pad" style={{ marginTop: 16 }}>
        <div className="card-title"><h2>Exploração recorrente</h2><span>Temporal Schedule</span></div>
        <form className={styles.layout} onSubmit={createSchedule}>
          <div className={styles.formGrid}>
            <div className={styles.field}><label htmlFor="schedule_name">Identificador</label><input id="schedule_name" name="schedule_name" pattern="[a-z0-9][a-z0-9-]+" defaultValue="weekly-discovery" /></div>
            <div className={styles.field}><label htmlFor="schedule_interval_hours">Intervalo em horas</label><input id="schedule_interval_hours" name="schedule_interval_hours" type="number" min={24} max={720} defaultValue={168} /></div>
            <div className={styles.field}><label htmlFor="schedule_minimum_liquidity">Liquidez mínima (R$)</label><input id="schedule_minimum_liquidity" name="schedule_minimum_liquidity" defaultValue="5000000" /></div>
            <div className={styles.field}><label htmlFor="schedule_maximum_suggestions">Máximo por execução</label><input id="schedule_maximum_suggestions" name="schedule_maximum_suggestions" type="number" min={1} max={100} defaultValue={20} /></div>
          </div>
          <fieldset className={styles.field}><legend>Estratégias recorrentes</legend><label><input type="checkbox" name="schedule_strategy" value="quality" defaultChecked /> Qualidade</label><label><input type="checkbox" name="schedule_strategy" value="value" defaultChecked /> Value</label><label><input type="checkbox" name="schedule_strategy" value="growth" /> Crescimento</label><label><input type="checkbox" name="schedule_strategy" value="dividend" /> Dividendos</label><label><input type="checkbox" name="schedule_strategy" value="event_driven" /> Eventos</label></fieldset>
          <p className="subtitle">Cada ocorrência cria uma execução independente. Sobreposição é bloqueada e o agendamento pausa em caso de falha.</p>
          <button className="button" disabled={submitting}>Criar exploração recorrente</button>
        </form>
      </section>

      <section className="card card-pad" style={{ marginTop: 16 }}>
        <div className="card-title">
          <h2>Execuções e sugestões</h2>
          <button className="button secondary" type="button" onClick={() => void refresh()} disabled={loading}><RefreshCw size={14} /> Atualizar</button>
        </div>
        {loading && <p className="subtitle">Carregando execuções...</p>}
        {!loading && !runs.length && <p className="subtitle">Nenhuma exploração executada.</p>}
        {!!runs.length && (
          <div className={styles.toolbar}>
            <label className={styles.field}>
              <span>Execução</span>
              <select
                value={selected?.run.id ?? ""}
                onChange={(event) => void refresh(event.target.value)}
              >
                {runs.map((run) => (
                  <option key={run.id} value={run.id}>
                    {new Date(run.created_at).toLocaleString("pt-BR")} · {run.status} · {run.strategy_codes.join(", ")}
                  </option>
                ))}
              </select>
            </label>
            {selected && <span className="subtitle">Universo {selected.run.universe_size} · elegíveis {selected.run.eligible_size} · sugestões {selected.suggestions.length}</span>}
          </div>
        )}

        {selected?.run.error_detail && <div className={styles.error}>{selected.run.error_detail}</div>}
        {selected && !selected.suggestions.length && <p className="subtitle">A execução ainda não produziu sugestões ou nenhuma ação passou pelos filtros.</p>}
        {selected && !!selected.suggestions.length && (
          <div className={styles.sourceList} style={{ marginTop: 12 }}>
            {selected.suggestions.map((item) => (
              <article className={styles.source} key={item.id}>
                <div className={styles.sourceHeader}>
                  <div>
                    <strong>{item.exchange}:{item.ticker}</strong>
                    <div className={styles.meta}>quantitativo {score(item.quantitative_score)} · dados {score(item.data_coverage_score)} · fontes {score(item.source_discovery_score)}</div>
                  </div>
                  <span className="badge">{item.status}</span>
                </div>
                <p>{item.rationale}</p>
                {!!item.signals.length && <p className="subtitle"><strong>Sinais:</strong> {item.signals.join(" · ")}</p>}
                {!!item.risks.length && <p className="subtitle"><ShieldAlert size={13} /> <strong>Riscos:</strong> {item.risks.join(" · ")}</p>}
                {item.status === "new" && (
                  <div className={styles.actions}>
                    <button className="button" type="button" disabled={workingSuggestion === item.id} onClick={() => void promote(item.id)}><CheckCircle2 size={14} /> Promover para investigação</button>
                    <button className="button secondary" type="button" disabled={workingSuggestion === item.id} onClick={() => void dismiss(item.id)}><XCircle size={14} /> Dispensar</button>
                  </div>
                )}
                {item.promoted_candidate_id && <Link href={`/opportunities/candidates/${item.promoted_candidate_id}`}>Abrir candidato promovido</Link>}
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
