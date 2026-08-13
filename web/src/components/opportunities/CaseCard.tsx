import { FileText } from "lucide-react";

import { Badge } from "@/components/domain";
import type { ResearchCaseSummary } from "@/hooks/use-research-cases";

interface CaseCardProps {
  caseItem: ResearchCaseSummary;
  onSelect?: (id: string) => void;
}

export function CaseCard({ caseItem, onSelect }: CaseCardProps) {
  const c = caseItem;
  return (
    <tr
      onClick={onSelect ? () => onSelect(c.id) : undefined}
      style={onSelect ? { cursor: "pointer" } : undefined}
    >
      <td>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <FileText size={12} style={{ color: "var(--muted)" }} />
          <span style={{ fontWeight: 600 }}>{c.title || "Sem título"}</span>
        </div>
      </td>
      <td>
        <Badge tone="neutral">{c.case_type || "—"}</Badge>
      </td>
      <td>
        <Badge tone={c.priority === "high" ? "bad" : c.priority === "medium" ? "warn" : "neutral"}>
          {c.priority === "high"
            ? "Alta"
            : c.priority === "medium"
              ? "Média"
              : c.priority === "low"
                ? "Baixa"
                : c.priority || "—"}
        </Badge>
      </td>
      <td>
        <Badge
          tone={
            c.state === "ready_for_committee"
              ? "good"
              : c.state === "in_research"
                ? "warn"
                : "neutral"
          }
        >
          {c.state === "open"
            ? "Aberto"
            : c.state === "triaged"
              ? "Triado"
              : c.state === "in_research"
                ? "Em pesquisa"
                : c.state === "ready_for_committee"
                  ? "Pronto"
                  : c.state}
        </Badge>
      </td>
      <td style={{ color: "var(--muted)", fontSize: 12 }}>{c.created_by || "—"}</td>
    </tr>
  );
}
