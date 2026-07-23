from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from .enums import GapStatus, RequirementLevel, SourceKind, SourceStatus
from .models import (
    CandidateGap,
    CandidateReadiness,
    CandidateSource,
    ReadinessDimension,
    utcnow,
)


@dataclass(frozen=True, slots=True)
class SourceRequirement:
    code: str
    kind: SourceKind
    label: str
    level: RequirementLevel
    minimum_confidence: Decimal
    must_be_official: bool = True


DEFAULT_SOURCE_REQUIREMENTS: tuple[SourceRequirement, ...] = (
    SourceRequirement(
        code="company_website",
        kind=SourceKind.COMPANY_WEBSITE,
        label="Site oficial da companhia",
        level=RequirementLevel.REQUIRED,
        minimum_confidence=Decimal("0.75"),
    ),
    SourceRequirement(
        code="investor_relations",
        kind=SourceKind.INVESTOR_RELATIONS,
        label="Portal de relações com investidores",
        level=RequirementLevel.BLOCKING,
        minimum_confidence=Decimal("0.80"),
    ),
    SourceRequirement(
        code="financial_reports",
        kind=SourceKind.FINANCIAL_REPORTS,
        label="Página oficial de relatórios e resultados",
        level=RequirementLevel.BLOCKING,
        minimum_confidence=Decimal("0.80"),
    ),
    SourceRequirement(
        code="cvm_profile",
        kind=SourceKind.CVM_PROFILE,
        label="Cadastro oficial na CVM",
        level=RequirementLevel.BLOCKING,
        minimum_confidence=Decimal("0.90"),
    ),
    SourceRequirement(
        code="cvm_filings",
        kind=SourceKind.CVM_FILINGS,
        label="Canal oficial de documentos regulatórios",
        level=RequirementLevel.BLOCKING,
        minimum_confidence=Decimal("0.90"),
    ),
    SourceRequirement(
        code="b3_listing",
        kind=SourceKind.B3_LISTING,
        label="Listagem oficial na B3",
        level=RequirementLevel.BLOCKING,
        minimum_confidence=Decimal("0.90"),
    ),
    SourceRequirement(
        code="governance",
        kind=SourceKind.GOVERNANCE,
        label="Página de governança",
        level=RequirementLevel.OPTIONAL,
        minimum_confidence=Decimal("0.70"),
    ),
    SourceRequirement(
        code="newsroom",
        kind=SourceKind.NEWSROOM,
        label="Canal oficial de notícias",
        level=RequirementLevel.OPTIONAL,
        minimum_confidence=Decimal("0.70"),
    ),
)


