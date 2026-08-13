"""Unit tests for ia_investing.domain.portfolio_decision — decision pack logic."""

from __future__ import annotations

import pytest

from ia_investing.domain.portfolio_decision import (
    CommitteeVote,
    PortfolioDecisionInputs,
    decision_pack_sha256,
    validate_committee_vote,
    validate_decision_inputs,
)


@pytest.mark.unit
class TestValidateDecisionInputs:
    def _make(self, **overrides) -> PortfolioDecisionInputs:
        defaults = dict(
            portfolio_id="p1",
            proposed_by="user1",
            input_snapshot_sha256="a" * 64,
            proposal_sha256="b" * 64,
            risk_opinion="approved",
            compliance_opinion="approved",
            optimizer_status="optimal",
            eligible=True,
            hard_breach=False,
        )
        defaults.update(overrides)
        return PortfolioDecisionInputs(**defaults)

    def test_valid(self):
        validate_decision_inputs(self._make())  # should not raise

    def test_invalid_hash_length(self):
        with pytest.raises(ValueError, match="SHA-256"):
            validate_decision_inputs(self._make(input_snapshot_sha256="short"))

    def test_ineligible(self):
        with pytest.raises(ValueError, match="ineligible"):
            validate_decision_inputs(self._make(eligible=False))

    def test_hard_breach(self):
        with pytest.raises(ValueError, match="hard risk breach"):
            validate_decision_inputs(self._make(hard_breach=True))

    def test_invalid_optimizer(self):
        with pytest.raises(ValueError, match="optimizer"):
            validate_decision_inputs(self._make(optimizer_status="failed"))

    def test_risk_not_approved(self):
        with pytest.raises(ValueError, match="risk opinion"):
            validate_decision_inputs(self._make(risk_opinion="rejected"))

    def test_compliance_not_approved(self):
        with pytest.raises(ValueError, match="compliance opinion"):
            validate_decision_inputs(self._make(compliance_opinion="pending"))


@pytest.mark.unit
class TestValidateCommitteeVote:
    def _make_vote(self, **overrides) -> CommitteeVote:
        defaults = dict(
            actor_id="voter1",
            role="risk_officer",
            decision="approved",
            rationale="Looks good",
            signature_sha256="c" * 64,
        )
        defaults.update(overrides)
        return CommitteeVote(**defaults)

    def test_valid(self):
        validate_committee_vote(self._make_vote(), proposed_by="user1", existing_actors=frozenset())

    def test_self_approval_raises(self):
        with pytest.raises(PermissionError, match="cannot approve"):
            validate_committee_vote(self._make_vote(actor_id="user1"), proposed_by="user1", existing_actors=frozenset())

    def test_duplicate_actor_raises(self):
        with pytest.raises(ValueError, match="already voted"):
            validate_committee_vote(self._make_vote(), proposed_by="user1", existing_actors=frozenset({"voter1"}))

    def test_invalid_role(self):
        with pytest.raises(ValueError, match="not authorized"):
            validate_committee_vote(self._make_vote(role="intern"), proposed_by="user1", existing_actors=frozenset())

    def test_invalid_decision(self):
        with pytest.raises(ValueError, match="invalid committee decision"):
            validate_committee_vote(self._make_vote(decision="maybe"), proposed_by="user1", existing_actors=frozenset())

    def test_empty_rationale(self):
        with pytest.raises(ValueError, match="rationale"):
            validate_committee_vote(self._make_vote(rationale="  "), proposed_by="user1", existing_actors=frozenset())

    def test_conditional_without_conditions(self):
        with pytest.raises(ValueError, match="explicit conditions"):
            validate_committee_vote(
                self._make_vote(decision="approved_with_conditions", conditions=()),
                proposed_by="user1",
                existing_actors=frozenset(),
            )

    def test_conditional_with_conditions(self):
        validate_committee_vote(
            self._make_vote(decision="approved_with_conditions", conditions=("review in 30d",)),
            proposed_by="user1",
            existing_actors=frozenset(),
        )


@pytest.mark.unit
class TestDecisionPackSha256:
    def test_deterministic(self):
        inputs = PortfolioDecisionInputs(
            portfolio_id="p1", proposed_by="u1",
            input_snapshot_sha256="a" * 64, proposal_sha256="b" * 64,
            risk_opinion="approved", compliance_opinion="approved",
            optimizer_status="optimal", eligible=True, hard_breach=False,
        )
        vote = CommitteeVote(
            actor_id="v1", role="risk_officer", decision="approved",
            rationale="ok", signature_sha256="c" * 64,
        )
        h1 = decision_pack_sha256(inputs, (vote,))
        h2 = decision_pack_sha256(inputs, (vote,))
        assert h1 == h2
        assert len(h1) == 64
