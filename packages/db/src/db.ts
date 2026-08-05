/**
 * Thin Postgres read helper for TypeScript consumers (M1.13).
 *
 * This is NOT a mirror of valora_pipeline.db (M1.12). Per spec §7, Python
 * owns the extraction pipeline and writes facts; TypeScript owns the API,
 * web app, and Excel add-in, which read them. There is deliberately no
 * publishFact or any bitemporal write path here — see "What this module
 * does NOT do" below.
 *
 * Every read that resolves "what was true as of instant X" calls the
 * facts_as_of() database function (M1.10), never a hand-written
 * knowledge_period containment query. That function existing as a
 * database object rather than a constant in either language is the whole
 * point: this module and valora_pipeline.db both call the same one query,
 * so they cannot silently disagree about the boundary.
 *
 * Types: hand-written, not generated. M9.7 will generate shared TypeScript
 * types from the API's OpenAPI spec, but that describes the API's public
 * HTTP request/response JSON contract — it does not yet exist, and even
 * once it does, it is a different layer from this module's job (typed
 * database rows for whatever TypeScript backend code calls these
 * functions). Until M9.7 lands, and possibly after, these interfaces are
 * kept in sync with db/migrations by hand, the same discipline
 * valora_pipeline.db already requires on the Python side. No code
 * generator is built here — that is explicitly M9.7's job, not this one's.
 *
 * What this module does NOT do, and why:
 *
 * - No publishFact / no write path of any kind. A second implementation
 *   of the bitemporal write, in a second language, called by nothing
 *   today, is exactly the liability M1.8/M1.9 exist to prevent — it would
 *   eventually get called, and then the guarantee has two versions that
 *   can diverge. If TypeScript ever genuinely needs to write facts, that
 *   is a decision for whoever builds that need, made deliberately, not
 *   inherited from this module's existence.
 * - No connection pooling policy, no retry logic, no CRUD beyond the three
 *   read functions below — no consumer needs more yet (see PROGRESS.md).
 */

import { getConfig } from "@valora/config";
import pg from "pg";

// DATE columns (period_start, period_end) have no timezone component.
// node-postgres's default parser treats the string as local midnight and
// converts to a JS Date, which silently shifts the calendar date by a day
// depending on the server's local timezone. Returning the raw string
// avoids that entirely — callers get exactly "2024-07-01", never a Date
// object that might resolve to the 30th in UTC.
const PG_TYPE_DATE = 1082;
pg.types.setTypeParser(PG_TYPE_DATE, (value: string) => value);

export interface Bbox {
  readonly x0: number;
  readonly y0: number;
  readonly x1: number;
  readonly y1: number;
}

/**
 * One row of `facts`, as returned by `facts_as_of()` — minus
 * knowledge_period. That column is the bitemporal bookkeeping
 * facts_as_of() itself resolves; no caller of this module needs the raw
 * range, only the resolved value, so it is not part of this public shape.
 * (valora_pipeline.db's Fact, by contrast, does include it — that module
 * serves the write path, which needs it. This module does not.)
 */
export interface Fact {
  readonly id: number;
  readonly companyId: number;
  readonly conceptId: number;
  readonly lineItemId: number | null;
  /** Plain "YYYY-MM-DD", not a Date — see the DATE type-parser note above. */
  readonly periodStart: string;
  readonly periodEnd: string;
  readonly periodType: string;
  readonly basis: string;
  /** Raw NUMERIC as a string, never parsed to a JS number: floating-point
   * would risk silently corrupting a verified financial value. Callers
   * needing arithmetic should use a decimal library, not `Number()`. */
  readonly value: string;
  readonly currency: string;
  readonly scale: string;
  readonly documentId: number;
  readonly page: number;
  readonly bbox: Bbox;
  readonly confidence: number | null;
  readonly verifiedBy: number | null;
  readonly verifiedAt: Date | null;
  readonly extractionRunId: number | null;
}

export interface Company {
  readonly id: number;
  readonly name: string;
  readonly jseCode: string;
  readonly sector: string | null;
  readonly archetype: string;
  readonly fyeMonth: number;
}

