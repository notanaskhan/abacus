// C11 in fixture mode (P-11-T03; docs/contracts/c11-renderer.md; ADR-320): the generated-document
// and report-template routes on the live shapes, seed-derived from Brightwater Hale at E0 (Mon Sep
// 14, 2026, 9:24 AM CT). One generated document: Copperleaf Coffee Roasters' engagement letter,
// version 1 a draft Grace Holloway rendered, version 2 the final Priya Raman approved; its fields,
// one changed variable (the fee), the standard-clause compare; and the firm's engagement-letter
// template with its version. The fixture writes nothing: regenerate answers a Drafting ticket,
// import a dry-run report and publish refuses as the server does for a published version.
import type {
  ChangesOut,
  CompareOut,
  FieldRegionsOut,
  GeneratedDocumentOut,
  ImportReportOut,
  ListPageReportTemplateOut,
  RenderTicketOut,
  ReportTemplateVersionOut,
} from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not_found" };

export const COPPERLEAF_LETTER_ID = stableId("generated-document:copperleaf-engagement-letter");
const TEMPLATE_ID = stableId("report-template:brightwater-hale:engagement-letter");
const OWNER_ID = stableId("engagement-letter:copperleaf-2026");

/** A deterministic 64-hex digest for a label (seed hashes, never real file hashes). */
function hex64(label: string): string {
  return (stableId(`${label}:a`) + stableId(`${label}:b`)).replaceAll("-", "").slice(0, 64);
}

const DRAFT_HASH = hex64("copperleaf-letter:content:v1");

export const COPPERLEAF_LETTER: GeneratedDocumentOut = {
  id: COPPERLEAF_LETTER_ID,
  kind: "engagement_letter",
  owner_ref: { type: "engagement_letter", id: OWNER_ID },
  status: "approved",
  out_of_date: true,
  out_of_date_reasons: ["engagement.fee_changed"],
  current_version: 2,
  versions: [
    {
      n: 1,
      mode: "draft",
      files: [
        {
          format: "pdf",
          evidence_version_id: stableId("evidence-version:copperleaf-letter:v1:pdf"),
          render_hash: hex64("copperleaf-letter:v1:pdf"),
          page_count: 3,
        },
      ],
      content_hash: DRAFT_HASH,
      template: { id: TEMPLATE_ID, version_no: 1, name: "Engagement letter · CAS" },
      snapshot_sha256: hex64("copperleaf-letter:snapshot:v1"),
      engine_version: "weasyprint 70.0 · pydyf 0.13.0 · pango 1.56.3 · fonts 1",
      requested_by: { kind: "human", label: "Grace Holloway" },
      approval: null,
      created_at: "2026-09-11T15:02:00Z",
    },
    {
      n: 2,
      mode: "final",
      files: [
        {
          format: "pdf",
          evidence_version_id: stableId("evidence-version:copperleaf-letter:v2:pdf"),
          render_hash: hex64("copperleaf-letter:v2:pdf"),
          page_count: 3,
        },
      ],
      content_hash: DRAFT_HASH,
      template: { id: TEMPLATE_ID, version_no: 1, name: "Engagement letter · CAS" },
      snapshot_sha256: hex64("copperleaf-letter:snapshot:v1"),
      engine_version: "weasyprint 70.0 · pydyf 0.13.0 · pango 1.56.3 · fonts 1",
      requested_by: { kind: "human", label: "Priya Raman" },
      approval: { by: "Priya Raman", at: "2026-09-11T16:40:00Z" },
      created_at: "2026-09-11T16:41:00Z",
    },
  ],
  allowed_actions: ["generated_document.read", "generated_document.regenerate"],
};

const FIELDS: FieldRegionsOut = {
  items: [
    {
      field_key: "client.name",
      label: "Client",
      page: 1,
      rect_pt: [72, 144, 340, 158],
      value_text: "Copperleaf Coffee Roasters, Inc.",
      match_id: `gd:${COPPERLEAF_LETTER_ID}:2#client.name`,
    },
    {
      field_key: "engagement.monthly_fee",
      label: "Monthly fee",
      page: 3,
      rect_pt: [312, 210, 372, 224],
      value_text: "2,400.00",
      match_id: `gd:${COPPERLEAF_LETTER_ID}:2#engagement.monthly_fee`,
    },
  ],
};

