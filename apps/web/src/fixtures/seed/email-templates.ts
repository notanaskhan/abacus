// POR-20's seed (R-01-T22, R-01-T25): Brightwater Hale's six email templates as the server holds
// them after the T22 import, the sample recipients of each artboard and the follow-up policy.
// Template words are POR-20's "Seeded template content", verbatim, written with the key's
// whitelisted variables exactly as the backend slice (`brightwater_hale/email_templates.py`)
// imports them; this file is the TypeScript seed's copy of those database rows, never product
// copy. Sample values are the artboards' (Claire Feld's two open items, Sam Ortiz's 9 items, …).
//
// `renderEmail` and `lintTemplate` stand in for the server in fixture mode only: the same block
// layout as `communications/render.py` (every value escaped, one button) and the lint's code
// rules, so a draft edited in a fixture shows findings and keeps Publish disabled.

import type {
  EmailTemplateDraftOut,
  EmailTemplateOut,
  EmailTemplateRowOut,
  EmailTemplateVersionOut,
  FollowUpPolicyOut,
  LintFindingOut,
  TemplateBlock,
  TemplatePersonOut,
  TemplateVariableOut,
} from "@abacus/api-client";
import { DEMO_INSTANT, daysBefore } from "./clock";
import { stableId } from "./prng";

export const GRACE: TemplatePersonOut = {
  user_id: stableId("user:grace-holloway"),
  display_name: "Grace Holloway",
};
export const GRACE_EMAIL = "grace.holloway@brightwaterhale.com";
export const FROM_DISPLAY = "Brightwater Hale";
export const FROM_ADDRESS = "clients@brightwaterhale.com";
const FOOTER =
  "You're receiving this because you're a client of {firm_name}. We never include account " +
  "numbers or tax amounts in email.";

type Kind = TemplateBlock["kind"];
type CtaTarget = NonNullable<EmailTemplateVersionOut["cta_target"]>;
export type TemplateAction = NonNullable<EmailTemplateOut["allowed_actions"]>[number];

export interface TemplateContentSeed {
  subject: string;
  preheader: string;
  blocks: TemplateBlock[];
  cta_label: string;
  cta_target: CtaTarget;
}

function blocks(rows: readonly (readonly [string, Kind, string])[]): TemplateBlock[] {
  return rows.map(([id, kind, text]) => ({ id, kind, text }));
}

export interface SampleRecipient {
  /** The sample contact's id (`sample_contact_id`). */
  id: string;
  name: string;
  /** The Send test sheet's second line ("Reminder · 2 open items for her 2025 tax return"). */
  line: string;
  email: string;
  values: Record<string, string>;
}

export interface TemplateSeed {
  key: string;
  name: string;
  usedByLabel: string;
  usedByScreen: string | null;
  audience: EmailTemplateRowOut["audience"];
  variables: string[];
  published: number;
  content: TemplateContentSeed;
  sample: SampleRecipient;
}

const GENERAL = [
  "client_first_name",
  "firm_name",
  "work_item",
  "open_items",
  "due_date",
  "portal_link",
  "staff_name",
];

export const PREVIEW_LINK = "https://brightwater-hale.example-portal.test/portal";

const contact = (slug: string): string => stableId(`contact:${slug}`);

