---
name: accessibility-inclusive-design
description: Use when implementing or reviewing keyboard navigation, screen reader support, semantic HTML, ARIA, contrast, motion preferences, and responsive accessibility.
---

# Accessibility & Inclusive Design

Keyboard navigation, screen reader support, semantic HTML, ARIA, contrast, motion, and responsive design for the IA-Investing platform.

## Core Principles

- **Design for real diversity.** People use different devices, abilities, and contexts.
- **Start with purpose.** What is this element for? Then choose the right semantic HTML.
- **Prefer native semantics.** `<button>` over `<div onclick>`. `<nav>` over `<div class="nav">`.
- **Make structure machine-readable.** Headings, landmarks, labels, and ARIA attributes help assistive technology.
- **Progressively enhance.** Core functionality works without JavaScript. Enhanced with it.
- **Give users control.** Respect `prefers-reduced-motion`, `prefers-color-scheme`, and font size preferences.

## WCAG AA Compliance (Default)

### Contrast Requirements
- Normal text: 4.5:1 minimum
- Large text (18px+ or 14px+ bold): 3:1 minimum
- Interactive elements: 3:1 minimum
- Focus indicators: 3:1 minimum

### Keyboard Navigation
- All interactive elements must be focusable
- Focus order must be logical (top-to-bottom, left-to-right)
- Focus indicator must be visible (use `:focus-visible`)
- No keyboard traps
- Escape closes modals/dropdowns
- Tab moves forward, Shift+Tab moves backward

### Screen Reader Support
- All images have `alt` text (or `alt=""` for decorative)
- Form inputs have associated `<label>` elements
- Headings create a logical hierarchy (h1 > h2 > h3)
- Landmarks: `<header>`, `<nav>`, `<main>`, `<footer>`
- Live regions for dynamic content (`aria-live="polite"`)
- `aria-label` or `aria-labelledby` for complex widgets

## Forms Accessibility

- **Persistent labels** — Never use placeholder as label
- **Validate on submit first** — Then on change
- **Show password** — Preferred over hide password
- **Error messages** — Associated with fields via `aria-describedby`
- **Required fields** — Use `aria-required="true"` and visual indicator
- **Fieldsets** — Group related inputs with `<fieldset>` and `<legend>`

## Dynamic Content

- **Prefer "Load more"** over infinite scroll (better for keyboard/screen reader)
- **Announce loading states** with `aria-live="polite"`
- **Announce errors** with `aria-live="assertive"`
- **Preserve focus** when content updates
- **Don't auto-focus** after dynamic updates (unless it's a search input)

## Motion & Animation

- **Respect `prefers-reduced-motion`** — Disable or reduce animations
- **No auto-playing animations** — Let users trigger them
- **Keep animations under 5 seconds**
- **Provide pause/stop controls** for carousels or auto-updating content

## This Project's Accessibility Checklist

- [ ] All images have appropriate `alt` text
- [ ] All form inputs have visible labels
- [ ] Focus order is logical
- [ ] Focus indicators are visible (use `:focus-visible`)
- [ ] Color contrast meets WCAG AA (4.5:1)
- [ ] Headings create logical hierarchy
- [ ] Landmarks are used (`<nav>`, `<main>`, etc.)
- [ ] Dynamic content uses `aria-live`
- [ ] Keyboard navigation works for all interactions
- [ ] `prefers-reduced-motion` is respected
- [ ] Modal focus is trapped
- [ ] Error messages are associated with fields
- [ ] Required fields are marked
- [ ] No color-only indicators

## Testing

1. Navigate the entire app using only keyboard
2. Test with a screen reader (VoiceOver on Mac, NVDA on Windows)
3. Check color contrast with browser DevTools
4. Test with `prefers-reduced-motion: reduce`
5. Test at 200% zoom
6. Test with high contrast mode
7. Verify focus order is logical
8. Verify all interactive elements are focusable
