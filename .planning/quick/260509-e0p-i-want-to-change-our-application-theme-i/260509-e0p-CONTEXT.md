---
name: Quick Task 260509-e0p Context
description: Locked decisions for blue/purple glass morphism theme rollout
type: quick-task-context
---

# Quick Task 260509-e0p: Blue/Purple Glass Morphism Theme - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning

<domain>
## Task Boundary

Change the application theme to a blue/purple glass morphism design. Scope is the Next.js frontend (`frontend/`): the global stylesheet, layout, and existing components (ChatApp, chat, dashboard, shared, sidebar, trace). Backend, agent logic, and data pipeline are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Color Palette
- **Dark cosmic** palette only (no light mode, no toggle).
- Base: deep navy/indigo (around `#0a0a1a` / `#0f0f23`).
- Primary brand: blue (`#3b82f6` family) → purple/violet (`#8b5cf6` family) gradient.
- Accents: cyan/violet highlights for focus, links, and active states.
- Text: high-contrast off-white (`#e5e7ff`-ish) for body, muted lavender for secondary.

### Glass Intensity
- **Medium frost** as the default surface treatment.
- `backdrop-filter: blur(12px)` (with `-webkit-` fallback).
- Surface fill ≈ `rgba(255,255,255,0.08–0.10)` over the dark base.
- 1px gradient border (blue→purple at low opacity) on cards/panels.
- Subtle inner highlight (top edge) for the "glass" feel; soft outer shadow for depth.
- Apply consistently to: sidebar, chat bubbles (assistant + user differentiated), dashboard cards, trace panels, modals/popovers.

### Background Treatment
- **Static gradient mesh** behind everything.
- 2–3 large radial-gradient "blobs" (blue + purple + a touch of cyan) positioned to corners, fixed (no animation, no JS).
- Implemented in CSS on `body` / a root background layer so it never scrolls or repaints per route.
- Goal: visible through glass surfaces, never competing with content.

### Claude's Discretion
- Exact hex values within the chosen families (pick a coherent set; document them as CSS custom properties / Tailwind theme tokens).
- Token naming (e.g. `--surface-glass`, `--border-glass`, `--bg-mesh-1`) and where they live (`globals.css` via Tailwind v4 `@theme` block is preferred since the project uses Tailwind v4).
- Specific component-by-component class application — keep it consistent, do not redesign layouts.
- Hover/focus/disabled states: derive logically from the palette (slightly brighter fill on hover, ring with brand gradient on focus).
- Scrollbar styling and selection color to match the theme (nice-to-have, not required).
- Reduced-motion / accessibility: keep contrast ratios readable (WCAG AA on body text); since background is static, no motion concerns.

</decisions>

<specifics>
## Specific Ideas

- Stack is Next.js 15 + React 19 + Tailwind v4 (CSS-first config — `@import "tailwindcss";` in `frontend/app/globals.css`, no `tailwind.config.*`). Theme tokens should be defined via Tailwind v4's `@theme` directive in `globals.css`.
- Existing component areas to restyle: `frontend/components/ChatApp.tsx`, `frontend/components/chat/`, `frontend/components/dashboard/`, `frontend/components/shared/`, `frontend/components/sidebar/`, `frontend/components/trace/`, plus `frontend/app/layout.tsx` for the root background layer.
- No new heavyweight UI libraries — restyle in place using Tailwind utilities and a small set of reusable glass classes/tokens.

</specifics>

<canonical_refs>
## Canonical References

No external specs. Decisions above are the contract.

</canonical_refs>
