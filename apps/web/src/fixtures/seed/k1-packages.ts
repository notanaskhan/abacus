// TXP-12's K-1 packages on fixtures (T-02-T25; T-02 §3.6, docs/screens/TXP-12.md): the Ridgeline
// 2025 Form 1065 set (five recipients), the Bluestem 1120-S (two shareholders) and the Calloway
// 1041 (two beneficiaries), as `GET /v1/tax-returns/{id}/k1-packages` answers them, by artboard.
// Names, notes, periods, states, dates and box figures are the handoff's (spec.md, README.md);
// TINs are last four only and live on the package detail, never a row (ADR-031). Every amount is
// a decimal string as the server sends it; the browser never adds them up (ADR-050).
import type {
  K1BoxLineOut,
  K1DocumentOut,
  K1HandoffOut,
  K1MaskedTinOut,
  K1PackageOut,
  K1PackageStatus,
  K1ReleaseCheckOut,
} from "@abacus/api-client";
import { stableId } from "./prng";
import { TAX_RETURNS } from "./tax";

function returnOf(client: string): string {
  const row = TAX_RETURNS.find((r) => r.client === client && !r.label.endsWith(":2"));
  if (row === undefined) throw new Error(`no TY2025 return for ${client}`);
  return row.id;
}

export const RIDGELINE_RETURN = returnOf("Ridgeline Property Partners, LP");
export const BLUESTEM_RETURN = returnOf("Bluestem Analytics, LLC");
export const CALLOWAY_RETURN = returnOf("Calloway Family Trust");
/** F: a 1065 with no K-1 set imported yet. */
export const EMPTY_RETURN = returnOf("Harborview Dental Properties, LP");
export const FELD_RETURN = returnOf("Jonah & Claire Feld");
export const SHAH_RETURN = returnOf("Meera Shah");

/** The "Deliverable ready" version the release confirm names (POR-20's template, T-02-T21). */
export const DELIVERABLE_READY_VERSION = stableId("email-template:deliverable_ready:v1");

/** TXP-12's artboards as data conditions. */
export type K1Variant = "drafts" | "approved" | "released" | "amended";

const SHARED_SEP_10 = "2026-09-10T15:12:00Z";
const RELEASED = "2026-09-15T15:30:00Z";

interface Recipient {
  ref: string;
  name: string;
  kind: K1PackageOut["recipient_kind"];
  note?: string;
  locality?: string;
  contact: string;
  tin: K1MaskedTinOut;
  period?: readonly [string, string];
  /** Its own 1040 in the firm, a share target (DEC-88). */
  related?: { id: string; client: string; status: string };
  /** The released-state status (B). */
  after: K1PackageStatus;
}

const RIDGELINE: readonly Recipient[] = [
  {
    ref: "ridgeline-gp",
    name: "Ridgeline GP LLC",
    kind: "gp",
    note: "Owen Calder, managing member",
    contact: "Owen Calder",
    tin: { kind: "ein", last4: "3318" },
    after: "released",
  },
  {
    ref: "meera-shah",
    name: "Meera Shah",
    kind: "lp",
    locality: "Chicago, IL",
    contact: "Meera Shah",
    tin: { kind: "ssn", last4: "2290" },
    related: { id: SHAH_RETURN, client: "Meera Shah", status: "preparing" },
    after: "viewed",
  },
  {
    ref: "pell-street-ventures",
    name: "Pell Street Ventures LLC",
    kind: "lp",
    note: "35% → 30% at 6/30",
    contact: "authorized member",
    tin: { kind: "ein", last4: "7741" },
    after: "downloaded",
  },
  {
    ref: "pell-street-ii",
    name: "Pell Street II LLC",
    kind: "lp",
    note: "admitted 7/1/2025",
    contact: "authorized member",
    tin: { kind: "ein", last4: "5106" },
    period: ["2025-07-01", "2025-12-31"],
    after: "bounced",
  },
  {
    ref: "jonah-feld",
    name: "Jonah Feld",
    kind: "lp",
    locality: "Brooklyn, NY",
    contact: "Jonah Feld",
    tin: { kind: "ssn", last4: "4417" },
    related: { id: FELD_RETURN, client: "Jonah & Claire Feld", status: "in_review" },
    after: "viewed",
  },
];

const BLUESTEM: readonly Recipient[] = [
  {
    ref: "arjun-mehta",
    name: "Arjun Mehta",
    kind: "shareholder",
    note: "70%",
    contact: "Arjun Mehta",
    tin: { kind: "ssn", last4: "6120" },
    after: "downloaded",
  },
  {
    ref: "sunita-rao",
    name: "Sunita Rao",
    kind: "shareholder",
    note: "30%",
    contact: "Sunita Rao",
    tin: { kind: "ssn", last4: "8834" },
    after: "downloaded",
  },
];

