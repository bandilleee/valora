/**
 * Tests for @valora/db (M1.13), against a real local Postgres.
 *
 * Same isolation approach as the Python suites: each test runs inside its
 * own transaction, rolled back at teardown via `withRollback`, so no
 * test's inserts leak into another test or into whatever was in the
 * database before the run.
 *
 * No skip logic anywhere in this file: a database that is unreachable
 * must fail these tests, not silently skip them.
 *
 * test_as_of_at_exact_boundary_instant is a deliberate line-for-line port
 * of the same scenario in services/pipeline/tests/test_facts_as_of.py and
 * db/migrations' own facts_as_of() — same t1/t2/t3 shape, same assertion.
 * That is the actual point of this test: if TypeScript and Python
 * disagree about which row wins at the shared boundary instant, one of
 * them is lying to a customer, and this test is what would catch it.
 */

import assert from "node:assert/strict";
import test from "node:test";
import pg from "pg";

import { createClient, getCompanies, getConcepts, getFactsAsOf } from "./db.ts";

const BBOX = { x0: 0, y0: 0, x1: 0.1, y1: 0.1 };

async function withRollback(run: (client: pg.Client) => Promise<void>): Promise<void> {
  const client = createClient();
  await client.connect();
  try {
    await client.query("begin");
    try {
      await run(client);
    } finally {
      await client.query("rollback");
    }
  } finally {
    await client.end();
  }
}

function instant(offsetDays = 0): Date {
  const base = Date.UTC(2026, 0, 1);
  return new Date(base + offsetDays * 24 * 60 * 60 * 1000);
}

async function insertCompany(client: pg.Client, jseCode: string): Promise<number> {
  const result = await client.query<{ id: string }>(
    `insert into companies (name, jse_code, sector, archetype, fye_month)
     values ($1, $2, 'Retail', 'retail', 6)
     returning id`,
    [`Test Co ${jseCode}`, jseCode],
  );
  return Number(result.rows[0]?.id);
}

async function insertConcept(client: pg.Client, code: string): Promise<number> {
  const result = await client.query<{ id: string }>(
    `insert into concepts (code, label, archetype_set, sign_convention, unit_type)
     values ($1, $2, array['retail'], 'natural', 'currency')
     returning id`,
    [code, code],
  );
  return Number(result.rows[0]?.id);
}

async function insertDocument(client: pg.Client, key: string): Promise<number> {
  const sha256 = Buffer.from(key).toString("hex").padEnd(64, "0").slice(0, 64);
  const result = await client.query<{ id: string }>(
    `insert into documents (s3_key, sha256) values ($1, $2) returning id`,
    [`test/${key}.pdf`, sha256],
  );
  return Number(result.rows[0]?.id);
}

interface InsertFactOptions {
  readonly companyId: number;
  readonly conceptId: number;
  readonly documentId: number;
  readonly knowledgePeriod: string; // raw tstzrange literal, e.g. '[2026-01-01,)'
  readonly value?: number;
  readonly basis?: string;
}

/** Fabricates a fact row with a directly-specified knowledge_period. Used
 * only for query-boundary tests (the exact-instant case), matching the
 * Python suite's own convention: the write path is not what those tests
 * are about. */
async function insertFact(client: pg.Client, options: InsertFactOptions): Promise<void> {
  await client.query(
    `insert into facts (
       company_id, concept_id, period_start, period_end, period_type, basis,
       value, currency, scale, document_id, page, bbox, knowledge_period
     ) values (
       $1, $2, '2024-07-01', '2025-06-30', 'FY', $3, $4, 'ZAR', 'units', $5, 1, $6, $7::tstzrange
     )`,
    [
      options.companyId,
      options.conceptId,
      options.basis ?? "as_reported",
      options.value ?? 1000,
      options.documentId,
      JSON.stringify(BBOX),
      options.knowledgePeriod,
    ],
  );
}

/** Realistic restatement: close the current open-ended row, insert the new
 * one open-ended, same transaction — mirroring the Python suite's
 * `_restate_fact` and M2.12/M6's expected write path. Raw SQL because
 * there is deliberately no TypeScript equivalent of publish_fact. */
async function restateFact(
  client: pg.Client,
  options: {
    companyId: number;
    conceptId: number;
    documentId: number;
    restatedAt: Date;
    newValue: number;
  },
): Promise<void> {
  const updateResult = await client.query(
    `update facts
     set knowledge_period = tstzrange(lower(knowledge_period), $1, '[)')
     where company_id = $2 and concept_id = $3 and upper_inf(knowledge_period)`,
    [options.restatedAt.toISOString(), options.companyId, options.conceptId],
  );
  assert.equal(updateResult.rowCount, 1, "expected exactly one currently-open row to restate");
  await insertFact(client, {
    companyId: options.companyId,
    conceptId: options.conceptId,
    documentId: options.documentId,
    knowledgePeriod: `[${options.restatedAt.toISOString()},)`,
    value: options.newValue,
  });
}

