---
name: information-architecture-navigation
description: Use when designing or reviewing navigation, labels, taxonomy, search, content grouping, and wayfinding in the web frontend.
---

# Information Architecture & Navigation

Navigation, labels, taxonomy, hierarchy, search, content grouping, and wayfinding for the IA-Investing platform.

## Core Principles

- **Design for finding AND understanding.** IA isn't just navigation—it's how users build a mental model of the system.
- **Start from users, content, and context.** Not from the org chart or database schema.
- **Support multiple paths.** Users think differently. Provide search, filters, shortcuts, and structured navigation.
- **Make invisible IA explicit.** Labels, breadcrumbs, and structure should be visible and consistent.
- **Use labels as promises.** Every label must accurately describe what's behind it. No jargon, no ambiguity.

## This Project's Navigation

Current routes in `web/src/app/`:
- `/agents` — AI agent management
- `/assets` — Instrument catalog
- `/audit` — Audit trail
- `/backtests` — Backtesting
- `/committee` — Committee decisions
- `/data-quality` — Data quality monitoring
- `/login` — Authentication
- `/macro` — Macro/policy data
- `/opportunities` — Investment opportunities
- `/paper` — Paper trading
- `/policy` — Policy events
- `/portfolios` — Portfolio management
- `/risk` — Risk assessment

Current sidebar: task-driven, green accent (#5ee0a4), collapses at 1100px to icons, bottom nav at 680px.

## Workflow: Critique IA

1. List all main navigation items and their labels.
2. Group items by user task, not by data type.
3. Check if labels are plain language (no jargon).
4. Verify the hierarchy: global nav > section nav > local nav.
5. Test if a new user can find [feature X] in < 3 clicks.
6. Check if search covers all major content types.
7. Verify breadcrumbs match the navigation hierarchy.
8. Check if filters and sort options make sense for the data.
9. Test empty states for navigation guidance.
10. Document specific IA improvements.

## Workflow: Create IA

1. List all content types and their relationships.
2. Group by user tasks (research, monitor, decide, execute).
3. Design the navigation hierarchy (max 3 levels deep).
4. Write labels in plain language.
5. Design the search experience (what's searchable, results format).
6. Create filter/sort patterns for each data type.
7. Design breadcrumbs and wayfinding elements.
8. Test with 5 sample user tasks.
9. Document the IA map.
10. Implement navigation components.
11. Add keyboard shortcuts for power users.
12. Review against common mistakes.

## Default Patterns for This Project

- **Global nav:** Sidebar with icons + labels, collapses to icons only.
- **Section nav:** Tabs or sub-nav within each page.
- **Local nav:** Breadcrumbs + action buttons.
- **Search:** Global search bar in the header.
- **Filters:** Sidebar or above-table filters with clear labels.
- **Empty states:** Title + description + action button.
