import type { CandidateStatus } from "@/lib/candidate-api";

const labels: Record<CandidateStatus, string> = {
  suggested: "Sugerida",
  identity_resolution: "Identidade",
  source_discovery: "Descobrindo fontes",
  awaiting_user_input: "Aguardando complemento",
  source_validation: "Validando fontes",
  document_collection: "Coletando documentos",
  data_quality: "Qualidade de dados",
  fundamental_analysis: "Análise fundamentalista",
  risk_analysis: "Análise de risco",
  committee_review: "Comitê",
  approved: "Aprovada",
  rejected: "Reprovada",
  watchlist: "Observação",
  cancelled: "Cancelada",
};

export function CandidateStatusBadge({ status }: { status: CandidateStatus }) {
  const tone = status === "approved" ? "good" : status === "rejected" || status === "cancelled" ? "bad" : status === "awaiting_user_input" ? "warn" : undefined;
  return <span className="badge" data-tone={tone}>{labels[status]}</span>;
}
