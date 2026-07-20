# Web Frontend Guidelines

## Design System

### Color Tokens (Dark Theme — Default)
| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#07100e` | Page background |
| `--surface` | `#0d1916` | Card/panel background |
| `--surface-2` | `#12221d` | Elevated surface |
| `--surface-3` | `#193029` | Hover/active surface |
| `--line` | `#25443a` | Borders |
| `--text` | `#edf7f1` | Primary text |
| `--muted` | `#8eaaa0` | Secondary text |
| `--accent` | `#5ee0a4` | Primary action/brand |
| `--amber` | `#f4bd63` | Warning |
| `--red` | `#ff857f` | Error/destructive |
| `--blue` | `#76b6ff` | Info/link |

### Light Theme
Override via `data-theme="light"` on `:root`. All tokens remapped in `globals.css`.

### Typography
- Font: `"Segoe UI", Inter, system-ui, sans-serif`
- Mono: `"Cascadia Code", "SFMono-Regular", Consolas, monospace`
- Scale: Use `rem` for font sizes. Base is 16px.

### Spacing
8px grid: `4, 8, 12, 16, 24, 32, 48, 64`

### Border Radius
- `--radius: 14px` for cards/panels
- Use `8px` for buttons/inputs
- Use `50%` for avatars/circles

### Breakpoints
- `1100px` — Sidebar collapses to icons
- `680px` — Bottom navigation replaces sidebar

## Component Guidelines

### Existing Components (globals.css)
- `.shell` — App layout wrapper
- `.sidebar` — Left navigation
- `.brand` — Logo area
- `.nav-link` — Navigation item
- `.card` — Content container
- `.metric` — KPI display
- `.badge` — Status label
- `.table` — Data table
- `.btn` — Action button
- `.grid-4` / `.grid-3` — Responsive grid
- `.split` — Two-column layout
- `.tab-trigger` — Tab navigation
- `.toolbar` — Action bar
- `.state-panel` — Status display
- `.event` / `.timeline` — Event items

### Libraries
- `@radix-ui/react-dialog` — Modal dialogs
- `@radix-ui/react-dropdown-menu` — Dropdown menus
- `@radix-ui/react-tabs` — Tab panels
- `@tanstack/react-query` — Server state
- `@tanstack/react-table` — Data tables
- `echarts` — Charts
- `lucide-react` — Icons
- `react-hook-form` — Form state
- `zod` — Schema validation
- `openapi-fetch` — API client

## Coding Standards

### TypeScript
- Strict mode enabled
- Use interfaces for component props
- Prefer `type` for unions/intersections
- Export types alongside components

### React
- Functional components only
- Use hooks for state/side effects
- Props destructuring in function signature
- Memoize expensive computations

### CSS
- Use CSS custom properties (no magic numbers)
- Use `rem` for font sizes, `px` for borders/shadows
- Follow the spacing scale (8px grid)
- Design in both themes (dark + light)
- Responsive at 1100px and 680px

### Forms
- Use `react-hook-form` + `zod` for validation
- Labels above inputs (never placeholder-only)
- Validate on submit, then on blur
- Show errors inline near the field
- Disable submit while loading

### State
- Server state: `@tanstack/react-query`
- UI state: `useState` / `useReducer`
- URL state: Search params
- Form state: `react-hook-form`
- Global state: Context (only if truly needed)

## Accessibility

- All images have `alt` text
- All form inputs have visible labels
- Focus order is logical
- Focus indicators visible (`:focus-visible`)
- Color contrast WCAG AA (4.5:1)
- Headings create logical hierarchy (h1 > h2 > h3)
- Landmarks: `<header>`, `<nav>`, `<main>`, `<footer>`
- Dynamic content uses `aria-live`
- Keyboard navigation for all interactions
- Respect `prefers-reduced-motion`
- Modal focus trapped
- Error messages associated with fields via `aria-describedby`

## Commands

- `npm run dev` — Start dev server
- `npm run build` — Production build
- `npm run lint` — ESLint check
- `npm run typecheck` — TypeScript check
- `npm run test` — Run tests (vitest)
- `npm run test:e2e` — Playwright tests
- `npm run format` — Prettier format
- `npm run generate:api` — Regenerate API types from openapi.json

## File Structure

```
web/src/
├── app/              # Next.js App Router pages
├── components/       # Reusable UI components
├── lib/              # Utilities, API client, types
├── hooks/            # Custom React hooks
└── styles/           # Additional styles (globals.css is primary)
```
