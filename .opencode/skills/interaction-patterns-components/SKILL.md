---
name: interaction-patterns-components
description: Use when choosing or implementing interaction patterns, navigation, menus, cards, tables, dashboards, modals, flows, and component states.
---

# Interaction Patterns & Components

Navigation patterns, menus, cards, tables, dashboards, modals, flows, and state management for the IA-Investing platform.

## Core Principles

- **Start with people, goals, and context.** Not with components or technology.
- **Treat interaction as conversation.** Each screen should answer: "What can I do here?" and "What happened?"
- **Choose the simplest pattern.** Don't use a modal when a page works. Don't use a page when inline works.
- **Preserve wayfinding.** Users should always know where they are and how to get back.
- **Match pattern to data and task.** Tables for structured data. Cards for summaries. Lists for items. Dashboards for overview.

## Screen Types

| Type | Purpose | Pattern |
|------|---------|---------|
| Overview | Summary of many items | Dashboard with cards/metrics |
| Focus | Detail on one item | Detail page with sections |
| Make | Create something new | Form or wizard |
| Do | Complete a task | Flow with steps |
| Dashboard | Monitor status | Grid of metrics + charts |
| Flow | Multi-step process | Stepper or wizard |
| Workspace | Complex editing | Split panel or canvas |

## Component Patterns

### Tables
- Use `@tanstack/react-table` (already in project)
- Sortable headers, filterable columns
- Pagination or "Load more" (prefer Load more for < 100 items)
- Row actions via dropdown or context menu
- Empty state with illustration

### Cards
- Consistent padding (16px)
- Clear hierarchy: title > description > metadata
- Action buttons at bottom or in header
- Hover state for interactive cards
- Loading skeleton

### Modals/Dialogs
- Use `@radix-ui/react-dialog` (already in project)
- Only for destructive actions or focused tasks
- Always have a clear close action
- Trap focus inside the dialog
- Escape key closes

### Forms
- Labels above inputs (not placeholders)
- Validation on submit, then on change
- Clear error messages near the field
- Submit button disabled while loading
- Success feedback after submission

### Navigation
- Sidebar for global navigation (already implemented)
- Tabs for section navigation
- Breadcrumbs for deep hierarchies
- Back button for linear flows

## This Project's Components

From `globals.css`:
- `.card` — Content container with border and radius
- `.metric` — Key-value display with large number
- `.badge` — Status indicators (colors for states)
- `.table` — Data table with hover rows
- `.btn` — Action buttons (primary/secondary/ghost)
- `.grid-4` / `.grid-3` — Responsive grids
- `.split` — Two-column layout
- `.tab-trigger` — Tab navigation
- `.toolbar` — Action bar with buttons
- `.state-panel` — Status display
- `.event` / `.timeline` — Event lists

## Workflow: Choose Pattern

1. What is the user's goal on this screen?
2. What type of data are they working with?
3. What action do they need to take?
4. Choose the simplest pattern that works.
5. Design all states (empty, loading, error, success).
6. Ensure keyboard accessibility.
7. Test on mobile (680px breakpoint).
8. Document the pattern's API and usage guidelines.