const CALLOWAY: readonly Recipient[] = [
  {
    ref: "nora-calloway",
    name: "Nora Calloway",
    kind: "beneficiary",
    contact: "Nora Calloway",
    tin: { kind: "ssn", last4: "5512" },
    after: "draft",
  },
  {
    ref: "theo-calloway",
    name: "Theo Calloway",
    kind: "beneficiary",
    contact: "Theo Calloway",
    tin: { kind: "ssn", last4: "7034" },
    after: "draft",
  },
];

function packageId(ret: string, ref: string, version = 1): string {
  return stableId(`k1-package:${ret}:${ref}:v${String(version)}`);
}

function documents(
  ret: string,
  ref: string,
  states: readonly string[],
  k3: boolean,
  draft: boolean,
  version = 1,
): K1DocumentOut[] {
  const doc = (kind: K1DocumentOut["kind"], jurisdiction: string | null): K1DocumentOut => ({
    id: stableId(`k1-doc:${ret}:${ref}:v${String(version)}:${kind}:${jurisdiction ?? ""}`),
    kind,
    jurisdiction,
    evidence_version_id: stableId(
      `k1-ev:${ret}:${ref}:v${String(version)}:${kind}:${jurisdiction ?? ""}`,
    ),
    is_draft: draft,
  });
  return [
    doc("k1", null),
    ...(k3 ? [doc("k3", null)] : []),
    ...states.map((s) => doc("state_k1", s)),
    doc("letter", null),
  ];
}

interface ReturnSet {
  id: string;
  form: K1PackageOut["form"];
  recipients: readonly Recipient[];
  states: readonly string[];
  k3: K1PackageOut["k3_status"];
}

const SETS: readonly ReturnSet[] = [
  {
    id: RIDGELINE_RETURN,
    form: "1065",
    recipients: RIDGELINE,
    states: ["IL", "CO", "NY"],
    k3: "included",
  },
  { id: BLUESTEM_RETURN, form: "1120s", recipients: BLUESTEM, states: ["NY"], k3: "not_required" },
  { id: CALLOWAY_RETURN, form: "1041", recipients: CALLOWAY, states: [], k3: "not_included" },
];

function handoffs(r: Recipient, released: boolean): K1HandoffOut[] {
  if (r.related === undefined) return [];
  return [
    {
      target_return_id: r.related.id,
      target_name: r.related.client,
      target_form: "1040",
      status: released ? "final_replaced" : "draft_shared",
      shared_at: SHARED_SEP_10,
      replaced_at: released ? RELEASED : null,
    },
  ];
}

function rowOf(set: ReturnSet, r: Recipient, variant: K1Variant): K1PackageOut {
  // Bluestem's are released and downloaded on the season's record; Calloway's stay drafts.
  const released =
    set.id === BLUESTEM_RETURN ||
    (set.id === RIDGELINE_RETURN && (variant === "released" || variant === "amended"));
  const status: K1PackageStatus = released ? r.after : "draft";
  const final = released || variant === "approved";
  return {
    id: packageId(set.id, r.ref),
    recipient_id: stableId(`k1-recipient:${set.id}:${r.ref}`),
    recipient_name: r.name,
    recipient_kind: r.kind,
    form: set.form,
    tax_year: 2025,
    status,
    k3_status: set.k3,
    state_codes: [...set.states],
    released_at: released ? RELEASED : null,
    version_no: 1,
    allowed_actions: released
      ? ["k1_package.resend", "k1_package.share_internal", "k1_recipient.review_details"]
      : ["k1_package.share_internal", "k1_recipient.review_details"],
    documents: documents(set.id, r.ref, set.states, set.k3 === "included", !final),
    period_start: r.period?.[0] ?? null,
    period_end: r.period?.[1] ?? null,
    ownership_note: r.note ?? null,
    locality: r.locality ?? null,
    delivery_contact_name: r.contact,
    supersedes_package_id: null,
    handoffs: handoffs(r, released),
    details_change: null,
    related_returns:
      r.related === undefined
        ? []
        : [
            {
              return_id: r.related.id,
              client_name: r.related.client,
              form: "1040",
              status: r.related.status,
            },
          ],
  };
}

/** E (Mon Oct 5): the amended Feld K-1 replaces the Sep 15 package, which stays struck through. */
function amended(set: ReturnSet, r: Recipient): K1PackageOut[] {
  const old = rowOf(set, r, "released");
  const next: K1PackageOut = {
    ...old,
    id: packageId(set.id, r.ref, 2),
    status: "draft",
    released_at: null,
    version_no: 2,
    allowed_actions: ["k1_package.share_internal", "k1_recipient.review_details"],
    documents: documents(set.id, r.ref, set.states, true, false, 2),
    supersedes_package_id: old.id,
    handoffs: [],
  };
  return [next, { ...old, status: "superseded", allowed_actions: [] }];
}