class ReadinessEvaluator:
    def __init__(
        self,
        requirements: tuple[SourceRequirement, ...] = DEFAULT_SOURCE_REQUIREMENTS,
    ) -> None:
        self.requirements = requirements

    def evaluate(
        self,
        *,
        sources: tuple[CandidateSource, ...],
        open_gaps: tuple[CandidateGap, ...] = (),
        identity_resolved: bool,
        latest_documents_collected: bool = False,
        financial_data_validated: bool = False,
        fundamental_analysis_complete: bool = False,
        risk_analysis_complete: bool = False,
        committee_pack_complete: bool = False,
    ) -> CandidateReadiness:
        dimensions: list[ReadinessDimension] = []
        missing_source_kinds: list[SourceKind] = []

        dimensions.append(
            ReadinessDimension(
                code="identity",
                label="Identidade do emissor e instrumento",
                satisfied=identity_resolved,
                score=Decimal("1") if identity_resolved else Decimal("0"),
                reason="Identidade resolvida" if identity_resolved else "Ticker/CNPJ/CVM ainda não reconciliados",
                blocking=not identity_resolved,
            )
        )

        for requirement in self.requirements:
            matching = [
                source
                for source in sources
                if source.kind is requirement.kind
                and source.status is SourceStatus.VERIFIED
                and source.confidence >= requirement.minimum_confidence
                and (source.official or not requirement.must_be_official)
            ]
            satisfied = bool(matching)
            if not satisfied:
                missing_source_kinds.append(requirement.kind)
            dimensions.append(
                ReadinessDimension(
                    code=requirement.code,
                    label=requirement.label,
                    satisfied=satisfied,
                    score=Decimal("1") if satisfied else Decimal("0"),
                    reason=(
                        f"{len(matching)} fonte(s) verificada(s)"
                        if satisfied
                        else "Fonte oficial ausente, não verificada ou abaixo da confiança mínima"
                    ),
                    blocking=(requirement.level is RequirementLevel.BLOCKING and not satisfied),
                )
            )

        operational_dimensions = (
            ("documents", "Documentos atuais coletados", latest_documents_collected),
            ("financial_data", "Dados financeiros validados", financial_data_validated),
            ("fundamental_analysis", "Análise fundamentalista concluída", fundamental_analysis_complete),
            ("risk_analysis", "Análise de risco concluída", risk_analysis_complete),
            ("committee_pack", "Dossiê de comitê completo", committee_pack_complete),
        )
        for code, label, satisfied in operational_dimensions:
            dimensions.append(
                ReadinessDimension(
                    code=code,
                    label=label,
                    satisfied=satisfied,
                    score=Decimal("1") if satisfied else Decimal("0"),
                    reason="Concluído" if satisfied else "Pendente",
                    blocking=False,
                )
            )

        open_blockers = {gap.code for gap in open_gaps if gap.blocks_progress}
        dimension_blockers = {dimension.code for dimension in dimensions if dimension.blocking}
        blockers = tuple(sorted(open_blockers | dimension_blockers))

        # Blocking and required source dimensions receive greater weight than optional/late-stage dimensions.
        weighted_total = Decimal("0")
        weight_sum = Decimal("0")
        requirement_by_code = {requirement.code: requirement for requirement in self.requirements}
        for dimension in dimensions:
            requirement = requirement_by_code.get(dimension.code)  # type: ignore[assignment]
            if dimension.code == "identity" or (
                requirement is not None and requirement.level is RequirementLevel.BLOCKING
            ):
                weight = Decimal("2")
            elif requirement is not None and requirement.level is RequirementLevel.REQUIRED:
                weight = Decimal("1.5")
            else:
                weight = Decimal("1")
            weight_sum += weight
            weighted_total += dimension.score * weight
        score = (weighted_total / weight_sum).quantize(Decimal("0.0001"))

        return CandidateReadiness(
            score=score,
            dimensions=tuple(dimensions),
            blocker_codes=blockers,
            missing_source_kinds=tuple(dict.fromkeys(missing_source_kinds)),
        )

    def derive_source_gaps(
        self,
        *,
        candidate_id: UUID,
        sources: tuple[CandidateSource, ...],
        existing_gaps: tuple[CandidateGap, ...] = (),
    ) -> tuple[CandidateGap, ...]:
        by_code = {gap.code: gap for gap in existing_gaps}
        now = utcnow()
        output: list[CandidateGap] = []
        for requirement in self.requirements:
            has_verified_source = any(
                source.kind is requirement.kind
                and source.status is SourceStatus.VERIFIED
                and source.confidence >= requirement.minimum_confidence
                and (source.official or not requirement.must_be_official)
                for source in sources
            )
            existing = by_code.get(requirement.code)
            if has_verified_source:
                if existing is not None and existing.status is GapStatus.OPEN:
                    output.append(
                        CandidateGap(
                            id=existing.id,
                            candidate_id=existing.candidate_id,
                            code=existing.code,
                            title=existing.title,
                            description=existing.description,
                            source_kind=existing.source_kind,
                            level=existing.level,
                            status=GapStatus.RESOLVED,
                            requested_user_action=existing.requested_user_action,
                            created_at=existing.created_at,
                            resolved_at=now,
                            resolved_by="system:source-readiness",
                            resolution_notes="Resolvido automaticamente por fonte verificada.",
                        )
                    )
                elif existing is not None:
                    output.append(existing)
                continue
            if existing is not None and existing.status is GapStatus.OPEN:
                output.append(existing)
                continue
            output.append(
                CandidateGap(
                    id=uuid4(),
                    candidate_id=candidate_id,
                    code=requirement.code,
                    title=f"Fonte ausente: {requirement.label}",
                    description=(
                        "O processo automático não encontrou uma fonte oficial confiável. "
                        "A análise não deve assumir uma URL nem prosseguir silenciosamente."
                    ),
                    source_kind=requirement.kind,
                    level=requirement.level,
                    status=GapStatus.OPEN,
                    requested_user_action=(
                        f"Informe a URL oficial de {requirement.label.lower()} e solicite nova análise."
                    ),
                    created_at=now,
                )
            )
        unrelated = [gap for gap in existing_gaps if gap.code not in {r.code for r in self.requirements}]
        return (*output, *unrelated)
