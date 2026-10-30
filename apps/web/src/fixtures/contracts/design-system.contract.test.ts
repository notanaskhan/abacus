// F-05-T44: the design system's consumer contract tests (TypeScript fixture assertions run in the
// provider's CI), for the four contracts the F-05 templates and kits read:
//   C2    the status registry: every generated enum a template draws has its words (EnumCovered)
//   C4    citations v2, the viewer manifest, regions and masks: what E1, E2 and the E5 shell read
//   C5    `/v1/me.portal`: the shell and nav the T7 PortalLayout and PortalToolbar draw
//   P-36  the list envelope `{items, next_cursor, total, counts, facets}` the T1 IndexList reads
// "A breaking change to any consumed schema fails the provider's CI before a template breaks": each
// mapping below is typed against the generated client, so a removed field, a renamed one, or a new
// enum literal without a home is a `tsc` error; each fixture is also checked against openapi.json
// at run time, for what a type cannot say. Fixtures are Brightwater Hale, synthetic.
import type {
  BinderStatus,
  CitationV2Out,
  ClientStatus,
  EngagementStatus,
  EvidenceUnlockOut,
  Facet,
  ListPageAccessLogRow,
  ListPageAuditEventRow,
  ListPageActivityEventOut,
  ListPageBinderRequestRowOut,
  ListPageBinderRowOut,
  ListPageChangeLogEntryOut,
  ListPageCitationV2Out,
  ListPageClientRelationshipOut,
  ListPageClientRowOut,
  ListPageConsentOut,
  ListPageDecisionCardItemOut,
  ListPageEnvelopeListRow,
  ListPageHumanGateOut,
  ListPageInboxThreadRow,
  ListPageIntakeUploadOut,
  ListPageIssueItemOut,
  ListPageK1PackageOut,
  ListPageKnowledgeItemOut,
  ListPageMappingSetSummaryOut,
  ListPagePortalEnvelopeRow,
  ListPageReferenceSetOut,
  ListPageReferenceSetVersionOut,
  ListPageReportTemplateOut,
  ListPageReviewNoteItemOut,
  ListPageReviewQueueItemOut,
  ListPageSampleItemOut,
  ListPageSampleSetSummaryOut,
  ListPageStandardOut,
  ListPageTaxReturnRowOut,
  ListPageWallEventOut,
  ListPageWorkItemRowOut,
  MePortalOut,
  PiiMaskOut,
  RequestStatus,
  ViewerManifestOut,
  ViewerRegionOut,
  ViewerRegionsOut,
} from "@abacus/api-client";
import {
  type CitationView,
  type EnumCovered,
  type ListEnvelope,
  type LocatorKind,
  type MatchId,
  PORTAL_AREAS,
  type PortalVariant,
  STATUS_REGISTRY,
  contractMatchId,
  registryWord,
} from "@abacus/ui";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { validateSchema } from "../schema-check";

/** `true` only when each of A and B is assignable to the other. */
type Equal<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;

const here = dirname(fileURLToPath(import.meta.url));
const SPEC = JSON.parse(
  readFileSync(
    join(here, "..", "..", "..", "..", "..", "packages", "api-client", "openapi.json"),
    "utf8",
  ),
) as {
  components: {
    schemas: Record<string, { properties?: Record<string, unknown>; required?: string[] }>;
  };
};

// ---- P-36: the list envelope (T1 IndexList) ------------------------------------------------------

/** What a list page must keep for T1: the fields `ListEnvelope` reads, in shapes it accepts. */
interface ListPageShape<T> {
  items: T[];
  next_cursor?: string | null;
  total: number;
  total_capped?: boolean;
  counts?: { [code: string]: number };
  facets?: { [key: string]: Facet[] };
}

/** The one adaptation every T1 screen makes (CLI-01, BND-01): absent cursor and counts. */
function envelope<T>(page: ListPageShape<T>): ListEnvelope<T> {
  return {
    items: page.items,
    next_cursor: page.next_cursor ?? null,
    total: page.total,
    ...(page.total_capped === undefined ? {} : { total_capped: page.total_capped }),
    counts: page.counts ?? {},
    ...(page.facets === undefined ? {} : { facets: page.facets }),
  };
}

