"use client";

import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { NewsSource } from "@/hooks/use-news";

interface SourceFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  source?: NewsSource | null;
  onSubmit: (data: { name: string; source_type?: string; url_pattern?: string; trust_level?: number; is_active?: boolean }) => void;
  isPending: boolean;
  error?: Error | null;
}

const SOURCE_TYPES = [
  { value: "rss_google", label: "RSS Google News" },
  { value: "rss_reuters", label: "RSS Reuters" },
  { value: "rss", label: "RSS (generico)" },
  { value: "api", label: "API" },
  { value: "scraper", label: "Scraper" },
  { value: "manual", label: "Manual" },
];

export function SourceFormModal({
  open,
  onOpenChange,
  source,
  onSubmit,
  isPending,
  error,
}: SourceFormModalProps) {
  const isEdit = !!source;

  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState("rss");
  const [urlPattern, setUrlPattern] = useState("");
  const [trustLevel, setTrustLevel] = useState(3);

  useEffect(() => {
    if (open) {
      if (source) {
        setName(source.name);
        setSourceType(source.source_type ?? "rss");
        setUrlPattern(source.url_pattern ?? "");
        setTrustLevel(source.trust_level ?? 3);
      } else {
        setName("");
        setSourceType("rss");
        setUrlPattern("");
        setTrustLevel(3);
      }
    }
  }, [open, source?.id, source?.name, source?.source_type, source?.url_pattern, source?.trust_level]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    const data: { name: string; source_type?: string; url_pattern?: string; trust_level?: number } = {
      name: name.trim(),
      source_type: sourceType || undefined,
      trust_level: trustLevel,
    };
    if (urlPattern.trim()) data.url_pattern = urlPattern.trim();

    onSubmit(data);
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            zIndex: 50,
          }}
        />
        <Dialog.Content
          style={{
            position: "fixed",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: "var(--radius)",
            padding: 24,
            width: 440,
            maxWidth: "90vw",
            maxHeight: "85vh",
            overflowY: "auto",
            zIndex: 51,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <Dialog.Title style={{ fontSize: 16, fontWeight: 600, color: "var(--text)", margin: 0 }}>
              {isEdit ? "Editar Fonte" : "Nova Fonte"}
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                aria-label="Fechar"
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)", padding: 4 }}
              >
                <X size={16} />
              </button>
            </Dialog.Close>
          </div>

          <Dialog.Description style={{ fontSize: 13, color: "var(--muted)", marginBottom: 16 }}>
            {isEdit ? "Atualize as configuracoes da fonte de noticias." : "Adicione uma nova fonte de coleta de noticias."}
          </Dialog.Description>

          {error && (
            <div
              role="alert"
              style={{
                padding: "8px 12px",
                marginBottom: 16,
                background: "var(--red)",
                color: "var(--bg)",
                borderRadius: 6,
                fontSize: 12,
              }}
            >
              {error.message}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label htmlFor="source-name" style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
                Nome *
              </label>
              <input
                id="source-name"
                className="form-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ex: Bloomberg Brasil"
                required
                autoFocus
              />
            </div>

            <div>
              <label htmlFor="source-type" style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
                Tipo
              </label>
              <select
                id="source-type"
                className="form-input"
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
              >
                {SOURCE_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="source-url" style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
                URL Pattern (opcional)
              </label>
              <input
                id="source-url"
                className="form-input"
                value={urlPattern}
                onChange={(e) => setUrlPattern(e.target.value)}
                placeholder="Ex: https://exemplo.com/rss"
              />
            </div>

            <div>
              <label htmlFor="source-trust" style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
                Nivel de confianca: {trustLevel}
              </label>
              <input
                id="source-trust"
                type="range"
                min={1}
                max={5}
                value={trustLevel}
                onChange={(e) => setTrustLevel(Number(e.target.value))}
                style={{ width: "100%" }}
              />
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--muted)" }}>
                <span>1 - CVM/B3/RI</span>
                <span>5 - Midia social</span>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
              <Dialog.Close asChild>
                <button className="button" type="button" style={{ background: "var(--surface-2)", color: "var(--text)" }}>
                  Cancelar
                </button>
              </Dialog.Close>
              <button className="button" type="submit" disabled={isPending || !name.trim()}>
                {isPending ? "Salvando..." : isEdit ? "Salvar" : "Criar"}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
