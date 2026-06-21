---
name: sternmazal18-investment-memo
description: >
  Use this skill whenever the user uploads or references deal materials for SternMazal 18 —
  including pitch decks, term sheets, PPMs, one-pagers, offering memoranda, or any investment
  opportunity — or asks to "review", "screen", "underwrite", "memo", "diligence", or "analyze"
  an investment. Triggers on any asset class: real estate, private equity, venture, private
  credit/debt, digital assets, or hybrid structures. Activate immediately on upload of deal
  materials without waiting for further instruction.
---

# SternMazal 18 — Investment Memo Skill

> Produces a 2–3 page institutional investment memo with an independent re-underwrite,
> a clear gate recommendation, and a built-in second-agent review.

**Disclaimer carried in every output:** *This memo is independent analysis prepared for
SternMazal 18's own decision-making. It is not investment, legal, or tax advice.*

---

## Trigger Conditions

Activate this skill when:
- A file is uploaded that appears to be deal materials (deck, term sheet, PPM, one-pager, CIM)
- The user asks to review, screen, underwrite, memo, analyze, or diligence an investment
- The user references a named deal or opportunity and asks for an assessment
- The user pastes deal terms or a capital structure into the chat

When triggered, immediately begin Step 1 without asking for confirmation.

---

## Required Files

| File | Status | Purpose |
|------|--------|---------|
| `SKILL.md` | This file | Operating instructions |
| `memo_template.md` | Required | Output structure |
| `scoring_rubric.md` | Required | Gate and conviction definitions |
| `house_criteria.CONFIG.md` | Optional | House criteria and portfolio context |

Check whether `house_criteria.CONFIG.md` is populated. If fields are blank or the file is
absent, run normally and flag the scorecard section as unpopulated (see Step 6).

---

## Execution — Run These Steps in Order

### Step 1 — Extract & Normalize the Deal

Pull all key terms into a normalized fact sheet regardless of asset class. Capture:

- **Sponsor / manager** — name, domicile, track record claims made in the materials
- **Asset class** — real estate, PE, VC, private credit, digital assets, hybrid
- **Instrument** — equity, preferred equity, mezzanine, LP interest, token, note, etc.
- **Check size & total raise** — investor minimum; total raise; syndicate structure
- **Stated return** — IRR, MOIC, yield, target return (as quoted in materials)
- **Hold / term** — stated duration; extension options; liquidity events
- **Fees & promote / carry** — management fee, acquisition fee, disposition fee, promote
  structure or carried interest, any other fee layers
- **Capital structure / seniority** — what is senior to the investor; LTV/LTC if applicable
- **Use of proceeds** — where the money actually goes
- **Investor rights** — voting, information, major-decision consent, removal rights

**Flag** anything material that is absent from the materials — list it explicitly at the
bottom of the fact sheet as "Missing / not disclosed."

---

### Step 2 — Independent Re-Underwrite

Do NOT accept the sponsor's numbers. Rebuild headline economics from first principles.

**Always:**

1. **Recompute MOIC and IRR yourself** from the stated cashflows. Show the arithmetic.
   Distinguish the durable multiple (MOIC) from the duration-sensitive rate (IRR).
   Show how the IRR moves if timing slips 12 and 24 months.

2. **Identify the 1–2 key value drivers** — the assumptions that explain most of the
   return (e.g., exit cap rate, exit PSF, revenue growth rate, exit multiple,
   default/recovery rate, token price). Build a simple three-scenario sensitivity:

   | Scenario | Key Assumption | MOIC | IRR | Notes |
   |----------|---------------|------|-----|-------|
   | Downside | [value] | | | |
   | Base | [value] | | | |
   | Upside | [value] | | | |

3. **Restate returns net of all fees and promote layers** the investor actually bears —
   not gross project economics. Show the fee drag explicitly.

4. **Reconcile internal inconsistencies** — if two pages of the materials show different
   headline returns, call it out and use the more conservative figure.

If cashflows are not provided, state that explicitly and note it as a question for
the promoters. Do not fabricate numbers.

---

### Step 3 — Ground in Current Reality

Search for and cite current data to test the deal's market-facing claims. For each deal:

- **Sponsor / manager track record** — verify claims; search for defaults, litigation,
  regulatory actions, negative press. If unverifiable, say so.
- **Current market pricing** — cap rates, PSF, yield spreads, entry multiples, comparables
  for the relevant asset class and geography. Trust credible current data over the deck.
- **Supply / demand dynamics** — competitive landscape, new supply pipeline, absorption.
- **Sector and macro context** — tailwinds and headwinds relevant to the thesis.
- **Regulatory / counterparty issues** — zoning, permitting, regulatory exposure, key
  counterparty creditworthiness.

Cite all external sources. Surface conflicts between the materials and current data rather
than resolving them silently.

---

### Step 4 — Risk & Merit Analysis

Produce an honest assessment. The single most important risk leads the "don't like" list.

**What I Like** — genuine merits only; avoid hollow positives.