// Every generated list page adapts. A page that drops `items` or `total`, renames `next_cursor`,
// or changes `counts` or a facet's `{value, label, n}` stops compiling here.
const LIST_PAGES = {
  ListPage_AccessLogRow_: (p: ListPageAccessLogRow) => envelope(p), // N-01: FIL-01 access log
  ListPage_ActivityEventOut_: (p: ListPageActivityEventOut) => envelope(p),
  ListPage_AuditEventRow_: (p: ListPageAuditEventRow) => envelope(p), // P-07-T57: Activity
  ListPage_BinderRequestRowOut_: (p: ListPageBinderRequestRowOut) => envelope(p),
  ListPage_BinderRowOut_: (p: ListPageBinderRowOut) => envelope(p),
  ListPage_ChangeLogEntryOut_: (p: ListPageChangeLogEntryOut) => envelope(p), // K-01: KNW-01
  ListPage_CitationV2Out_: (p: ListPageCitationV2Out) => envelope(p),
  ListPage_ClientRelationshipOut_: (p: ListPageClientRelationshipOut) => envelope(p),
  ListPage_ClientRowOut_: (p: ListPageClientRowOut) => envelope(p),
  ListPage_ConsentOut_: (p: ListPageConsentOut) => envelope(p), // T-01: ADM-05
  ListPage_DecisionCardItemOut_: (p: ListPageDecisionCardItemOut) => envelope(p),
  ListPage_EnvelopeListRow_: (p: ListPageEnvelopeListRow) => envelope(p), // N-02: SIG-01
  ListPage_HumanGateOut_: (p: ListPageHumanGateOut) => envelope(p),
  ListPage_InboxThreadRow_: (p: ListPageInboxThreadRow) => envelope(p), // N-01: INB-01
  ListPage_IntakeUploadOut_: (p: ListPageIntakeUploadOut) => envelope(p), // N-01: POR-03
  ListPage_IssueItemOut_: (p: ListPageIssueItemOut) => envelope(p),
  ListPage_K1PackageOut_: (p: ListPageK1PackageOut) => envelope(p), // T-02: TXP-12
  ListPage_KnowledgeItemOut_: (p: ListPageKnowledgeItemOut) => envelope(p), // K-01: KNW-01
  ListPage_MappingSetSummaryOut_: (p: ListPageMappingSetSummaryOut) => envelope(p), // A-03: AUD-31
  ListPage_PortalEnvelopeRow_: (p: ListPagePortalEnvelopeRow) => envelope(p), // N-02: POR-06
  ListPage_ReferenceSetOut_: (p: ListPageReferenceSetOut) => envelope(p), // K-02: KNW-04
  ListPage_ReferenceSetVersionOut_: (p: ListPageReferenceSetVersionOut) => envelope(p), // K-02: KNW-04
  ListPage_ReportTemplateOut_: (p: ListPageReportTemplateOut) => envelope(p), // P-11: C11 templates
  ListPage_ReviewNoteItemOut_: (p: ListPageReviewNoteItemOut) => envelope(p),
  ListPage_ReviewQueueItemOut_: (p: ListPageReviewQueueItemOut) => envelope(p), // K-01: KNW-01
  ListPage_SampleItemOut_: (p: ListPageSampleItemOut) => envelope(p), // A-03: AUD-11
  ListPage_SampleSetSummaryOut_: (p: ListPageSampleSetSummaryOut) => envelope(p), // A-03: AUD-11
  ListPage_StandardOut_: (p: ListPageStandardOut) => envelope(p), // K-02: KNW-04
  ListPage_TaxReturnRowOut_: (p: ListPageTaxReturnRowOut) => envelope(p), // T-02: TAX-01
  ListPage_WallEventOut_: (p: ListPageWallEventOut) => envelope(p), // G-01-T02
  ListPage_WorkItemRowOut_: (p: ListPageWorkItemRowOut) => envelope(p),
} as const;

