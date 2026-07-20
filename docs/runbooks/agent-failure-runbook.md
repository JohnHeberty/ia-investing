# Agent Framework Failure Runbook

## 1. Provider Outage

### Symptoms
- Agent runs fail with error code `provider_transient` or `provider_rejected`
- `ProviderError` exceptions in application logs with `retryable=True`
- OpenTelemetry spans show provider.complete failures
- Increased `agent.runtime.runs` counter with `agent.status=failed`

### Impact
- All agent runs for the affected capability fail immediately or after retries
- `partial_failure_capabilities` populated in `CoordinatorOutput`
- Research workflows stall awaiting specialist outputs

### Mitigation
1. **Retry with backoff**: The framework retries transient errors automatically. Confirm retries are exhausting before manual intervention.
2. **Fallback to mock (test only)**: In non-production environments, swap `AgentProvider` to `MockProvider` with preloaded fixtures to unblock testing.
3. **Check provider status page**: Verify whether the upstream provider (OpenAI, etc.) has an active incident.
4. **Switch model profile**: If a specific model is degraded, update the `model_profile` artifact for the affected capability to a working model.

### Escalation
- If retries exhaust within 5 minutes, page the platform team.
- If the provider outage exceeds 30 minutes, activate the provider failover plan documented in the infrastructure runbook.

---

## 2. Budget Exceeded

### Symptoms
- `GuardrailViolationError` with code `budget_exceeded`
- Error detail specifies which budget field was exceeded (e.g., `cost_usd`, `prompt_tokens`, `duration_ms`)
- `agent.runtime.guardrail_trips` counter increments

### Impact
- The affected agent run is rejected before producing output
- Repeated budget violations indicate either runaway token usage or misconfigured limits

### Mitigation
1. **Review budget config**: Inspect the `RunBudget` stored on `AgentVersion.budgets` for the affected capability version.
2. **Adjust per capability**: Increase limits if the capability legitimately needs more tokens (e.g., filing analysis with large context windows). Use `EvalThresholds.max_average_cost_usd` as a guide.
3. **Investigate token usage**: Check if the prompt or schema artifacts have grown unexpectedly. A large `input_payload` or verbose instructions can inflate `prompt_tokens`.
4. **Check tool call budget**: If `tool_calls` is the exceeded field, review whether the agent is making redundant tool invocations.

### Escalation
- If budget limits are correct and violations persist, escalate to the agent framework team to investigate potential prompt regression.
- For cost anomalies exceeding 2x the configured limit, open a cost incident.

---

## 3. Guardrail Violation

### Symptoms
- `GuardrailViolationError` with one of these codes:
  - `prompt_injection`: Untrusted text contained injection patterns (e.g., "ignore previous instructions")
  - `personal_data`: Input contains CPF or other PII matching the `_PII_PATTERN`
  - `citation_coverage`: Material findings (confidence >= 0.5) lack required citations
  - `unknown_citation`: Output references evidence IDs not in the authorized case
  - `cutoff_mismatch`: Output changed the pinned knowledge cutoff
  - `capability_mismatch`: Specialist output capability doesn't match the run's pinned capability

### Impact
- The agent run is immediately rejected
- `agent.runtime.guardrail_trips` counter increments
- Downstream consumers receive no output for the request

### Mitigation
1. **Audit input**: For `prompt_injection` and `personal_data`, inspect the `input_payload` for untrusted text from external sources (news feeds, SEC filings, web scrapes).
2. **Check untrusted sources**: If PII is appearing in financial data feeds, add a sanitization layer before the data enters the agent pipeline.
3. **Review citation coverage**: For `citation_coverage` violations, the agent produced material findings without citing evidence. Review the prompt to ensure the agent understands citation requirements.
4. **Verify evidence authorization**: For `unknown_citation`, confirm the evidence IDs in the agent output are present in the `ResearchEvidence` table for the case.

### Escalation
- Repeated `prompt_injection` violations from a specific data source indicate a compromised upstream. Page the data engineering team.
- `citation_coverage` violations that persist after prompt review indicate a model regression. Trigger eval gate re-evaluation.

---

## 4. Eval Promotion Failure

### Symptoms
- `PromotionDecision.passed` is `False`
- `PromotionDecision.failures` contains one or more of:
  - `schema_pass_below_threshold`
  - `citation_coverage_below_threshold`
  - `task_score_below_threshold`
  - `cost_above_threshold`
  - `latency_above_threshold`
  - `schema_pass_regressed`
  - `citation_coverage_regressed`

### Impact
- The candidate agent version cannot be promoted to production
- The gate remains closed until the issues are resolved
- Shadow runs continue with the baseline version

### Mitigation
1. **Review prompt/model changes**: Compare the candidate version's prompt hash, schema hash, and model name against the baseline using `EvalGate.requires_eval()`.
2. **Run shadow comparison**: Execute `ShadowRunner.shadow_run()` on representative cases to compare baseline vs candidate outputs side by side.
3. **Inspect diff_summary**: The `ShadowResult.diff_summary` shows which keys were added, removed, or changed between versions.
4. **Tune thresholds if needed**: Use capability-specific thresholds from `eval_thresholds.py` rather than the generic defaults.
5. **Fix regressions**: If `citation_coverage_regressed` or `schema_pass_regressed`, the candidate is worse than the baseline on protected metrics. Revert the change or fix the regression before re-promoting.

