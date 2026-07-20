---
name: ux-research-discovery-testing
description: Use when planning or conducting discovery interviews, usability tests, synthesis, and evidence-backed UX recommendations.
---

# UX Research, Discovery & Testing

Discovery interviews, usability tests, synthesis, and evidence-backed recommendations for the IA-Investing platform.

## Core Principles

- **Start with a decision, not a method.** What do we need to decide? Then choose the research method.
- **Separate business questions from research questions.** "Will this increase revenue?" is a business question. "Can users find the portfolio list?" is a research question.
- **Prefer behavior over preference claims.** What people do matters more than what they say.
- **Use the smallest credible research loop.** Don't over-research. Quick tests beat no tests.

## Research Modes

| Mode | Purpose | Method |
|------|---------|--------|
| Generative | Discover needs and opportunities | Interviews, observation |
| Descriptive | Understand current behavior | Surveys, analytics |
| Evaluative | Test solutions | Usability testing |
| Causal | Understand why | A/B testing, interviews |

## Evidence Ladder

Strongest to weakest evidence:
1. **Observed behavior** — Watched someone do it
2. **Behavioral data** — Analytics, metrics
3. **Artifacts** — Screenshots, documents, recordings
4. **Self-report** — What someone says they did
5. **Preference claims** — What someone says they want

## Usability Test Protocol

### Before the Test
1. Define what you're testing (feature, flow, or concept)
2. Write 3-5 tasks that cover the key user goals
3. Prepare the test environment (prototype or live app)
4. Recruit 5-7 participants (diverse roles: Gestor, Analista, Risk, Compliance)

### During the Test
1. **Intro** — "We're testing the interface, not you. There are no wrong answers."
2. **Context** — Give a brief scenario
3. **Task** — "Try to [ accomplish X ]."
4. **Think aloud** — "Tell me what you're thinking as you go."
5. **Observe** — Watch what they do, not just what they say
6. **Probes** — "What did you expect to happen?" "How did you know to click that?"

### After the Test
1. **Debrief** — "What was confusing? What was clear?"
2. **Severity** — Rate issues: Critical > Major > Minor
3. **Synthesis** — Group findings by theme
4. **Recommendations** — Actionable, specific, prioritized

## Severity Rating

| Level | Definition | Action |
|-------|-----------|--------|
| Critical | Blocks task completion | Fix immediately |
| Major | Causes confusion or significant delay | Fix before launch |
| Minor | Slight inconvenience | Fix when possible |
| Cosmetic | Aesthetic issue | Low priority |

## Synthesis Framework

### Affinity Diagram
1. Write each observation on a sticky note
2. Group related observations
3. Name each group (theme)
4. Identify patterns across groups
5. Prioritize by impact and frequency

### Key Metrics
- **Task success rate** — % of users who complete the task
- **Time on task** — How long it takes
- **Error rate** — How many mistakes
- **Satisfaction** — Subjective rating (1-5 scale)

## Quick Tests (5-Minute Usability)

1. Show the screen for 5 seconds
2. Ask: "What is this page for?"
3. Ask: "What would you do first?"
4. Give a task
5. Watch them try
6. Note where they struggle

## This Project's Research Priorities

### Phase 1 (Immediate)
- Can users find and create a portfolio?
- Can users understand portfolio status and NAV?
- Can users navigate between sections (portfolios, risk, backtests)?
- Can users complete a trade intent flow?

### Phase 2 (After MVP)
- Can committee members complete the approval flow?
- Can risk analysts understand and act on breaches?
- Can backtest users set up and run a backtest?
- Can agents be monitored and managed effectively?

### Phase 3 (Continuous)
- Are error messages helpful?
- Are loading states clear?
- Are empty states guiding users?
- Is the mobile experience usable?

## Research Templates

### Interview Script
```
1. Tell me about your role and what you do day-to-day.
2. How do you currently [task related to our product]?
3. What's frustrating about the current process?
4. What would an ideal solution look like?
5. [Show prototype] Walk me through how you'd use this.
6. What's confusing? What's clear?
7. How does this compare to what you use now?
```

### Usability Test Script
```
1. [Context] You're a portfolio manager reviewing performance.
2. [Task] Find the PETR4 portfolio and check its latest NAV.
3. [Observe] Watch their clicks, time, and verbal reactions.
4. [Probe] What did you expect to see? Where did you look first?
5. [Debrief] What was confusing? What would you change?
```
