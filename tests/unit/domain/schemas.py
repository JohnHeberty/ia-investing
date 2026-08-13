from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas import FilingReviewVerdict
from schemas._filing import Claim, Risk


class TestFilingReviewVerdict:
    def _make_valid(self, **overrides) -> dict:
        base = {
            "verdict": "positive",
            "confidence": 0.85,
            "summary_pt": "Bons resultados no trimestre.",
            "materiality_score": 0.6,
            "thesis_effect": "strengthen",
            "claims": [
                {
                    "text": "Receita cresceu 15%",
                    "status": "verified",
                    "source_location": "DRE Q3",
                    "evidence_strength": 0.9,
                }
            ],
            "risks": [
                {
                    "description": "Alíquota pode mudar",
                    "severity": "medium",
                    "probability": 0.3,
                    "mitigation": "Cenário pessimista incluído",
                }
            ],
            "data_gaps": ["Sem guidance oficial"],
            "invalidation_triggers": ["Lucro cai 30%"],
        }
        base.update(overrides)
        return base

    def test_valid_json(self):
        data = self._make_valid()
        v = FilingReviewVerdict(**data)
        assert v.verdict == "positive"
        assert v.confidence == 0.85
        assert len(v.claims) == 1

    def test_required_fields_enforced(self):
        with pytest.raises(ValidationError):
            FilingReviewVerdict()

    def test_invalid_verdict_enum(self):
        data = self._make_valid(verdict="maybe")
        with pytest.raises(ValidationError):
            FilingReviewVerdict(**data)

    def test_invalid_thesis_effect_enum(self):
        data = self._make_valid(thesis_effect="invalid")
        with pytest.raises(ValidationError):
            FilingReviewVerdict(**data)

    def test_confidence_out_of_range(self):
        data = self._make_valid(confidence=1.5)
        with pytest.raises(ValidationError):
            FilingReviewVerdict(**data)

    def test_materiality_score_negative_out_of_range(self):
        data = self._make_valid(materiality_score=-2.0)
        with pytest.raises(ValidationError):
            FilingReviewVerdict(**data)

    def test_empty_claims_list(self):
        data = self._make_valid(claims=[])
        v = FilingReviewVerdict(**data)
        assert v.claims == []

    def test_empty_risks_list(self):
        data = self._make_valid(risks=[])
        v = FilingReviewVerdict(**data)
        assert v.risks == []

    @pytest.mark.parametrize("verdict", ["positive", "negative", "neutral"])
    def test_valid_verdict_values(self, verdict):
        data = self._make_valid(verdict=verdict)
        v = FilingReviewVerdict(**data)
        assert v.verdict == verdict

    @pytest.mark.parametrize("thesis_effect", ["strengthen", "weaken", "no_change"])
    def test_valid_thesis_effect_values(self, thesis_effect):
        data = self._make_valid(thesis_effect=thesis_effect)
        v = FilingReviewVerdict(**data)
        assert v.thesis_effect == thesis_effect


class TestClaim:
    def test_valid_claim(self):
        c = Claim(text="Test", status="verified", source_location="Q3", evidence_strength=0.8)
        assert c.status == "verified"

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            Claim(text="Test", status="pending", source_location="Q3", evidence_strength=0.8)


class TestRisk:
    def test_valid_risk(self):
        r = Risk(description="Risk", severity="high", probability=0.5, mitigation="Mitigate")
        assert r.severity == "high"

    def test_invalid_severity(self):
        with pytest.raises(ValidationError):
            Risk(description="Risk", severity="critical", probability=0.5, mitigation="Mitigate")

    def test_probability_out_of_range(self):
        with pytest.raises(ValidationError):
            Risk(description="Risk", severity="low", probability=1.5, mitigation="Mitigate")
