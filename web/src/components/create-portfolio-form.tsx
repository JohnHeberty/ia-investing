"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { useCreatePortfolio } from "@/hooks/use-portfolios";

interface CreatePortfolioFormProps {
  onClose: () => void;
}

export function CreatePortfolioForm({ onClose }: CreatePortfolioFormProps) {
  const router = useRouter();
  const createPortfolio = useCreatePortfolio();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [baseCurrency, setBaseCurrency] = useState("BRL");
  const [initialCapital, setInitialCapital] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    try {
      const cap = parseFloat(initialCapital);
      const initialCapitalNum = isNaN(cap) ? undefined : cap;
      const result = await createPortfolio.mutateAsync({
        name: name.trim(),
        description: description.trim() || undefined,
        base_currency: baseCurrency,
        initial_capital: initialCapitalNum,
        is_paper_trading: true,
      });

      if (result?.id) {
        router.push(`/portfolios/${result.id}`);
      }
      onClose();
    } catch (err) {
      console.error("Failed to create portfolio:", err);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="card card-pad" style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 600 }}>
      <div className="card-title">
        <h2>Nova Carteira</h2>
      </div>

      <div>
        <label style={{ display: "block", fontSize: 14, color: "var(--muted)", marginBottom: 4 }}>
          Nome da Carteira *
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ex: Fundo Brasil Long Only"
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
          Descrição
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Descreva o objetivo da carteira..."
          rows={3}
          style={{
            width: "100%",
            borderRadius: 8,
            border: "1px solid var(--line)",
            background: "var(--surface-2)",
            padding: "8px 12px",
            fontSize: 14,
            color: "var(--text)",
            resize: "vertical",
          }}
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <label style={{ display: "block", fontSize: 14, color: "var(--muted)", marginBottom: 4 }}>
            Moeda Base
          </label>
          <select
            value={baseCurrency}
            onChange={(e) => setBaseCurrency(e.target.value)}
            style={{
              width: "100%",
              borderRadius: 8,
              border: "1px solid var(--line)",
              background: "var(--surface-2)",
              padding: "8px 12px",
              fontSize: 14,
              color: "var(--text)",
            }}
          >
            <option value="BRL">BRL - Real Brasileiro</option>
            <option value="USD">USD - Dólar Americano</option>
            <option value="EUR">EUR - Euro</option>
          </select>
        </div>

        <div>
          <label style={{ display: "block", fontSize: 14, color: "var(--muted)", marginBottom: 4 }}>
            Capital Inicial
          </label>
          <input
            type="number"
            value={initialCapital}
            onChange={(e) => setInitialCapital(e.target.value)}
            placeholder="1000000"
            min="0"
            step="1000"
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

      {createPortfolio.isError && (
        <div className="state-panel" data-state="error" role="alert" style={{ marginTop: 8 }}>
          <strong>Erro ao criar carteira</strong>
          {createPortfolio.error?.message || "Tente novamente."}
        </div>
      )}

      <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
        <button
          type="submit"
          className="button"
          disabled={createPortfolio.isPending || !name.trim()}
          style={{ opacity: createPortfolio.isPending || !name.trim() ? 0.5 : 1 }}
        >
          {createPortfolio.isPending ? "Criando..." : "Criar Carteira"}
        </button>
        <button
          type="button"
          className="button secondary"
          onClick={onClose}
          disabled={createPortfolio.isPending}
        >
          Cancelar
        </button>
      </div>
    </form>
  );
}
