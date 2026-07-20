---
name: ux-usability-foundations
description: Use when evaluating or implementing affordances, feedback, constraints, error prevention, navigation clarity, and task flow in the UI.
---

# UX Usability Foundations

Affordances, feedback, constraints, error prevention, navigation clarity, and task flow for the IA-Investing platform.

## Core Principles

- **Start with goals, not screens.** What is the user trying to accomplish?
- **Make the next action obvious.** Users should never wonder "what do I click?"
- **Show what is possible.** Disabled buttons, grayed-out options, and empty states should communicate possibility.
- **Match the mental model.** The interface should work how users think it works.
- **Favor recognition over recall.** Show options instead of requiring memory.
- **Reduce work.** Every extra click, field, or decision is friction.
- **Give immediate feedback.** Every action should have a visible result.
- **Prevent errors before explaining them.** Disable invalid states, confirm destructive actions.

## Affordances

Elements should look like what they do:
- **Buttons** look clickable (raised, colored, with clear labels)
- **Links** look like links (colored, underlined on hover)
- **Draggable** elements have a grip handle
- **Editable** fields have a clear border and cursor
- **Sortable** columns have sort indicators

## Feedback

Every user action needs feedback:
- **Click** → Visual response (button depresses, color changes)
- **Submit** → Loading state → Success/error message
- **Hover** → Tooltip or highlight
- **Focus** → Visible focus ring
- **Error** → Inline message + visual indicator
- **Success** → Confirmation message or state change

## Constraints

Prevent errors by constraining choices:
- **Disabled states** — Gray out unavailable options
- **Input validation** — Reject invalid characters
- **Confirmation dialogs** — For destructive actions
- **Undo** — Allow reversing actions when possible
- **Limits** — Show character counts, file size limits

## Error Prevention

1. **Disable invalid states** — Can't submit empty required fields
2. **Confirm destructive actions** — "Are you sure you want to delete?"
3. **Auto-save** — Prevent data loss
4. **Input masks** — Guide formatting (dates, phone numbers)
5. **Defaults** — Pre-fill reasonable values
6. **Warnings** — Before irreversible actions

## Navigation Clarity

- **You are here** — Breadcrumbs, active states, highlights
- **How to get back** — Back button, breadcrumbs, clear hierarchy
- **Where am I going** — Descriptive labels, preview on hover
- **How much is left** — Progress indicators for multi-step flows

## Task Flow

Every task should follow:
1. **Orient** — User understands what this screen is for
2. **Decide** — User knows what action to take
3. **Act** — User performs the action
4. **Feedback** — User sees the result
5. **Next** — User knows what to do next

## This Project's Usability Checklist

- [ ] Every interactive element has a visible affordance
- [ ] Every action has immediate feedback
- [ ] Destructive actions require confirmation
- [ ] Invalid states are prevented, not just reported
- [ ] Navigation is clear (breadcrumbs, active states)
- [ ] Progress is shown for multi-step flows
- [ ] Empty states guide the user
- [ ] Error messages are helpful and specific
- [ ] Loading states are shown for async operations
- [ ] Keyboard shortcuts are available for power users

## Common Usability Anti-patterns to Avoid

- Mystery meat navigation (unlabeled icons)
- Dead clicks (elements that look clickable but aren't)
- Hidden options (features only discoverable via keyboard)
- Confirmation fatigue (asking "are you sure?" for everything)
- Silent failures (no feedback on actions)
- Progressive disclosure overload (too many options at once)
- Modal madness (too many dialogs)
- Infinite scroll without pagination (hard to bookmark/share)