describe("P-36 list envelope (T1)", () => {
  it("covers every list page the schema has, and each keeps the envelope's fields", () => {
    const pages = Object.keys(SPEC.components.schemas).filter((k) => k.startsWith("ListPage_"));
    expect(pages.sort()).toEqual(Object.keys(LIST_PAGES).sort());
    for (const name of pages) {
      const schema = SPEC.components.schemas[name];
      expect(schema?.required ?? [], name).toEqual(expect.arrayContaining(["items", "total"]));
      expect(Object.keys(schema?.properties ?? {}), name).toEqual(
        expect.arrayContaining(["items", "next_cursor", "total", "counts", "facets"]),
      );
    }
  });

  it("a binder page becomes T1's envelope: counts per code, facets as {value, label, n}", () => {
    const page: ListPageBinderRowOut = {
      items: [],
      next_cursor: null,
      total: 0,
      counts: { draft: 0, published: 0 },
      facets: { season: [{ value: "2025", label: "TY2025", n: 0 }] },
    };
    expect(validateSchema("ListPage_BinderRowOut_", page)).toEqual([]);
    const env = LIST_PAGES.ListPage_BinderRowOut_(page);
    expect(env).toEqual({
      items: [],
      next_cursor: null,
      total: 0,
      counts: { draft: 0, published: 0 },
      facets: { season: [{ value: "2025", label: "TY2025", n: 0 }] },
    });
    // A page without cursor or counts still makes an envelope (a first page, no tiles).
    expect(envelope({ items: [], total: 0 })).toEqual({
      items: [],
      next_cursor: null,
      total: 0,
      counts: {},
    });
  });
});

// ---- C2: the status registry (status.ts, StatusPill, the T1 tiles) -------------------------------

describe("C2 status registry", () => {
  it("has words for every literal of the enums the templates draw", () => {
    const covered = [
      true satisfies EnumCovered<"binder", BinderStatus>,
      true satisfies EnumCovered<"request", RequestStatus>,
      true satisfies EnumCovered<"engagement", EngagementStatus>,
      true satisfies EnumCovered<"client", ClientStatus>,
      true satisfies EnumCovered<"citation", CitationV2Out["state"]>,
      true satisfies EnumCovered<"viewer", ViewerManifestOut["status"]>,
      true satisfies EnumCovered<"evidence_unlock", EvidenceUnlockOut["status"]>,
    ];
    expect(covered.every(Boolean)).toBe(true);
  });

  it("every code reads as a word, and none is the match purple", () => {
    for (const [object, codes] of Object.entries(STATUS_REGISTRY)) {
      for (const [code, entry] of Object.entries(
        codes as Record<string, { label: string; variant: string | null }>,
      )) {
        expect(entry.label.trim(), `${object}.${code}`).not.toBe("");
        expect(entry.variant, `${object}.${code}`).not.toBe("match");
      }
    }
    expect(registryWord("viewer", "password_protected").label).not.toBe("password_protected");
  });
});

// ---- C4: citations, viewer manifest, regions (E1, E2, C-07, E5) ----------------------------------

/** The kinds C4 derives match ids for are the locator kinds E1 knows, both ways. */
const kindsMatch: Equal<CitationV2Out["kind"], LocatorKind> = true;

/** A C4 citation as the C-07 marker and popover draw it; the match id is the server's (INV-2). */
function citationView(c: CitationV2Out): CitationView {
  return {
    n: c.n,
    title: c.title,
    quote: c.quote ?? "",
    loc: c.loc,
    match: c.match_id === null ? null : contractMatchId({ kind: c.kind, match_id: c.match_id }),
  };
}

/** A region lights with its citation's match id, at page-point rects (C4 §3.4). */
function regionMatch(r: ViewerRegionOut): MatchId {
  return contractMatchId(r);
}

/** What the E5 shell reads off the manifest: page sizes, mask boxes and their tokens. */
interface ShellPage {
  n: number;
  width_pt: number;
  height_pt: number;
  rotation: 0 | 90 | 180 | 270;
}
type Rect = readonly [number, number, number, number];
const pagesFit: ShellPage[] = [] as ViewerManifestOut["pages"];
const maskRect: Rect = [0, 0, 0, 0] satisfies PiiMaskOut["rect"];
const regionRect: Rect = [0, 0, 0, 0] satisfies ViewerRegionOut["rects"][number];

const CITATION: CitationV2Out = {
  id: "0b3b1f59-7a5a-4b0e-9a8e-2f6c1b9d4e01",
  n: 1,
  kind: "document_text",
  title: "Harborline certified trust report",
  loc: "Page 1",
  quote: "Net trust assets",
  quote_state: "shown",
  value_text: null,
  match_id: "ev:7c1e2f0a-1d9b-4c3e-8f2a-5b6d7e8f9a01#p1",
  state: "valid",
  verified: true,
  verification_reason: null,
  created_by: { kind: "agent", label: "Hannah Leclerc via Agent" },
  retrieved_at: null,
  source: {
    type: "evidence",
    id: "7c1e2f0a-1d9b-4c3e-8f2a-5b6d7e8f9a01",
    version: "1",
    evidence_version_id: "7c1e2f0a-1d9b-4c3e-8f2a-5b6d7e8f9a01",
    page: 1,
  },
  used_in: 1,
  moved: null,
  allowed_actions: [],
};