test("getFactsAsOf returns the correct version across a revision", async () => {
  await withRollback(async (client) => {
    const companyId = await insertCompany(client, "T01");
    const conceptId = await insertConcept(client, "t01_revenue");
    const documentId = await insertDocument(client, "t01");

    const original = instant(0);
    const restatedAt = instant(10);

    await insertFact(client, {
      companyId,
      conceptId,
      documentId,
      knowledgePeriod: `[${original.toISOString()},)`,
      value: 1000,
    });
    await restateFact(client, { companyId, conceptId, documentId, restatedAt, newValue: 1050 });

    const before = await getFactsAsOf(client, instant(5));
    const beforeMatch = before.filter((f) => f.companyId === companyId);
    assert.equal(beforeMatch.length, 1);
    assert.equal(beforeMatch[0]?.value, "1000");

    const after = await getFactsAsOf(client, instant(20));
    const afterMatch = after.filter((f) => f.companyId === companyId);
    assert.equal(afterMatch.length, 1);
    assert.equal(afterMatch[0]?.value, "1050");

    const current = await getFactsAsOf(client);
    const currentMatch = current.filter((f) => f.companyId === companyId);
    assert.equal(currentMatch.length, 1);
    assert.equal(currentMatch[0]?.value, "1050");
  });
});

test(
  "getFactsAsOf at the exact boundary instant returns the second row " +
    "(ported from test_facts_as_of.py — cross-language agreement)",
  async () => {
    await withRollback(async (client) => {
      const companyId = await insertCompany(client, "T02");
      const conceptId = await insertConcept(client, "t02_revenue");
      const documentId = await insertDocument(client, "t02");

      const t1 = instant(0);
      const t2 = instant(10);
      const t3 = instant(20);

      // [t1, t2) and [t2, t3): t2 is excluded from the first (upper bound,
      // exclusive) and included in the second (lower bound, inclusive),
      // per the [lower, upper) convention M1.8 decided on. An as_of query
      // at exactly t2 must return the SECOND row.
      await insertFact(client, {
        companyId,
        conceptId,
        documentId,
        knowledgePeriod: `[${t1.toISOString()},${t2.toISOString()})`,
        value: 1111,
      });
      await insertFact(client, {
        companyId,
        conceptId,
        documentId,
        knowledgePeriod: `[${t2.toISOString()},${t3.toISOString()})`,
        value: 2222,
      });

      const atBoundary = await getFactsAsOf(client, t2);
      const match = atBoundary.filter((f) => f.companyId === companyId);
      assert.equal(match.length, 1);
      assert.equal(match[0]?.value, "2222");
    });
  },
);

test("getFactsAsOf before any knowledge existed returns no rows", async () => {
  await withRollback(async (client) => {
    const companyId = await insertCompany(client, "T03");
    const conceptId = await insertConcept(client, "t03_revenue");
    const documentId = await insertDocument(client, "t03");
    const knowledgeBegins = instant(10);

    await insertFact(client, {
      companyId,
      conceptId,
      documentId,
      knowledgePeriod: `[${knowledgeBegins.toISOString()},)`,
      value: 9999,
    });

    const results = await getFactsAsOf(client, instant(0));
    assert.deepEqual(
      results.filter((f) => f.companyId === companyId),
      [],
    );
  });
});

test("getFactsAsOf returns value as a string, not a parsed number", async () => {
  await withRollback(async (client) => {
    const companyId = await insertCompany(client, "T04");
    const conceptId = await insertConcept(client, "t04_revenue");
    const documentId = await insertDocument(client, "t04");

    await insertFact(client, {
      companyId,
      conceptId,
      documentId,
      knowledgePeriod: `[${instant(0).toISOString()},)`,
      value: 47000,
    });

    const [fact] = (await getFactsAsOf(client)).filter((f) => f.companyId === companyId);
    assert.equal(typeof fact?.value, "string");
    assert.equal(fact?.value, "47000");
    assert.deepEqual(fact?.bbox, BBOX);
    assert.equal(typeof fact?.periodStart, "string");
    assert.equal(fact?.periodStart, "2024-07-01");
  });
});

test("getCompanies returns rows shaped per the companies table", async () => {
  // Self-contained, like every other test here — does not depend on
  // M1.11's seed script having run (CI does not run it, and no other test
  // in this file assumes seeded data either).
  await withRollback(async (client) => {
    const companyId = await insertCompany(client, "T06");
    const companies = await getCompanies(client);
    const found = companies.find((c) => c.id === companyId);
    assert.ok(found, "expected the freshly inserted company to be returned");
    assert.equal(found?.jseCode, "T06");
    assert.equal(found?.archetype, "retail");
    assert.equal(found?.fyeMonth, 6);
  });
});

test("getConcepts returns rows shaped per the concepts table", async () => {
  await withRollback(async (client) => {
    const conceptId = await insertConcept(client, "t05_test_concept");
    const concepts = await getConcepts(client);
    const found = concepts.find((c) => c.id === conceptId);
    assert.ok(found, "expected the freshly inserted concept to be returned");
    assert.deepEqual(found?.archetypeSet, ["retail"]);
    assert.equal(found?.signConvention, "natural");
  });
});
