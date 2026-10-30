// SIG-02 · Envelope builder (N-02-T21): the handoff's words (spec.md, the SIG-02 screenshots) and
// docs/screens/SIG-02.md's copy keys. Check codes and identity methods are the server's
// identifiers; these are their words.
import type { IdentityMethod, PolicyFamily } from "../../domain/signatures";

type Role = "signer" | "countersigner" | "ero";

export const COPY = {
  documents: "Documents",
  checks: "Checks",
  pages: (n: number) => `${String(n)} ${n === 1 ? "page" : "pages"}`,
  readOnly: "read-only for signer",
  move: (title: string) => `Move ${title}`,
  moved: (title: string, at: number) => `${title} moved to position ${String(at)}`,
  preview: "Preview",
  placed: "Placed fields",
  // N-02-T30: placing fields for a signer (click on the page, or the next line from the toolbar).
  placeTitle: "Place fields",
  placeFor: "For",
  placeNext: "Place on next line",
  removeField: "Remove",
  field: {
    signature: "Sign here",
    date: "Date",
    pin: "PIN",
    initial: "Initial",
    title_prefill: "Title",
  },
  signers: "Signers",
  order: "Order",
  orders: { sequential: "Sequential", parallel: "Parallel" },
  identity: "Identity",
  role: "Role",
  identities: {
    kba: "Identity questions (KBA)",
    email_code: "Email + SMS code",
    in_person_id: "In-person ID check",
    firm_sso: "Firm SSO",
  } satisfies Record<IdentityMethod, string>,
  identityRefused: (family: PolicyFamily) =>
    family === "efile_authorization"
      ? "Not allowed for e-file authorizations"
      : "Not allowed by this signing policy",
  roles: { signer: "Signer", countersigner: "Countersigner", ero: "ERO" } satisfies Record<
    Role,
    string
  >,
  emailRequired: "Email required",
  noEmail: (name: string) => `${name} has no email on file.`,
  delivery: "Delivery",
  channel: "Channel",
  channelValue: "Portal + email notice",
  message: "Message",
  reminders: "Reminders",
  cadences: {
    daily_until_signed: "Daily until signed",
    every_3_days: "Every 3 days",
    weekly: "Weekly",
  } as Readonly<Record<string, string>>,
  expires: "Expires",
  dating: "Dating",
  fixedDate: "Date as of a fixed date",
  fixedHelp: "Use for representation letters (dated as of the report date)",
  retention: "Retention",
  checkWords: {
    amounts_match: "Amounts match the exported return",
    signer_gp_managing_member: "Signer is the managing member of the general partner",
    ero_efin: "ERO and EFIN populated",
    no_ssn_visible: "No SSNs visible in the signer packet",
    letter_partner_approved: "Letter approved by the engagement partner",
    signer_gp_managing_partner: "Signer is the managing partner of the general partner",
    countersign_after_client: "Countersignature follows the client",
    no_tin_visible: "No SSNs or EINs visible in the signer packet",
  } as Readonly<Record<string, string>>,
  saveDraft: "Save draft",
  saved: "Draft saved",
  sent: (names: string, number: string) => `Sent to ${names} · ${number}`,
  failed: "Couldn't save. Try again.",
  changed: "Someone changed this draft. Reopen it to see their version.",
  keep: {
    title: "Keep this draft?",
    body: "Your changes aren't saved yet.",
    discard: "Discard changes",
    save: "Save draft",
  },
  loading: "Loading the envelope",
  missing: "This envelope isn't available.",
} as const;

/** The footer's gate sentence, from the envelope's family and its work item. */
export function gateSentence(
  family: PolicyFamily,
  number: string,
  workItem: string | null | undefined,
): string | null {
  const form = (workItem ?? "").split(" · ")[0] ?? "";
  if (family === "efile_authorization" && form !== "")
    return `Gate: e-file of the ${form} is blocked until this envelope is Completed (TAX-12).`;
  if (family === "engagement_letter")
    return `Gate: work on ${number} starts when this envelope is Completed (ENG-04).`;
  return null;
}

/** Where the signed copy is filed (SIG-02 "Retention"). */
export function retentionLine(
  family: PolicyFamily,
  number: string,
  client: string,
  workItem: string | null | undefined,
): string {
  const form = (workItem ?? "").split(" · ")[0] ?? "";
  if (family === "efile_authorization")
    return `Signed copy → Files › ${form} › Signed authorizations · keep 7 years`;
  return `Signed copy → Files › ${client} › Engagements › ${number}`;
}
