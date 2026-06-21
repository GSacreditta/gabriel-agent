# ADR-011 — Workflow Agent Tier

- **Status:** Draft
- **Date:** 2026-06-20
- **Supersedes:** —
- **Related:** ADR-008 (LangGraph Supervisor), ADR-009 (Hybrid LLM tier), ADR-012 (Second-agent review sub-graph)

## Context

The agent roster defined in [docs/MULTI_AGENT_ORCHESTRATION_PLAN.md §3.2](../MULTI_AGENT_ORCHESTRATION_PLAN.md) is currently all **infrastructure** — DB, File Management, Extraction, Storage, HDL, Research. Each owns a horizontal primitive (CRUD, file ops, OCR, vector ops, approval, retrieval). None owns a named domain deliverable.

SternMazal 18 needs many **vertical** agents that compose those primitives to produce house-specific artifacts: investment memos, year-end tax letters, capital-call reconciliations, distribution-waterfall checks. The first of these — the InvestMemo agent — is specified at [InvestMemo_Agent/SKILL.md](../../InvestMemo_Agent/SKILL.md) with template, scoring rubric, and house-criteria config. Without an architectural tier for this class, every new workflow agent becomes a bespoke integration decision.

## Decision

Formalize a **Workflow Agent tier** alongside the infrastructure tier. The tier is a *convention*, not a new base class. Every workflow agent:

1. Lives at `app/agents/<name>/` with three siblings — `agent.py` (BaseAgent subclass), `nodes/` (sub-graph nodes), `skill/` (human-editable spec).
2. Ships a `skill/` folder with `SKILL.md` + at least one template + `scoring_rubric.md` + `<house>_criteria.CONFIG.md`.
3. Composes infrastructure agents through the graph — never calls OCR/PDF/FAISS/Drive services directly.
4. Declares its LLM sensitivity tier in agent metadata; the LiteLLM gateway enforces.
5. Interrupts via HDL at exactly two points per deliverable: primary draft, reviewer verdict (only on disagreement).
6. Persists output to a workflow-specific Postgres table with rubric outputs as first-class columns.

Full contract: [MULTI_AGENT_ORCHESTRATION_PLAN.md Appendix A](../MULTI_AGENT_ORCHESTRATION_PLAN.md#appendix-a--workflow-agent-contract).

## Reference Implementation

**InvestMemo Agent** — produces SternMazal 18 investment memos from deal materials. Skill spec at [InvestMemo_Agent/](../../InvestMemo_Agent/), to be relocated to `app/agents/invest_memo/skill/` in Phase 4.5.

## Consequences

- New workflow agents are mechanical to add: copy the InvestMemo skeleton, swap the skill folder, declare the tier binding, register in the supervisor router.
- Directors can edit `house_criteria.CONFIG.md` for any workflow without a code change.
- HDL inbox can filter by `request_type` prefix for per-workflow review queues.
- The tier is extensible: TaxLetter, CapCall, DistributionRecon are pre-reserved slots.

## Status

Draft. Full body and ratification deferred until Phase 4.5 implementation kickoff (gated on DB-auth fix + LangGraph harness + local LLM tier).
