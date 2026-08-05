# JSE coverage universe — MVP 12 companies

Source-verified extract backing `docs/valora_mvp.md` §3 and the M1.11 seed
script. Every `fye_month` value below was checked against a SENS-derived
"Annual Financial Statements" or "Group Results" filing (via Moneyweb and
Sharenet, both of which republish JSE SENS announcements verbatim) — never
from recollection. Several of these companies use 52/53-week retail
calendars whose exact year-end date floats within, or occasionally just
past, a calendar month boundary; where that applies it is noted explicitly,
along with the reasoning for which month is recorded.

**Retrieval date: 2026-08-06.**

## Companies

| # | Legal / listed name | JSE code | fye_month | Sector | Archetype |
|---|---|---|---|---|---|
| 1 | Shoprite Holdings Limited | SHP | 6 (June) | Food Retailers & Wholesalers | retail |
| 2 | Pick n Pay Stores Limited | PIK | 2 (February) | Food Retailers & Wholesalers | retail |
| 3 | Boxer Retail Limited | BOX | 2 (February) | Food Retailers & Wholesalers | retail |
| 4 | The SPAR Group Limited | SPP | 9 (September) | Food Retailers & Wholesalers | retail |
| 5 | Woolworths Holdings Limited | WHL | 6 (June) | General Retailers (food & fashion/beauty/home) | retail |
| 6 | Mr Price Group Limited | MRP | 3 (March) | Apparel/General Retailers | retail |
| 7 | Truworths International Limited | TRU | 6 (June) | Apparel Retailers | retail |
| 8 | The Foschini Group Limited | TFG | 3 (March) | Apparel/General Retailers | retail |
| 9 | Clicks Group Limited | CLS | 8 (August) | Food & Drug Retailers / Health & Beauty | retail |
| 10 | Dis-Chem Pharmacies Limited | DCP | 2 (February) | Food & Drug Retailers / Health & Beauty | retail |
| 11 | Pepkor Holdings Limited | PPH | 9 (September) | General Retailers / Apparel & Merchandise | retail |
| 12 | AVI Limited | AVI | 6 (June) | Food Producers / Branded Consumer Goods | retail (not a store operator — see PROGRESS.md open questions) |

Sector labels are a general classification for reference only, not verified
to the same primary-source rigor as `fye_month`.

## fye_month sourcing detail

