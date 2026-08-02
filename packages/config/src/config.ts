import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const REQUIRED_KEYS = [
  "DATABASE_URL",
  "AWS_REGION",
  "AWS_ACCESS_KEY_ID",
  "AWS_SECRET_ACCESS_KEY",
  "S3_BUCKET",
] as const;

export interface Config {
  readonly databaseUrl: string;
  readonly awsRegion: string;
  readonly awsAccessKeyId: string;
  readonly awsSecretAccessKey: string;
  readonly s3Bucket: string;
  readonly awsEndpointUrl: string | null;
  /**
   * True when pointed at LocalStack; false means real AWS. This is the one
   * place that resolves the environment — callers building an S3/SQS client
   * pass `awsEndpointUrl` straight through instead of writing their own
   * if/else on "am I local".
   */
  readonly usesLocalStack: boolean;
}

function repoRootEnvFile(): string | null {
  let dir = dirname(fileURLToPath(import.meta.url));
  while (true) {
    if (existsSync(join(dir, ".git"))) {
      return join(dir, ".env");
    }
    const parent = dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

/** Loads the repo-root .env into process.env, if one exists. Safe to call more than once. */
export function loadDotEnvIfPresent(): void {
  const envFile = repoRootEnvFile();
  if (envFile === null) return;
  try {
    process.loadEnvFile(envFile);
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code !== "ENOENT") {
      throw err;
    }
  }
}

/**
 * Validates and returns typed config from the given environment map.
 * Fails loudly (throws) if a required variable is missing, rather than
 * returning `undefined` for a caller to trip over later.
 */
export function loadConfig(env: Record<string, string | undefined> = process.env): Config {
  const missing = REQUIRED_KEYS.filter((key) => !env[key]);
  if (missing.length > 0) {
    throw new Error(`Missing required environment variable(s): ${missing.join(", ")}`);
  }

  const awsEndpointUrl = env.AWS_ENDPOINT_URL?.trim() || null;

  return {
    databaseUrl: env.DATABASE_URL as string,
    awsRegion: env.AWS_REGION as string,
    awsAccessKeyId: env.AWS_ACCESS_KEY_ID as string,
    awsSecretAccessKey: env.AWS_SECRET_ACCESS_KEY as string,
    s3Bucket: env.S3_BUCKET as string,
    awsEndpointUrl,
    usesLocalStack: awsEndpointUrl !== null,
  };
}

/** Loads .env (if present) then returns validated config from process.env. */
export function getConfig(): Config {
  loadDotEnvIfPresent();
  return loadConfig(process.env);
}
