---
name: design-systems-frontend-architecture
description: Use when creating or reviewing design tokens, component contracts, responsive layouts, CSS architecture, and frontend system governance.
---

# Design Systems & Frontend Architecture

Tokens, component contracts, responsive layouts, CSS strategy, and governance for the IA-Investing platform.

## Core Principles

- **Design systems, not pages.** Build reusable foundations first, then compose pages from them.
- **Think in parts and wholes.** Every component should work alone and in combination.
- **Separate function from perception.** A button's behavior (click handler) is separate from its look (green background).
- **Start with purpose before abstraction.** Don't create a component until you see 3+ similar uses.

## Architecture Model

```
Foundations/Tokens → Primitives → Components → Templates → Pages
     ↓                  ↓            ↓             ↓          ↓
  Colors, Spacing    Button,     Card, Table,   Dashboard,  Agents,
  Typography, Grid   Input,      Modal, Tabs    Settings,   Portfolios,
  Shadows, Radius    Badge       Nav, Toolbar    Detail      Risk
```

## Token Naming Convention

Use **role + state** over raw appearance:

```css
/* Good */
--color-action-primary        /* Role: action, Variant: primary */
--color-action-primary-hover  /* Role: action, Variant: primary, State: hover */
--color-surface-default       /* Role: surface, Variant: default */

/* Bad */
--color-green                 /* Raw appearance - what if green means error elsewhere? */
--color-5ee0a4                /* Hex value - meaningless */
```

## This Project's CSS Architecture

From `globals.css` (590 lines):
- CSS custom properties for tokens
- Class-based components (`.card`, `.btn`, `.table`)
- Responsive via `@media` breakpoints
- Dark/light themes via `:root` and `[data-theme="light"]`
- No CSS-in-JS (pure CSS)
- No CSS modules (single globals.css)

## Component Contract Template

Every component should document:

```markdown
## Component Name

**Purpose:** What it does
**Use when:** When to use this component
**Do not use when:** When to use something else

### Props/Variants
| Prop | Type | Default | Description |
|------|------|---------|-------------|

### States
- Default
- Hover
- Focus
- Active
- Disabled
- Loading
- Error
- Empty

### Accessibility
- Keyboard behavior
- Screen reader text
- ARIA attributes

### Responsive
- Desktop (> 1100px)
- Tablet (680-1100px)
- Mobile (< 680px)
```

## Responsive Strategy

This project uses two breakpoints:
- **1100px** — Sidebar collapses to icons
- **680px** — Bottom navigation replaces sidebar

Strategy:
1. Design mobile-first (680px)
2. Enhance for tablet (680-1100px)
3. Full experience on desktop (> 1100px)

## CSS Guidelines

1. **Use custom properties** for all colors, spacing, fonts
2. **Use rem** for font sizes, **px** for borders and shadows
3. **Use the spacing scale** (4/8/12/16/24/32/48/64)
4. **Use semantic class names** (`.card-primary` not `.green-box`)
5. **Group related styles** with comments
6. **Keep specificity low** — avoid `!important`
7. **Test in both themes** — every component must work in dark and light

## Governance

- New components require a design review
- Breaking changes require a migration guide
- All components must pass accessibility tests
- Document "Use when" and "Do not use when" for every pattern
- Version the design system independently if possible