const CHANGES: ChangesOut = {
  items: [
    {
      key: "engagement.monthly_fee",
      label: "Monthly fee",
      was: "2,400.00",
      now: "2,650.00",
      masked: false,
    },
  ],
};

const COMPARE: CompareOut = {
  to: "standard",
  blocks: [
    {
      block_id: "fees",
      clause_id: "fees-fixed-monthly",
      ops: [
        { op: "equal", text: "Our fee is a fixed monthly amount of" },
        { op: "insert", text: "2,400.00, billed on the first business day of each month." },
      ],
    },
  ],
};

const TEMPLATES: ListPageReportTemplateOut = {
  items: [
    {
      id: TEMPLATE_ID,
      family: "engagement_letter",
      name: "Engagement letter · CAS",
      description: "Monthly compilation and bookkeeping engagements.",
      current_version: 1,
      published_at: "2026-08-03T14:00:00Z",
    },
  ],
  next_cursor: null,
  total: 1,
};

const TEMPLATE_VERSION: ReportTemplateVersionOut = {
  template_id: TEMPLATE_ID,
  version_no: 1,
  layout_key: "letter",
  body: [
    { type: "heading", level: 1, text: "Engagement letter" },
    {
      type: "paragraph",
      runs: [
        { type: "text", text: "This letter confirms the services we will provide to " },
        { type: "var", key: "client.name" },
        { type: "text", text: "." },
      ],
    },
  ],
  clauses: [],
  variables: [
    { key: "client.name", label: "Client", value_type: "name" },
    { key: "engagement.monthly_fee", label: "Monthly fee", value_type: "money" },
  ],
  publications: [{ action: "published", by: "Margaret Okonkwo", at: "2026-08-03T14:00:00Z" }],
  content_sha256: hex64("template:engagement-letter:v1"),
};

const isLetter = (id: string | undefined): boolean => id === COPPERLEAF_LETTER_ID;

export function reportingHandlers(): Record<string, FixtureHandler> {
  return {
    "GET /v1/report-templates": () => json(TEMPLATES),
    "GET /v1/report-templates/{template_id}/versions/{version_no}": ({ params }) =>
      params.template_id === TEMPLATE_ID && params.version_no === "1"
        ? json(TEMPLATE_VERSION)
        : json(NOT_FOUND, 404),
    "POST /v1/report-templates/import": () =>
      json({
        ok: true,
        errors: [],
        warnings: [],
        draft_version_id: null,
      } satisfies ImportReportOut),
    "POST /v1/report-templates/{template_id}/versions/{version_no}/publish": () =>
      json({ detail: "already_published" }, 409),
    "GET /v1/generated-documents/{document_id}": ({ params }) =>
      isLetter(params.document_id) ? json(COPPERLEAF_LETTER) : json(NOT_FOUND, 404),
    "GET /v1/generated-documents/{document_id}/versions/{version_no}/fields": ({ params }) =>
      isLetter(params.document_id) ? json(FIELDS) : json(NOT_FOUND, 404),
    "GET /v1/generated-documents/{document_id}/versions/{version_no}/compare": ({ params }) =>
      isLetter(params.document_id) ? json(COMPARE) : json(NOT_FOUND, 404),
    "GET /v1/generated-documents/{document_id}/changes": ({ params }) =>
      isLetter(params.document_id) ? json(CHANGES) : json(NOT_FOUND, 404),
    "POST /v1/generated-documents/{document_id}/regenerate": ({ params }) =>
      isLetter(params.document_id)
        ? json({
            generated_document_id: COPPERLEAF_LETTER_ID,
            version_no: 3,
            status: "drafting",
          } satisfies RenderTicketOut)
        : json(NOT_FOUND, 404),
  };
}
