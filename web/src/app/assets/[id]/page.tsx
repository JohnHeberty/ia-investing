"use client";

import { Suspense, useState } from "react";
import { useParams } from "next/navigation";
import { Database, ExternalLink } from "lucide-react";

import { AsOfIndicator, Badge, Metric } from "@/components/domain";
import {
  DataStatePanel,
  LoadingSkeleton,
  StaleWarning,
} from "@/components/data-state-components";
import { ConfidenceBar, EvidenceTag, FreshnessPill } from "@/components/evidence-tags";
import { SourceDrawer, type SourceEntry } from "@/components/source-drawer";
import { useInstrument } from "@/hooks/use-instrument";
import { useUrlState, filterPresets } from "@/hooks/use-url-state";

function AssetContent() {
  const params = useParams();
  const assetId = typeof params.id === "string" ? params.id : null;
  const [urlState] = useUrlState(filterPresets.asset);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const { instrument, isLoading, isError, dataState } = useInstrument(assetId);

  if (isLoading) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Asset 360</div>
            <h1>Carregando ativo...</h1>
          </div>
        </div>
        <section className="grid grid-4">
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
          <LoadingSkeleton lines={4} />
        </section>
        <section style={{ marginTop: 14 }}>
          <LoadingSkeleton lines={6} />
        </section>
      </>
    );
  }

  if (isError) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Asset 360</div>
            <h1>Erro ao carregar ativo</h1>
          </div>
        </div>
        <DataStatePanel
          state="error"
          title="Erro ao carregar dados do ativo"
          detail="Não foi possível acessar as informações do instrumento. Verifique o ID e tente novamente."
        />
      </>
    );
  }

  if (!instrument) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="eyebrow">Asset 360</div>
            <h1>Ativo não encontrado</h1>
          </div>
        </div>
        <DataStatePanel
          state="missing"
          title="Instrumento não encontrado"
          detail={`Nenhum instrumento encontrado com o ID "${assetId ?? ""}". Verifique o identificador.`}
        />
      </>
    );
  }

  const safetyMargin = instrument.safety_margin
    ? parseFloat(instrument.safety_margin)
    : null;
  const evidencePct = instrument.evidence_coverage
    ? parseInt(instrument.evidence_coverage, 10)
    : 0;
  const isStale = dataState === "stale";

  const sources: SourceEntry[] = instrument.data_sources.map((s) => ({
    id: s.id,
    name: s.name,
    type: s.type as SourceEntry["type"],
    retrievedAt: s.retrievedAt,
    confidence: s.confidence,
  }));

  return (
    <>
      <div className="page-head">
        <div>
          <div className="eyebrow">Asset 360</div>
          <h1>
            {instrument.ticker} · {instrument.name}
          </h1>
          <p className="subtitle">
            {instrument.exchange} · {instrument.listing} ·{" "}
            {instrument.instrument_type} · válido no as_of selecionado
          </p>
        </div>
        <AsOfIndicator
          value={
            instrument.valid_as_of
              ? new Date(instrument.valid_as_of).toLocaleString("pt-BR", {
                  day: "2-digit",
                  month: "short",
                  year: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "—"
          }
          freshness={isStale ? "Desatualizado" : "Atual"}
        />
      </div>

      {isStale && (
        <div style={{ marginBottom: 14 }}>
          <StaleWarning
            lastUpdated={instrument.valid_as_of || new Date().toISOString()}
            source="instruments/resolve"
          />
        </div>
      )}

      <section className="grid grid-4" aria-label="Indicadores do ativo">
        <Metric
          label="Valor justo"
          value={instrument.fair_value ?? "—"}
          note={instrument.fair_value ? "DCF ponderado" : "dado ausente não vira zero"}
        />
        <Metric
          label="Preço observado"
          value={instrument.observed_price ?? "—"}
          note={instrument.observed_price ? "último preço" : "aguardando observação"}
        />
        <Metric
          label="Margem de segurança"
          value={safetyMargin != null ? `${safetyMargin.toFixed(1)}%` : "—"}
          note={safetyMargin != null ? "cenário base" : "dado ausente não vira zero"}
          tone={safetyMargin != null && safetyMargin > 0 ? "positive" : undefined}
        />
        <Metric
          label="Evidence coverage"
          value={`${evidencePct}%`}
          note={`${instrument.material_claims} claims materiais`}
        />
      </section>

      {/* Evidence coverage detail */}
      <section className="card card-pad" style={{ marginTop: 14 }}>
        <div className="card-title">
          <h2>Cobertura de evidências</h2>
          <button
            onClick={() => setDrawerOpen(true)}
            className="icon-button"
            style={{
              background: "var(--surface-2)",
              border: "1px solid var(--line)",
              borderRadius: 6,
              padding: "4px 10px",
              cursor: "pointer",
              color: "var(--text)",
              fontSize: 12,
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
            aria-label="Abrir fontes de dados"
          >
            <Database size={12} /> Fontes <ExternalLink size={10} />
          </button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <ConfidenceBar value={evidencePct} label="Cobertura total" />
          {instrument.material_claims > 0 && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
              <EvidenceTag kind="fact">{instrument.material_claims} fatos verificados</EvidenceTag>
              <EvidenceTag kind="inference">inferências derivadas</EvidenceTag>
            </div>
          )}
        </div>
      </section>

      {/* Safety margin visual indicator */}
      {safetyMargin != null && (
        <section className="card card-pad" style={{ marginTop: 14 }}>
          <div className="card-title">
            <h2>Margem de segurança</h2>
            <Badge tone={safetyMargin > 20 ? "good" : safetyMargin > 0 ? "warn" : "bad"}>
              {safetyMargin > 20 ? "Saudável" : safetyMargin > 0 ? "Atenção" : "Insuficiente"}
            </Badge>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8 }}>
            <div
              style={{
                flex: 1,
                height: 24,
                background: "var(--surface-2)",
                borderRadius: 12,
                overflow: "hidden",
                position: "relative",
              }}
            >
              <div
                style={{
                  width: `${Math.min(100, Math.max(0, safetyMargin))}%`,
                  height: "100%",
                  background:
                    safetyMargin > 20
                      ? "var(--accent)"
                      : safetyMargin > 0
                        ? "var(--amber)"
                        : "var(--red)",
                  borderRadius: 12,
                  transition: "width 0.3s ease",
                }}
              />
              <span
                style={{
                  position: "absolute",
                  right: 8,
                  top: "50%",
                  transform: "translateY(-50%)",
                  fontSize: 11,
                  fontFamily: "var(--font-mono)",
                  color: "var(--text)",
                }}
              >
                {safetyMargin.toFixed(1)}%
              </span>
            </div>
          </div>
          <p
            style={{
              color: "var(--muted)",
              fontSize: 11,
              marginTop: 8,
            }}
          >
            Diferença entre valor justo e preço observado. Margem positiva indica subvalorização
            no cenário base.
          </p>
        </section>
      )}

      {/* Sections */}
      <section className="grid grid-3" style={{ marginTop: 14 }}>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Métricas e provenance</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Receita, dívida, margens e caixa exibem definição, linhagem de fatos, status e knowledge
            cutoff.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Tese e valuation</h2>
            <Badge tone="good">Saudável</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            A versão ativa liga assumptions aprovadas, cenários bear/base/bull e gatilhos de
            invalidação.
          </p>
        </article>
        <article className="card card-pad">
          <div className="card-title">
            <h2>Eventos e política</h2>
            <Badge tone="warn">Atenção</Badge>
          </div>
          <p style={{ color: "var(--muted)", fontSize: 12, lineHeight: 1.65 }}>
            Mudança regulatória em consulta pública está separada de norma vigente e aguarda
            corroboration.
          </p>
        </article>
      </section>

      {instrument.data_sources.length > 0 && (
        <SourceDrawer
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          sources={sources}
          title={`Fontes de ${instrument.ticker}`}
        />
      )}
    </>
  );
}

export default function AssetPage() {
  return (
    <Suspense
      fallback={
        <>
          <div className="page-head">
            <div>
              <div className="eyebrow">Asset 360</div>
              <h1>Carregando ativo...</h1>
            </div>
          </div>
          <LoadingSkeleton lines={6} />
        </>
      }
    >
      <AssetContent />
    </Suspense>
  );
}
