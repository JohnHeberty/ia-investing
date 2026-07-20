---
name: ux-writing-content-design
description: Use when writing or reviewing microcopy, labels, CTAs, empty states, error messages, notifications, and content design for the UI.
---

# UX Writing & Content Design

Microcopy, labels, CTAs, empty states, onboarding, errors, and notifications for the IA-Investing platform.

## Core Principles

- **Words are design material.** Every label, button, and message shapes the experience.
- **Start with the user task.** What are they trying to do? Write for that.
- **Prefer useful over clever.** Clarity beats creativity in UI copy.
- **Design the conversation, not isolated strings.** The flow of text matters more than individual words.
- **Make actions consequence-revealing.** Users should know what happens when they click.

## Voice & Tone

This project's voice:
- **Professional** — This is a financial platform. Be authoritative but not cold.
- **Warm** — Be helpful and approachable, not robotic.
- **Direct** — Say what needs to be said. No filler words.
- **Precise** — Use exact terms (dates, amounts, statuses). No ambiguity.

## Error Pattern

```
Avoid → Explain → Resolve
```

1. **Avoid** — Prevent the error if possible (disable button, validate early)
2. **Explain** — If error happens, say what went wrong in plain language
3. **Resolve** — Tell them how to fix it

### Error Message Template
```
[What happened] — [Why it happened] — [How to fix it]
```

### Examples
```
✓ "Portfolio name is required"
✓ "Insufficient balance to complete this trade"
✓ "Risk assessment failed — check that the policy exists and try again"
✗ "Error 403"
✗ "Invalid input"
✗ "Something went wrong"
```

## Empty State Pattern

```
Title + Description + Action
```

### Template
```
[What would be here] — [Why it's empty] — [What to do about it]
```

### Examples
```
✓ "No portfolios yet — Create your first portfolio to start tracking performance"
✓ "No trade intents — Create a trade intent to execute a paper trade"
✓ "No results found — Try adjusting your filters or search terms"
✗ "No data"
✗ "Empty"
```

## Labels

- Use nouns for labels ("Portfolio Name", not "Enter the name")
- Be consistent ("Create" everywhere, not "Add" sometimes and "New" others)
- Keep labels short (1-3 words)
- Use sentence case ("Portfolio name", not "Portfolio Name")

## Buttons & CTAs

- Use verbs ("Create Portfolio", not "Portfolio" or "New")
- Be specific ("Export as CSV", not "Export")
- Show consequence ("Delete Portfolio" not "Remove")
- Primary action: one per screen/section
- Destructive actions: red or labeled "Delete"/"Remove"

## Notifications

- **Info** — Something happened that's useful to know
- **Success** — Action completed successfully
- **Warning** — Something might need attention
- **Error** — Something failed and needs action

### Notification Template
```
[What happened] — [What it means] — [What to do]
```

## Numbers & Dates

- Use local format (Brazilian: 1.234,56 not 1,234.56)
- Show relative time for recent events ("2 hours ago")
- Show absolute time for important dates ("2026-07-20")
- Use abbreviations for large numbers (1,2K not 1,200)

## Four-Pass Edit

1. **Purposeful** — Does every word serve the user's task?
2. **Concise** — Can we say it with fewer words?
3. **Conversational** — Does it sound like a human?
4. **Clear** — Will a new user understand it?

## This Project's Content Patterns

### Status Labels
- `draft` → "Draft"
- `researching` → "Researching"
- `simulated` → "Simulated"
- `committee_review` → "In Review"
- `approved` → "Approved"
- `paper_live` → "Live (Paper)"

### Action Buttons
- "Create Mandate"
- "Create Portfolio"
- "Create Version"
- "Approve Version"
- "Run Backtest"
- "Publish NAV"

### Error Messages
- "Mandate not found"
- "Permission required: portfolio:read"
- "Concurrency conflict — portfolio was modified. Refresh and try again."
- "Risk assessment contains hard breaches — resolve before approving"
