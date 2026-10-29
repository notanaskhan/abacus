// INB-02's triage bundles (N-01-T15; docs/screens/INB-02.md; handoff INB-02 spec), one per
// artboard, on C5's `MessageTriageOut` shape, at E0 (Mon Sep 14, 2026, 9:25 AM CT). Names, files,
// paths and confidences are the handoff's; file names the INB-02 spec leaves out come from the
// TPL-08 board (the boards win). Dev and test only.
import type {
  AttachmentFlagOut,
  AttachmentTriageOut,
  ClassificationOut,
  DestinationCandidate,
  InboxAttachmentOut,
  MessageTriageOut,
  TriageDefaults,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type Inb02State = "a" | "a2" | "b" | "c" | "d" | "e" | "f" | "g";

export interface TriageMessage {
  subject: string;
  sender: string;
  bundle: MessageTriageOut;
}

const CLASSIFIED_AT = "2026-09-14T14:12:00Z"; // 9:12 AM CT

function hexOf(head: string, tail: string, seed: string): string {
  const body = Array.from(seed.padEnd(56, seed), (c) => (c.charCodeAt(0) % 16).toString(16))
    .join("")
    .slice(0, 56);
  return `${head}${body}${tail}`;
}

function attachment(name: string, kb: number, head: string, tail: string): InboxAttachmentOut {
  return {
    id: stableId(`inbox-attachment:triage:${name}`),
    file_name: name,
    media_type: name.endsWith(".xlsx")
      ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      : "application/pdf",
    size_bytes: kb * 1024,
    fingerprint: `sha256:${hexOf(head, tail, name)}`,
    status: "waiting",
    flags: [],
    filed: null,
    ignored_reason: null,
    held_at: null,
    thumbnail_ref: null,
    allowed_actions: ["inbox.triage", "inbox.file", "inbox.read_content"],
  };
}

function classification(
  form: string | null,
  year: number | null,
  issuer: string | null,
  pages: number | null,
  last4: string | null,
  matches: boolean | null,
): ClassificationOut {
  return {
    form_family: form,
    form_code: form,
    tax_year: year,
    issuer_name: issuer,
    page_count: pages,
    taxpayer_tin: last4 === null ? null : { kind: "ssn", last4, presence: "on_file" },
    taxpayer_matches_client: matches,
    proposed_by_kind: "rule",
    citation_ids: [],
  };
}

function candidate(
  path: string[],
  confidence: number,
  kind: DestinationCandidate["kind"] = "request",
  state: string | null = "open",
  requestedOn: string | null = null,
): DestinationCandidate {
  return {
    kind,
    id: stableId(`destination:${path.join(">")}`),
    path,
    confidence,
    source: "rule",
    request_state: state,
    requested_on: requestedOn,
    proposal_id: null,
  };
}

function flag(
  kind: AttachmentFlagOut["kind"],
  severity: AttachmentFlagOut["severity"],
  facts: AttachmentFlagOut["facts"] = {},
): AttachmentFlagOut {
  return { kind, severity, ref_evidence_version_id: null, facts };
}

function defaults(over: Partial<TriageDefaults> = {}): TriageDefaults {
  return {
    decision: "file",
    decision_forced: false,
    reason_codes: [],
    rename_to: null,
    version_mode: "new_document",
    tell_client: false,
    template_key: null,
    ...over,
  };
}

function card(
  a: InboxAttachmentOut,
  c: ClassificationOut | null,
  candidates: DestinationCandidate[],
  flags: AttachmentFlagOut[],
  d: TriageDefaults,
  supersede: string | null = null,
): AttachmentTriageOut {
  return {
    attachment: { ...a, flags },
    classification: c,
    candidates,
    supersede_candidate_version_id: supersede,
    defaults: d,
  };
}

function bundle(key: string, cards: AttachmentTriageOut[]): MessageTriageOut {
  return {
    message_id: stableId(`inbound-message:triage:${key}`),
    attachments: cards,
    seen_proposals: [],
    classified_at: CLASSIFIED_AT,
    notify_names: ["Kevin Osei"],
  };
}

const FELD = "Jonah & Claire Feld";

function feld(): TriageMessage {
  return {
    subject: "Re: 2025 tax documents",
    sender: "Claire Feld",
    bundle: bundle("feld", [
      card(
        attachment("Feld_1095C_2025.pdf", 412, "7c41", "e09a"),
        classification("1095-C", 2025, "Mercer Hill Health", 2, "2208", true),
        [
          candidate(
            [
              FELD,
              "TY2025 Form 1040 · 2025 Binder",
              "Health & Medical › Form 1095-C From Mercer Hill Health",
            ],
            0.96,
            "request",
            "open",
            "2026-02-03",
          ),
        ],
        [],
        defaults({ rename_to: "Claire_Feld_2025_1095C_MercerHill.pdf" }),
      ),
      card(
        attachment("Feld_1095C_2024.pdf", 398, "a19d", "5b72"),
        classification("1095-C", 2024, "Mercer Hill Health", 2, "2208", true),
        [candidate([FELD, "TY2024 Form 1040 · Source documents"], 1, "request", "on_file")],
        [
          flag("wrong_year", "block_bulk", { tax_year: 2024, open_year: 2025 }),
          flag("duplicate_hash", "block_bulk", {
            file_name: "Claire_Feld_2024_1095C_MercerHill.pdf",
            received_on: "2025-03-03",
          }),
        ],
        defaults({ decision: "ignore", reason_codes: ["wrong_year", "duplicate"] }),
      ),
    ]),
  };
}

const TRIAGE: Readonly<Record<Inb02State, () => TriageMessage>> = {
  a: feld,
  a2: feld,
  f: feld,
  b: () => ({
    subject: "Receipts for August Amex charges",
    sender: "Ben Ashby",
    bundle: bundle("copper", [
      card(
        attachment("Amex_Receipt_RoastersGuild.pdf", 96, "3e10", "c2d4"),
        classification("Receipt", null, null, 1, null, null),
        [
          candidate(
            [
              "Copperleaf Coffee Roasters, Inc.",
              "August 2026 Close",
              "Receipts",
              "Amex ••1009 · Aug 19 · 486.00",
            ],
            0.61,
            "close_receipt",
            null,
          ),
          candidate(
            [
              "Copperleaf Coffee Roasters, Inc.",
              "August 2026 Close",
              "Receipts",
              "Amex ••1009 · Aug 12 · 486.00",
            ],
            0.58,
            "close_receipt",
            null,
          ),
        ],
        [flag("ambiguous_candidates", "block_bulk", { candidates: 2 })],
        defaults(),
      ),
    ]),
  }),
  c: () => ({
    subject: "Avery’s corrected W-2",
    sender: "Wren Collins",
    bundle: bundle("collins", [
      card(
        attachment("Avery_W2_Front.pdf", 212, "5f02", "a811"),
        classification("W-2c", 2025, null, 1, "7713", false),
        [candidate(["Wren Collins", "TY2025 Form 1040 · 2025 Binder", "Income › W-2s"], 0.92)],
        [flag("tin_mismatch", "force_hold", { form_last4: "7713", record_last4: "7731" })],
        defaults({
          decision: "hold",
          decision_forced: true,
          tell_client: true,
          template_key: "hold_tin_mismatch",
        }),
      ),
    ]),
  }),
  d: () => ({
    subject: "Re: IRS letter — the 1099s you asked for",
    sender: "Harold Stein",
    bundle: bundle("stein", [
      ...["Stein_1099B_2024_Corrected.pdf", "Stein_1099DIV_2024.pdf"].map((name, i) =>
        card(
          attachment(name, i === 0 ? 264 : 188, "b7c3", "1e5f"),
          classification(i === 0 ? "1099-B" : "1099-DIV", 2024, null, 2, null, null),
          [
            candidate(
              ["Harold Stein", "Notices · IRS CP2000 · TY2024 (N2)", "Supporting documents"],
              0.93,
              "notice",
              null,
            ),
          ],
          [],
          defaults(),
        ),
      ),
      card(
        attachment("Stein_CP2000_2024_copy.pdf", 412, "d0a6", "77b2"),
        classification("CP2000", 2024, null, 4, null, null),
        [
          candidate(
            ["Harold Stein", "Notices · IRS CP2000 · TY2024 (N2)"],
            1,
            "notice",
            "on_file",
          ),
        ],
        [flag("duplicate_of_notice", "block_bulk")],
        defaults({ decision: "ignore", reason_codes: ["duplicate"] }),
      ),
    ]),
  }),
  e: () => ({
    subject: "Census corrections for the 401(k) audit",
    sender: "Dana Kowalski",
    bundle: bundle("north", [
      card(
        attachment("Census_Corrections_2025.xlsx", 88, "64e1", "0b93"),
        classification(null, 2025, null, null, null, null),
        [
          candidate(
            [
              "Northwind Robotics 401(k) Plan",
              "PY2025 EBP Audit",
              "Census & Payroll",
              "Full participant census for the audit year",
            ],
            0.94,
            "request",
            "received",
            "2026-08-28",
          ),
        ],
        [flag("possible_replacement", "info", { received_on: "2026-08-28" })],
        defaults({ version_mode: "new_version" }),
        stableId("evidence-version:northwind-census-v1"),
      ),
    ]),
  }),
  g: () => ({
    subject: "NY notice and 1099s",
    sender: "Priyanka Iyer",
    bundle: bundle("iyer", [
      card(
        attachment("Iyer_2025_1099DIV_Halvard_Corrected.pdf", 176, "9a21", "f4c0"),
        classification("1099-DIV", 2025, "Halvard Securities", 2, "5530", true),
        [
          candidate(
            [
              "Priyanka & Sam Iyer",
              "TY2025 Form 1040 · 2025 Binder",
              "Income › 1099-DIV From Halvard Securities",
            ],
            0.97,
            "request",
            "received",
          ),
        ],
        [
          flag("possible_replacement", "info", {
            file_name: "Iyer_2025_1099DIV_Halvard.pdf",
            channel: "portal upload",
            received_on: "2026-03-02",
          }),
        ],
        defaults({ version_mode: "new_version_supersede" }),
        stableId("evidence-version:iyer-1099div-v1"),
      ),
    ]),
  }),
};

export function triageOf(state: Inb02State): TriageMessage {
  return TRIAGE[state]();
}
