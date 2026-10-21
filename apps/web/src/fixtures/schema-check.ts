// Test support for the interim seed (F-04-T05): checks a value against the OpenAPI document the
// client is generated from. The TypeScript types stop a schema change at compile time; this stops
// one at run time too, for what a type cannot say (uuid and date formats, lengths, enums, and a
// field the schema does not have). Imported by tests only.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

type Schema = Record<string, unknown>;

interface OpenApi {
  paths: Record<
    string,
    Record<string, { responses: Record<string, { content?: Record<string, { schema: Schema }> }> }>
  >;
  components: { schemas: Record<string, Schema> };
}

const here = dirname(fileURLToPath(import.meta.url));
const SPEC = JSON.parse(
  readFileSync(
    join(here, "..", "..", "..", "..", "packages", "api-client", "openapi.json"),
    "utf8",
  ),
) as OpenApi;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DATE = /^\d{4}-\d{2}-\d{2}$/;
const DATE_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;

function resolve(schema: Schema): Schema {
  const ref = schema.$ref;
  if (typeof ref !== "string") return schema;
  const target = SPEC.components.schemas[ref.replace("#/components/schemas/", "")];
  if (target === undefined) throw new Error(`unknown schema ${ref}`);
  return target;
}

function check(schema: Schema, value: unknown, at: string, errors: string[]): void {
  const node = resolve(schema);
  const anyOf = node.anyOf as Schema[] | undefined;
  if (anyOf !== undefined) {
    const attempts = anyOf.map((option) => {
      const own: string[] = [];
      check(option, value, at, own);
      return own;
    });
    if (!attempts.some((own) => own.length === 0)) errors.push(`${at}: matches no option`);
    return;
  }
  const enumValues = node.enum as unknown[] | undefined;
  if (enumValues !== undefined && !enumValues.includes(value)) {
    errors.push(`${at}: ${JSON.stringify(value)} is not one of ${enumValues.join(", ")}`);
    return;
  }
  switch (node.type) {
    case "null":
      if (value !== null) errors.push(`${at}: expected null`);
      return;
    case "string": {
      if (typeof value !== "string") return void errors.push(`${at}: expected a string`);
      if (node.format === "uuid" && !UUID.test(value)) errors.push(`${at}: not a uuid`);
      if (node.format === "date" && !DATE.test(value)) errors.push(`${at}: not a date`);
      if (node.format === "date-time" && !DATE_TIME.test(value))
        errors.push(`${at}: not a date-time`);
      if (typeof node.minLength === "number" && value.length < node.minLength)
        errors.push(`${at}: too short`);
      if (typeof node.maxLength === "number" && value.length > node.maxLength)
        errors.push(`${at}: too long`);
      return;
    }
    case "integer":
      if (!Number.isInteger(value)) errors.push(`${at}: expected an integer`);
      return;
    case "number":
      if (typeof value !== "number") errors.push(`${at}: expected a number`);
      return;
    case "boolean":
      if (typeof value !== "boolean") errors.push(`${at}: expected a boolean`);
      return;
    case "array": {
      if (!Array.isArray(value)) return void errors.push(`${at}: expected an array`);
      value.forEach((entry, i) => {
        check(node.items as Schema, entry, `${at}[${String(i)}]`, errors);
      });
      return;
    }
    case "object": {
      if (typeof value !== "object" || value === null || Array.isArray(value)) {
        return void errors.push(`${at}: expected an object`);
      }
      const properties = (node.properties ?? {}) as Record<string, Schema>;
      const record = value as Record<string, unknown>;
      for (const name of (node.required ?? []) as string[]) {
        if (!(name in record)) errors.push(`${at}.${name}: required`);
      }
      for (const [name, entry] of Object.entries(record)) {
        const property = properties[name];
        if (property === undefined) {
          if (node.additionalProperties === undefined || node.additionalProperties === false) {
            errors.push(`${at}.${name}: not in the schema`);
          }
        } else check(property, entry, `${at}.${name}`, errors);
      }
      return;
    }
    default:
      return;
  }
}

/** The errors of `value` against the named component schema (`EngagementOut`); empty when valid. */
export function validateSchema(name: string, value: unknown): string[] {
  const errors: string[] = [];
  check({ $ref: `#/components/schemas/${name}` }, value, name, errors);
  return errors;
}

/** The errors of a response body against the 200 schema of `METHOD path` in the OpenAPI document. */
export function validateResponse(method: string, path: string, value: unknown): string[] {
  const schema =
    SPEC.paths[path]?.[method.toLowerCase()]?.responses["200"]?.content?.["application/json"]
      ?.schema;
  if (schema === undefined) throw new Error(`${method} ${path} has no 200 JSON schema`);
  const errors: string[] = [];
  check(schema, value, `${method} ${path}`, errors);
  return errors;
}
