---
name: forms-inputs-checkout
description: Use when building or reviewing forms, input validation, data entry flows, checkout, and registration in the web frontend.
---

# Forms, Inputs & Checkout

Forms, validation, checkout, registration, and data entry flows for the IA-Investing platform.

## Core Principles

- **Start outside-in.** What does the user want to accomplish? Then design the form to get there.
- **Remove, defer, infer, default before adding fields.** Every field is friction.
- **Make the path obvious.** Users should always know what's next.
- **Match controls to questions.** Dropdowns for few options, radio for 2-3, checkboxes for multiple.
- **Validate to help, not scold.** Errors should guide correction, not punish.

## Decision Framework

```
Remove → Infer → Default → Defer → Ask → Explain → Validate → Recover
```

1. **Remove** — Can we not ask this at all?
2. **Infer** — Can we figure it out from context?
3. **Default** — Can we pre-fill a reasonable value?
4. **Defer** — Can we ask later?
5. **Ask** — We must ask. Make it easy.
6. **Explain** — Tell them why we need it.
7. **Validate** — Check on submit, then on change.
8. **Recover** — Help them fix errors quickly.

## Form Patterns

### Single-column forms
- Labels above inputs
- One field per line
- Clear section dividers
- Submit at the bottom

### Inline forms
- Search bars
- Quick actions
- Filter controls

### Multi-step forms (wizards)
- Progress indicator
- Back/Next navigation
- Save progress
- Summary before submit

## Validation Strategy

1. **On submit** — Show all errors
2. **On blur** — Validate the field that just lost focus
3. **On change** — Only after first submit attempt
4. **Error messages** — Below the field, in red, with icon
5. **Success feedback** — Inline checkmark or color change

### Validation Rules
- Required fields: `aria-required="true"` + visual indicator
- Email: Standard format validation
- Numbers: Allow only valid characters
- Dates: Use native date pickers when possible
- Strings: Min/max length clearly labeled

## This Project's Form Components

From `globals.css`:
- Input fields use the card/surface styling
- Buttons use `.btn` with variants
- Forms are typically in modals or full pages

### Existing Libraries
- `react-hook-form` — Form state management
- `zod` — Schema validation
- `@radix-ui/react-dialog` — Modal forms

## Common Patterns in This Project

### Create Portfolio
```
Name (required) → Description (optional) → Initial Capital (optional)
```

### Create Trade Intent
```
Instrument (search) → Side (buy/sell) → Quantity → Order Type → Limit Price (if limit)
→ Earliest Execution → Expires At → Reason
```

### Approval Decision
```
Optimization Run (reference) → Risk Snapshot (reference) → Rationale (required) → Votes
```

## Accessibility

- All inputs have visible `<label>` elements
- Error messages use `aria-describedby`
- Required fields use `aria-required`
- Fieldsets group related inputs
- Tab order is logical
- Submit button is keyboard accessible
- Error summary at top of form for screen readers

## Workflow: Design Form

1. List all fields needed
2. Apply the Remove/Infer/Default/Defer framework
3. Group related fields
4. Choose the right input type for each field
5. Define validation rules
6. Design error messages
7. Design success feedback
8. Add accessibility attributes
9. Test keyboard navigation
10. Test with screen reader
11. Test on mobile (680px)
12. Document the form's API