export const TEMPLATES: readonly TemplateSeed[] = [
  {
    key: "invitation",
    name: "Invitation",
    usedByLabel: "CLI-04 invites, prospect intake",
    usedByScreen: "CLI-04",
    audience: ["client", "third_party"],
    variables: [
      "client_first_name",
      "firm_name",
      "inviter_name",
      "organisation_name",
      "scope_summary",
      "portal_link",
    ],
    published: 3,
    content: {
      subject: "{firm_name} invited you to upload documents",
      preheader: "",
      blocks: blocks([
        ["headline", "heading", "You've been asked for {scope_summary}"],
        [
          "intro",
          "paragraph",
          "Hi {client_first_name}, Brightwater Hale LLP is auditing the Northwind Robotics 401(k) " +
            "Plan and has asked {organisation_name} for {scope_summary}. Sign in to upload them " +
            "securely.",
        ],
        ["questions", "note", "Questions? Message {inviter_name} in your request room."],
        [
          "footer",
          "footer",
          "You're receiving this because {firm_name} asked {organisation_name} for documents. We " +
            "never include account numbers or tax amounts in email. This link expires in 14 days.",
        ],
      ]),
      cta_label: "Open requests",
      cta_target: "portal_home",
    },
    sample: {
      id: contact("sam-ortiz"),
      name: "Sam Ortiz",
      line: "Invitation · Keystone Retirement Services",
      email: "sam.ortiz@keystoneretirement.com",
      values: {
        client_first_name: "Sam",
        firm_name: "Brightwater Hale",
        inviter_name: "Marcus Delaney",
        organisation_name: "Keystone Retirement Services",
        scope_summary: "9 items",
        portal_link: PREVIEW_LINK,
      },
    },
  },
  {
    key: "reminder",
    name: "Reminder",
    usedByLabel: "Binders, close requests, PBC",
    usedByScreen: null,
    audience: ["client", "third_party"],
    variables: GENERAL,
    published: 3,
    content: {
      subject: "2 items still needed for your {work_item}",
      preheader: "",
      blocks: blocks([
        ["headline", "heading", "We still need 2 items"],
        [
          "intro",
          "paragraph",
          "Hi {client_first_name}, we're working on your {work_item}. To keep it on track, please " +
            "upload:",
        ],
        ["items", "item_list", "{open_items}"],
        ["drop", "paragraph", "Drop the files in your portal and they'll be sorted for you."],
        ["questions", "note", "Questions? Message {staff_name} in your portal."],
        ["footer", "footer", FOOTER],
      ]),
      cta_label: "Open your portal",
      cta_target: "documents",
    },
    sample: {
      id: contact("claire-feld"),
      name: "Claire Feld",
      line: "Reminder · 2 open items for her 2025 tax return",
      email: "claire.feld@gmail.com",
      values: {
        client_first_name: "Claire",
        firm_name: "Brightwater Hale",
        work_item: "2025 tax return",
        open_items:
          "Form 1095-C From Mercer Hill Health\n2025 federal (1040-ES) and New York (IT-2105) " +
          "estimated payment confirmations",
        due_date: "September 24, 2026",
        portal_link: PREVIEW_LINK,
        staff_name: "Kevin Osei",
      },
    },
  },
  {
    key: "signature_request",
    name: "Signature request",
    usedByLabel: "SIG-02 envelopes",
    usedByScreen: "SIG-01",
    audience: ["client"],
    variables: ["client_first_name", "firm_name", "document_title", "due_date", "portal_link"],
    published: 2,
    content: {
      subject: "Please sign: {document_title}",
      preheader: "",
      blocks: blocks([
        ["headline", "heading", "Ready for your signature"],
        [
          "intro",
          "paragraph",
          "Hi {client_first_name}, please review and sign your {document_title}.",
        ],
        ["due", "paragraph", "Due {due_date}."],
        ["questions", "note", "Questions? Message Daniel Reyes in your portal."],
        ["footer", "footer", FOOTER],
      ]),
      cta_label: "Review and sign",
      cta_target: "sign",
    },
    sample: {
      id: contact("owen-calder"),
      name: "Owen Calder",
      line: "Signature request · Ridgeline Property Partners, LP",
      email: "owen.calder@ridgelinepp.com",
      values: {
        client_first_name: "Owen",
        firm_name: "Brightwater Hale",
        document_title: "engagement letter — cost segregation and section 754 analysis",
        due_date: "September 24, 2026",
        portal_link: PREVIEW_LINK,
      },
    },
  },
  {
    key: "deliverable_ready",
    name: "Deliverable ready",
    usedByLabel: "Returns, K-1s, statements, reports",
    usedByScreen: "TXP-12",
    audience: ["client"],
    variables: ["client_first_name", "firm_name", "deliverable_title", "portal_link"],
    published: 2,
    content: {
      subject: "Your {deliverable_title} is ready",
      preheader: "",
      blocks: blocks([
        ["headline", "heading", "Ready to view"],
        [
          "intro",
          "paragraph",
          "Hi {client_first_name}, your {deliverable_title} is in your portal. Sign in to view or " +
            "download it.",
        ],
        ["questions", "note", "Questions? Message Olivia Brandt in your portal."],
        ["footer", "footer", FOOTER],
      ]),
      cta_label: "View your K-1",
      cta_target: "deliverables",
    },
    sample: {
      id: contact("meera-shah"),
      name: "Meera Shah",
      line: "Deliverable ready · Ridgeline K-1 recipient",
      email: "meera.shah@shahadvisory.com",
      values: {
        client_first_name: "Meera",
        firm_name: "Brightwater Hale",
        deliverable_title: "2025 K-1 from Ridgeline Property Partners, LP",
        portal_link: PREVIEW_LINK,
      },
    },
  },
  {
    key: "confirmation_request",
    name: "Confirmation request",
    usedByLabel: "AUD-14 · single-use link, no portal",
    usedByScreen: "AUD-14",
    audience: ["respondent"],
    variables: ["respondent_org", "firm_name", "organisation_name", "due_date", "portal_link"],
    published: 1,
    content: {
      subject: "Confirmation request — balance at June 30, 2026 (reference C2)",
      preheader: "",
      blocks: blocks([
        ["headline", "heading", "Please confirm a balance"],
        [
          "intro",
          "paragraph",
          "Hi Rachel, as auditors of {organisation_name}, we're asking {respondent_org} to " +
            "confirm the balance it owed Granite Peak at June 30, 2026. Please respond directly " +
            "to us using the secure link.",
        ],
        [
          "genuine",
          "note",
          "This link works once and expires on {due_date}. To check it's genuine, call " +
            "Brightwater Hale using the number on our website.",
        ],
        [
          "footer",
          "footer",
          "You're receiving this because {organisation_name} authorized us to confirm a balance " +
            "with you. We never include account numbers or tax amounts in email.",
        ],
      ]),
      cta_label: "Respond securely",
      cta_target: "confirm",
    },
    sample: {
      id: contact("summit-trail-outfitters"),
      name: "Summit Trail Outfitters",
      line: "Confirmation request · Rachel Imholt, accounts payable",
      email: "r.imholt@example.com",
      values: {
        respondent_org: "Summit Trail Outfitters",
        firm_name: "Brightwater Hale",
        organisation_name: "Granite Peak Outdoor Supply, Inc.",
        due_date: "October 9, 2026",
        portal_link: PREVIEW_LINK,
      },
    },
  },
  {
    key: "reconnect_request",
    name: "Reconnect request",
    usedByLabel: "CLS-11 · expired connections",
    usedByScreen: "CLS-11",
    audience: ["client"],
    variables: ["client_first_name", "firm_name", "portal_link", "connection_name"],
    published: 1,
    content: {
      subject: "Please reconnect {connection_name} for your monthly close",
      preheader: "",
      blocks: blocks([
        ["headline", "heading", "Reconnect {connection_name}"],
        [
          "intro",
          "paragraph",
          "Hi {client_first_name}, {connection_name} asks you to sign in again every 90 days, so " +
            "new card transactions aren't reaching us for your August 2026 close. Reconnecting in " +
            "your portal restarts the feed.",
        ],
        ["questions", "note", "Questions? Message Raj Malhotra in your portal."],
        ["footer", "footer", FOOTER],
      ]),
      cta_label: "Reconnect",
      cta_target: "connections",
    },
    sample: {
      id: contact("tess-moreno"),
      name: "Tess Moreno",
      line: "Reconnect request · Copperleaf Coffee Roasters, Inc.",
      email: "tess@copperleafcoffee.com",
      values: {
        client_first_name: "Tess",
        firm_name: "Brightwater Hale",
        portal_link: PREVIEW_LINK,
        connection_name: "American Express",
      },
    },
  },
];