### Escalation
- If the candidate fails on `task_score` but all other metrics pass, consult with the domain team on whether the threshold should be adjusted.
- If a model upgrade causes regression across multiple capabilities, escalate to the model evaluation team.

---

## 5. Rollback Procedure

### Symptoms
- A promoted agent version is producing degraded outputs
- Guardrail violations or budget exceeded errors spike after a version promotion
- Customer complaints about output quality for a specific capability

### Impact
- Active runs using the affected version may produce incorrect results
- New runs should be routed to the previous stable version

### Rollback Steps
1. **Identify the current version**: Query `AgentVersion` for the affected capability to find the current active version number.
2. **Identify the target version**: Find the previous version with `is_active=True` that you want to roll back to.
3. **Deactivate current version**: Update the current `AgentVersion.is_active` to `False`.
4. **Activate previous version**: Update the target `AgentVersion.is_active` to `True`.
5. **Record audit event**: Log a rollback event with:
   - `capability`: The affected capability logical_id
   - `from_version`: The version being deactivated
   - `to_version`: The version being reactivated
   - `reason`: Description of why the rollback was triggered
   - `operator`: Who performed the rollback
6. **Verify**: Trigger a test run with the rolled-back version to confirm it produces valid output.

### Post-Rollback
- The rolled-back version should pass the eval gate with existing thresholds.
- Monitor the capability for 15 minutes post-rollback to confirm stability.
- File a follow-up ticket to investigate and fix the issue in the failed version.

---

## 6. Cost Anomaly

### Symptoms
- `cost_histogram` shows a spike in `agent.runtime.cost` for a capability
- Individual runs show `cost_usd` significantly above `EvalThresholds.max_average_cost_usd`
- Monthly cost tracking exceeds budget forecast

### Impact
- Increased operational costs
- May trigger budget exceeded guardrails for subsequent runs

### Mitigation
1. **Check model pricing**: Verify the model's per-token pricing hasn't changed. Update `_pricing.py` cost estimates if needed.
2. **Review token usage**: Compare `prompt_tokens` and `completion_tokens` against historical baselines for the same capability.
3. **Inspect input payload size**: A sudden increase in `input_payload` size (e.g., a large SEC filing) can inflate `prompt_tokens`.
4. **Review timeout configuration**: If `max_duration_ms` is high, long-running provider calls accumulate cost.
5. **Check for retry storms**: Multiple retries of the same request multiply cost. Verify the retry policy is not causing excessive provider calls.

### Escalation
- If cost spike is >3x baseline for a capability, escalate to the platform team.
- If caused by model pricing changes, notify the finance team and update cost forecasts.

---

## 7. Latency Anomaly

### Symptoms
- `p95_latency_ms` in `EvalMetrics` exceeds `EvalThresholds.max_p95_latency_ms` (default 30s)
- `duration_histogram` shows p95 above threshold for a capability
- Individual runs show `duration_ms` exceeding 30 seconds
- `agent.runtime.duration` histogram tail is elevated

### Impact
- User-facing research workflows experience delays
- Temporal workflow activities may time out
- Queue depth increases as runs take longer to complete

### Mitigation
1. **Check provider status**: Verify the LLM provider's latency dashboard. External latency spikes are the most common cause.
2. **Review timeout config**: Ensure `OpenAIAgentsProvider.timeout_seconds` is appropriately set. Too low causes premature failures; too high wastes resources waiting.
3. **Inspect input complexity**: Large inputs or complex schemas increase provider processing time.
4. **Check for concurrent load**: High concurrency can cause provider-side rate limiting and increased latency.
5. **Review tool call count**: Each tool call adds a round-trip. If the agent is making excessive tool calls, optimize the prompt to reduce unnecessary invocations.

### Escalation
- If p95 latency exceeds 60s for more than 5 minutes, page the platform team.
- If caused by provider-side issues, monitor for provider incident updates.

---

## 8. Shadow Run Divergence

### Symptoms
- `ShadowResult.outputs_agree` is `False`
- `ShadowResult.diff_summary` shows `added`, `removed`, or `changed` keys
- `ShadowResult.baseline_error` or `ShadowResult.candidate_error` is not `None`
- `ShadowGateResult.gate_open` is `False` due to output disagreement

### Impact
- Candidate version cannot be promoted
- Indicates behavioral differences between baseline and candidate

### Mitigation
1. **Compare outputs**: Review `baseline_output` vs `candidate_output` to understand the nature of the divergence.
2. **Review diff_summary**: Parse the `diff_summary` string:
   - `added=[key]`: Candidate output contains keys not in baseline
   - `removed=[key]`: Candidate output is missing keys from baseline
   - `changed=[key]`: Key exists in both but values differ
   - `identical`: Outputs match exactly
   - `structural_mismatch`: Key sets are completely disjoint
3. **Check for provider errors**: If `baseline_error` or `candidate_error` is set, one variant failed. Check the error code (e.g., `provider_transient`).
4. **Review prompt changes**: If only the prompt changed (same model/schema), the divergence is expected. Decide if the new behavior is acceptable.
5. **Run on multiple cases**: Execute `ShadowGate.batch_shadow_gate()` on a broader dataset to determine if the divergence is consistent or case-specific.

### Escalation
- If divergence is consistent across all cases, the model or prompt change is fundamentally different. Revert or accept explicitly.
- If divergence is case-specific, investigate whether the input payload triggered a corner case. Add the case to the eval dataset for regression testing.