**What I Don't Like / Key Risks** — prioritized, specific, and honest. Always interrogate:

- True concentration vs. marketed diversification
- Single-sponsor / manager correlation risk
- Liquidity and lock-up terms vs. stated need
- Capital-call or follow-on exposure
- Position in the capital stack — what is senior to the investor
- Alignment: fee leakage, promote structure, sponsor co-investment
- Asset-class-specific failure modes (see Asset-Class Lenses below)

**Strongest counter-case** — briefly argue the other side for intellectual honesty.

---

### Step 5 — Verdict

State:
- **GATE: GO / DILIGENCE / PASS** (see `scoring_rubric.md` for definitions)
- **Conviction: X/5** (see `scoring_rubric.md`)
- **The 2–3 things the decision actually hinges on**

The gate and conviction score must appear near the top of the output memo, visible
without scrolling. Do not bury the verdict at the end.

---

### Step 6 — House-Criteria Scorecard

Grade the deal against SternMazal 18's house criteria and current portfolio context.

**If `house_criteria.CONFIG.md` is populated:**
- Grade each criterion pass / fail / marginal
- Compute the deal's marginal effect on portfolio concentration by asset class, sector,
  and geography
- Flag any hard no-go triggers (auto-PASS)

**If `house_criteria.CONFIG.md` is absent or unpopulated:**
Render the scorecard skeleton with explicit placeholders and print:

> *"House criteria & portfolio data not yet available — fit scorecard shown as template;
> populate house_criteria.CONFIG.md to enable grading and concentration analysis."*

---

### Step 7 — Questions for the Promoters

A tight list (≈8–14 questions) that would resolve the biggest unknowns. Always include:

- The net-of-fees waterfall with worked numeric example
- The downside / break-even case and what makes the sponsor whole vs. the investor
- Capital-stack verification (lender commitments, loan terms, any mezzanine)
- Track-record verification — references, audited financials, realized vs. unrealized
- Specific resolution of the key sensitivities identified in Step 2
- Governance rights: consent rights, removal triggers, information rights
- Any material item flagged as missing in Step 1

Number the questions. Be specific — generic questions waste the promoters' time.

---

### Step 8 — Second-Agent Review

This section appears in a clearly separated block with a distinct reviewer voice.
Label it: `— SECOND-AGENT REVIEW —`

The reviewer must:

1. **Re-underwrite key numbers independently** — rebuild, don't just sanity-check.
   If numbers don't match the primary analysis, say so explicitly.

2. **Run a light adversarial pass:**
   - Check the primary analyst's arithmetic
   - Flag where the primary was too harsh or too lenient
   - Surface any risks the primary missed
   - Argue the strongest counter-case briefly for intellectual balance

3. **Deliver a verdict on the analysis quality:**
   - Is the gate/conviction score appropriate?
   - Are there changes required before this reaches the principal?
   - The reviewer is permitted — and expected — to disagree with the primary gate/score
     and must say so explicitly if they do

The second-agent section should be roughly ½–¾ page.

---

## Asset-Class Lenses

The skill auto-selects the matching lens based on Step 1. Apply all relevant lenses
for hybrid structures, weighted by capital allocation.

### Real Estate / Real Assets
Basis vs. market; going-in vs. exit cap rate and spread; LTC and LTV; contingency
adequacy; absorption / lease-up assumptions; submarket supply pipeline; sensitivity
to exit cap and pricing; geographic / insurance / climate / permitting risk.

### Private Equity / Venture
Entry multiple vs. sector comparables; revenue growth and margin assumptions vs.
public comps; exit multiple realism (avoid assuming expansion); cap table and dilution
path; burn rate and runway; TAM / competitive moat durability; governance and
information rights; LP / GP alignment.

### Private Credit / Debt
Yield vs. credit risk; seniority and security package; covenant quality; LTV and
coverage ratios; default and recovery scenarios; duration and refinance risk; sponsor
recourse and guarantee structure; liquidity of the instrument.

### Digital Assets / Emerging Tech
Token / economic design and value accrual; custody and counterparty risk; regulatory
exposure and jurisdiction; liquidity and lock-up mechanics; volatility and drawdown
tolerance; thesis durability vs. competitive / technical disruption; whether returns
are speculative price appreciation vs. cash-flow-backed.

---

## Output Format

Follow `memo_template.md` exactly. Target **2–3 pages** of printed output.

- **Prose-forward** — tables and lists only where they aid clarity
- **Gate and conviction visible near the top** — principal must see recommendation
  without scrolling
- **Sources cited** in the footer alongside the as-of date
- **Not-advice disclaimer** in the header and footer of every memo

---

## Grounding & Guardrails

- Never fabricate figures, cashflows, or sponsor history
- If a number is not in the materials and cannot be sourced, say so and add it to the
  question list
- Trust credible current data over the materials; surface conflicts explicitly
- Always include the strongest counter-case for intellectual balance
- Do not be reflexively negative — honest assessment includes genuine merits
- Keep the memo skimmable in five minutes for a principal
