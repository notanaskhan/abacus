// POR-13's K-1s on fixtures (T-02-T27; T-02 §3.7; docs/screens/POR-13.md): what
// `GET /v1/portal/k1s`, `/k1s/expected` and `/k1s/{id}` answer each recipient by artboard. Nora
// Calloway's 2025 K-1 (released Sep 29; amended Oct 5), Pell Street Ventures LLC's Ridgeline K-1
// (expected at E0, released Sep 15) and Meera Shah's Ridgeline K-1 inside her full portal (DV-11).
// Figures are the handoff's (§9.4: 40,000 + 120,000 = 160,000; 2b 96,000 inside 2a; Pell Street
// 400,270 / 5,980 / 2,015 / 180,000) as decimal strings; the browser never adds them up.
// A row carries no amounts and no TIN; the detail carries the recipient's own TIN masked.
import type {
  K1BoxLineOut,
  K1DocumentOut,
  K1PackageDetailOut,
  K1PackageOut,
  MeOut,
  PortalK1ExpectedOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type Por13Variant =
  "nora_released" | "pell_expected" | "pell_released" | "nora_amended" | "meera_expected";

const CALLOWAY = "Calloway Family Trust";
const RIDGELINE = "Ridgeline Property Partners, LP";

function docs(key: string, kinds: readonly (readonly [K1DocumentOut["kind"], string | null])[]) {
  return kinds.map(([kind, jurisdiction]): K1DocumentOut => ({
    id: stableId(`portal-k1-doc:${key}:${kind}:${jurisdiction ?? ""}`),
    kind,
    jurisdiction,
    evidence_version_id: stableId(`portal-k1-ev:${key}:${kind}:${jurisdiction ?? ""}`),
    is_draft: false,
  }));
}

function pkg(
  key: string,
  over: Partial<K1PackageOut> & Pick<K1PackageOut, "recipient_name" | "form">,
): K1PackageOut {
  return {
    id: stableId(`portal-k1:${key}`),
    recipient_id: stableId(`portal-k1-recipient:${over.recipient_name}`),
    recipient_kind: over.form === "1041" ? "beneficiary" : "lp",
    tax_year: 2025,
    status: "released",
    k3_status: "not_included",
    state_codes: [],
    released_at: null,
    version_no: 1,
    allowed_actions: ["download", "update_details"],
    documents: [],
    ...over,
  };
}

const NORA = pkg("nora-v1", {
  recipient_name: "Nora Calloway",
  form: "1041",
  issuer_name: CALLOWAY,
  state_codes: ["IL"],
  released_at: "2026-09-29T17:00:00Z",
  documents: docs("nora-v1", [
    ["k1", null],
    ["state_k1", "IL"],
    ["letter", null],
  ]),
});

const NORA_AMENDED = pkg("nora-v2", {
  recipient_name: "Nora Calloway",
  form: "1041",
  issuer_name: CALLOWAY,
  state_codes: ["IL"],
  released_at: "2026-10-05T14:10:00Z",
  version_no: 2,
  supersedes_package_id: NORA.id,
  documents: docs("nora-v2", [
    ["k1", null],
    ["state_k1", "IL"],
    ["letter", null],
  ]),
});

const PELL = pkg("pell-street-ventures", {
  recipient_name: "Pell Street Ventures LLC",
  form: "1065",
  issuer_name: RIDGELINE,
  k3_status: "included",
  state_codes: ["IL", "CO", "NY"],
  released_at: "2026-09-15T15:30:00Z",
  documents: docs("pell-street-ventures", [
    ["k1", null],
    ["k3", null],
    ["state_k1", "IL"],
    ["state_k1", "CO"],
    ["state_k1", "NY"],
    ["letter", null],
  ]),
});

const line = (
  box_code: string,
  description: string,
  amount: string,
  is_total = false,
): K1BoxLineOut => ({ document_kind: "k1", box_code, description, amount, is_total });

const NORA_LINES: readonly K1BoxLineOut[] = [
  line("1", "Interest income", "40000"),
  line("2a", "Ordinary dividends", "120000"),
  line("2b", "Qualified dividends (included in 2a)", "96000"),
  line("1+2a", "Total of boxes 1 and 2a", "160000", true),
];

const PELL_LINES: readonly K1BoxLineOut[] = [
  line("2", "Net rental real estate income", "400270"),
  line("5", "Interest income", "5980"),
  line("18A", "Tax-exempt interest income", "2015"),
  line("19A", "Distributions", "180000"),
];

const RIDGELINE_EXPECTED: PortalK1ExpectedOut = {
  issuer_name: RIDGELINE,
  form: "1065",
  tax_year: 2025,
  k3_status: "included",
  expected_on: "2026-09-15",
};

/** `GET /v1/portal/k1s` by artboard: released and later only. */
export function portalK1Rows(variant: Por13Variant): K1PackageOut[] {
  switch (variant) {
    case "nora_released":
      return [NORA];
    case "nora_amended":
      return [NORA_AMENDED, { ...NORA, status: "superseded", allowed_actions: ["download"] }];
    case "pell_released":
      return [PELL];
    case "pell_expected":
    case "meera_expected":
      return [];
  }
}

/** `GET /v1/portal/k1s/expected`: not released yet, no amounts and no id. */
export function portalK1Expected(variant: Por13Variant): PortalK1ExpectedOut[] {
  return variant === "pell_expected" || variant === "meera_expected" ? [RIDGELINE_EXPECTED] : [];
}

/** `GET /v1/portal/k1s/{id}`: the statement, the final documents and the person's own details. */
export function portalK1Detail(variant: Por13Variant, id: string): K1PackageDetailOut | undefined {
  const row = portalK1Rows(variant).find((r) => r.id === id);
  if (row === undefined) return undefined;
  const pell = row.recipient_name === "Pell Street Ventures LLC";
  return {
    package: row,
    lines: [...(pell ? PELL_LINES : NORA_LINES)],
    documents: row.documents ?? [],
    tin: pell
      ? { kind: "ein", presence: "on_file", last4: "7741" }
      : { kind: "ssn", presence: "on_file", last4: "5512" },
    address_on_file: true,
  };
}

/** The two K-1-only people of T-02 §1 (no invented name for the Pell Street member). */
export const K1_PERSONAS: Readonly<Record<string, { name: string; scope: string }>> = {
  "nora-calloway": { name: "Nora Calloway", scope: CALLOWAY },
  "pell-street-member": {
    name: "Pell Street Ventures LLC · authorized member",
    scope: RIDGELINE,
  },
};

/** `GET /v1/me` for a K-1-only person: the reduced `k1` shell (DEC-129). */
export function k1Me(base: MeOut, slug: string): MeOut {
  const persona = K1_PERSONAS[slug];
  if (persona === undefined) return base;
  return {
    ...base,
    user_id: stableId(`user:${slug}`),
    display_name: persona.name,
    portal: {
      shell: "k1",
      scopes: [
        {
          kind: "k1_package",
          id: stableId(`scope:k1:${slug}`),
          label: persona.scope,
          role_label: "K-1 recipient",
        },
      ],
      nav: [],
      landing: "k1s",
    },
  };
}