export function templateSeed(key: string): TemplateSeed | undefined {
  return TEMPLATES.find((t) => t.key === key);
}

/** Every template's sample recipient, as the Send test sheet lists them (POR-20 j). */
export const SAMPLE_RECIPIENTS: readonly SampleRecipient[] = TEMPLATES.map((t) => t.sample);

const VARIABLE_KIND: Record<string, TemplateVariableOut["kind"]> = {
  client_first_name: "person_name",
  firm_name: "organisation_name",
  work_item: "title",
  open_items: "item_list",
  due_date: "date",
  portal_link: "secure_link",
  staff_name: "person_name",
  inviter_name: "person_name",
  organisation_name: "organisation_name",
  scope_summary: "summary",
  document_title: "title",
  deliverable_title: "title",
  respondent_org: "organisation_name",
  connection_name: "title",
};
const PUBLIC = new Set(["firm_name"]);
const INTERNAL = new Set(["due_date", "staff_name"]);

export function variableOut(name: string): TemplateVariableOut {
  return {
    name,
    kind: VARIABLE_KIND[name] ?? "title",
    classification: PUBLIC.has(name) ? "public" : INTERNAL.has(name) ? "internal" : "confidential",
    block: name === "open_items",
  };
}

// ---- The server's renderer and lint, for fixture mode ----------------------------------------

