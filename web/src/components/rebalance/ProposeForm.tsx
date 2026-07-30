import { useState } from "react";
import { useProposeRebalance } from "@/hooks/use-rebalance";

export function ProposeForm({
  portfolioId,
  onClose,
}: {
  portfolioId: string;
  onClose: () => void;
}) {
  const propose = useProposeRebalance();
  const [targets, setTargets] = useState("");
  const [rationale, setRationale] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setParseError(null);
    let parsed: Record<string, number>;
    try {
      parsed = JSON.parse(targets) as Record<string, number>;
    } catch {
      setParseError("JSON inválido. Use o formato: {\"TICKER\": 0.25, ...}");
      return;
    }
    propose.mutate(
      { portfolioId, targetAllocations: parsed, rationale },
      { onSuccess: () => onClose() },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="card card-pad" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="card-title"><h3>Nova proposta de rebalanceamento</h3></div>
      <div>
        <label style={{ display: "block", fontSize: 14, color: "var(--muted)" }}>Target allocations (JSON)</label>
        <textarea
          style={{
            marginTop: 4,
            width: "100%",
            borderRadius: 8,
            border: "1px solid var(--line)",
            background: "var(--surface-2)",
            padding: 8,
            fontFamily: "var(--font-mono)",
            fontSize: 14,
            color: "var(--text)",
            resize: "vertical",
          }}
          rows={5}
          placeholder='{"AAPL": 0.25, "GOOGL": 0.15, "MSFT": 0.20}'
          value={targets}
          onChange={(e) => setTargets(e.target.value)}
        />
      </div>
      <div>
        <label style={{ display: "block", fontSize: 14, color: "var(--muted)" }}>Rationale</label>
        <textarea
          style={{
            marginTop: 4,
            width: "100%",
            borderRadius: 8,
            border: "1px solid var(--line)",
            background: "var(--surface-2)",
            padding: 8,
            fontSize: 14,
            color: "var(--text)",
            resize: "vertical",
          }}
          rows={3}
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
        />
      </div>
      <div style={{ display: "flex", gap: 12 }}>
        <button
          type="submit"
          className="button"
          disabled={propose.isPending || !targets || !rationale}
          style={{ opacity: propose.isPending || !targets || !rationale ? 0.5 : 1 }}
        >
          {propose.isPending ? "Criando..." : "Propor rebalanceamento"}
        </button>
        <button type="button" className="button secondary" onClick={onClose}>
          Cancelar
        </button>
      </div>
      {propose.isError && (
        <p style={{ fontSize: 14, color: "var(--red)" }}>Erro: {propose.error.message}</p>
      )}
    </form>
  );
}
