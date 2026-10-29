// P-11-T04 (SPEC-520 AC-32; F-06 §5.2): the T10 DocumentVM's header and the F-07 field manifest
// are satisfiable from C11's shapes, on the seed-derived fixture of the Copperleaf engagement
// letter (fixtures/handlers/reporting.ts). Written from the contract, not the implementation.
import type { GeneratedDocumentOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import type { FixtureRequest } from "../../app-core/fixture-mode";
import { documentHeader, fieldManifest } from "../../domain/documents/c11";
import { COPPERLEAF_LETTER, reportingHandlers } from "../handlers/reporting";
import { validateResponse } from "../schema-check";

const DF31 = ["drafting", "draft", "approved", "locked"];

describe("C11 → T10 DocumentVM header", () => {
  it("test_ac32 the status is the server's DF-31 word, unchanged", () => {
    const header = documentHeader(COPPERLEAF_LETTER);
    expect(DF31).toContain(header.status);
    expect(header.status).toBe(COPPERLEAF_LETTER.status);
  });

  it("test_ac32 an approved final version carries who approved and when, and no watermark", () => {
    const header = documentHeader(COPPERLEAF_LETTER);
    expect(header.approvedBy).toEqual({ name: "Priya Raman", at: "2026-09-11T16:40:00Z" });
    expect(header.watermark).toBe(false);
  });

  it("test_ac32 a current draft is stamped DRAFT and has no approver", () => {
    const draft: GeneratedDocumentOut = {
      ...COPPERLEAF_LETTER,
      status: "draft",
      current_version: 1,
    };
    const header = documentHeader(draft);
    expect(header.watermark).toBe(true);
    expect(header.approvedBy).toBeUndefined();
  });

  it("test_ac32 Regenerate draws only when the server allows it; out of date is the server's", () => {
    expect(documentHeader(COPPERLEAF_LETTER).canRegenerate).toBe(true);
    expect(documentHeader(COPPERLEAF_LETTER).outOfDate).toBe(true);
    const readOnly = { ...COPPERLEAF_LETTER, allowed_actions: ["generated_document.read"] };
    expect(documentHeader(readOnly).canRegenerate).toBe(false);
  });
});

describe("C11 → F-07 field manifest", () => {
  it("test_ac32 every field places on a page with a four-point rect and a gd: match id", async () => {
    const handler =
      reportingHandlers()[
        "GET /v1/generated-documents/{document_id}/versions/{version_no}/fields"
      ];
    expect(handler).toBeDefined();
    const response = await handler?.({
      method: "GET",
      path: "",
      params: { document_id: COPPERLEAF_LETTER.id, version_no: "2" },
      query: new URLSearchParams(),
      body: null,
      persona: undefined,
    });
    const manifest = fieldManifest(await (response as Response).json());
    expect(manifest.length).toBeGreaterThan(0);
    for (const f of manifest) {
      expect(f.page).toBeGreaterThanOrEqual(1);
      expect(f.rect.x1).toBeGreaterThan(f.rect.x0);
      expect(f.rect.bottom).toBeGreaterThan(f.rect.top);
      expect(f.matchId.startsWith("gd:")).toBe(true);
    }
  });
});

describe("C11 refusals in fixture mode", () => {
  it("test_ac32 publishing a published version answers 409 already_published", async () => {
    const handler =
      reportingHandlers()["POST /v1/report-templates/{template_id}/versions/{version_no}/publish"];
    const response = (await handler?.({
      method: "POST",
      path: "",
      params: {},
      query: new URLSearchParams(),
      body: null,
      persona: undefined,
    })) as Response;
    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({ detail: "already_published" });
  });
});

describe("C11 fixtures match the OpenAPI shapes", () => {
  const request = (params: Record<string, string>, method = "GET"): FixtureRequest => ({
    method,
    path: "",
    params,
    query: new URLSearchParams(),
    body: null,
    persona: undefined,
  });
  const doc = { document_id: COPPERLEAF_LETTER.id, version_no: "2" };
  const cases: readonly [string, string, Record<string, string>][] = [
    ["GET", "/v1/generated-documents/{document_id}", doc],
    ["GET", "/v1/generated-documents/{document_id}/versions/{version_no}/fields", doc],
    ["GET", "/v1/generated-documents/{document_id}/versions/{version_no}/compare", doc],
    ["GET", "/v1/generated-documents/{document_id}/changes", doc],
    ["POST", "/v1/generated-documents/{document_id}/regenerate", doc],
    ["GET", "/v1/report-templates", {}],
    ["POST", "/v1/report-templates/import", {}],
  ];
  it.each(cases)("test_ac32 %s %s validates", async (method, path, params) => {
    const handler = reportingHandlers()[`${method} ${path}`];
    expect(handler).toBeDefined();
    const response = (await handler?.(request(params, method))) as Response;
    expect(validateResponse(method, path, await response.json())).toEqual([]);
  });
});
