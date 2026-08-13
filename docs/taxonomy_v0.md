# Taxonomy v0

**Backlog task:** M2.11. **Status:** draft, single-company (Shoprite, SHP),
derived from the FY2024 and FY2025 golden workbooks
(`data/golden/shoprite_SHP_FY2024_hand_entry.xlsx`,
`data/golden/shoprite_SHP_FY2025_hand_entry.xlsx`) and their
`Concepts_Discovered` / `Structural_Changes` sheets. This is a **document**,
not a seed script — M2.12's loader is the first thing allowed to write any of
this into the `concepts` table. Nothing here has been executed against the
database.

Every concept below is traceable to a line that actually appears in one of
the two source documents (Shoprite Annual Financial Statements FY2024 or
FY2025). Nothing was imported from general accounting knowledge because it
seemed like it ought to exist — see the Completeness Check for proof of that
claim, not just an assertion of it.

---

## 1. How to read this document

- **§2** resolves the six questions the task posed, in order, before the
  concept list — the list only makes sense once these are decided.
- **§3** is the concept list itself: one row per concept, with statement,
  sign convention, unit type, archetype set, a one-line definition, and the
  as-reported label(s) it maps to in FY2024 and FY2025.
- **§4** is the completeness check: every `as_reported_label` in both
  workbooks, accounted for.
- **§5** states which concepts are expected to generalise to banks and which
  are retail-only, and the evidence for each call.
- **§6** is the honesty section: which of these decisions are single-company
  artifacts likely to be overturned at M8.7, and why.

---

## 2. The six questions, resolved

### (a) Which line is `revenue`?

**Decision:** `revenue` = Sale of merchandise alone (252,701 in FY2025;
232,088 restated FY2024; 240,718 as-originally-reported FY2024). The printed
"Revenue" total (256,682 FY2025; 246,082 as-originally-reported FY2024) is a
separate concept, `revenue_total`.

**Reasoning:** the task's own framing states it plainly — "Sale of
merchandise alone ... is what an analyst models" — and `Concepts_Discovered`
row 2 (FY2025 workbook) flags exactly this ambiguity as needing a decision.
An analyst opening a model and typing "Revenue" means the core retail line,
not the sum that happens to include interest income. Giving the modelled
number the short, obvious code (`revenue`) and the printed total the explicit
one (`revenue_total`) matches how the number is actually used, not how it is
printed.

