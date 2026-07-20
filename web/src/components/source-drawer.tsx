"use client";

import { X } from "lucide-react";
import type { ReactNode } from "react";

export type SourceEntry = {
  id: string;
  name: string;
  type: "filing" | "news" | "macro" | "political" | "manual";
  url?: string;
  retrievedAt: string;
  confidence: number;
};

export function SourceDrawer({
  open,
  onClose,
  sources,
  title = "Fontes e proveniência",
}: {
  open: boolean;
  onClose: () => void;
  sources: SourceEntry[];
  title?: string;
}) {
  if (!open) return null;
  return (
    <div
      className="source-drawer-overlay"
      role="dialog"
      aria-label={title}
      aria-modal="true"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.5)",
        zIndex: 100,
        display: "flex",
        justifyContent: "flex-end",
      }}
    >
      <nav
        className="source-drawer"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 380,
          maxWidth: "90vw",
          height: "100%",
          background: "var(--surface)",
          borderLeft: "1px solid var(--line)",
          padding: 24,
          overflowY: "auto",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>{title}</h2>
          <button
            onClick={onClose}
            aria-label="Fechar"
            className="icon-button"
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}
          >
            <X size={16} />
          </button>
        </div>
        {sources.length === 0 ? (
          <p style={{ color: "var(--muted)", fontSize: 13 }}>Nenhuma fonte registrada.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 12 }}>
            {sources.map((source) => (
              <li
                key={source.id}
                style={{
                  padding: 12,
                  background: "var(--surface-2)",
                  borderRadius: "var(--radius)",
                  fontSize: 12,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong>{source.name}</strong>
                  <Badge source={source} />
                </div>
                <div style={{ color: "var(--muted)", marginTop: 6, display: "flex", gap: 12 }}>
                  <span>{source.type}</span>
                  <span>{source.retrievedAt}</span>
                  <span>{Math.round(source.confidence * 100)}% confiança</span>
                </div>
                {source.url && (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: "var(--blue)", fontSize: 11, marginTop: 4, display: "inline-block" }}
                  >
                    Abrir fonte original
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </nav>
    </div>
  );
}

function Badge({ source }: { source: SourceEntry }) {
  const color =
    source.type === "filing"
      ? "var(--accent)"
      : source.type === "news"
        ? "var(--blue)"
        : source.type === "macro"
          ? "var(--amber)"
          : "var(--muted)";
  return (
    <span
      style={{
        fontSize: 10,
        padding: "2px 6px",
        borderRadius: 6,
        background: `${color}22`,
        color,
        fontWeight: 600,
        textTransform: "uppercase",
      }}
    >
      {source.type}
    </span>
  );
}