describe("C4 citations and the viewer", () => {
  it("a citation maps to the C-07 view with the server's match id", () => {
    expect(kindsMatch).toBe(true);
    expect(validateSchema("CitationV2Out", CITATION)).toEqual([]);
    const view = citationView(CITATION);
    expect(view.match).toBe(CITATION.match_id);
    expect(view.loc).toBe("Page 1");
    expect(citationView({ ...CITATION, match_id: null, quote: null })).toMatchObject({
      match: null,
      quote: "",
    });
  });

  it("a region carries the same match id and page-point rects", () => {
    const regions: ViewerRegionsOut = {
      items: [
        {
          match_id: CITATION.match_id ?? "",
          page: 1,
          rects: [[72, 144, 300, 160]],
          citation_id: CITATION.id,
          label: null,
          sheet: null,
          cell: null,
        },
      ],
    };
    expect(validateSchema("ViewerRegionsOut", regions)).toEqual([]);
    const [region] = regions.items;
    expect(region === undefined ? null : regionMatch(region)).toBe(CITATION.match_id);
  });

  it("the manifest gives the shell page sizes and mask tokens, never text", () => {
    expect([pagesFit, maskRect, regionRect]).toHaveLength(3);
    const manifest: ViewerManifestOut = {
      evidence_version_id: "7c1e2f0a-1d9b-4c3e-8f2a-5b6d7e8f9a01",
      file_name: "Harborline trust report.pdf",
      media_type: "application/pdf",
      status: "ready",
      reason: null,
      kind: "pages",
      page_count: 1,
      truncated: false,
      pages: [
        {
          n: 1,
          width_pt: 612,
          height_pt: 792,
          rotation: 0,
          image_w: 1240,
          image_h: 1605,
          text_layer: true,
          pii_scan: "done",
        },
      ],
      pii_masks: [],
      derivation_id: null,
      allowed_actions: [],
    };
    expect(validateSchema("ViewerManifestOut", manifest)).toEqual([]);
    const props = Object.keys(SPEC.components.schemas.ViewerManifestOut?.properties ?? {});
    expect(props).not.toContain("text");
    expect(props).not.toContain("words");
  });
});

// ---- C5: /v1/me.portal (T7 PortalLayout, PortalToolbar) -------------------------------------------

type PortalShell = MePortalOut["shell"];
type PortalNavCode = MePortalOut["nav"][number];

/** The T7 variant for each portal shell; `none` has no portal. A new shell fails here. */
const SHELL_VARIANT = {
  full: "split",
  k1: "reduced",
  limited: "reduced",
  none: null,
} as const satisfies Record<PortalShell, PortalVariant | null>;

/** Each nav code's area in PortalLayout's bar. A new code fails here until it has an area. */
const NAV_LABEL = {
  home: "Home",
  documents: "Documents",
  questions: "Questions",
  approvals: "Approvals",
  sign: "Sign",
  messages: "Messages",
  deliverables: "Deliverables",
} as const satisfies Record<PortalNavCode, string>;

describe("C5 portal shell and nav (T7)", () => {
  it("every shell has a variant and every nav code an area PortalLayout draws", () => {
    expect(Object.keys(SHELL_VARIANT).sort()).toEqual(["full", "k1", "limited", "none"].sort());
    const areas = PORTAL_AREAS.map((a) => a.label);
    for (const label of Object.values(NAV_LABEL)) expect(areas).toContain(label);
    expect(areas.length).toBe(Object.keys(NAV_LABEL).length);
  });

  it("a portal block validates and draws a bar of known areas with scope labels in words", () => {
    const portal: MePortalOut = {
      shell: "full",
      landing: "home",
      nav: ["home", "documents", "sign", "messages"],
      scopes: [
        {
          id: "3f0e9a4c-1b2d-4e5f-8a9b-0c1d2e3f4a5b",
          kind: "client",
          label: "Jonah & Claire Feld",
          role_label: "Client",
        },
      ],
    };
    expect(validateSchema("MePortalOut", portal)).toEqual([]);
    expect(SHELL_VARIANT[portal.shell]).toBe("split");
    expect(portal.nav.map((code) => NAV_LABEL[code])).toEqual([
      "Home",
      "Documents",
      "Sign",
      "Messages",
    ]);
    for (const scope of portal.scopes) expect(scope.label.trim()).not.toBe("");
  });
});