- **Shoprite (June)** — "Annual Financial Statements for the year ended 30
  June" 2019, 2023, 2024; "29 June 2025". *Floats*: separate operational
  trading-update announcements for 2021–2023 cited "52/53 weeks ended 2–4
  July," but every formal Annual Financial Statements filing found was
  June-dated. June recorded on the strength of the formal AFS title, which
  is the closer analogue to an annual report cover.
  [Listcorp: AFS 2024](https://www.listcorp.com/jse/shp/shoprite-holdings-limited/news/annual-financial-statements-for-the-year-ended-30-june-2024-3092357.html),
  [Listcorp: AFS 2019](https://www.listcorp.com/jse/shp/shoprite-holdings-limited/news/annual-financial-statements-for-the-year-ended-30-june-2019-2515565.html)
- **Pick n Pay (February)** — "Annual Financial Statements for the year
  ended 28 February 2026" — the company's own formal filing anchors to 28
  February even in years the actual 52/53-week trading date lands in early
  March (2 March 2025, 1 March 2026). *Floats*, but the formal AFS title
  consistently uses February.
  [Listcorp: AFS FY2025](https://www.listcorp.com/jse/pik/pick-n-pay-stores-limited/news/annual-financial-statements-for-the-year-ended-28-february-2025-3194376.html),
  [Sharenet SENS: 53 weeks ended 02 March 2025](https://www.sharenet.co.za/v3/sens_display.php?tdate=20250526070500&seq=1)
- **Boxer (February)** — Same 52/53-week retail calendar as its parent/
  majority owner Pick n Pay: "52 Weeks Ended 25 February 2024, 26 February
  2023 and 27 February 2022" (pre-listing historical financial
  information); *floats* to "53 weeks ended 2 March 2025" and "52 weeks
  ended 1 March 2026" in longer years. February recorded, same reasoning
  as Pick n Pay.
  [Listcorp: 53 weeks ended 2 March 2025](https://www.listcorp.com/jse/box/boxer-retail-limited/news/audited-annual-financial-results-for-the-53-weeks-ended-2-march-2025-3188482.html),
  [Moneyweb SENS: 52 weeks ended 1 March 2026](https://www.moneyweb.co.za/mny_sens/boxer-retail-limited-condensed-consolidated-audited-financial-results-for-the-52-weeks-ended-1-march-2026-and-cash-dividend-declaration/)
- **SPAR (September)** — "Audited group results for the 52 weeks ended 26
  September 2025." SPAR explicitly adopted a fixed 52-week (no 53-week)
  cycle from 2025; date stays within September, no crossing into October
  observed.
  [Moneyweb SENS](https://www.moneyweb.co.za/mny_sens/the-spar-group-limited-audited-group-results-for-the-52-weeks-ended-26-september-2025/)
- **Woolworths (June)** — "Audited Group Results for the 52/53 weeks
  ended" 25 June 2023, 30 June 2024, 29 June 2025, 28 June 2026. Every year
  found stayed within June; no July crossover observed (unlike Shoprite's
  trading-update announcements).
  [Moneyweb SENS: 53 weeks ended 30 June 2024](https://www.moneyweb.co.za/mny_sens/woolworths-holdings-limited-audited-group-results-for-the-53-weeks-ended-30-june-2024-cash-dividend-declaration-and-changes-to-the-board/)
- **Mr Price (March)** — "52 weeks ended 30 March 2024," "28 March 2026."
  *Floats*: one cited outlier, "53 weeks ended 3 April 2021." March is the
  clear majority.
  [Moneyweb SENS: 53 weeks ended 3 April 2021](https://www.moneyweb.co.za/mny_sens/mr-price-group-limited-preliminary-group-results-for-the-53-weeks-ended-3-april-2021-and-cash-dividend-declaration/)
- **Truworths (June)** — "52 weeks ended 30 June 2024," "29 June 2025."
  *Floats*: one cited outlier, "53 weeks ended 3 July 2022" — the largest
  single boundary crossing found among the twelve. June is the majority;
  this is the case with the least margin after Pick n Pay/Boxer.
  [Moneyweb SENS: 53 weeks ended 3 July 2022](https://www.moneyweb.co.za/mny_sens/truworths-international-limited-preliminary-audited-annual-results-for-the-53-weeks-ended-3-july-2022-dividend-declaration-changes-to-the-board/)
- **TFG (March)** — "Condensed consolidated financial statements for year
  ended 31 March 2025/2026" — fixed calendar date; week-count language
  found only on interim trading updates, not the year-end itself. Not a
  floating case.
  [Moneyweb SENS](https://www.moneyweb.co.za/mny_sens/the-foschini-group-limited-condensed-consolidated-financial-statements-for-year-ended-31-march-2026-ordinary-and-preference-share-dividends/)
- **Clicks (August)** — "Condensed consolidated annual group results for
  the year ended 31 August" 2023, 2024 — fixed calendar date, no
  week-count language found for year-end. Not a floating case.
  [Sharenet SENS](https://www.sharenet.co.za/v3/sens_display.php?tdate=20241024080000&seq=11)
- **Dis-Chem (February)** — "Audited Annual Consolidated Results for the
  twelve months ended" 29 February 2024, 28 February 2025 — fixed calendar
  month-end, described in "twelve months," not weeks. Not a floating case.
  [Sharenet SENS](https://www.sharenet.co.za/v3/sens_display.php?tdate=20240531070500&seq=2)
- **Pepkor (September)** — "Reviewed Annual Results for the year ended 30
  September 2024" — fixed calendar date; "52-week basis" language used
  only for like-for-like trading comparisons, not the statutory year-end
  date itself. Not a floating case.
  [Sharenet SENS](https://www.sharenet.co.za/v3/sens_display.php?tdate=20241126074000&seq=9)
- **AVI (June)** — "Results for the year ended 30 June 2025," AFS
  2023/2024 all consistently 30 June. No floating language found.
  [Listcorp: AVI results FY2025](https://www.listcorp.com/jse/avi/avi-limited/news/results-for-the-year-ended-30-june-2025-and-final-dividend-3240315.html),
  [Sharenet SENS](https://www.sharenet.co.za/v3/sens_display.php?tdate=20250908070500&seq=1)

## Known gaps in this extract

- **Share code suffixes.** Several of these companies have more than one
  listed instrument beyond their primary ordinary shares (e.g. TFG has
  ordinary `TFG` and preference `TFGP` shares). `jse_code` above refers
  only to the primary/ordinary listing. Full instrument-level detail
  (ISINs, share classes, preference shares) is out of scope for M1.11 by
  design (instruments are M1.3/a separate exercise) — flagging so it is
  not forgotten when instruments are seeded for these companies.
- **Boxer's history depth.** Boxer only listed on the JSE on 28 November
  2024. Its pre-listing statement discloses combined historical financial
  information for the 52-week periods ended 27 February 2022, 26 February
  2023, and 25 February 2024 — three years, not ten. I could not confirm
  from public sources whether usable financial data exists further back
  than FY2022. Boxer therefore cannot supply §3's stated "10 financial
  years" of history the way the other eleven companies can; the fact-volume
  estimate in `docs/valora_mvp.md` §3 has been adjusted accordingly (see
  that section for the recalculation).
