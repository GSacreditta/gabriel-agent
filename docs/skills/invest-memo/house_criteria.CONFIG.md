# SternMazal 18 — House Criteria & Portfolio Context

> **Status: UNPOPULATED**
> This file has not yet been filled in. Until populated, investment memos will run
> normally but the fit scorecard (Section 6) will display as a template with
> placeholder values and the following notice:
>
> *"House criteria & portfolio data not yet available — fit scorecard shown as
> template; populate house_criteria.CONFIG.md to enable grading and concentration
> analysis."*
>
> To activate the scorecard, fill in the fields below and save this file into the
> SternMazal 18 project. The skill will detect the populated fields automatically.

---

## Instructions for Populating This File

- Replace each `[FILL IN]` with the actual value
- For fields that do not apply, write `N/A`
- For lists, add as many items as needed using the same bullet format
- Do not change the field labels — they are referenced by the skill
- After populating, the skill will use these criteria to grade every memo and compute
  concentration impact automatically

---

## Part A — Return Thresholds

```
MINIMUM_IRR_NET:         [FILL IN]    # e.g., 15% net of fees — applies to all asset classes
MINIMUM_MOIC_NET:        [FILL IN]    # e.g., 1.7x net of fees
MINIMUM_YIELD_CREDIT:    [FILL IN]    # e.g., 10% current yield — applies to credit/debt only
TARGET_IRR_NET:          [FILL IN]    # e.g., 20% — "sweet spot" used in conviction scoring
TARGET_MOIC_NET:         [FILL IN]    # e.g., 2.0x
```

---

## Part B — Deal Sizing

```
MINIMUM_CHECK_SIZE:      [FILL IN]    # e.g., $500,000
MAXIMUM_CHECK_SIZE:      [FILL IN]    # e.g., $5,000,000
```

---

## Part C — Concentration Limits

```
MAX_SINGLE_DEAL_PCT:     [FILL IN]    # e.g., 5% of investable assets
MAX_SINGLE_SPONSOR_PCT:  [FILL IN]    # e.g., 10% across all deals with one sponsor/manager
MAX_ASSET_CLASS_PCT:     [FILL IN]    # e.g., 40% in any single asset class
MAX_SECTOR_PCT:          [FILL IN]    # e.g., 25% in any single sector
MAX_GEOGRAPHY_PCT:       [FILL IN]    # e.g., 60% in any single country; 30% in any single metro
```

---

## Part D — Liquidity & Lock-Up

```
MAX_LOCKUP_YEARS:        [FILL IN]    # e.g., 7 years — hard limit on illiquid exposure
MAX_ILLIQUID_PCT:        [FILL IN]    # e.g., 50% of portfolio in lock-up at any time
```

---

## Part E — Current Portfolio Weights

*Fill in current allocations as a percentage of total investable assets.
These are used to compute the marginal impact of each new deal.*

```
CURRENT_WEIGHT_REAL_ESTATE:       [FILL IN]%
CURRENT_WEIGHT_PRIVATE_EQUITY:    [FILL IN]%
CURRENT_WEIGHT_VENTURE:           [FILL IN]%
CURRENT_WEIGHT_PRIVATE_CREDIT:    [FILL IN]%
CURRENT_WEIGHT_DIGITAL_ASSETS:    [FILL IN]%
CURRENT_WEIGHT_PUBLIC_EQUITIES:   [FILL IN]%
CURRENT_WEIGHT_CASH_EQUIVALENTS:  [FILL IN]%
CURRENT_WEIGHT_OTHER:             [FILL IN]%

CURRENT_WEIGHT_US:                [FILL IN]%
CURRENT_WEIGHT_EUROPE:            [FILL IN]%
CURRENT_WEIGHT_ASIA_PACIFIC:      [FILL IN]%
CURRENT_WEIGHT_LATIN_AMERICA:     [FILL IN]%
CURRENT_WEIGHT_OTHER_GEO:         [FILL IN]%
```

---

## Part F — Sectors to Promote (Overweight / Prioritize)

*Deals in these sectors should be flagged positively in the scorecard.*

```
SECTORS_TO_PROMOTE:
  - [FILL IN]    # e.g., Industrial / Logistics real estate
  - [FILL IN]    # e.g., Healthcare / Life Sciences
  - [FILL IN]    # e.g., AI / ML infrastructure
  - [FILL IN]    # Add more as needed
```

---

## Part G — Sectors to Avoid (Underweight / Exclude Short of Hard No-Go)

*Deals in these sectors should receive a negative flag in the scorecard
but are not automatic passes unless also listed under Hard No-Gos.*

```
SECTORS_TO_AVOID:
  - [FILL IN]    # e.g., Retail real estate (class B/C malls)
  - [FILL IN]    # e.g., Fossil fuel extraction
  - [FILL IN]    # Add more as needed
```

---

## Part H — Hard No-Gos (Automatic PASS Triggers)

*Any deal matching a criterion here receives an automatic PASS regardless of
return, conviction, or gate — even if the primary analysis rates it GO.*

```
HARD_NO_GO_TRIGGERS:
  - [FILL IN]    # e.g., Any deal with > 2x leverage on a levered vehicle
  - [FILL IN]    # e.g., Deals where the sponsor has prior defaults with investor losses
  - [FILL IN]    # e.g., Geographies subject to OFAC sanctions
  - [FILL IN]    # e.g., Any deal structured in [specific jurisdiction]
  - [FILL IN]    # e.g., Instruments with no investor consent rights on major decisions
  - [FILL IN]    # Add more as needed
```

---

## Part I — Special Notes / Standing Instructions

*Any other standing instruction, preference, or context the skill should
carry into every memo.*

```
STANDING_NOTES:
  - [FILL IN]    # e.g., "Principal prefers co-investments over blind-pool funds"
  - [FILL IN]    # e.g., "Always note if the sponsor is a first-time fund manager"
  - [FILL IN]    # e.g., "Flag deals where total fee load exceeds 2% per annum"
  - [FILL IN]    # Add more as needed
```

---

*Last updated: [DATE]*
*Populated by: [NAME / ROLE]*
