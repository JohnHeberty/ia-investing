---
name: ui-visual-composition
description: Use when creating or reviewing UI visual hierarchy, spacing, typography, color, depth, imagery, and visual states. Applies to any frontend component or page in web/src/.
---

# UI Visual Composition

Visual hierarchy, spacing, typography, color, depth, imagery, and visual states for the IA-Investing platform.

## Core Principles

- **Hierarchy is backbone.** Size, weight, position, and contrast create levels. Every screen needs clear primary/secondary/tertiary.
- **Use familiar patterns.** Users shouldn't learn your layout. Standard patterns (cards, tables, lists, navs) reduce cognitive load.
- **Group by meaning.** Gestalt principles (proximity, similarity, closure) organize information without borders or labels.
- **Constrain with systems.** Spacing scale (4/8/12/16/24/32/48/64), type scale, color palette. No magic numbers.
- **Typography is structure.** Headings create landmarks. Body text is the default. Labels guide. Captions inform. Monospace signals code.
- **Color must carry meaning safely.** Never rely on color alone. Pair with icons, text, or patterns. Consider color blindness.

## This Project's Design Tokens

From `web/src/app/globals.css`:

```
Dark:  --bg: #07100e, --surface: #0d1916, --accent: #5ee0a4
Light: --bg: #f2f6f3, --surface: #ffffff, --accent: #167c54
Font:  "Segoe UI" / Inter, --radius: 14px
Breakpoints: 1100px (sidebar collapse), 680px (bottom nav)
```

## Workflow: Critique Existing UI

1. Identify the screen's primary goal.
2. Map current visual hierarchy (3 levels max).
3. Check spacing consistency against 8px grid.
4. Verify color contrast ratios (4.5:1 AA).
5. Test if the page works in both dark and light themes.
6. Check responsive behavior at 1100px and 680px breakpoints.
7. Verify all interactive states (hover, focus, active, disabled).
8. Check loading and error states have visual treatment.
9. Verify empty states are designed, not blank.
10. Check font sizes follow the type scale.
11. Verify depth uses shadows/elevation consistently.
12. Document specific improvements with rationale.

## Workflow: Create UI

1. Define the information hierarchy (what matters most?).
2. Sketch layout using the spacing scale.
3. Choose the right component pattern (card, table, list).
4. Apply color semantics (accent for actions, muted for secondary).
5. Design all states: default, hover, focus, active, disabled, loading, error, empty.
6. Test in both themes.
7. Verify responsive breakpoints.
8. Check accessibility (contrast, focus order, screen reader).
9. Document the component's API (props, variants).
10. Write usage guidelines ("Use when" / "Do not use when").
11. Add to the design system if reusable.
12. Review against common mistakes checklist.

## Common Mistakes to Avoid

- Using color as the only indicator of state
- Inconsistent spacing (3px, 7px, 13px instead of 4/8/12/16)
- Too many font sizes (more than 5-6 levels)
- No focus indicators on interactive elements
- Cards with no empty/loading/error states
- Shadows too subtle or too dramatic
- Typography that doesn't create clear hierarchy
- Ignoring the responsive breakpoints

## Quality Checklist

- [ ] Visual hierarchy is clear within 3 seconds
- [ ] Spacing follows the 8px grid
- [ ] Color contrast meets WCAG AA (4.5:1)
- [ ] All states are designed (hover, focus, active, disabled, loading, error, empty)
- [ ] Works in both dark and light themes
- [ ] Responsive at 1100px and 680px
- [ ] Typography creates clear landmarks
- [ ] Depth is used consistently (shadows/elevation)
- [ ] Interactive elements have clear affordances
- [ ] No color-only indicators