**Why this survives the FY2024→FY2025 component change:** the composition of
`revenue_total` changed (four components in FY2024: merchandise + other
operating income + interest + insurance; three in FY2025: merchandise +
alternative revenue + interest — insurance revenue was reclassified to
discontinued operations). `revenue` itself did not change definition across
that shift — it is still, in both years, the single printed "Sale of
merchandise" line. The decision is stable precisely because it does not
depend on counting components of a total; it points at one line that exists,
unchanged in meaning, in both years. `revenue_total`'s component structure
changing is exactly why M5.5 cannot hardcode what sums to it (see
`PROGRESS.md`'s "Validation rules cannot hardcode the composition of a
total") — but that is a fact about validating `revenue_total`, not about
what `revenue` means.

**What would change my mind:** if a second company in scope prints no
"Revenue" total at all and calls its merchandise line "Revenue" directly
(plausible for a single-segment retailer with no interest/investment
income), `revenue` and `revenue_total` would collapse to the same fact for
that company — which the schema already handles (`company_line_items` maps
two different as-reported labels to the same `concept_id` for two different
companies without conflict). That is not evidence v0's choice was wrong,
just that not every company needs both concepts populated.

### (b) Scope

**Decision:** one concept per scope, not a scope attribute on `facts`. E.g.
`total_current_assets_incl_hfs` and `current_assets_excl_hfs` are two
concepts, not one `current_assets` concept with a `scope` column.

**Reasoning, weighed explicitly as asked:**

- **Cost side.** `facts` is the table CLAUDE.md and the MVP spec (§7, "the
  fact schema is the only component where a mistake requires migrating live
  customer data") name as the one expensive-to-change table. `concepts` is
  cheap — a new row, no migration, no backfill of existing facts. Given a
  real cost asymmetry, the design that keeps the expensive table unchanged
  wins by default.
- **Scope is not one axis.** The task names three: held-for-sale
  (included/excluded), continuing-vs-total (the cash flow's "Operating
  profit" 15,380 vs the income statement's 14,943 — cash flow includes
  discontinued operations, `Concepts_Discovered` row 7), and
  segment-vs-consolidated (already resolved differently — see below). A
  single `scope` enum column could not hold "held-for-sale-excluded AND
  continuing-only AND pre-hyperinflation" simultaneously without becoming a
  bitmask or a second normalized table, which is exactly the schema
  complexity a `concepts` row avoids by simply being a distinct row.
- **The golden dataset itself already decided this**, independently of this
  document. `shoprite_SHP_FY2024_hand_entry.xlsx`'s BalanceSheet sheet
  captures BOTH `total_current_assets_incl_hfs` (the printed "Current
  assets" heading, 50,059) AND a separately-labelled
  `current_assets_excl_hfs` (the unlabelled subtotal directly above the
  held-for-sale line, 49,103) as two rows with two different
  `concept_suggestion` values, and `Checks` row 5 validates
  `current_assets_excl_hfs + assets_held_for_sale = total_current_assets_incl_hfs`
  as a three-concept identity. That check could not be written against a
  single `current_assets` concept plus a scope column without the check
  itself encoding which scope value means what — i.e. the check would still
  need to know there are two distinct things, so the "one concept + scope"
  design does not actually save anything at the point where scope matters
  most.
- **Segment scope: revised at M2.12 — see §3.5.** This section originally
  argued segment-vs-consolidated should NOT be modelled as separate
  concepts (`segment_trading_profit_supermarkets_rsa`,
  `segment_trading_profit_consolidated`, ...), on the reasoning that ONE
  concept (`segment_trading_profit`) mapped by six different
  `company_line_items` rows (one per `as_reported_label` value) keeps
  scope in the as-reported label, matching the other scope axes below.
  **Building the M2.12 loader found this reasoning incomplete**: unlike
  held-for-sale or continuing-vs-total scope, segment values must coexist
  as multiple simultaneous facts for the same company/period/basis, and
  `facts`' actual uniqueness (the M1.8 exclusion-constraint key) permits
  only one current fact per concept per company/period/basis — one shared
  concept across segments would make every segment after the first
  silently supersede and destroy the previous one. §3.5 now gives each
  (metric, segment) pair its own concept — the "six-plus concepts per
  metric" cost this bullet originally weighed against is exactly what was
  paid, once the alternative was found to silently corrupt data rather
  than merely cost more concept rows. The broader principle (scope lives
  in `concepts`, not in a new column on `facts`) still holds — this is a
  correction to which scope-encoding *mechanism* segments specifically
  need, not a reversal of that principle.

**How M5.3's balance rule knows which scope it has:** it does not need to
"know" a scope value — it composes the specific concepts its identity
requires (`current_assets_excl_hfs + assets_held_for_sale =
total_current_assets_incl_hfs`) by `concept_id`, the same way it already
composes `revenue - cost_of_sales = gross_profit`. Concept identity IS the
scope disambiguation; there is nothing further to resolve at query time.

**What would change my mind:** if scope combinations proliferated
multiplicatively (e.g. every one of ~150 concepts needing a held-for-sale
variant AND a continuing-operations variant AND a pre-hyperinflation
variant, independently), one concept per combination would produce an
unmanageable concept count and a scope attribute would start looking
cheaper than it does now. The evidence in two years of one company does not
show that: scope splits appear on perhaps a dozen concepts, not all of them,
and only where the company's own disclosure actually draws the distinction.

### (c) Unlabelled subtotals

**Decision:** synthesise-and-flag, exactly as the golden dataset already
does, with the bracketed convention `[unlabelled subtotal] <description>` as
the `as_reported_label`. No schema change. This closes the `PROGRESS.md`
open question "Unlabelled subtotals ... Decide in M2.11" — see below for
why no new column is needed, stated as a decision with its cost, not an
aside.

**Reasoning:** the open question asked whether this needs a new column on
`company_line_items` (`label_provenance`) plus a scope qualifier on `facts`.
It does not, because (b) above already resolves the actual problem these
five figures raise: they are not really "labels with no name," they are
**scope variants of an already-labelled total**, and (b) already handles
scope via distinct concepts. `current_assets_excl_hfs` is not a mystery
number needing a provenance flag — it is the held-for-sale-excluded scope of
"Current assets," which (b) already gives its own concept. The same applies
to the other four: `equity_attributable_owners` (the FY2024 unlabelled
subtotal above "Non-controlling interest," scope-excluded from `total_equity`),
and the FY2025 cash-flow / current-liabilities analogues the earlier open
question named but which are not separately captured as rows in either
golden workbook (see §4's unmapped list — they were noted as a phenomenon in
`Concepts_Discovered` and `PROGRESS.md`, but the workbook itself only
transcribed two of the five as actual rows: `current_assets_excl_hfs` and
`equity_attributable_owners`).

**The bracketed label is the flag**, doing the job `label_provenance` would
have done, at zero schema cost: `as_reported_label = '[unlabelled subtotal]
current assets excluding held for sale'` is self-documenting in the same
column every other row already uses, greppable, and requires no migration.
The alternative (a new `label_provenance` enum column: `printed` |
`synthesised`) is a real design that would cost a migration on
`company_line_items` (cheaper than `facts`, but still a schema change with a
backfill question for every existing row) for information the bracket prefix
already conveys in-band. Rejected for that reason: it is not that the column
is a bad idea, it is that it buys nothing the string convention doesn't
already buy, once (b) has already solved the harder half of the problem
(distinguishing what the number IS, not just flagging that its label was
missing).

**What would change my mind:** if a query needed to programmatically filter
"give me only synthesised labels" at scale (e.g. an audit report of every
place extraction invented wording), a real column beats a string prefix
convention. No such consumer exists yet.

**Known weakness, recorded rather than fixed:** the bracketed prefix is a
**convention, not a constraint.** Nothing in the schema enforces it —
`as_reported_label` is a plain `text not null` column, and there is nothing
stopping a future row from being synthesised without the prefix, or a
non-synthesised row from happening to start with a bracket. Any consumer
that needs to distinguish "the company printed this" from "extraction
invented this wording" has no column to query; it must parse the string.
The specific fragility: a query for "labels that are genuinely as-reported"
becomes a `LIKE '[unlabelled subtotal]%'` exclusion pattern against a magic
prefix, and that pattern is silently defeated by either a company that
legitimately prints a bracketed label on the face of a statement (not
observed in Shoprite's two years, but not excludable for a company not yet
examined), or a reviewer manually typing a variant of the convention
(`[synthesised]`, `[no label]`, a missing space) that means the same thing
to a human but not to a `LIKE` pattern. This is also in real tension with
principle 3: `as_reported_label` is documented (`company_line_items`'s own
migration comment, and the golden workbook's README) as "verbatim, as
printed by the company" — the words on the page, nothing added. A
synthesised value living in that column means the column no longer has one
meaning; it holds two different kinds of thing (what was printed, and what
extraction decided to call something that wasn't) distinguishable only by a
convention no constraint enforces. **Accepted for v0 because nothing
downstream depends on distinguishing the two yet, and the shape of the
eventual consumer isn't known.** The trigger for revisiting: **M7.4, the
review UI.** A reviewer looking at a synthesised label needs to SEE that it
was synthesised — that is a first-class display requirement (a badge, a
visual treatment, something a UI renders deliberately), not something the
UI should infer by pattern-matching punctuation in a string it happens to
be displaying. If M7.4 needs that distinction to render correctly, a real
`label_provenance` column on `company_line_items` becomes justified by an
actual consumer's actual requirement, not by anticipating one now. Not
built here for that reason — see M8.7's warning that redesign at the point
of real evidence beats guessing at the shape of a column before anything
needs it.

### (d) Company-defined measures

**Decision:** yes, concepts (`trading_profit`, `items_of_capital_nature`) —
capturing them is explicitly instructed by the README's own words ("Analysts
model trading profit heavily, so capture it") and both are in the concept
list below. Marked as company-defined via **the concept's one-line
definition text stating the source policy note**, not a new boolean column.

**Reasoning:** `trading_profit` and `items_of_capital_nature` are Shoprite's
own accounting-policy-note-1.1.2 constructs, not IFRS line items —
`Concepts_Discovered` rows 3 and 4 flag this explicitly as needing a
decision, and the README repeats the warning under "COMPANY-DEFINED
MEASURES." They must be concepts because the alternative (leaving them
unmapped, `company_line_items.mapping_status = 'unmapped'`) would mean
"trading profit" — the single most analyst-modelled non-GAAP line on this
statement — never becomes a queryable fact, which defeats the product.

A boolean `is_company_defined` column on `concepts` was considered and
rejected for v0: with exactly two company-defined concepts identified from
one company, a column carrying that fact for two rows out of ~150 is
premature structure for a signal the concept's own definition text already
carries in readable form. If M8.7 finds this recurring heavily across three
companies — which is plausible, since non-GAAP "trading profit"-style
measures are common in SA retail — a real column becomes worth its
migration cost at that point, with three companies' evidence instead of
one's.

**What happens at M8.7 if another company defines "trading profit"
differently:** this is not answered here — the task asks me to decide
whether these are concepts and how they're marked, not to pre-solve M8.7's
reconciliation. What I can state: v0's `trading_profit` concept is defined,
in its one-line definition, as *Shoprite's* trading profit per policy note
1.1.2, not a generic "trading profit" IFRS-equivalent. If Pick n Pay
discloses its own "trading profit" with a different policy definition, M8.7
has two honest options — treat them as the same concept if the definitions
are economically equivalent despite different wording (analysts already do
this informally), or split into `trading_profit_shp` /
`trading_profit_pnp`-style company-qualified concepts if they are not
comparable. v0 deliberately does not pre-guess which, because doing so
before seeing Pick n Pay's actual definition would be exactly the "import
concepts because they seem like they ought to exist" mistake the task
warned against, aimed at a company not yet examined. Flagged in §6 as an
expected M8.7 friction point.

**Known weakness, recorded rather than fixed:** same class of problem as
(c)'s bracket prefix, for the same reason. Company-defined status is
recorded in the concept's free-text definition ("**COMPANY-DEFINED**
measure, not IFRS. Defined in policy note 1.1.2(a)...") — this is a
**convention, not a constraint.** Nothing in the `concepts` schema
distinguishes a company-defined concept from an IFRS one; both are a
`text` `label`/definition with no flag. Any consumer that needs to act on
"is this concept company-defined" — to render a warning, to exclude it from
a cross-company comparison, to route it for extra review — must parse the
definition text for a marker like "COMPANY-DEFINED," which is exactly as
fragile as (c)'s bracket: a future concept added without that exact phrase
in its definition (a typo, a paraphrase, a reviewer who forgets the
convention) is silently indistinguishable from an IFRS-standard concept to
any such consumer. Unlike (c), this is not in tension with a stated
principle — `concepts.label`/definition text has no as-printed-verbatim
requirement the way `as_reported_label` does — but the operational fragility
is the same. **Accepted for v0 for the same reason as (c): nothing
downstream depends on distinguishing company-defined concepts
programmatically yet.** The same trigger applies: if **M7.4**'s review UI
needs to visually flag a company-defined concept as first-class UI
behaviour (so a reviewer or, eventually, an analyst comparing companies
sees the flag rather than having to already know Shoprite's policy note
1.1.2 by heart), a real `is_company_defined` boolean on `concepts` — already
proposed and deferred above — becomes justified by that concrete consumer.

### (e) Granularity

**Rule:** a line earns a concept if it is a distinct number printed on the
face of a primary statement, or in a note this task's source sheets
transcribed (segments note 2.1, HEPS reconciliation note 36), **regardless
of whether it is a subtotal mechanically derivable from other captured
concepts.** Two exceptions, both narrow:

1. **HEPS reconciliation gross/tax/net triplets** (e.g. "Profit on disposal
   of assets classified as held for sale [gross/tax effect/net]"): all
   three get concepts, not just net. Reasoning: SAICA Circular 1/2023's
   reconciliation format prints all three for every adjustment, the golden
   dataset's own note in row 34 of the FY2025 HEPS sheet explicitly flags
   this as "the treatment an engineer would get wrong," and `net` is not
   always simply `gross - tax` in a way a validator could reconstruct
   without also capturing tax (NCI-attributable adjustments net a third
   quantity in). Each triplet is one printed disclosure with three
   dimensions, not three redundant numbers.
2. **Item-specific HEPS adjustment lines are NOT individually generalised
   into reusable concepts beyond what actually recurs.** "Remeasurement of
   investment in joint venture to fair value on deemed disposal of Pingo
   Delivery (Pty) Ltd" got its own concept
   (`heps_adj_jv_remeasurement_{gross,tax,net}`) because it is a real,
   printed, material FY2025 line (R341m, the largest single adjustment that
   year per the workbook's own note) — but it is Shoprite-FY2025-specific
   and will very likely never recur verbatim. It is captured anyway, per
   the primary rule (it is a distinct printed number), not filtered out for
   being one-off. The alternative — a generic
   `heps_adj_other_{gross,tax,net}` bucket for anything not matching a
   known pattern — was rejected because it would silently merge genuinely
   different one-off events across years and companies into one
   uninterpretable "other," destroying exactly the specificity principle 3
   (as-reported never destroyed) protects.

**What does NOT earn a concept:** nothing in the two workbooks was excluded
on granularity grounds — every row that has a real `as_reported_label` (or a
synthesised one under (c)) got a concept. The FY2025 workbook's own
`Restatement_N45` and FY2024's `Bitemporal_Pair` sheets are demonstration
fixtures (bitemporal test cases), not new concepts — they reuse concepts
already defined from the primary statement sheets. Two of their
`concept_suggestion` values (`other_operating_income_/_alternative_revenue`,
`headline_earnings_per_share_-_total_(cents)`) are literally invalid under
the `concepts.code` CHECK constraint (contain `/`, `(`, `)`, `-`) — clear
evidence they are auto-generated label slugs, not real proposals, and are
mapped in §4 to the correct existing codes (`alternative_revenue`,
`heps_total`) rather than taken at face value.

**Consequence for count:** this rule produces roughly 150 non-segment
concepts from one company's two years, dominated by the ~30 HEPS
reconciliation line items. That is a real, stated cost of granularity —
see §6.

### (f) Sign convention

**Rule applied:** every concept that is naturally negative when it reduces
its parent total — i.e. printed in parentheses in the AFS, per the README's
own instruction that "Parentheses in the AFS mean negative" — is
`sign_convention = 'signed'`, stored with the sign it contributes (cost of
sales as a negative number). Concepts that are always positive magnitudes
regardless of role (revenue, assets, headline earnings) are `'natural'`.
This matches exactly the two definitions in the `concepts` migration's own
comment (`natural`: positive magnitude, caller applies the sign; `signed`:
stored with contributing sign, so summation works directly).

**Checked against M5.5's gross profit rule:** `revenue` (`natural`, always
positive) `+ cost_of_sales` (`signed`, stored negative, e.g. -191,259) `=
gross_profit` (`natural`, positive) works by plain addition:
252,701 + (-191,259) = 61,442, which matches the printed FY2025 gross
profit exactly. This is not hypothetical — it is the same arithmetic
`Checks` row 3/4 in both golden workbooks already verifies, and the
`cost_of_sales` row in the FY2025 IncomeStatement sheet is explicitly
annotated `"Printed in parentheses = negative. sign_convention 'signed'"`
— the golden dataset's own creator reached the same rule independently
while transcribing.

**Applied consistently:** every income-statement expense/deduction line
(cost of sales, depreciation, employee benefits, credit impairment losses,
other operating expenses, finance costs, income tax expense, most HEPS
adjustment lines with a negative printed value) is `signed`. Balance-sheet
contra items that reduce their section total when printed negative
(treasury shares, non-controlling interest when negative) are also
`signed`, for the same reason: `total_equity = stated_capital +
treasury_shares(signed) + reserves + non_controlling_interest(signed)` must
foot by plain addition, matching the FY2025 workbook's stated
`treasury_shares = -3,756` and `non_controlling_interest = -77`.

---

## 3. Concept list

Columns match the `concepts` table exactly:
`code` (CHECK `^[a-z][a-z0-9_]*$`), `label`, `statement` (`income_statement`
| `balance_sheet` | `cash_flow` | NULL for note-level/non-statement
concepts), `sign_convention` (`natural` | `signed`), `unit_type` (`currency`
| `currency_per_share` | `count` | `percentage` | `ratio` | `density`),
`archetype_set`. The workbooks' own `unit_type` value `cents_per_share` is
recorded here as `currency_per_share` — cents is ZAR's minor unit, not a
distinct unit family; the migration's `unit_type` domain has no
`cents_per_share` value, and `currency_per_share` (already used for HEPS)
is the correct fit.

`FY2024 as-reported label` / `FY2025 as-reported label` are populated where
the concept is present on the face of that year's statement; `—` means
absent that year (see §4 for why, per concept). Where a label changed
between years, both are given and the difference is noted.

### 3.1 Income statement

| code | label | sign | unit | archetype_set | definition | FY2024 label | FY2025 label |
|---|---|---|---|---|---|---|---|
| `revenue_total` | Revenue (total) | natural | currency | retail | Printed "Revenue" total; component composition changed FY2024→FY2025 (see §2a) | Revenue | Revenue |
| `revenue` | Revenue (sale of merchandise) | natural | currency | retail, bank | Core retail revenue line; what "revenue" means to an analyst modelling this business (see §2a) | Sale of merchandise | Sale of merchandise |
| `cost_of_sales` | Cost of sales | signed | currency | retail | Direct cost of goods sold | Cost of sales | Cost of sales |
| `gross_profit` | Gross profit | natural | currency | retail | `revenue + cost_of_sales` | Gross profit | Gross profit |
| `alternative_revenue` | Alternative revenue | natural | currency | retail, bank | Non-merchandise operating income; **relabelled** from "Other operating income" FY2024→FY2025 (same concept, `company_line_items` carries both labels) | Other operating income | Alternative revenue |
| `interest_revenue` | Interest revenue | natural | currency | retail, bank | Interest income earned | Interest revenue | Interest revenue |
| `insurance_revenue` | Insurance revenue | natural | currency | retail | IFRS 17 insurance revenue; **disappears from the face of FY2025** (reclassified into discontinued operations) | Insurance revenue | — |
| `insurance_service_expenses` | Insurance service expenses | signed | currency | retail | IFRS 17 insurance service expenses; disappears from FY2025 face for the same reason | Insurance service expenses | — |
| `equity_accounted_profit` | Share of profit of equity accounted investments | natural | currency | retail, bank | Associates/JVs equity-accounted share | Share of profit of equity accounted investments | Share of profit of equity accounted investments |
| `depreciation_amortisation` | Depreciation and amortisation | signed | currency | retail, bank | D&A, net of the portion disclosed within cost of sales | Depreciation and amortisation | Depreciation and amortisation |
| `employee_benefits` | Employee benefits | signed | currency | retail, bank | Staff costs, net of the portion disclosed within cost of sales | Employee benefits | Employee benefits |
| `credit_impairment_losses` | Credit impairment losses | signed | currency | retail, bank | Expected credit loss charge (IFRS 9) | Credit impairment losses | Credit impairment losses |
| `other_operating_expenses` | Other operating expenses | signed | currency | retail, bank | Residual operating expense line, net of cost-of-sales portion | Other operating expenses | Other operating expenses |
| `net_monetary_gain` | Net monetary gain | natural | currency | retail | IAS 29 hyperinflation monetary gain; **disappears from the face of FY2025** — see §6 on hyperinflation | Net monetary gain | — |
| `trading_profit` | Trading profit | natural | currency | retail | **Company-defined** (Shoprite policy note 1.1.2(a)), not an IFRS line — see §2d | Trading profit | Trading profit |
| `fx_gains_losses` | Exchange rate (losses)/gains | signed | currency | retail, bank | FX translation gains/losses | Exchange rate (losses)/gains | Exchange rate (losses)/gains |
| `lease_modification_profit` | Profit on lease modifications and terminations | natural | currency | retail | IFRS 16 lease modification/termination gains | Profit on lease modifications and terminations | Profit on lease modifications and terminations |
| `items_of_capital_nature` | Items of a capital nature | signed | currency | retail | **Company-defined** (Shoprite policy note 1.1.2(b), per SAICA Circular 1/2023) — see §2d | Items of a capital nature | Items of a capital nature |
| `operating_profit` | Operating profit | natural | currency | retail, bank | Trading profit adjusted for FX/lease/capital items | Operating profit | Operating profit |
| `interest_received_bank` | Interest received from bank account balances | natural | currency | retail | **Company-defined** scope: call and operating bank balances only (policy 1.1.2(c)) | Interest received from bank account balances | Interest received from bank account balances |
| `finance_costs` | Finance costs | signed | currency | retail, bank | Interest and other finance expense | Finance costs | Finance costs |
| `profit_before_tax` | Profit before income tax | natural | currency | retail, bank | Pre-tax profit | Profit before income tax | Profit before income tax |
| `income_tax_expense` | Income tax expense | signed | currency | retail, bank | Total tax charge | Income tax expense | Income tax expense |
| `profit_continuing_operations` | Profit from continuing operations | natural | currency | retail, bank | Post-tax profit, continuing operations only | Profit from continuing operations | Profit from continuing operations |
| `profit_discontinued_operations` | Profit/(loss) from discontinued operations | signed | currency | retail | Post-tax result, discontinued operations; **label changed** "Loss from discontinued operations (attributable to owners of the parent)" FY2024 → "Profit from discontinued operations" FY2025 (sign of the underlying result flipped, not just the label) | Loss from discontinued operations (attributable to owners of the parent) | Profit from discontinued operations |
| `profit_for_period` | Profit for the year | natural | currency | retail, bank | Total post-tax profit, continuing + discontinued | Profit for the year | Profit for the year |
| `other_comprehensive_income` | Other comprehensive (loss)/income, net of income tax | signed | currency | retail, bank | OCI for the period | Other comprehensive (loss)/income, net of income tax | — (not captured on the FY2025 sheet — see §4) |
| `total_comprehensive_income` | Total comprehensive income for the year | natural | currency | retail, bank | Profit for the year + OCI | Total comprehensive income for the year | — (see §4) |
| `profit_attributable_owners` | Profit attributable to owners of the parent | natural | currency | retail, bank | Profit split: parent shareholders | Profit/(loss) attributable to: owners of the parent | Profit attributable to owners of the parent |
| `profit_attributable_nci` | Profit attributable to non-controlling interest | signed | currency | retail, bank | Profit split: NCI | Profit/(loss) attributable to: non-controlling interest | Profit attributable to non-controlling interest |
| `tci_attributable_owners` | Total comprehensive income attributable to owners of the parent | natural | currency | retail, bank | TCI split: parent shareholders | Total comprehensive income attributable to: owners of the parent | — (see §4) |
| `tci_attributable_nci` | Total comprehensive income attributable to non-controlling interest | signed | currency | retail, bank | TCI split: NCI | Total comprehensive income attributable to: non-controlling interest | — (see §4) |
| `tci_continuing` | TCI to owners from continuing operations | natural | currency | retail | TCI split by continuing/discontinued | TCI to owners arises from: continuing operations | — (see §4) |
| `tci_discontinued` | TCI to owners from discontinued operations | signed | currency | retail | TCI split by continuing/discontinued | TCI to owners arises from: discontinued operations | — (see §4) |
| `eps_basic_continuing` | Basic EPS, continuing operations (cents) | natural | currency_per_share | retail, bank | Basic EPS, continuing ops only | Basic earnings per share from continuing operations (cents) | Basic earnings per share from continuing operations (cents) |
| `eps_diluted_continuing` | Diluted EPS, continuing operations (cents) | natural | currency_per_share | retail, bank | Diluted EPS, continuing ops only | — (see §4) | Diluted earnings per share from continuing operations (cents) |
| `eps_basic` | Basic EPS (cents) | natural | currency_per_share | retail, bank | Basic EPS, total | Basic earnings per share (cents) | Basic earnings per share (cents) |
| `eps_diluted` | Diluted EPS (cents) | natural | currency_per_share | retail, bank | Diluted EPS, total | Diluted earnings per share (cents) | Diluted earnings per share (cents) |

### 3.2 Balance sheet

| code | label | sign | unit | archetype_set | definition | FY2024 label | FY2025 label |
|---|---|---|---|---|---|---|---|
| `total_non_current_assets` | Non-current assets | natural | currency | retail, bank | Non-current assets total | Non-current assets | Non-current assets |
| `property_plant_equipment` | Property, plant and equipment | natural | currency | retail, bank | PP&E carrying value | Property, plant and equipment | Property, plant and equipment |
| `investment_properties` | Investment properties | natural | currency | retail | Investment property carrying value | Investment properties | Investment properties |
| `right_of_use_assets` | Right-of-use assets | natural | currency | retail, bank | IFRS 16 ROU asset carrying value | Right-of-use assets | Right-of-use assets |
| `intangible_assets` | Intangible assets | natural | currency | retail, bank | Intangibles carrying value | Intangible assets | Intangible assets |
| `equity_accounted_investments` | Equity accounted investments | natural | currency | retail, bank | Associates/JVs carrying value | Equity accounted investments | Equity accounted investments |
| `convertible_loans` | Convertible loans | natural | currency | retail | Convertible loan asset; **line disappears in FY2025** | Convertible loans | — |
| `investments_fvoci` | Investments at FVOCI | natural | currency | retail, bank | FVOCI investment carrying value | Investments at fair value through other comprehensive income | Investments at fair value through other comprehensive income |
| `insurance_cell_captive_non_current` | Investment in insurance cell captive arrangements (non-current) | natural | currency | retail | Insurance cell captive, non-current portion | Investment in insurance cell captive arrangements (non-current) | Investment in insurance cell captive arrangements (non-current) |
| `government_bonds_non_current` | Government bonds and bills (non-current) | natural | currency | retail, bank | Government securities, non-current | Government bonds and bills (non-current) | Government bonds and bills (non-current) |
| `loans_receivable_non_current` | Loans receivable (non-current) | natural | currency | retail, bank | Loans receivable, non-current | Loans receivable (non-current) | Loans receivable (non-current) |
| `deferred_tax_assets` | Deferred income tax assets | natural | currency | retail, bank | Deferred tax asset | Deferred income tax assets | Deferred income tax assets |
| `trade_receivables_non_current` | Trade and other receivables (non-current) | natural | currency | retail | Trade/other receivables, non-current | Trade and other receivables (non-current) | Trade and other receivables (non-current) |
| `total_current_assets_incl_hfs` | Current assets (including held-for-sale) | natural | currency | retail, bank | Printed "Current assets" heading — **includes** assets held for sale; see §2b | Current assets | Current assets |
| `current_assets_excl_hfs` | Current assets, excluding held-for-sale | natural | currency | retail, bank | Unlabelled subtotal, **synthesised label** — see §2c | [unlabelled subtotal] current assets excluding held for sale | — (not captured as a row in the FY2025 workbook — see §4) |
| `inventories` | Inventories | natural | currency | retail | Inventory carrying value | Inventories | Inventories |
| `trade_receivables_current` | Trade and other receivables (current) | natural | currency | retail, bank | Trade/other receivables, current | Trade and other receivables (current) | Trade and other receivables (current) |
| `current_tax_assets` | Current income tax assets | natural | currency | retail, bank | Current tax receivable | Current income tax assets | Current income tax assets |
| `insurance_cell_captive_current` | Investment in insurance cell captive arrangements (current) | natural | currency | retail | Insurance cell captive, current portion | Investment in insurance cell captive arrangements (current) | Investment in insurance cell captive arrangements (current) |
| `government_bonds_current` | Government bonds and bills (current) | natural | currency | retail, bank | Government securities, current | Government bonds and bills (current) | Government bonds and bills (current) |
| `loans_receivable_current` | Loans receivable (current) | natural | currency | retail, bank | Loans receivable, current | Loans receivable (current) | Loans receivable (current) |
| `restricted_cash` | Restricted cash | natural | currency | retail, bank | Cash not freely available | Restricted cash | Restricted cash |
| `cash_and_equivalents` | Cash and cash equivalents | natural | currency | retail, bank | Balance-sheet cash and equivalents | Cash and cash equivalents | Cash and cash equivalents |
| `assets_held_for_sale` | Assets classified as held for sale | natural | currency | retail | IFRS 5 assets held for sale | Assets classified as held for sale | Assets classified as held for sale |
| `total_assets` | Total assets | natural | currency | retail, bank | Balance sheet total assets | Total assets | Total assets |
| `stated_capital` | Stated capital | natural | currency | retail, bank | Share capital | Stated capital | Stated capital |
| `treasury_shares` | Treasury shares | signed | currency | retail, bank | Treasury share carrying value, contra-equity | Treasury shares | Treasury shares |
| `reserves` | Reserves | natural | currency | retail, bank | Equity reserves | Reserves | Reserves |
| `equity_attributable_owners` | Equity attributable to owners of the parent | natural | currency | retail, bank | Unlabelled subtotal, **synthesised label** — `stated_capital + treasury_shares + reserves` — see §2c | [unlabelled subtotal] attributable to owners of the parent | — (not captured as a row in the FY2025 workbook — see §4) |
| `non_controlling_interest` | Non-controlling interest | signed | currency | retail, bank | NCI in equity | Non-controlling interest | Non-controlling interest |
| `total_equity` | Total equity | natural | currency | retail, bank | Total equity | Total equity | Total equity |
| `total_non_current_liabilities` | Non-current liabilities | natural | currency | retail, bank | Non-current liabilities total | Non-current liabilities | Non-current liabilities |
| `lease_liabilities_non_current` | Lease liabilities (non-current) | natural | currency | retail | IFRS 16 lease liability, non-current | — (see §4) | Lease liabilities (non-current) |
| `borrowings_non_current` | Borrowings (non-current) | natural | currency | retail, bank | Interest-bearing debt, non-current | — (see §4) | Borrowings (non-current) |
| `deferred_tax_liabilities` | Deferred income tax liabilities | natural | currency | retail, bank | Deferred tax liability | — (see §4) | Deferred income tax liabilities |
| `provisions_non_current` | Employee benefit and other provisions (non-current) | natural | currency | retail, bank | Provisions, non-current | — (see §4) | Employee benefit and other provisions (non-current) |
| `trade_payables_non_current` | Trade and other payables (non-current) | natural | currency | retail | Trade/other payables, non-current | — (see §4) | Trade and other payables (non-current) |
| `total_current_liabilities` | Current liabilities | natural | currency | retail, bank | Current liabilities total | — (see §4) | Current liabilities |
| `trade_payables_current` | Trade and other payables (current) | natural | currency | retail | Trade/other payables, current | — (see §4) | Trade and other payables (current) |
| `contract_liabilities` | Contract liabilities | natural | currency | retail | IFRS 15 contract liability | — (see §4) | Contract liabilities |
| `lease_liabilities_current` | Lease liabilities (current) | natural | currency | retail | IFRS 16 lease liability, current | — (see §4) | Lease liabilities (current) |
| `borrowings_current` | Borrowings (current) | natural | currency | retail, bank | Interest-bearing debt, current | — (see §4) | Borrowings (current) |
| `current_tax_liabilities` | Current income tax liabilities | natural | currency | retail, bank | Current tax payable | — (see §4) | Current income tax liabilities |
| `provisions_current` | Employee benefit and other provisions (current) | natural | currency | retail, bank | Provisions, current | — (see §4) | Employee benefit and other provisions (current) |
| `bank_overdrafts` | Bank overdrafts and other short-term facilities | natural | currency | retail, bank | Overdrafts and short-term facilities | — (see §4) | Bank overdrafts and other short-term facilities |
| `liabilities_held_for_sale` | Liabilities directly associated with assets classified as held for sale | natural | currency | retail | IFRS 5 liabilities held for sale | — (see §4) | Liabilities directly associated with assets classified as held for sale |
| `total_liabilities` | Total liabilities | natural | currency | retail, bank | Balance sheet total liabilities | — (see §4) | Total liabilities |
| `total_equity_and_liabilities` | Total equity and liabilities | natural | currency | retail, bank | Balance sheet total equity and liabilities | — (see §4) | Total equity and liabilities |

### 3.3 Cash flow

| code | label | sign | unit | archetype_set | definition | FY2024 label | FY2025 label |
|---|---|---|---|---|---|---|---|
| `cash_from_operating_activities` | Cash flows from operating activities | natural | currency | retail, bank | Net operating cash flow | Cash flows from operating activities | Cash flows from operating activities |
| `operating_profit_cf` | Operating profit (per cash flow statement) | natural | currency | retail | Operating profit as the cash flow's own starting point — **includes discontinued operations, unlike the income statement's `operating_profit`** (`Concepts_Discovered` row 7) | Operating profit (per cash flow) | Operating profit (per cash flow statement) |
| `investment_income_removed` | Less: investment income and interest revenue earned | signed | currency | retail | Reversal of investment income from the indirect-method starting point | Less: investment income and interest revenue earned | Less: investment income and interest revenue earned |
| `non_cash_items` | Non-cash items | natural | currency | retail, bank | Non-cash addback (note 38.1) | Non-cash items | Non-cash items |
| `working_capital_movement` | Changes in working capital | signed | currency | retail | Working capital movement (note 38.2) | Changes in working capital | Changes in working capital |
| `cash_generated_from_operations` | Cash generated from operations | natural | currency | retail, bank | Operating cash generation before interest/tax/dividends | Cash generated from operations | Cash generated from operations |
| `interest_received_cf` | Interest received | natural | currency | retail, bank | Interest received, cash flow statement | Interest received | Interest received |
| `interest_paid_cf` | Interest paid | signed | currency | retail, bank | Interest paid, cash flow statement | Interest paid | Interest paid |
| `dividends_received_cf` | Dividends received | natural | currency | retail | Dividends received, cash flow statement | Dividends received | Dividends received |
| `dividends_paid_cf` | Dividends paid | signed | currency | retail, bank | Dividends paid, cash flow statement (note 38.3) | Dividends paid | Dividends paid |
| `income_tax_paid_cf` | Income tax paid | signed | currency | retail, bank | Tax paid, cash flow statement (note 38.4) | Income tax paid | Income tax paid |
| `cash_from_investing_activities` | Cash flows utilised by investing activities | natural | currency | retail, bank | Net investing cash flow | Cash flows utilised by investing activities | Cash flows utilised by investing activities |
| `capex_expansion` | Capex to expand operations | signed | currency | retail | Growth capex; Shoprite splits expand/maintain — retail-specific disclosure granularity, not all retailers do this (FY2025 workbook note) | Investment in property, plant and equipment and other intangible assets to expand operations | Investment in property, plant and equipment and other intangible assets to expand operations |
| `capex_maintenance` | Capex to maintain operations | signed | currency | retail | Maintenance capex | Investment in property, plant and equipment and other intangible assets to maintain operations | Investment in property, plant and equipment and other intangible assets to maintain operations |
| `capex_trademarks` | Investment in trademarks to expand operations | signed | currency | retail | One-off trademark capex; **present FY2024, absent FY2025** | Investment in trademarks to expand operations | — |
| `payment_insurance_cell` | Payment for investment in insurance cell captive arrangements | signed | currency | retail | Cash paid into insurance cell captive | — (see §4) | Payment for investment in insurance cell captive arrangements |
| `investment_assets_held_for_sale` | Investment in assets classified as held for sale | signed | currency | retail | Capex on assets subsequently held for sale | Investment in assets classified as held for sale | Investment in assets classified as held for sale |
| `investment_convertible_loans` | Investment in convertible loans | signed | currency | retail | Cash invested in convertible loans | Investment in convertible loans | Investment in convertible loans |
| `payment_investments_fvoci` | Payment for investments at FVOCI | signed | currency | retail, bank | Cash paid for FVOCI investments | Payment for investments at fair value through other comprehensive income | Payment for investments at fair value through other comprehensive income |
| `proceeds_disposal_ppe` | Proceeds on disposal of PP&E and intangible assets | natural | currency | retail, bank | Disposal proceeds, PP&E/intangibles | Proceeds on disposal of property, plant and equipment and intangible assets | Proceeds on disposal of property, plant and equipment and intangible assets |
| `proceeds_disposal_discontinued` | Cash inflows from disposal of discontinued operations | natural | currency | retail | Disposal proceeds, discontinued operations (note 35.2) | Cash inflows as a result of the disposal of discontinued operations | Cash inflows as a result of the disposal of discontinued operations |
| `proceeds_disposal_held_for_sale` | Proceeds on disposal of assets classified as held for sale | natural | currency | retail | Disposal proceeds, held-for-sale assets | Proceeds on disposal of assets classified as held for sale | Proceeds on disposal of assets classified as held for sale |
| `insurance_recovery_social_unrest` | Proceeds from insurance recovery (social unrest) | natural | currency | retail | One-off insurance recovery; **present FY2024, absent FY2025** | Proceeds from insurance recovery for property, plant and equipment relating to social unrest | — |
| `payments_government_bonds` | Payments for government bonds and bills | signed | currency | retail, bank | Cash paid for government securities | Payments for government bonds and bills | Payments for government bonds and bills |
| `proceeds_government_bonds` | Proceeds from government bonds and bills | natural | currency | retail, bank | Cash received from government securities | Proceeds from government bonds and bills | Proceeds from government bonds and bills |
| `loans_advanced` | Loans receivable advanced | signed | currency | retail, bank | Cash advanced as loans receivable | Loans receivable advanced | Loans receivable advanced |
| `loans_repaid` | Loans receivable repaid | natural | currency | retail, bank | Cash received on loans receivable | Loans receivable repaid | Loans receivable repaid |
| `proceeds_disposal_associate` | Proceeds on disposal of investment in associate | natural | currency | retail | Disposal proceeds, associate investment | — (see §4) | Proceeds on disposal of investment in associate |
| `angola_tax_guarantees` | Decrease/(increase) in ring-fenced Angola tax guarantees | signed | currency | retail | Movement in ring-fenced Angola tax guarantee balance | Decrease/(increase) in ring-fenced Angola tax guarantees | Decrease in ring-fenced Angola tax guarantees |
| `investment_in_associate` | Investment in associate | signed | currency | retail, bank | Cash invested in associate (note 9) | Investment in associate | Investment in associate |
| `acquisition_pingo` | Acquisition of Pingo Delivery (Pty) Ltd | signed | currency | retail | One-off acquisition (note 38.5), FY2025-specific | — | Acquisition of Pingo Delivery (Pty) Ltd |
| `acquisition_subsidiaries_inflow` | Cash inflow on acquisition of subsidiaries | natural | currency | retail | Cash acquired with a subsidiary (note 38.5), FY2024-specific | Cash inflow on acquisition of subsidiaries | — |
| `acquisition_massmart` | Acquisition of select businesses from Massmart Holdings Ltd | signed | currency | retail | One-off acquisition (note 38.6), FY2024-specific | Acquisition of select businesses from Massmart Holdings Ltd | — |
| `acquisition_other_subsidiaries` | Acquisition of other subsidiaries and operations | signed | currency | retail | Residual acquisition spend | — | Acquisition of other subsidiaries and operations |
| `acquisition_other_operations` | Acquisition of other operations | signed | currency | retail | Residual acquisition spend (FY2024 wording) | Acquisition of other operations | — |
| `disposal_subsidiary_outflow` | Cash outflow on disposal of investment in subsidiary | signed | currency | retail | Cash outflow, subsidiary disposal (note 38.6/38.7 — note number shifted) | Cash outflow on disposal of investment in subsidiary | Cash outflow on disposal of investment in subsidiary |
| `cash_from_financing_activities` | Cash flows utilised by financing activities | natural | currency | retail, bank | Net financing cash flow | Cash flows utilised by financing activities | Cash flows utilised by financing activities |
| `lease_repayments` | Repayment of lease liability obligations | signed | currency | retail | IFRS 16 lease principal repayment | Repayment of lease liability obligations | Repayment of lease liability obligations |
| `treasury_share_purchases` | Purchase of treasury shares | signed | currency | retail, bank | Cash spent buying back treasury shares | Purchase of treasury shares | Purchase of treasury shares |
| `treasury_share_proceeds` | Proceeds from treasury shares disposed | natural | currency | retail, bank | Cash received disposing treasury shares | Proceeds from treasury shares disposed | Proceeds from treasury shares disposed |
| `borrowings_repaid` | Repayment of borrowings | signed | currency | retail, bank | Debt principal repaid | — (see §4) | Repayment of borrowings |
| `borrowings_raised` | Borrowings raised | natural | currency | retail, bank | New debt drawn | — (see §4) | Borrowings raised |
| `net_cash_movement` | Net movement in cash and cash equivalents | signed | currency | retail, bank | Total net cash movement for the period | — (see §4) | Net movement in cash and cash equivalents |
| `cash_opening` | Cash and cash equivalents at the beginning of the year | natural | currency | retail, bank | Opening cash balance | — (see §4) | Cash and cash equivalents at the beginning of the year |
| `fx_effect_on_cash` | Effect of exchange rate movements and hyperinflation on cash | signed | currency | retail | FX/hyperinflation effect on cash balance | — (see §4) | Effect of exchange rate movements and hyperinflation on cash and cash equivalents |
| `cash_closing` | Cash and cash equivalents at the end of the year | natural | currency | retail, bank | Closing cash per the cash flow statement — **net of overdrafts, excludes short-term facilities, differs from the balance sheet's `cash_and_equivalents`** (FY2025 workbook note: 9,323 vs 9,946) | — (see §4) | Cash and cash equivalents at the end of the year |

### 3.4 HEPS reconciliation (note 36)

Every one of these is present, under some label, in both years' HEPS
sheets, unless marked otherwise. Several change wording — or even the
underlying sign of the event described — between FY2024 and FY2025; those
are called out explicitly rather than silently normalised, per principle 3.

| code | label | sign | unit | archetype_set | definition | FY2024 label | FY2025 label |
|---|---|---|---|---|---|---|---|
| `profit_attributable_owners_net` | Net profit attributable to owners of the parent [net] | natural | currency | retail, bank | HEPS reconciliation starting point | Net profit attributable to owners of the parent [net] | Net profit attributable to owners of the parent [net] |
| `heps_adj_discontinued_net` | Profit/(loss) from discontinued operations [net] | signed | currency | retail | HEPS adjustment: remove discontinued operations; **sign of the underlying event flips between years** (FY2024 a loss, FY2025 a profit) with a corresponding label change | Loss from discontinued operations [net] | Profit from discontinued operations [net] |
| `earnings_continuing_net` | Earnings from continuing operations [net] | natural | currency | retail, bank | Subtotal after removing discontinued operations | Earnings from continuing operations [net] | Earnings from continuing operations [net] |
| `heps_adj_disposal_held_for_sale_gross` | Profit on disposal of assets classified as held for sale [gross] | signed | currency | retail | HEPS adjustment, gross | Profit on disposal of assets classified as held for sale [gross] | Profit on disposal of assets classified as held for sale [gross] |
| `heps_adj_disposal_held_for_sale_tax` | Profit on disposal of assets classified as held for sale [tax effect] | signed | currency | retail | HEPS adjustment, tax effect | Profit on disposal of assets classified as held for sale [tax effect] | Profit on disposal of assets classified as held for sale [tax effect] |
| `heps_adj_disposal_held_for_sale_net` | Profit on disposal of assets classified as held for sale [net] | signed | currency | retail | HEPS adjustment, net | Profit on disposal of assets classified as held for sale [net] | Profit on disposal of assets classified as held for sale [net] |
| `heps_adj_sale_leaseback_gross` | Profit on sale and leaseback transaction [gross] | signed | currency | retail | HEPS adjustment, gross | Profit on sale and leaseback transaction [gross] | Profit on sale and leaseback transaction [gross] |
| `heps_adj_sale_leaseback_tax` | Profit on sale and leaseback transaction [tax effect] | signed | currency | retail | HEPS adjustment, tax effect | Profit on sale and leaseback transaction [tax effect] | Profit on sale and leaseback transaction [tax effect] |
| `heps_adj_sale_leaseback_net` | Profit on sale and leaseback transaction [net] | signed | currency | retail | HEPS adjustment, net | Profit on sale and leaseback transaction [net] | Profit on sale and leaseback transaction [net] |
| `heps_adj_disposal_ppe_gross` | Loss on disposal and scrapping of PP&E and intangible assets [gross] | signed | currency | retail, bank | HEPS adjustment, gross | Loss on disposal and scrapping of property, plant and equipment and intangible assets [gross] | Loss on disposal and scrapping of property, plant and equipment and intangible assets [gross] |
| `heps_adj_disposal_ppe_tax` | Loss on disposal and scrapping of PP&E and intangible assets [tax effect] | signed | currency | retail, bank | HEPS adjustment, tax effect | Loss on disposal and scrapping of property, plant and equipment and intangible assets [tax effect] | Loss on disposal and scrapping of property, plant and equipment and intangible assets [tax effect] |
| `heps_adj_disposal_ppe_net` | Loss on disposal and scrapping of PP&E and intangible assets [net] | signed | currency | retail, bank | HEPS adjustment, net | Loss on disposal and scrapping of property, plant and equipment and intangible assets [net] | Loss on disposal and scrapping of property, plant and equipment and intangible assets [net] |
| `heps_adj_impairment_ppe_gross` | (Reversal of) impairment of property, plant and equipment [gross] | signed | currency | retail, bank | HEPS adjustment, gross; **sign of the underlying event flips between years** (FY2024 an impairment, FY2025 a reversal) with a corresponding label change — same phenomenon as `heps_adj_discontinued_net`, see §6 on whether the two-label pattern should collapse to sign-only | Impairment of property, plant and equipment [gross] | Reversal of impairment of property, plant and equipment [gross] |
| `heps_adj_impairment_ppe_tax` | (Reversal of) impairment of property, plant and equipment [tax effect] | signed | currency | retail, bank | HEPS adjustment, tax effect | Impairment of property, plant and equipment [tax effect] | Reversal of impairment of property, plant and equipment [tax effect] |
| `heps_adj_impairment_ppe_net` | (Reversal of) impairment of property, plant and equipment [net] | signed | currency | retail, bank | HEPS adjustment, net | Impairment of property, plant and equipment [net] | Reversal of impairment of property, plant and equipment [net] |
| `heps_adj_impairment_inv_prop_gross` | Impairment of investment properties [gross] | signed | currency | retail | HEPS adjustment, gross | Impairment of investment properties [gross] | Impairment of investment properties [gross] |
| `heps_adj_impairment_inv_prop_tax` | Impairment of investment properties [tax effect] | signed | currency | retail | HEPS adjustment, tax effect | Impairment of investment properties [tax effect] | Impairment of investment properties [tax effect] |
| `heps_adj_impairment_inv_prop_net` | Impairment of investment properties [net] | signed | currency | retail | HEPS adjustment, net | Impairment of investment properties [net] | Impairment of investment properties [net] |
| `heps_adj_impairment_rou_gross` | Impairment of right-of-use assets [gross] | signed | currency | retail | HEPS adjustment, gross | Impairment of right-of-use assets [gross] | Impairment of right-of-use assets [gross] |
| `heps_adj_impairment_rou_tax` | Impairment of right-of-use assets [tax effect] | signed | currency | retail | HEPS adjustment, tax effect | Impairment of right-of-use assets [tax effect] | Impairment of right-of-use assets [tax effect] |
| `heps_adj_impairment_rou_net` | Impairment of right-of-use assets [net] | signed | currency | retail | HEPS adjustment, net | Impairment of right-of-use assets [net] | Impairment of right-of-use assets [net] |
| `heps_adj_impairment_intangibles_gross` | Impairment of intangible assets [gross] | signed | currency | retail, bank | HEPS adjustment, gross | Impairment of intangible assets [gross] | Impairment of intangible assets [gross] |
| `heps_adj_impairment_intangibles_tax` | Impairment of intangible assets [tax effect] | signed | currency | retail, bank | HEPS adjustment, tax effect | Impairment of intangible assets [tax effect] | Impairment of intangible assets [tax effect] |
| `heps_adj_impairment_intangibles_net` | Impairment of intangible assets [net] | signed | currency | retail, bank | HEPS adjustment, net | Impairment of intangible assets [net] | Impairment of intangible assets [net] |
| `heps_adj_impairment_associate_gross` | Impairment of investment in associate [gross] | signed | currency | retail, bank | HEPS adjustment, gross; FY2024-specific | Impairment of investment in associate [gross] | — |
| `heps_adj_impairment_associate_tax` | Impairment of investment in associate [tax effect] | signed | currency | retail, bank | HEPS adjustment, tax effect; FY2024-specific | Impairment of investment in associate [tax effect] | — |
| `heps_adj_impairment_associate_net` | Impairment of investment in associate [net] | signed | currency | retail, bank | HEPS adjustment, net; FY2024-specific | Impairment of investment in associate [net] | — |
| `heps_adj_insurance_claims_gross` | Insurance claims receivable [gross] | signed | currency | retail | HEPS adjustment, gross | Insurance claims receivable [gross] | Insurance claims receivable [gross] |
| `heps_adj_insurance_claims_tax` | Insurance claims receivable [tax effect] | signed | currency | retail | HEPS adjustment, tax effect | Insurance claims receivable [tax effect] | Insurance claims receivable [tax effect] |
| `heps_adj_insurance_claims_net` | Insurance claims receivable [net] | signed | currency | retail | HEPS adjustment, net | Insurance claims receivable [net] | Insurance claims receivable [net] |
| `heps_adj_disposal_subsidiary_gross` | Loss on disposal of subsidiary [gross] | signed | currency | retail, bank | HEPS adjustment, gross; FY2024-specific | Loss on disposal of subsidiary [gross] | — |
| `heps_adj_disposal_subsidiary_tax` | Loss on disposal of subsidiary [tax effect] | signed | currency | retail, bank | HEPS adjustment, tax effect; FY2024-specific | Loss on disposal of subsidiary [tax effect] | — |
| `heps_adj_disposal_subsidiary_net` | Loss on disposal of subsidiary [net] | signed | currency | retail, bank | HEPS adjustment, net; FY2024-specific | Loss on disposal of subsidiary [net] | — |
| `heps_adj_jv_remeasurement_gross` | Remeasurement of investment in joint venture to fair value on deemed disposal of Pingo Delivery (Pty) Ltd [gross] | signed | currency | retail | HEPS adjustment, gross; FY2025-specific, one-off (see §2e) | — | Remeasurement of investment in joint venture to fair value on deemed disposal of Pingo Delivery (Pty) Ltd [gross] |
| `heps_adj_jv_remeasurement_tax` | Remeasurement of investment in joint venture to fair value on deemed disposal of Pingo Delivery (Pty) Ltd [tax effect] | signed | currency | retail | HEPS adjustment, tax effect; FY2025-specific | — | Remeasurement of investment in joint venture to fair value on deemed disposal of Pingo Delivery (Pty) Ltd [tax effect] |
| `heps_adj_jv_remeasurement_net` | Remeasurement of investment in joint venture to fair value on deemed disposal of Pingo Delivery (Pty) Ltd [net] | signed | currency | retail | HEPS adjustment, net; FY2025-specific | — | Remeasurement of investment in joint venture to fair value on deemed disposal of Pingo Delivery (Pty) Ltd [net] |
| `heps_adj_other_investing_gross` | (Loss)/profit on other investing activities [gross] | signed | currency | retail, bank | HEPS adjustment, gross; **sign of the underlying event flips between years** (FY2024 a profit, FY2025 a loss) with a corresponding label change — same phenomenon as `heps_adj_discontinued_net` and `heps_adj_impairment_ppe_gross` | Profit on other investing activities [gross] | Loss on other investing activities [gross] |
| `heps_adj_other_investing_tax` | (Loss)/profit on other investing activities [tax effect] | signed | currency | retail, bank | HEPS adjustment, tax effect | Profit on other investing activities [tax effect] | Loss on other investing activities [tax effect] |
| `heps_adj_other_investing_net` | (Loss)/profit on other investing activities [net] | signed | currency | retail, bank | HEPS adjustment, net | Profit on other investing activities [net] | Loss on other investing activities [net] |
| `heps_adj_nci_gross` | Re-measurements attributable to non-controlling interest [gross] | signed | currency | retail, bank | HEPS adjustment, gross | Re-measurements attributable to non-controlling interest [gross] | Re-measurements attributable to non-controlling interest [gross] |
| `heps_adj_nci_tax` | Re-measurements attributable to non-controlling interest [tax effect] | signed | currency | retail, bank | HEPS adjustment, tax effect | Re-measurements attributable to non-controlling interest [tax effect] | Re-measurements attributable to non-controlling interest [tax effect] |
| `heps_adj_nci_net` | Re-measurements attributable to non-controlling interest [net] | signed | currency | retail, bank | HEPS adjustment, net | Re-measurements attributable to non-controlling interest [net] | Re-measurements attributable to non-controlling interest [net] |
| `headline_earnings_continuing_gross` | Headline earnings from continuing operations [gross] | natural | currency | retail, bank | Headline earnings, continuing operations, gross | Headline earnings from continuing operations [gross] | Headline earnings from continuing operations [gross] |
| `headline_earnings_continuing_tax` | Headline earnings from continuing operations [tax effect] | signed | currency | retail, bank | Headline earnings, continuing operations, tax effect | Headline earnings from continuing operations [tax effect] | Headline earnings from continuing operations [tax effect] |
| `headline_earnings_continuing_net` | Headline earnings from continuing operations [net] | natural | currency | retail, bank | Headline earnings, continuing operations, net | Headline earnings from continuing operations [net] | Headline earnings from continuing operations [net] |
| `heps_disc_addback_net` | Profit from discontinued operations (add back) [net] | natural | currency | retail | FY2025-specific reconciliation step (discontinued profit was positive, added back) — see §6 on whether this and `heps_disc_deduct_net` should collapse to one signed concept | — | Profit from discontinued operations (add back) [net] |
| `heps_disc_deduct_net` | Loss from discontinued operations (deduct) [net] | signed | currency | retail | FY2024-specific reconciliation step (discontinued result was a loss, deducted) — same reconciliation position as `heps_disc_addback_net`, opposite sign of the underlying event; kept as two concepts rather than one because the printed labels and arithmetic role (add vs deduct) differ, not just the sign — see §6 for whether this survives M8.7 | Loss from discontinued operations (deduct) [net] | — |
| `heps_adj_capital_discontinued_gross` | Items of a capital nature from discontinued operations [gross] | signed | currency | retail | FY2025-specific reconciliation line, gross | — | Items of a capital nature from discontinued operations [gross] |
| `heps_adj_capital_discontinued_tax` | Items of a capital nature from discontinued operations [tax effect] | signed | currency | retail | FY2025-specific reconciliation line, tax effect | — | Items of a capital nature from discontinued operations [tax effect] |
| `heps_adj_capital_discontinued_net` | Items of a capital nature from discontinued operations [net] | signed | currency | retail | FY2025-specific reconciliation line, net | — | Items of a capital nature from discontinued operations [net] |
| `headline_earnings_gross` | Headline earnings [gross] | natural | currency | retail, bank | Total headline earnings, gross | Headline earnings [gross] | Headline earnings [gross] |
| `headline_earnings_tax` | Headline earnings [tax effect] | signed | currency | retail, bank | Total headline earnings, tax effect | Headline earnings [tax effect] | Headline earnings [tax effect] |
| `headline_earnings_net` | Headline earnings [net] | natural | currency | retail, bank | Total headline earnings, net — numerator of HEPS | Headline earnings [net] | Headline earnings [net] |
| `shares_in_issue` | Number of ordinary shares in issue (net of treasury shares) | natural | count | retail, bank | Share count, net of treasury; FY2025-only in the workbook (see §4) | — | Number of ordinary shares in issue (net of treasury shares) |
| `weighted_average_shares` | Weighted average number of ordinary shares | natural | count | retail, bank | Weighted average share count — HEPS denominator; FY2025-only in the workbook (see §4) | — | Weighted average number of ordinary shares |
| `weighted_average_shares_diluted` | Weighted average number of ordinary shares adjusted for dilution | natural | count | retail, bank | Diluted weighted average share count; FY2025-only in the workbook (see §4) | — | Weighted average number of ordinary shares adjusted for dilution |
| `heps_continuing` | Headline earnings per share from continuing operations (cents) | natural | currency_per_share | retail, bank | HEPS, continuing operations only | Headline earnings per share from continuing operations (cents) | Headline earnings per share from continuing operations (cents) |
| `heps_discontinued` | Headline earnings per share - discontinued (cents) | signed | currency_per_share | retail | HEPS, discontinued operations only | Headline earnings per share - discontinued (cents) | Headline earnings per share - discontinued (cents) |
| `heps_total` | Headline earnings per share - total (cents) | natural | currency_per_share | retail, bank | **THE number SA analysts use** (workbook's own annotation) | Headline earnings per share - total (cents) | Headline earnings per share - total (cents) |
| `heps_diluted_total` | Diluted headline earnings per share - total (cents) | natural | currency_per_share | retail, bank | Diluted HEPS, total | Diluted headline earnings per share - total (cents) | Diluted headline earnings per share - total (cents) |

### 3.5 Segment note (note 2.1) — retail-only

**Revised at M2.12** (loader task) — see the note at the end of this
section for why the original design (one concept per metric, segment
carried only by `company_line_items.as_reported_label`) does not survive
contact with `facts`' actual uniqueness constraint, and was replaced with
**one concept per (metric, segment) pair**. 7 metrics × 7 distinct segment
values across the two years (6 in FY2025, 7 in FY2024 — Furniture) = 49
concept codes.

| code | label | sign | unit | archetype_set | definition | FY2024 as-reported label | FY2025 as-reported label |
|---|---|---|---|---|---|---|---|
| `segment_revenue_external_supermarkets_rsa` | Segment revenue — external, Supermarkets RSA | natural | currency | retail | Sale of merchandise to external customers — Supermarkets RSA | Sale of merchandise - external :: Supermarkets RSA | Sale of merchandise - external :: Supermarkets RSA |
| `segment_revenue_external_supermarkets_non_rsa` | Segment revenue — external, Supermarkets Non-RSA | natural | currency | retail | Sale of merchandise to external customers — Supermarkets Non-RSA | Sale of merchandise - external :: Supermarkets Non-RSA | Sale of merchandise - external :: Supermarkets Non-RSA |
| `segment_revenue_external_furniture` | Segment revenue — external, Furniture | natural | currency | retail | Sale of merchandise to external customers — Furniture. FY2024-only: Furniture became a discontinued operation and does not appear in FY2025's segment note | Sale of merchandise - external :: Furniture | — |
| `segment_revenue_external_other` | Segment revenue — external, Other operating segments | natural | currency | retail | Sale of merchandise to external customers — Other operating segments | Sale of merchandise - external :: Other operating segments | Sale of merchandise - external :: Other operating segments |
| `segment_revenue_external_total` | Segment revenue — external, Total operating segments | natural | currency | retail | Sale of merchandise to external customers — Total operating segments (subtotal, before reconciling items) | Sale of merchandise - external :: Total operating segments | Sale of merchandise - external :: Total operating segments |
| `segment_revenue_external_hyperinflation` | Segment revenue — external, the hyperinflation/reconciling column | natural | currency | retail | Sale of merchandise to external customers — the hyperinflation/reconciling column | Sale of merchandise - external :: Hyperinflation effect | Sale of merchandise - external :: Hyperinflation effect and other reconciling items |
| `segment_revenue_external_consolidated` | Segment revenue — external, Consolidated | natural | currency | retail | Sale of merchandise to external customers — Consolidated (group total, after reconciling items) | Sale of merchandise - external :: Consolidated | Sale of merchandise - external :: Consolidated |
| `segment_revenue_intersegment_supermarkets_rsa` | Segment revenue — inter-segment, Supermarkets RSA | natural | currency | retail | Sale of merchandise between segments — Supermarkets RSA | Sale of merchandise - inter-segment :: Supermarkets RSA | Sale of merchandise - inter-segment :: Supermarkets RSA |
| `segment_revenue_intersegment_supermarkets_non_rsa` | Segment revenue — inter-segment, Supermarkets Non-RSA | natural | currency | retail | Sale of merchandise between segments — Supermarkets Non-RSA | Sale of merchandise - inter-segment :: Supermarkets Non-RSA | Sale of merchandise - inter-segment :: Supermarkets Non-RSA |
| `segment_revenue_intersegment_furniture` | Segment revenue — inter-segment, Furniture | natural | currency | retail | Sale of merchandise between segments — Furniture. FY2024-only: Furniture became a discontinued operation and does not appear in FY2025's segment note | Sale of merchandise - inter-segment :: Furniture | — |
| `segment_revenue_intersegment_other` | Segment revenue — inter-segment, Other operating segments | natural | currency | retail | Sale of merchandise between segments — Other operating segments | Sale of merchandise - inter-segment :: Other operating segments | Sale of merchandise - inter-segment :: Other operating segments |
| `segment_revenue_intersegment_total` | Segment revenue — inter-segment, Total operating segments | natural | currency | retail | Sale of merchandise between segments — Total operating segments (subtotal, before reconciling items) | Sale of merchandise - inter-segment :: Total operating segments | Sale of merchandise - inter-segment :: Total operating segments |
| `segment_revenue_intersegment_hyperinflation` | Segment revenue — inter-segment, the hyperinflation/reconciling column | natural | currency | retail | Sale of merchandise between segments — the hyperinflation/reconciling column | Sale of merchandise - inter-segment :: Hyperinflation effect | Sale of merchandise - inter-segment :: Hyperinflation effect and other reconciling items |
| `segment_revenue_intersegment_consolidated` | Segment revenue — inter-segment, Consolidated | natural | currency | retail | Sale of merchandise between segments — Consolidated (group total, after reconciling items) | Sale of merchandise - inter-segment :: Consolidated | Sale of merchandise - inter-segment :: Consolidated |
| `segment_revenue_total_supermarkets_rsa` | Segment revenue — total, Supermarkets RSA | natural | currency | retail | External + inter-segment revenue — Supermarkets RSA | Sale of merchandise - total :: Supermarkets RSA | Sale of merchandise - total :: Supermarkets RSA |
| `segment_revenue_total_supermarkets_non_rsa` | Segment revenue — total, Supermarkets Non-RSA | natural | currency | retail | External + inter-segment revenue — Supermarkets Non-RSA | Sale of merchandise - total :: Supermarkets Non-RSA | Sale of merchandise - total :: Supermarkets Non-RSA |
| `segment_revenue_total_furniture` | Segment revenue — total, Furniture | natural | currency | retail | External + inter-segment revenue — Furniture. FY2024-only: Furniture became a discontinued operation and does not appear in FY2025's segment note | Sale of merchandise - total :: Furniture | — |
| `segment_revenue_total_other` | Segment revenue — total, Other operating segments | natural | currency | retail | External + inter-segment revenue — Other operating segments | Sale of merchandise - total :: Other operating segments | Sale of merchandise - total :: Other operating segments |
| `segment_revenue_total_total` | Segment revenue — total, Total operating segments | natural | currency | retail | External + inter-segment revenue — Total operating segments (subtotal, before reconciling items) | Sale of merchandise - total :: Total operating segments | Sale of merchandise - total :: Total operating segments |
| `segment_revenue_total_hyperinflation` | Segment revenue — total, the hyperinflation/reconciling column | natural | currency | retail | External + inter-segment revenue — the hyperinflation/reconciling column | Sale of merchandise - total :: Hyperinflation effect | Sale of merchandise - total :: Hyperinflation effect and other reconciling items |
| `segment_revenue_total_consolidated` | Segment revenue — total, Consolidated | natural | currency | retail | External + inter-segment revenue — Consolidated (group total, after reconciling items) | Sale of merchandise - total :: Consolidated | Sale of merchandise - total :: Consolidated |
| `segment_trading_profit_supermarkets_rsa` | Segment trading profit/(loss), Supermarkets RSA | signed | currency | retail | Trading profit — Supermarkets RSA | Trading profit :: Supermarkets RSA | Trading profit/(loss) :: Supermarkets RSA |
| `segment_trading_profit_supermarkets_non_rsa` | Segment trading profit/(loss), Supermarkets Non-RSA | signed | currency | retail | Trading profit — Supermarkets Non-RSA | Trading profit :: Supermarkets Non-RSA | Trading profit/(loss) :: Supermarkets Non-RSA |
| `segment_trading_profit_furniture` | Segment trading profit/(loss), Furniture | signed | currency | retail | Trading profit — Furniture. FY2024-only: Furniture became a discontinued operation and does not appear in FY2025's segment note | Trading profit :: Furniture | — |
| `segment_trading_profit_other` | Segment trading profit/(loss), Other operating segments | signed | currency | retail | Trading profit — Other operating segments | Trading profit :: Other operating segments | Trading profit/(loss) :: Other operating segments |
| `segment_trading_profit_total` | Segment trading profit/(loss), Total operating segments | signed | currency | retail | Trading profit — Total operating segments (subtotal, before reconciling items) | Trading profit :: Total operating segments | Trading profit/(loss) :: Total operating segments |
| `segment_trading_profit_hyperinflation` | Segment trading profit/(loss), the hyperinflation/reconciling column | signed | currency | retail | Trading profit — the hyperinflation/reconciling column | Trading profit :: Hyperinflation effect | Trading profit/(loss) :: Hyperinflation effect and other reconciling items |
| `segment_trading_profit_consolidated` | Segment trading profit/(loss), Consolidated | signed | currency | retail | Trading profit — Consolidated (group total, after reconciling items) | Trading profit :: Consolidated | Trading profit/(loss) :: Consolidated |
| `segment_interest_revenue_supermarkets_rsa` | Segment interest revenue (included in trading profit), Supermarkets RSA | natural | currency | retail | Interest revenue component of segment trading profit — Supermarkets RSA | Interest revenue included in trading profit :: Supermarkets RSA | Interest revenue included in trading profit :: Supermarkets RSA |
| `segment_interest_revenue_supermarkets_non_rsa` | Segment interest revenue (included in trading profit), Supermarkets Non-RSA | natural | currency | retail | Interest revenue component of segment trading profit — Supermarkets Non-RSA | Interest revenue included in trading profit :: Supermarkets Non-RSA | Interest revenue included in trading profit :: Supermarkets Non-RSA |
| `segment_interest_revenue_furniture` | Segment interest revenue (included in trading profit), Furniture | natural | currency | retail | Interest revenue component of segment trading profit — Furniture. FY2024-only: Furniture became a discontinued operation and does not appear in FY2025's segment note | Interest revenue included in trading profit :: Furniture | — |
| `segment_interest_revenue_other` | Segment interest revenue (included in trading profit), Other operating segments | natural | currency | retail | Interest revenue component of segment trading profit — Other operating segments | Interest revenue included in trading profit :: Other operating segments | Interest revenue included in trading profit :: Other operating segments |
| `segment_interest_revenue_total` | Segment interest revenue (included in trading profit), Total operating segments | natural | currency | retail | Interest revenue component of segment trading profit — Total operating segments (subtotal, before reconciling items) | Interest revenue included in trading profit :: Total operating segments | Interest revenue included in trading profit :: Total operating segments |
| `segment_interest_revenue_hyperinflation` | Segment interest revenue (included in trading profit), the hyperinflation/reconciling column | natural | currency | retail | Interest revenue component of segment trading profit — the hyperinflation/reconciling column | Interest revenue included in trading profit :: Hyperinflation effect | Interest revenue included in trading profit :: Hyperinflation effect and other reconciling items |
| `segment_interest_revenue_consolidated` | Segment interest revenue (included in trading profit), Consolidated | natural | currency | retail | Interest revenue component of segment trading profit — Consolidated (group total, after reconciling items) | Interest revenue included in trading profit :: Consolidated | Interest revenue included in trading profit :: Consolidated |
| `segment_depreciation_amortisation_supermarkets_rsa` | Segment depreciation and amortisation, Supermarkets RSA | natural | currency | retail | D&A — Supermarkets RSA | Depreciation and amortisation :: Supermarkets RSA | Depreciation and amortisation :: Supermarkets RSA |
| `segment_depreciation_amortisation_supermarkets_non_rsa` | Segment depreciation and amortisation, Supermarkets Non-RSA | natural | currency | retail | D&A — Supermarkets Non-RSA | Depreciation and amortisation :: Supermarkets Non-RSA | Depreciation and amortisation :: Supermarkets Non-RSA |
| `segment_depreciation_amortisation_furniture` | Segment depreciation and amortisation, Furniture | natural | currency | retail | D&A — Furniture. FY2024-only: Furniture became a discontinued operation and does not appear in FY2025's segment note | Depreciation and amortisation :: Furniture | — |
| `segment_depreciation_amortisation_other` | Segment depreciation and amortisation, Other operating segments | natural | currency | retail | D&A — Other operating segments | Depreciation and amortisation :: Other operating segments | Depreciation and amortisation :: Other operating segments |
| `segment_depreciation_amortisation_total` | Segment depreciation and amortisation, Total operating segments | natural | currency | retail | D&A — Total operating segments (subtotal, before reconciling items) | Depreciation and amortisation :: Total operating segments | Depreciation and amortisation :: Total operating segments |
| `segment_depreciation_amortisation_hyperinflation` | Segment depreciation and amortisation, the hyperinflation/reconciling column | natural | currency | retail | D&A — the hyperinflation/reconciling column | Depreciation and amortisation :: Hyperinflation effect | Depreciation and amortisation :: Hyperinflation effect and other reconciling items |
| `segment_depreciation_amortisation_consolidated` | Segment depreciation and amortisation, Consolidated | natural | currency | retail | D&A — Consolidated (group total, after reconciling items) | Depreciation and amortisation :: Consolidated | Depreciation and amortisation :: Consolidated |
| `segment_total_assets_supermarkets_rsa` | Segment total assets, Supermarkets RSA | natural | currency | retail | Total assets — Supermarkets RSA | Total assets :: Supermarkets RSA | Total assets :: Supermarkets RSA |
| `segment_total_assets_supermarkets_non_rsa` | Segment total assets, Supermarkets Non-RSA | natural | currency | retail | Total assets — Supermarkets Non-RSA | Total assets :: Supermarkets Non-RSA | Total assets :: Supermarkets Non-RSA |
| `segment_total_assets_furniture` | Segment total assets, Furniture | natural | currency | retail | Total assets — Furniture. FY2024-only: Furniture became a discontinued operation and does not appear in FY2025's segment note | Total assets :: Furniture | — |
| `segment_total_assets_other` | Segment total assets, Other operating segments | natural | currency | retail | Total assets — Other operating segments | Total assets :: Other operating segments | Total assets :: Other operating segments |
| `segment_total_assets_total` | Segment total assets, Total operating segments | natural | currency | retail | Total assets — Total operating segments (subtotal, before reconciling items) | Total assets :: Total operating segments | Total assets :: Total operating segments |
| `segment_total_assets_hyperinflation` | Segment total assets, the hyperinflation/reconciling column | natural | currency | retail | Total assets — the hyperinflation/reconciling column | Total assets :: Hyperinflation effect | Total assets :: Hyperinflation effect and other reconciling items |
| `segment_total_assets_consolidated` | Segment total assets, Consolidated | natural | currency | retail | Total assets — Consolidated (group total, after reconciling items) | Total assets :: Consolidated | Total assets :: Consolidated |

**The reconciling column is a segment, not a special case.** "Hyperinflation
effect and other reconciling items" (FY2025) / "Hyperinflation effect"
(FY2024), "Total operating segments," and "Consolidated" each get their own
concept per metric, exactly like an operating segment — this is how M5.7's
rule ("segments + reconciling = consolidated") reads the reconciling column
as a capturable fact rather than a special-cased gap, per
`Concepts_Discovered` row 5 and the earlier open question this resolves.

**Why this section changed from the original M2.11 design.** The original
version of this section gave each of the 7 metrics ONE shared concept
(e.g. `segment_trading_profit`), with segment identity carried only in
`company_line_items.as_reported_label`'s `Metric :: Segment` compound
string, per §2b's general principle that scope belongs in concepts/labels,
not in a `facts` column. That reasoning is right for the *other* scope
axes in §2b (held-for-sale, continuing-vs-total) — it fails specifically
for segments, discovered while building the M2.12 loader, because
`facts`' actual uniqueness (the M1.8 exclusion-constraint key:
`company_id, concept_id, period_start, period_type, basis`) allows only
ONE current fact per concept per company/period/basis combination.
Loading all 6–7 segment values of one metric under one shared concept
would not create 6–7 coexisting facts; each `publish_fact` call after the
first would **supersede** the previous one under that identity, silently
destroying every segment value except the last one loaded, with no error
— the closing UPDATE genuinely has a "current" row to close every time. §2b's
"concepts are cheap, `facts` is expensive" reasoning still applies — it is
exactly why the fix is 49 concept rows, not a `segment` column on `facts`
— but the *specific* mechanism (one concept, many labels) that works for
held-for-sale scope does not work for a scope axis where multiple values
must coexist as separate facts for the same company/period/basis
simultaneously. See `PROGRESS.md`'s 2.12 entry for the full account of
how this was found and fixed before any data was loaded.

---

## 4. Completeness check

**Method:** every distinct `(statement, as_reported_label)` pair across the
non-fixture sheets of both workbooks (`IncomeStatement`, `BalanceSheet`,
`CashFlow`, `HEPS`, `Segments` in both; `Restatement_N45` in the FY2025
workbook and `Bitemporal_Pair` in the FY2024 workbook are bitemporal test
fixtures reusing concepts already defined elsewhere, checked separately
below, not counted as a new-concept source) was extracted programmatically
from the two `.xlsx` files and checked against §3's table. This is a
computed count, not an estimate.

### Result

Computed programmatically (a script reading both `.xlsx` files' data rows
directly, cross-checked against every `code | ... | FY2024 label | FY2025
label` row in §3.1–3.5), not estimated or eyeballed:

| | Count |
|---|---|
| Distinct `(statement, label)` pairs across all data sheets, both workbooks (incl. segment and fixture sheets) | 284 |
| Of which, in `segment_note` (8 distinct metric-label strings — 7 metrics, one renamed mid-set — × up to 7 segment/reconciling/total columns) | 61 |
| Of which, needing a concept from §3.1–3.4 (`income_statement`, `balance_sheet`, `cash_flow`, `heps_reconciliation`) | 205 |
| Of which, in the `bitemporal_pair` / `Restatement_N45` fixture sheets — **and NOT already counted above** (`Restatement_N45` tags its rows `statement = 'income_statement'`, so 10 of its 28 rows are exact duplicates of existing IncomeStatement-sheet pairs, already in the 205; `Bitemporal_Pair` tags all 18 of its rows `statement = 'bitemporal_pair'`, a distinct tag, so none of those 18 overlap by key even though every one reuses an existing concept) | 18 |
| **Check: 205 + 61 + 18 = 284** | **284 ✓** |
| Mapped to a concept in §3.1–3.4, verified by exact string match against that table's FY2024/FY2025 columns | **205 / 205** |
| Fixture-only pairs traced by hand to an existing concept (not a new mapping — see below) | **18 / 18** |
| Mismatch (workbook label with no matching doc row, or doc row claiming a label absent from both workbooks) | **0** |
| Deliberately unmapped, with reason | **0** |
| Unnoticed (found during the check but not accounted for anywhere in this document) | **0** |

**Every one of the 205 non-segment, non-fixture labels is mapped, and the
match was verified by exact string comparison, not by inspection.** (An
earlier draft of this section reported 151 from a manual count during
drafting — rerunning the check programmatically after §3 was complete found
the real number is 205; the manual estimate undercounted the HEPS
reconciliation table specifically. The number below is the one the script
produced against the final document, and the script is reproducible: it
regex-extracts every `code | label | sign | unit | archetype_set |
definition | FY2024 label | FY2025 label` row from §3.1–3.4, collects the
non-`—` FY2024/FY2025 cells as claimed labels, and diffs that set against
the workbooks' own `as_reported_label` column.)

The segment sheet's 61 pairs collapse to 7 concepts (§3.5) by design — that
is not 61 unmapped labels, it is 61 label instances of 7 concepts (across 8
distinct metric-label strings, since "Trading profit" was relabelled
"Trading profit/(loss)" between years — both map to `segment_trading_profit`,
noted in §3.5's table), exactly the mechanism §2b describes. The two
fixture sheets' 18 genuinely fixture-only pairs (all from `Bitemporal_Pair`
— `Restatement_N45`'s rows use `statement = 'income_statement'`, so 10 of
its 28 rows are exact-key duplicates of core IncomeStatement pairs already
in the 205, not additional labels) reuse concepts already listed in §3.1
(checked individually — every `concept_suggestion` value appearing only in
`Restatement_N45` or `Bitemporal_Pair` and nowhere else was traced to its
correct §3.1 concept by matching the underlying printed value and label
wording, e.g. `Bitemporal_Pair`'s `profit_from_continuing_operations` →
`profit_continuing_operations`, `Bitemporal_Pair`'s malformed
`other_operating_income_/_alternative_revenue` → `alternative_revenue`).

**No label was found that genuinely has no home.** The closest candidates —
the five FY2025 "unlabelled subtotal" figures the earlier open question
named (current assets/liabilities excl. HFS, equity attributable to owners,
two cash-flow reconciliation figures) — resolve into two outcomes, not one
uniform "unmapped" bucket, and this distinction matters for reading the
count honestly:

- **Two of the five ARE captured as rows**, in the FY2024 workbook only
  (`current_assets_excl_hfs`, `equity_attributable_owners`) — counted in the
  205 above, mapped in §3.2.
- **The other three (a current-liabilities-excl-HFS subtotal and two
  cash-flow reconciliation figures) were never transcribed as rows in
  either workbook** — they are named in `Concepts_Discovered` and
  `PROGRESS.md` as an observed phenomenon in the source PDF, but no
  `row_id` in either workbook corresponds to them, so they cannot appear in
  a "distinct label" count computed from the workbooks' own rows. This is
  not a gap in this taxonomy document — v0's job is to map what the golden
  workbooks captured, and M2.12's loader condition is explicitly about
  those workbooks' rows, not the PDF's full content. It IS a real, named
  gap in the golden dataset's own transcription coverage, worth flagging
  for whoever verifies the FY2025 workbook next: if those three figures are
  added as rows later, they follow the exact `current_assets_excl_hfs`
  pattern already established (§2c) — a `[unlabelled subtotal] ...` label
  and a concept following the same naming convention as
  `current_assets_excl_hfs` (i.e. `current_liabilities_excl_hfs`, not yet
  minted here since no row exists to source it from).

**Other completeness notes surfaced by the check, not failures of it:**

- The FY2024 workbook's `BalanceSheet` sheet stops after "Non-current
  liabilities" — it never transcribes current liabilities, contract
  liabilities, lease liabilities, borrowings, held-for-sale liabilities, or
  the equity-and-liabilities total for FY2024/FY2023. All of those concepts
  exist in §3.2 (sourced from the FY2025 sheet, which does capture them,
  and from `Structural_Changes`' evidence that these lines exist in both
  years' AFS), with FY2024 label `—` and a "(see §4)" pointer, honestly
  reflecting that the FY2024 golden workbook itself has this gap — it is
  not something v0 introduced.
- Similarly, the FY2024 `CashFlow` sheet stops after "Proceeds from
  treasury shares disposed" — borrowings raised/repaid, net cash movement,
  opening/closing cash, and the FX effect on cash are never transcribed for
  FY2024. Same treatment: concept exists (sourced from FY2025), FY2024
  label marked `—`.
- The FY2025 `IncomeStatement` sheet stops after the four EPS lines — it
  never transcribes OCI, total comprehensive income, or the TCI attribution
  splits, all of which the FY2024 sheet does capture. Concepts exist
  (§3.1), FY2025 label marked `—`.
- `eps_diluted_continuing` is captured in FY2025 but not FY2024 (FY2024's
  workbook has basic-continuing, basic, and diluted, but not
  diluted-continuing).

None of these four points are this document inventing concepts "because
they ought to exist" — every concept above with a `—` in one year's column
still has a real printed label in the OTHER year's column, which is the
traceability the task requires. A concept with `—` in both columns does not
exist in this document; there is no such row in §3.

---

## 5. Bank generalisation (§5.6)

Per §5.6, bank concepts (NII, NIM, IFRS 9 staging, RWA, capital ratios) must
be representable but are explicitly **not invented here** — that is M8.9's
job, and this document is derived from a retailer, not a bank. What follows
is only a classification of v0's own concepts: which ones a bank would also
report under a materially similar meaning, versus which are retail-specific,
based on evidence already visible in v0's own data — not a guess about bank
disclosure.

**Expected universal (`archetype_set` includes `bank` in §3's tables
above):** every concept whose underlying accounting event is not
retail-specific — cash, receivables/payables, PP&E, intangibles, tax
(current and deferred), leases (IFRS 16 applies to any lessee), borrowings,
equity structure (stated capital, treasury shares, reserves, NCI), EPS/HEPS
mechanics (SAICA Circular 1/2023 governs all JSE issuers, not just
retailers), and the primary-statement subtotal/total lines (profit before
tax, income tax expense, profit for the year, total assets/liabilities/
equity). A bank has all of these in some form. This is the majority of
§3.1–3.2 and about half of §3.4.

**Evidence basis:** these are exactly the line items that were already
generic enough in Shoprite's own statements to carry no retail-specific
wording — "Deferred income tax assets," "Right-of-use assets," "Trade and
other payables" are accounting-standard vocabulary, not retail vocabulary.
That a single retail company's disclosure of them looks like what any
IFRS-reporting company would disclose is the actual evidence; it is not
inferred from outside knowledge of bank statements.

**Retail-only (marked `archetype_set: [retail]` only):** `revenue`
(specifically "sale of merchandise" — a bank has no merchandise),
`cost_of_sales` / `gross_profit` (a bank has no COGS concept in the retail
sense), `trading_profit` (Shoprite-specific company-defined measure —
almost certainly meaningless for a bank's income statement structure),
`insurance_revenue` / `insurance_service_expenses` (IFRS 17 — could recur
for a bancassurer, but that is a different archetype question, not
evidence from this data), `net_monetary_gain` (IAS 29 hyperinflation — an
operational-geography fact, not retail-specific in principle, but this
document has no bank evidence either way, so left conservatively retail-only
rather than guessed), everything under the segment note (Shoprite's specific
segment structure), the capex expand/maintain split (retail-specific
disclosure choice per the FY2025 workbook's own note that "not all retailers
do this," so certainly not assumed for banks), and the HEPS adjustment lines
tied to retail-specific events (sale-and-leaseback, disposal of
held-for-sale retail assets, Pingo Delivery).

**What this classification is NOT:** it is not a prediction that these
`archetype_set` values are correct once M8.9 actually examines a bank's
AFS. It is the honest output of "does this concept's definition, as written
from Shoprite's disclosure, contain anything retail-specific" — a text-level
judgment about one company's wording, not an accounting judgment about bank
disclosure this document has no basis to make.

---

## 6. What v0 is, and what I expect M8.7 to challenge

**This is one company, two years.** The backlog is explicit that M8.7 (three
companies) is "the milestone most likely to force redesign" and deliberately
does this work at three companies rather than twelve so re-mapping happens
once, early. The following decisions in this document are the ones I expect
to be tested hardest, and why — so that when Pick n Pay's actual AFS
disagrees, the question "was v0 wrong, or is Pick n Pay just different" has
a clear answer already on record, not one invented after the fact to save
face.

1. **`revenue` = sale of merchandise, `revenue_total` = the printed total
   (§2a).** This is the single highest-risk call in the document. Shoprite
   happens to print an explicit "Revenue" total that sums components, which
   is what created the ambiguity to resolve in the first place. If Pick n
   Pay's AFS prints only one revenue line with no such split, there is
   nothing to disagree about — `revenue` and `revenue_total` simply
   coincide for PnP, which the schema tolerates. But if Woolworths or TFG
   structures its revenue disclosure completely differently (e.g. splitting
   by merchandise category with no single natural "core" line an analyst
   would call "revenue"), this two-concept split may not generalise cleanly
   and could need a third pattern M8.7 has to invent. **Signal to watch
   for:** if a second company's "the number analysts actually model" is
   genuinely ambiguous between three or more printed lines, not two, the
   binary `revenue`/`revenue_total` split was too simple.

2. **Company-defined measures marked via definition text only, no schema
   flag (§2d).** This was a two-concept decision (`trading_profit`,
   `items_of_capital_nature`) made from one company. If M8.7 finds three or
   more genuinely distinct company-defined "trading profit"-equivalent
   measures across the three companies with materially different
   definitions, a real `is_company_defined` boolean (or a
   `defining_company_id` FK) stops being premature structure and becomes
   the obviously correct fix — this document is not claiming the boolean is
   wrong forever, only that two data points don't justify it yet.

3. **`heps_disc_addback_net` / `heps_disc_deduct_net` as two concepts, not
   one signed concept (§3.4).** This was a judgment call under real
   uncertainty, flagged honestly rather than resolved with false
   confidence: the same reconciliation position (removing/adding back
   discontinued operations' profit) appears with a different label and
   arithmetic role depending on whether discontinued operations were
   profitable (FY2025: add back) or a loss (FY2024: deduct) that specific
   year. I chose to treat this as two concepts because the printed label
   changes, not just the sign — but a strong counter-argument exists: this
   could equally be ONE concept (`heps_disc_reversal`) with `signed`
   convention, letting the stored sign do the work these two separate codes
   currently do. I did not choose that because at the point of writing this
   document, I could not confirm from two years of one company's data
   whether the label consistently tracks the sign (i.e. whether Shoprite
   would print "deduct" for every future loss year and "add back" for every
   profit year, or whether the wording is more idiosyncratic than that). If
   a third company's HEPS reconciliation makes the sign-tracks-label pattern
   clear, this should very likely collapse to one concept — it is a two-line
   entry in v0 specifically because I would rather flag an unresolved
   judgment call than force a confident-looking wrong answer into a table
   that reads as settled.

4. **Segment scope resolved via `company_line_items` labels, not per-scope
   concepts (§2b, §3.5).** This generalised cleanly across Shoprite's OWN
   segment count change (four → three), which is reassuring, but it is
   still evidence from one company's segment note structure. If a second
   company's segment note uses a structurally different disclosure (e.g. a
   matrix of segment × geography rather than Shoprite's flat segment list),
   the `Metric :: Segment` compound-label convention may need to become
   `Metric :: Segment :: Geography` or similar — additive, not a redesign,
   but worth watching.

5. **Hyperinflation is under-modelled, on purpose, for now.**
   `net_monetary_gain` is the only IAS 29 concept in v0, and it is marked
   retail-only with low confidence (§5). `Concepts_Discovered` row 9 flags
   that Ghana is hyperinflationary and Angola ceased to be, and that
   hyperinflation adjustments "flow through several lines" — meaning the
   true footprint of IAS 29 in Shoprite's own statements is almost
   certainly larger than one concept (the segment note's "Hyperinflation
   effect" reconciling column is a second manifestation already captured
   under §3.5, so it is not zero, but it is not comprehensively modelled
   either). This was not resolved here because the two golden workbooks did
   not transcribe enough hyperinflation-specific note detail to do so
   without guessing at structure the source documents don't show in the
   sheets I read. Flagged, not solved — a real gap, not an oversight.

6. **192 non-segment concepts from one company is a real number** (§3.1–3.4
   combined, excluding the 7 segment concepts in §3.5), **and it will
   roughly double or triple, not stay flat, once companies two and three
   add their own one-off lines** (their own version of Pingo Delivery,
   Massmart, social-unrest insurance claims). §2e's granularity rule is
   what produces this — capturing HEPS reconciliation lines individually
   rather than bucketing them. If M8.7 finds this unmanageable
   at three companies, the rule itself (not just individual concept
   mappings) is what would need to change, most likely toward a
   `heps_adjustment_type` free-text or enum note-detail table rather than a
   dedicated concept per line item. I judged the current approach right for
   v0 because it protects principle 3 (nothing destroyed, nothing merged
   into an "other" bucket that loses information) at the cost of a large
   concept count — that trade-off is the thing most likely to be
   relitigated at scale, and I want that relitigation to be a considered
   decision at M8.7, not a surprise.
