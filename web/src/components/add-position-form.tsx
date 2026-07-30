"use client";

import { useState } from "react";

import { useAddPosition } from "@/hooks/use-portfolios";

interface AddPositionFormProps {
  portfolioId: string;
  onClose: () => void;
}

export function AddPositionForm({ portfolioId, onClose }: AddPositionFormProps) {
  const addPosition = useAddPosition();

  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [currentPrice, setCurrentPrice] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker.trim() || !quantity || !avgCost) return;

    const qty = parseFloat(quantity);
    const cost = parseFloat(avgCost);
    if (isNaN(qty) || qty <= 0 || isNaN(cost) || cost <= 0) return;

    try {
      await addPosition.mutateAsync({
        portfolioId,
        ticker: ticker.trim().toUpperCase(),
        quantity: qty,
        avgCost: cost,
        currentPrice: currentPrice ? parseFloat(currentPrice) : undefined,
      });
      onClose();
    } catch (err) {
      console.error("Failed to add position:", err);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="card card-pad" style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 500 }}>
      <div className="card-title">
        <h2>Adicionar Posição</h2>
      </div>

      <div>
        <label style={{ display: "block", fontSize: 14, color: "var(--muted)", marginBottom: 4 }}>
          Ticker *
        </label>
        <input
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Ex: PETR4"
          required
          style={{
            width: "100%",
            borderRadius: 8,
            border: "1px solid var(--line)",
            background: "var(--surface-2)",
            padding: "8px 12px",
            fontSize: 14,
            color: "var(--text)",
            textTransform: "uppercase",
          }}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <label style={{ display: "block", fontSize: 14, color: "var(--muted)", marginBottom: 4 }}>
            Quantidade *
          </label>
          <input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="1000"
            min="0"
            step="1"
            required
            style={{
              width: "100%",
              borderRadius: 8,
              border: "1px solid var(--line)",
              background: "var(--surface-2)",
              padding: "8px 12px",
              fontSize: 14,
              color: "var(--text)",
            }}
          />
        </div>

        <div>
          <label style={{ display: "block", fontSize: 14, color: "var(--muted)", marginBottom: 4 }}>
            Preço Médio (R$) *
          </label>
          <input
            type="number"
            value={avgCost}
            onChange={(e) => setAvgCost(e.target.value)}
            placeholder="35.50"
            min="0"
            step="0.01"
            required
            style={{
              width: "100%",
              borderRadius: 8,
              border: "1px solid var(--line)",
              background: "var(--surface-2)",
              padding: "8px 12px",
              fontSize: 14,
              color: "var(--text)",
            }}
          />
        </div>
      </div>

      <div>
        <label style={{ display: "block", fontSize: 14, color: "var(--muted)", marginBottom: 4 }}>
          Preço Atual (R$)
        </label>
        <input
          type="number"
          value={currentPrice}
          onChange={(e) => setCurrentPrice(e.target.value)}
          placeholder="38.20"
          min="0"
          step="0.01"
          style={{
            width: "100%",
            borderRadius: 8,
            border: "1px solid var(--line)",
            background: "var(--surface-2)",
            padding: "8px 12px",
            fontSize: 14,
            color: "var(--text)",
          }}
        />
      </div>

      {addPosition.isError && (
        <div className="state-panel" data-state="error" role="alert" style={{ marginTop: 8 }}>
          <strong>Erro ao adicionar posição</strong>
          {addPosition.error?.message || "Tente novamente."}
        </div>
      )}

      <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
        <button
          type="submit"
          className="button"
          disabled={addPosition.isPending || !ticker.trim() || !quantity || !avgCost}
          style={{ opacity: addPosition.isPending || !ticker.trim() || !quantity || !avgCost ? 0.5 : 1 }}
        >
          {addPosition.isPending ? "Adicionando..." : "Adicionar Posição"}
        </button>
        <button
          type="button"
          className="button secondary"
          onClick={onClose}
          disabled={addPosition.isPending}
        >
          Cancelar
        </button>
      </div>
    </form>
  );
}
