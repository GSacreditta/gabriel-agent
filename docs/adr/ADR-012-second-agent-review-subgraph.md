# ADR-012 — Second-Agent Review as a Sub-Graph Pattern

- **Status:** Draft
- **Date:** 2026-06-20
- **Supersedes:** —
- **Related:** ADR-008 (LangGraph Supervisor), ADR-011 (Workflow Agent tier)

## Context

The InvestMemo skill specifies a "second-agent review" in [SKILL.md Step 8](../../InvestMemo_Agent/SKILL.md): an independent analytical voice that re-underwrites key numbers, runs an adversarial pass, and delivers a verdict — explicitly permitted to disagree with the primary gate/conviction.

There are two ways to implement this:

| Implementation | What it is | Failure modes |
|---|---|---|
| **Single-prompt role-play** | One LLM call instructs the model to "now switch perspective and review the above as a skeptical second analyst" | Sycophancy (LLM defers to its own prior reasoning); non-deterministic on re-entry; verdict buried in prose and must be string-parsed |
| **Sub-graph node** | Reviewer is a distinct graph node with its own system prompt, fed the primary's *final memo only* (not its reasoning chain), writing a typed verdict to state | Deterministic on checkpoint resume; verdict is a typed field; reviewer cannot be "primed" by the primary's reasoning |

## Decision

Implement second-agent review as a **distinct graph node** in the workflow agent's sub-graph. The reviewer:

- Re-underwrites key numbers independently from the same normalized inputs the primary received.
- Does **not** see the primary's reasoning chain — only the primary's final memo output.
- Has a distinct system prompt emphasizing skepticism and independent computation.
- Writes a typed verdict to `GabrielAgentState`:
  ```python
  {
      "reviewer_gate": Literal["GO", "DILIGENCE", "PASS"],
      "reviewer_conviction": int,                        # 1–5
      "agrees_with_primary": bool,
      "disagreement_summary": str | None,                # populated iff agrees_with_primary is False
  }
  ```
- Binds to the **same LLM tier** as the primary (per ADR-011) — review must not "leak up" sensitivity by using a more permissive model.

Disagreement (`agrees_with_primary == False`) triggers the second HDL interrupt defined in MULTI_AGENT_ORCHESTRATION_PLAN.md §4.5. Concurrence does not.

## Why this matters across workflows

This pattern is not InvestMemo-specific. **Every workflow agent benefits from an adversarial reviewer node:**

- TaxLetter: reviewer checks that elections, basis adjustments, and entity attributions are internally consistent.
- CapCall: reviewer verifies wire instructions against last-known-good and flags any divergence.
- DistributionRecon: reviewer recomputes the waterfall independently and compares.

The Workflow Agent Contract (ADR-011 §A.8) lists "sub-graph includes a reviewer node" as a checklist item for every new workflow.

## Consequences

- Reviewer state is auditable: the verdict is a column, not a parsed string.
- Graph resume from HDL checkpoint hits the reviewer node deterministically — no re-rolled prompt.
- HDL load stays bounded: at most one extra interrupt per deliverable, only on disagreement.
- Cost: two LLM calls per memo instead of one. Acceptable given the volume (memos are not high-throughput).

## Status

Draft. Full body and ratification deferred until Phase 4.5 implementation kickoff.
