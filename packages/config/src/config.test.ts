import assert from "node:assert/strict";
import { test } from "node:test";
import { loadConfig } from "./config.ts";

const REQUIRED_ENV = {
  DATABASE_URL: "postgres://valora:valora@localhost:5432/valora",
  AWS_REGION: "af-south-1",
  AWS_ACCESS_KEY_ID: "test",
  AWS_SECRET_ACCESS_KEY: "test",
  S3_BUCKET: "valora-documents-dev",
};

test("resolves to LocalStack when AWS_ENDPOINT_URL is set", () => {
  const config = loadConfig({ ...REQUIRED_ENV, AWS_ENDPOINT_URL: "http://localhost:4566" });
  assert.equal(config.usesLocalStack, true);
  assert.equal(config.awsEndpointUrl, "http://localhost:4566");
});

test("resolves to real AWS when AWS_ENDPOINT_URL is unset", () => {
  const config = loadConfig({ ...REQUIRED_ENV });
  assert.equal(config.usesLocalStack, false);
  assert.equal(config.awsEndpointUrl, null);
});

test("resolves to real AWS when AWS_ENDPOINT_URL is blank", () => {
  const config = loadConfig({ ...REQUIRED_ENV, AWS_ENDPOINT_URL: "" });
  assert.equal(config.usesLocalStack, false);
  assert.equal(config.awsEndpointUrl, null);
});

test("throws when a required variable is missing", () => {
  const { DATABASE_URL: _omit, ...incomplete } = REQUIRED_ENV;
  assert.throws(() => loadConfig(incomplete));
});