const PLACEHOLDER = /\{([a-z][a-z0-9_]{0,39})\}/g;

function escape(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#x27;");
}

function fill(text: string, values: Record<string, string>): string {
  return text.replace(PLACEHOLDER, (whole, name: string) => values[name] ?? whole);
}

export interface Rendered {
  subject: string;
  html: string;
  text: string;
}

/** As `render.py`: blocks in order, the one button before the first note or footer. */
export function renderEmail(
  content: TemplateContentSeed | EmailTemplateDraftOut | EmailTemplateVersionOut,
  values: Record<string, string>,
  width: 600 | 390,
): Rendered {
  const link = values.portal_link ?? PREVIEW_LINK;
  const label = content.cta_label === null ? null : fill(content.cta_label, values);
  const html: string[] = [];
  const text: string[] = [];
  let placed = label === null;
  const button = (): void => {
    if (label === null) return;
    const size =
      width === 390 ? "display:block;width:100%;box-sizing:border-box" : "display:inline-block";
    html.push(
      `<p style="margin:8px 0 24px 0"><a href="${escape(link)}" style="${size};padding:12px 20px;` +
        `border:1px solid;border-radius:6px;text-align:center;text-decoration:none;font-weight:500">` +
        `${escape(label)}</a></p>`,
    );
    text.push(`${label}: ${link}`);
    placed = true;
  };
  for (const block of content.blocks) {
    if (!placed && (block.kind === "note" || block.kind === "footer")) button();
    const filled = fill(block.text, values);
    if (block.kind === "item_list") {
      const lines = filled.split("\n").filter((l) => l.trim() !== "");
      html.push(
        `<ul style="margin:0 0 16px 0;padding:0 0 0 20px">${lines
          .map((l) => `<li style="margin:0 0 6px 0">${escape(l.trim())}</li>`)
          .join("")}</ul>`,
      );
      text.push(lines.map((l) => `- ${l.trim()}`).join("\n"));
      continue;
    }
    const body = filled.split("\n").map(escape).join("<br>");
    const tag =
      block.kind === "heading"
        ? `<h1 style="margin:0 0 16px 0;font-size:20px;font-weight:500">${body}</h1>`
        : block.kind === "note"
          ? `<p style="margin:0 0 12px 0;font-size:13px">${body}</p>`
          : block.kind === "footer"
            ? `<p style="margin:16px 0 0 0;font-size:12px">${body}</p>`
            : `<p style="margin:0 0 16px 0;font-size:15px;line-height:22px">${body}</p>`;
    html.push(tag);
    text.push(filled);
  }
  if (!placed) button();
  const subject = fill(content.subject, values);
  const page =
    '<!doctype html><html><head><meta charset="utf-8">' +
    `<title>${escape(subject)}</title></head><body style="margin:0;padding:0">` +
    `<table role="presentation" width="100%"><tr><td align="center" style="padding:24px 16px">` +
    `<table role="presentation" width="${String(width)}" style="width:100%;max-width:${String(width)}px;` +
    `font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"><tr><td>${html.join("")}` +
    "</td></tr></table></td></tr></table></body></html>";
  return { subject, html: page, text: `${text.filter((t) => t !== "").join("\n\n")}\n` };
}