/** The rows `GET …/k1-packages` answers for a return under a variant (newest version first). */
export function k1Rows(returnId: string, variant: K1Variant): K1PackageOut[] {
  const set = SETS.find((s) => s.id === returnId);
  if (set === undefined) return [];
  return set.recipients.flatMap((r) =>
    variant === "amended" && set.id === RIDGELINE_RETURN && r.ref === "jonah-feld"
      ? amended(set, r)
      : [rowOf(set, r, variant)],
  );
}

/** The tiles: counts by status, as the server counts them. */
export function k1Counts(rows: readonly K1PackageOut[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const r of rows) out[r.status] = (out[r.status] ?? 0) + 1;
  return out;
}

/** The release check by variant: before Daniel Reyes's final approval, and after it (A5). */
export function k1Check(returnId: string, variant: K1Variant): K1ReleaseCheckOut {
  const rows = k1Rows(returnId, variant);
  const ready = rows.filter((r) => r.status === "draft").map((r) => r.id);
  const approved = variant === "approved" || returnId === BLUESTEM_RETURN;
  const failing = [
    ...(approved ? [] : ["not_final_approved"]),
    ...(rows.length === 0 ? ["no_packages"] : []),
    ...(approved || rows.length === 0 ? [] : ["final_k1s_missing"]),
    ...(rows.length > 0 && ready.length === 0 ? ["nothing_to_release"] : []),
  ];
  return {
    eligible: failing.length === 0,
    failing,
    package_ids: failing.length === 0 ? ready : [],
    email_template_version_id: DELIVERABLE_READY_VERSION,
  };
}

/** A package's masked TIN (the detail's only, ADR-031). */
export function k1Tin(packageId_: string): K1MaskedTinOut | null {
  for (const set of SETS) {
    for (const r of set.recipients) {
      for (const v of [1, 2]) {
        if (packageId(set.id, r.ref, v) === packageId_) return r.tin;
      }
    }
  }
  return null;
}

const line = (
  document_kind: K1BoxLineOut["document_kind"],
  box_code: string,
  description: string,
  amount: string,
): K1BoxLineOut => ({ document_kind, box_code, description, amount, is_total: false });

/** A2: Jonah Feld's boxes and state lines as drafted (TXP-05 and TXP-09 agree). */
const JONAH: readonly K1BoxLineOut[] = [
  line("k1", "2", "Net rental real estate income", "307900"),
  line("k1", "5", "Interest income", "4600"),
  line("k1", "18A", "Tax-exempt interest income", "1550"),
  line("k1", "19A", "Distributions", "150000"),
  line("k1", "20A", "Investment income", "4600"),
  line("k1", "K", "Item K", "2762075"),
  line("k1", "L", "Item L ending", "1912500"),
  line("state_k1", "IL", "IL nonresident share", "141634"),
  line("state_k1", "IL-PTET", "PTET credit", "7011"),
  line("state_k1", "CO", "CO", "4268"),
  line("state_k1", "NY", "NY (IT-653 PTET credit)", "4746"),
];

const BLUESTEM_LINES: Readonly<Record<string, readonly string[]>> = {
  "arjun-mehta": ["602000", "8680", "2940", "434000"],
  "sunita-rao": ["258000", "3720", "1260", "186000"],
};

const CALLOWAY_LINES: Readonly<Record<string, readonly string[]>> = {
  "nora-calloway": ["40000", "120000", "96000"],
  "theo-calloway": ["20000", "60000", "48000"],
};

/** A package's box lines (the detail; readers of the return's content only). */
export function k1Lines(pkg: K1PackageOut): K1BoxLineOut[] {
  const ref = SETS.flatMap((s) => s.recipients).find((r) => r.name === pkg.recipient_name)?.ref;
  if (ref === "jonah-feld") return [...JONAH];
  const b = ref === undefined ? undefined : BLUESTEM_LINES[ref];
  if (b !== undefined) {
    const [income = "0", interest = "0", nondeductible = "0", distributions = "0"] = b;
    return [
      line("k1", "1", "Ordinary business income", income),
      line("k1", "4", "Interest income", interest),
      line("k1", "16C", "Nondeductible expenses", nondeductible),
      line("k1", "16D", "Distributions", distributions),
    ];
  }
  const c = ref === undefined ? undefined : CALLOWAY_LINES[ref];
  if (c !== undefined) {
    const [interest = "0", ordinary = "0", qualified = "0"] = c;
    return [
      line("k1", "1", "Interest income", interest),
      line("k1", "2a", "Ordinary dividends", ordinary),
      line("k1", "2b", "Qualified dividends", qualified),
    ];
  }
  return [];
}