export interface Concept {
  readonly id: number;
  readonly code: string;
  readonly label: string;
  readonly archetypeSet: readonly string[];
  readonly statement: string | null;
  readonly signConvention: string;
  readonly unitType: string;
}

/** Opens a client using the single source of truth for DATABASE_URL
 * (@valora/config), never process.env directly — the same rule M0.8
 * established and valora_pipeline.db already follows. Caller owns the
 * client's lifecycle (connect/end). */
export function createClient(): pg.Client {
  return new pg.Client({ connectionString: getConfig().databaseUrl });
}

interface FactRow {
  id: string;
  company_id: string;
  concept_id: string;
  line_item_id: string | null;
  period_start: string;
  period_end: string;
  period_type: string;
  basis: string;
  value: string;
  currency: string;
  scale: string;
  document_id: string;
  page: number;
  bbox: Bbox;
  confidence: string | null;
  verified_by: string | null;
  verified_at: Date | null;
  extraction_run_id: string | null;
}

function factFromRow(row: FactRow): Fact {
  return {
    id: Number(row.id),
    companyId: Number(row.company_id),
    conceptId: Number(row.concept_id),
    lineItemId: row.line_item_id === null ? null : Number(row.line_item_id),
    periodStart: row.period_start,
    periodEnd: row.period_end,
    periodType: row.period_type,
    basis: row.basis,
    value: row.value,
    currency: row.currency,
    scale: row.scale,
    documentId: Number(row.document_id),
    page: row.page,
    bbox: row.bbox,
    confidence: row.confidence === null ? null : Number(row.confidence),
    verifiedBy: row.verified_by === null ? null : Number(row.verified_by),
    verifiedAt: row.verified_at,
    extractionRunId: row.extraction_run_id === null ? null : Number(row.extraction_run_id),
  };
}

/**
 * Facts as of a given instant (default: now — the current view). Calls
 * the canonical facts_as_of() database function (M1.10) rather than
 * reimplementing the knowledge_period containment check in TypeScript —
 * CLAUDE.md records that reimplementation as the specific risk this
 * function exists to prevent. Callers wanting company/concept/period
 * filtering compose it in SQL on top of this query, the same pattern
 * valora_pipeline.db's get_facts_as_of uses.
 */
export async function getFactsAsOf(
  client: pg.Client | pg.Pool,
  asOf?: Date,
): Promise<Fact[]> {
  const result =
    asOf === undefined
      ? await client.query<FactRow>("select * from facts_as_of()")
      : await client.query<FactRow>("select * from facts_as_of($1)", [asOf]);
  return result.rows.map(factFromRow);
}

interface CompanyRow {
  id: string;
  name: string;
  jse_code: string;
  sector: string | null;
  archetype: string;
  fye_month: number;
}

function companyFromRow(row: CompanyRow): Company {
  return {
    id: Number(row.id),
    name: row.name,
    jseCode: row.jse_code,
    sector: row.sector,
    archetype: row.archetype,
    fyeMonth: row.fye_month,
  };
}

/** Reference data for GET /v1/companies (M9.4). */
export async function getCompanies(client: pg.Client | pg.Pool): Promise<Company[]> {
  const result = await client.query<CompanyRow>(
    "select id, name, jse_code, sector, archetype, fye_month from companies order by id",
  );
  return result.rows.map(companyFromRow);
}

interface ConceptRow {
  id: string;
  code: string;
  label: string;
  archetype_set: string[];
  statement: string | null;
  sign_convention: string;
  unit_type: string;
}

function conceptFromRow(row: ConceptRow): Concept {
  return {
    id: Number(row.id),
    code: row.code,
    label: row.label,
    archetypeSet: row.archetype_set,
    statement: row.statement,
    signConvention: row.sign_convention,
    unitType: row.unit_type,
  };
}

/** Reference data for GET /v1/concepts (M9.4). */
export async function getConcepts(client: pg.Client | pg.Pool): Promise<Concept[]> {
  const result = await client.query<ConceptRow>(
    "select id, code, label, archetype_set, statement, sign_convention, unit_type "
      + "from concepts order by id",
  );
  return result.rows.map(conceptFromRow);
}
