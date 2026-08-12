"use client";

import type { FormEvent } from "react";
import styles from "@/components/candidates/candidate-intelligence.module.css";

export function ScheduleForm({
  onSubmit,
  submitting,
}: {
  onSubmit: (e: FormEvent<HTMLFormElement>) => void;
  submitting: boolean;
}) {
  return (
    <section className="card card-pad section-gap">
      <div className="card-title"><h2>Exploração recorrente</h2><span>Temporal Schedule</span></div>
      <form className={styles.layout} onSubmit={onSubmit}>
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
  );
}