const RULES: readonly (readonly [LintFindingOut["code"], RegExp])[] = [
  ["tin_shape", /\b\d{3}[\s.-]?\d{2}[\s.-]?\d{4}\b/],
  ["account_number", /(?:••|\*{2,}|[xX]{2,}|#)\s?\d{4}\b|(?<!\d)\d{10,}(?!\d)/],
  ["amount", /[$€£]\s?\d|\b\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?\b/],
  ["platform_name", /accrued/i],
  ["foreign_link", /\b(?:https?:\/\/|www\.)|\{portal_link\}/i],
  ["attachment", /\b(?:attach(?:ed|es|ing|ment|ments)?|enclos(?:ed|ure|ures))\b/i],
  ["second_button", /\bclick (?:here|below|the button|the link)\b|\[[^\]\n]{1,60}\]/i],
  ["banned_word", /\b(?:agents?|tasks?|issues?|confidence|passwords?|materiality)\b|\bAI\b/],
];

/** The lint's code rules over a draft or version: identifier-only findings, as the server's. */
export function lintTemplate(
  content: TemplateContentSeed | EmailTemplateDraftOut | EmailTemplateVersionOut,
  variables: readonly string[],
): LintFindingOut[] {
  const parts: [string, string][] = [
    ["subject", content.subject],
    ["preheader", content.preheader],
    ...(content.cta_label === null ? [] : [["cta_label", content.cta_label] as [string, string]]),
    ...content.blocks.map((b): [string, string] => [b.id, b.text]),
  ];
  const found: LintFindingOut[] = [];
  for (const [where, text] of parts) {
    const names = [...text.matchAll(PLACEHOLDER)].map((m) => m[1] ?? "");
    if (names.some((n) => !variables.includes(n))) {
      found.push({ code: "unregistered_variable", block_id: where, variable: null });
    }
    const bare = text.replace(PLACEHOLDER, (t) => (t === "{portal_link}" ? t : " "));
    for (const [code, rule] of RULES) {
      if (rule.test(bare)) found.push({ code, block_id: where, variable: null });
    }
  }
  return found;
}

// ---- The rows the scenarios start from -----------------------------------------------------

export const PUBLISHED_AT = daysBefore(30);
export const DRAFT_SAVED_AT = "2026-09-14T14:12:00.000Z";
export const PUBLISHED_V4_AT = "2026-09-14T14:27:00.000Z";

export function versionOut(
  seed: TemplateSeed,
  version: number,
  publishedAt: string = PUBLISHED_AT,
): EmailTemplateVersionOut {
  return {
    version,
    subject: seed.content.subject,
    preheader: seed.content.preheader,
    blocks: seed.content.blocks,
    cta_label: seed.content.cta_label,
    cta_target: seed.content.cta_target,
    content_sha256: stableSha(`${seed.key}:v${String(version)}`),
    published_at: publishedAt,
    published_by: GRACE,
  };
}

export function draftOut(seed: TemplateSeed, expectedVersion = 1): EmailTemplateDraftOut {
  return {
    expected_version: expectedVersion,
    base_version: seed.published,
    subject: seed.content.subject,
    preheader: seed.content.preheader,
    blocks: seed.content.blocks,
    cta_label: seed.content.cta_label,
    cta_target: seed.content.cta_target,
    saved_at: DRAFT_SAVED_AT,
    saved_by: GRACE,
  };
}

function stableSha(text: string): string {
  const id = stableId(text).replaceAll("-", "");
  return (id + id).slice(0, 64);
}

export interface TemplateState {
  published: EmailTemplateVersionOut | null;
  draft: EmailTemplateDraftOut | null;
}

export function rowOut(seed: TemplateSeed, state: TemplateState): EmailTemplateRowOut {
  return {
    key: seed.key,
    name: seed.name,
    group: "designed",
    audience: seed.audience,
    used_by_label: seed.usedByLabel,
    used_by_screen: seed.usedByScreen,
    published:
      state.published === null
        ? null
        : {
            version: state.published.version,
            published_at: state.published.published_at,
            published_by: state.published.published_by ?? null,
          },
    draft:
      state.draft === null
        ? null
        : { version: (state.published?.version ?? 0) + 1, saved_at: state.draft.saved_at },
  };
}

export function templateOut(
  seed: TemplateSeed,
  state: TemplateState,
  actions: readonly TemplateAction[],
): EmailTemplateOut {
  return {
    key: seed.key,
    name: seed.name,
    audience: seed.audience,
    firm_editable: true,
    variables: seed.variables.map(variableOut),
    published: state.published,
    draft: state.draft,
    allowed_actions: state.draft === null ? actions.filter((a) => a !== "publish") : [...actions],
  };
}

/** Brightwater Hale's follow-up policy (DEC-74): every 7 days, at most 4, weekdays 9:00 AM. */
export const FOLLOW_UP_POLICY: FollowUpPolicyOut = {
  policy: {
    cadence_days: 7,
    max_reminders: 4,
    send_local_time: "09:00",
    weekdays_only: true,
    stop_on_binder_done: true,
    notify_preparer_after_max: true,
    cc_assigned_preparer: false,
    mode: "draft_for_person",
  },
  version: 1,
  next_send: {
    sample_contact_id: null,
    last_sent_at: "2026-09-14T14:00:00Z",
    next_send_at: "2026-09-21T14:00:00Z",
    shifted_from: null,
  },
};

export const SEED_CLOCK = DEMO_INSTANT;
