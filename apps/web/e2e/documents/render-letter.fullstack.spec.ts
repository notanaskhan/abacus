// P-11-T16 (P-11 §1 story, AC3.4; ENG-04, SHL-08): the Copperleaf engagement letter rendered by
// C11 on the full stack and staging, on the harness (axe and INV-1 to INV-5 after each step).
// Priya Raman (CAS partner) reads the seeded draft: its PDF's render_hash is the same on two reads
// and in a second run (the same snapshot renders the same bytes, ADR-042); SHL-08 opens it; a fee
// change in Draft re-renders it as version 2 with a new hash, by code (no model writes letter
// text, DEC-79). Nothing here approves, sends or signs (INV-1).
//
// The fixture project has no renderer: it is fixme there. Hosted runs read the seeded engagement
// from the environment (`ABACUS_E2E_COPPERLEAF_ENGAGEMENT`, a synthetic id the seed writes);
// without it the test skips. "Out of date · Update from data" on ENG-04 needs a fee change on the
// engagement to reach the letter as a C11 source event; the `engagement_letter` kind registers no
// source event yet (DEC-1664), so that step is fixme with its owner.
import type { Page } from "@playwright/test";
import { expect, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const ENGAGEMENT = process.env.ABACUS_E2E_COPPERLEAF_ENGAGEMENT;
// The render_hash of the seeded draft's PDF as the previous nightly saw it (optional): when set,
// this run must render the same bytes ("stable across two runs").
const PREVIOUS_HASH = process.env.ABACUS_E2E_COPPERLEAF_RENDER_HASH;

type Json = Record<string, unknown>;
interface PdfFile {
  format: string;
  evidence_version_id: string | null;
  render_hash: string;
}
interface Version {
  n: number;
  files: PdfFile[];
  content_hash: string;
}
interface Document {
  current_version: number | null;
  out_of_date: boolean;
  versions: Version[];
}

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

/** A request as the signed-in persona, with the SPA's own session (the harness probe's way). */
async function api(
  page: Page,
  method: "GET" | "PUT",
  path: string,
  body?: Json,
  extra: Record<string, string> = {},
): Promise<{ status: number; json: Json; headers: Record<string, string> }> {
  const headers = await page.evaluate(() => {
    const read = (key: string): string | null => sessionStorage.getItem(key);
    const session = JSON.parse(read("abacus.session") ?? "null") as {
      accessToken?: string;
    } | null;
    const out: Record<string, string> = {};
    if (session?.accessToken !== undefined) out.Authorization = `Bearer ${session.accessToken}`;
    const tenant = read("abacus.tenant");
    if (tenant !== null) out["X-Abacus-Tenant"] = tenant;
    return out;
  });
  const response = await page.request.fetch(path, {
    method,
    headers: { ...headers, ...extra },
    ...(body === undefined ? {} : { data: body }),
    failOnStatusCode: false,
  });
  const text = await response.text();
  return {
    status: response.status(),
    json: text.startsWith("{") ? (JSON.parse(text) as Json) : {},
    headers: response.headers(),
  };
}

function pdfOf(doc: Document): PdfFile {
  const current = doc.versions.find((v) => v.n === doc.current_version);
  const pdf = current?.files.find((f) => f.format === "pdf");
  if (pdf === undefined) throw new Error("the current version has no PDF");
  return pdf;
}

test.describe("Copperleaf engagement letter rendered by C11, full stack (P-11-T16)", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
    test.fixme(journey.project === "fixture", "no renderer in the fixture project");
    test.skip(ENGAGEMENT === undefined, "ABACUS_E2E_COPPERLEAF_ENGAGEMENT is not set");
  });

  test(
    "the seeded draft renders the same bytes twice and opens in SHL-08",
    owner("P-11 · P-11-T16 full-stack render · S21, Fri Aug 20, 2027"),
    async ({ journey }) => {
      await journey.as("priya-raman", `/engagements/${ENGAGEMENT ?? ""}`);
      const page = journey.page;
      let documentId = "";
      let pdf: PdfFile | undefined;
      await journey.step("P-11 step 1: the Copperleaf draft from the seed", async () => {
        const letter = await api(
          page,
          "GET",
          `/v1/engagements/${ENGAGEMENT ?? ""}/letter/composer`,
        );
        expect(letter.status).toBe(200);
        expect(letter.json.status).toBe("draft");
        documentId = String(letter.json.generated_document_id);
        const first = await api(page, "GET", `/v1/generated-documents/${documentId}`);
        const again = await api(page, "GET", `/v1/generated-documents/${documentId}`);
        expect(first.status).toBe(200);
        pdf = pdfOf(first.json as unknown as Document);
        expect(pdfOf(again.json as unknown as Document).render_hash).toBe(pdf.render_hash);
        if (PREVIOUS_HASH !== undefined) expect(pdf.render_hash).toBe(PREVIOUS_HASH);
        expect(pdf.evidence_version_id).not.toBeNull();
      });
      await journey.step("P-11 step 2: SHL-08 opens the draft PDF", async () => {
        await page.goto(`/viewer/${pdf?.evidence_version_id ?? ""}`);
        await expect(page.locator("[data-viewer-bar]").first()).toBeVisible();
        await expect(page.getByRole("button", { name: /^(Approve|Send|Sign)/u })).toHaveCount(0);
      });
    },
  );

  test(
    "a fee change in Draft renders version 2 with a new hash",
    owner("P-11 · P-11-T16 full-stack regenerate · S21, Fri Aug 20, 2027"),
    async ({ journey }) => {
      await journey.as("priya-raman", `/engagements/${ENGAGEMENT ?? ""}`);
      const page = journey.page;
      await journey.step("P-11 step 3: the fee changes and the letter renders again", async () => {
        const letter = await api(
          page,
          "GET",
          `/v1/engagements/${ENGAGEMENT ?? ""}/letter/composer`,
        );
        expect(letter.status).toBe(200);
        const documentId = String(letter.json.generated_document_id);
        const before = await api(page, "GET", `/v1/generated-documents/${documentId}`);
        const was = before.json as unknown as Document;
        const fees = letter.json.fees as { basis: string; lines: Json[] };
        const lines = fees.lines.map((line, i) =>
          i === 0 ? { ...line, amount_cents: Number(line.amount_cents) + 50_000 } : line,
        );
        const clauses = letter.json.clauses as { key: string; state: string }[];
        const variables = letter.json.variables as {
          key: string;
          value: string | null;
          source: string;
        }[];
        const changed = await api(
          page,
          "PUT",
          `/v1/engagements/${ENGAGEMENT ?? ""}/letter/composer`,
          {
            template_version_id: letter.json.template_version_id,
            clause_states: Object.fromEntries(clauses.map((c) => [c.key, c.state])),
            variables: Object.fromEntries(
              variables
                .filter((v) => v.source === "override" && v.value !== null)
                .map((v) => [v.key, v.value]),
            ),
            section_overrides: {},
            fees: { basis: fees.basis, lines },
          },
          { "If-Match": `"${String(letter.json.version)}"` },
        );
        expect(changed.status).toBe(200);
        const after = await api(page, "GET", `/v1/generated-documents/${documentId}`);
        const now = after.json as unknown as Document;
        expect(now.current_version).toBe((was.current_version ?? 0) + 1);
        expect(pdfOf(now).render_hash).not.toBe(pdfOf(was).render_hash);
      });
    },
  );

  test.fixme(
    "a fee change on the engagement shows Out of date · Update from data, and Update gives version 2",
    owner(
      "P-11 / N-02 · engagement_letter source events (DEC-1664) and ENG-04's live swap (N-02-T37)",
    ),
    async ({ journey }) => {
      await journey.as("priya-raman", `/engagements/${ENGAGEMENT ?? ""}`);
    },
  );
});
