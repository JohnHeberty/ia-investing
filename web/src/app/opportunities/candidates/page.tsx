"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Radar, RefreshCw } from "lucide-react";
import { CandidateCreateForm } from "@/components/candidates/candidate-create-form";
import { CandidateStatusBadge } from "@/components/candidates/candidate-status";
import { listCandidates, type CandidateStatus } from "@/lib/candidate-api";
import styles from "@/components/candidates/candidate-intelligence.module.css";

const filterOptions: Array<[CandidateStatus | "", string]> = [
  ["", "Todos"],
  ["awaiting_user_input", "Aguardando complemento"],
  ["source_discovery", "Descobrindo fontes"],
  ["fundamental_analysis", "Em análise"],
  ["committee_review", "Comitê"],
  ["approved", "Aprovados"],
  ["rejected", "Reprovados"],
  ["watchlist", "Observação"],
];

export default function CandidateQueuePage() {
  const [status, setStatus] = useState<CandidateStatus | "">("");
  const [showCreate, setShowCreate] = useState(false);

  const candidatesQuery = useQuery({
    queryKey: ["candidates", status],
    queryFn: async () => {
      const result = await listCandidates(status || undefined);
      return Array.isArray(result) ? result : (result.items ?? []);
    },
    staleTime: 30_000,
  });

  const items = candidatesQuery.data ?? [];

  const metrics = useMemo(
    () => ({
      total: items.length,
      waiting: items.filter((item) => item.status === "awaiting_user_input").length,
      committee: items.filter((item) => item.status === "committee_review").length,
      approved: items.filter((item) => item.status === "approved").length,
    }),
    [items],
  );

  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">Candidate intelligence</div>
          <h1>Candidatos de investimento</h1>
          <p className="subtitle">
            Cadastro manual e descoberta autônoma usando o mesmo fluxo auditável de identidade,
            fontes, documentos, análise, risco e comitê.
          </p>
        </div>
        <div className={styles.actions}>
          <Link className="button secondary" href="/opportunities/exploration">
            <Radar size={14} /> Exploração autônoma
          </Link>
          <button className="button" onClick={() => setShowCreate((value) => !value)}>
            <Plus size={14} /> Novo candidato
          </button>
        </div>
      </header>

      {showCreate && <CandidateCreateForm onClose={() => setShowCreate(false)} />}

      <section className="grid grid-4 section-gap" aria-live="polite">
        <article className="card metric">
          <div className="metric-label">Na visão atual</div>
          <div className="metric-value">{metrics.total}</div>
          <div className="metric-note">candidatos</div>
        </article>
        <article className="card metric">
          <div className="metric-label">Precisam de você</div>
          <div className="metric-value warning">{metrics.waiting}</div>
          <div className="metric-note">lacunas ou fontes</div>
        </article>
        <article className="card metric">
          <div className="metric-label">Prontos para decisão</div>
          <div className="metric-value">{metrics.committee}</div>
          <div className="metric-note">em comitê</div>
        </article>
        <article className="card metric">
          <div className="metric-label">Elegíveis</div>
          <div className="metric-value positive">{metrics.approved}</div>
          <div className="metric-note">aprovados</div>
        </article>
      </section>

      <section className="card card-pad section-gap" aria-live="polite">
        <div className={styles.toolbar}>
          <div className="card-title mb-0">
            <h2>Fila de investigação</h2>
            <span>{items.length} registros</span>
          </div>
          <div className={styles.actions}>
            <select
              aria-label="Filtrar candidatos por estado"
              value={status}
              onChange={(event) => setStatus(event.target.value as CandidateStatus | "")}
            >
              {filterOptions.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <button
              className="button secondary"
              onClick={() => void candidatesQuery.refetch()}
              disabled={candidatesQuery.isFetching}
            >
              <RefreshCw size={14} /> Atualizar
            </button>
          </div>
        </div>

        {candidatesQuery.isError && (
          <div className={`${styles.error} section-gap`} role="alert">
            {candidatesQuery.error instanceof Error
              ? candidatesQuery.error.message
              : "Falha ao carregar candidatos"}
          </div>
        )}
        {candidatesQuery.isLoading ? (
          <div className="state-panel section-gap">
            <strong>Carregando candidatos</strong>Consultando o estado operacional e as lacunas.
          </div>
        ) : items.length === 0 ? (
          <div className="state-panel section-gap">
            <strong>Nenhum candidato nesta visão</strong>Cadastre uma ação ou inicie a exploração
            autônoma.
          </div>
        ) : (
          <div className="table-wrap section-gap">
            <table className="table">
              <thead>
                <tr>
                  <th>Ativo</th>
                  <th>Origem</th>
                  <th>Estado</th>
                  <th>Decisão</th>
                  <th>Atualização</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.ticker}</strong>
                      <div className="portfolio-meta">{item.legal_name ?? item.exchange}</div>
                    </td>
                    <td>{item.origin === "manual" ? "Indicação manual" : "Agente explorador"}</td>
                    <td>
                      <CandidateStatusBadge status={item.status} />
                    </td>
                    <td>{item.final_decision ?? "—"}</td>
                    <td className="numeric">
                      {new Intl.DateTimeFormat("pt-BR", {
                        dateStyle: "short",
                        timeStyle: "short",
                      }).format(new Date(item.updated_at))}
                    </td>
                    <td>
                      <Link
                        className="button secondary"
                        href={`/opportunities/candidates/${item.id}`}
                      >
                        Abrir
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
