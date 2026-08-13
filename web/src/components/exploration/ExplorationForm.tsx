"use client";

import type { FormEvent } from "react";
import styles from "@/components/candidates/candidate-intelligence.module.css";

export function ExplorationForm({
  onSubmit,
  submitting,
}: {
  onSubmit: (e: FormEvent<HTMLFormElement>) => void;
  submitting: boolean;
}) {
  return (
    <div className="split">
      <form className={`card card-pad ${styles.layout}`} onSubmit={onSubmit}>
        <div className="card-title">
          <h2>Nova exploração</h2>
          <span>paper research</span>
        </div>
        <fieldset className={styles.field}>
          <legend>Estratégias</legend>
          <label>
            <input type="checkbox" name="strategy" value="quality" defaultChecked /> Qualidade
          </label>
          <label>
            <input type="checkbox" name="strategy" value="value" defaultChecked /> Value
          </label>
          <label>
            <input type="checkbox" name="strategy" value="growth" /> Crescimento
          </label>
          <label>
            <input type="checkbox" name="strategy" value="dividend" /> Dividendos
          </label>
          <label>
            <input type="checkbox" name="strategy" value="event_driven" /> Eventos
          </label>
        </fieldset>
        <div className={styles.formGrid}>
          <div className={styles.field}>
            <label htmlFor="minimum_liquidity">Liquidez média diária mínima (R$)</label>
            <input
              id="minimum_liquidity"
              name="minimum_liquidity"
              inputMode="decimal"
              defaultValue="5000000"
            />
          </div>
          <div className={styles.field}>
            <label htmlFor="maximum_suggestions">Máximo de sugestões</label>
            <input
              id="maximum_suggestions"
              name="maximum_suggestions"
              type="number"
              min={1}
              max={100}
              defaultValue={20}
            />
          </div>
        </div>
        <button className="button" disabled={submitting}>
          {submitting ? "Iniciando..." : "Iniciar exploração"}
        </button>
      </form>

      <aside className="card card-pad">
        <div className="card-title">
          <h2>Controles obrigatórios</h2>
          <span>sem compra autônoma</span>
        </div>
        <div className={styles.gapList}>
          <div className={styles.gap}>
            <strong>Shortlist determinística</strong>
            <p className="subtitle">
              O agent não pode introduzir ticker fora do universo filtrado.
            </p>
          </div>
          <div className={styles.gap}>
            <strong>Deduplicação</strong>
            <p className="subtitle">Ativos já cobertos, bloqueados ou em cooldown são excluídos.</p>
          </div>
          <div className={styles.gap}>
            <strong>Promoção explícita</strong>
            <p className="subtitle">
              Uma sugestão vira candidato; depois passa por identidade, fontes, dados, análise,
              risco e comitê.
            </p>
          </div>
          <div className={styles.gap}>
            <strong>Nenhuma ordem</strong>
            <p className="subtitle">
              A exploração não altera carteiras e não acessa credenciais de corretora.
            </p>
          </div>
        </div>
      </aside>
    </div>
  );
}
