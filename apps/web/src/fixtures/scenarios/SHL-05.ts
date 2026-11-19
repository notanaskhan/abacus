// SHL-05 Support panel: one fixture scenario per artboard (G-04-T19; handoff SHL-05 a-f and d'),
// Grace Holloway (Firm Admin) on Mon Sep 14, 2026. Every word is the handoff's: Ines's thread, the
// Feld 2025 Form 1040 session request (awaiting, then granted by Felix Andersen until 11:41 AM), the
// six help-article titles under the four group bands, the seven status rows with CCH Axcess Tax
// export at "Needs attention", and the offline chip and email line. Help article bodies are
// platform content (G-04-T20 database rows); the in-drawer article (d') carries only the facts the
// thread states. Dev and test only.
import type {
  ConversationOut,
  FirmStatusOut,
  HelpArticleOut,
  HelpArticlesOut,
  SessionCardOut,
} from "@abacus/api-client";
import { type Scenario, defineScenarios, json } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { stableId } from "../seed/prng";

const E0 = seedScenario();
export const SHL05_INSTANT = "2026-09-14T09:24:00-05:00";
export const CCH_ARTICLE = "exporting-a-return-to-cch-axcess";

const msg = (
  n: number,
  staff: boolean,
  at: string,
  body: string,
  article: string | null = null,
) => ({
  id: stableId(`shl05:message:${String(n)}`),
  author_kind: staff ? ("staff" as const) : ("firm_user" as const),
  author_display_name: staff ? "Ines" : "Grace Holloway",
  body,
  created_at: at,
  related_article_slug: article,
});

const THREAD = [
  msg(
    1,
    false,
    "2026-09-14T09:18:00-05:00",
    "Our CCH Axcess exports are taking a long time this morning. Ridgeline's 1065 is due tomorrow.",
  ),
  msg(
    2,
    true,
    "2026-09-14T09:19:00-05:00",
    "Thanks, Grace. CCH Axcess is accepting exports with delays of up to 15 minutes since 8:40 AM CT. Exports queue and finish on their own; nothing is lost. Ridgeline's return shows 'Not yet exported', so it isn't affected yet.",
    CCH_ARTICLE,
  ),
  msg(3, false, "2026-09-14T09:20:00-05:00", "Can you check Kevin's export from Friday too?"),
  msg(
    4,
    true,
    "2026-09-14T09:21:00-05:00",
    "I can, with a support session. I've sent a request to grant access to one return (Feld 2025 Form 1040) for 2 hours. Felix Andersen or you can approve it in Firm settings › Security.",
  ),
];

function card(granted: boolean): SessionCardOut {
  return {
    session_id: stableId("shl05:session:feld"),
    scope_label: "2025 Form 1040 · Jonah & Claire Feld",
    duration_minutes: 120,
    status: granted ? "active" : "requested",
    can_decide: true,
    decided_by_display_name: granted ? "Felix Andersen" : null,
    expires_at: granted ? "2026-09-14T11:41:00-05:00" : null,
  };
}

function conversation(state: "a" | "b" | "c" | "f"): ConversationOut {
  const online = state !== "b";
  return {
    id: state === "f" ? null : stableId("shl05:conversation"),
    availability: {
      online,
      replies_in_minutes: online ? 4 : null,
      next_open_at: online ? null : "2026-09-15T08:00:00-05:00",
      reply_email: online ? null : "grace.holloway@brightwaterhale.com",
    },
    messages: state === "f" ? [] : THREAD,
    session_cards: state === "f" ? [] : [card(state === "c")],
    suggestions: state === "f" ? ["Ask about a sync", "Report a problem with an agent run"] : [],
  };
}

const art = (slug: string, title: string, group_key: string) => ({
  slug,
  title,
  group_key,
  summary: "",
  read_minutes: 4,
});

function articles(): HelpArticlesOut {
  return {
    query: null,
    groups: [
      {
        key: "suggested",
        label: "Suggested for this page",
        articles: [
          art(
            "reading-the-tax-returns-status-tiles",
            "Reading the Tax Returns status tiles",
            "suggested",
          ),
          art(
            "what-draft-k1-pre-release-blocks",
            "What 'Draft K-1 · pre-release' blocks",
            "suggested",
          ),
        ],
      },
      {
        key: "tax_returns",
        label: "Tax returns",
        articles: [
          art(
            CCH_ARTICLE,
            "Exporting a return to CCH Axcess: statuses and retries",
            "tax_returns",
          ),
        ],
      },
      {
        key: "agents_approvals",
        label: "Agents & approvals",
        articles: [
          art(
            "approving-agent-proposals-and-checkpoints",
            "Approving agent proposals and checkpoints",
            "agents_approvals",
          ),
          art(
            "within-threshold-batch-approvals",
            "Within-threshold batch approvals and BH AJE thresholds v2",
            "agents_approvals",
          ),
        ],
      },
      {
        key: "client_portal",
        label: "Client portal",
        articles: [
          art(
            "inviting-a-spouse-or-delegate",
            "Inviting a client's spouse or delegate",
            "client_portal",
          ),
          art(
            "sending-form-8879-for-e-signature",
            "Sending Form 8879 for e-signature",
            "client_portal",
          ),
        ],
      },
    ],
  };
}

function article(): HelpArticleOut {
  return {
    slug: CCH_ARTICLE,
    title: "Exporting a return to CCH Axcess: statuses and retries",
    read_minutes: 4,
    version: 1,
    published_at: "2026-09-01T09:00:00-05:00",
    blocks: [
      { kind: "paragraph", text: "Exports queue and finish on their own; nothing is lost." },
    ],
  };
}

function status(): FirmStatusOut {
  const ok = (key: string, label: string, kind: "core" | "integration" = "core") => ({
    key,
    label,
    kind,
    state: "operational" as const,
    note: null,
  });
  return {
    region_label: "US",
    history_url: "#incident-history", // the deployment's status page (VITE_STATUS_PAGE_URL) in production
    components: [
      ok("app", "Accrued app"),
      ok("agents", "Agents & Workbench"),
      ok("portal", "Client portal"),
      ok("esign", "E-signature & identity verification"),
      {
        key: "cch_axcess_export",
        label: "CCH Axcess Tax export",
        kind: "integration",
        state: "needs_attention",
        note: "Delays up to 15 min since 8:40 AM CT",
      },
      ok("qbo_sync", "QuickBooks Online sync", "integration"),
      ok("m365_mail", "Microsoft 365 mail ingest", "integration"),
    ],
  };
}

export const SHL05_STATES = ["a", "b", "c", "d", "d2", "e", "f"] as const;
export type Shl05State = (typeof SHL05_STATES)[number];

function at(state: Shl05State): Scenario {
  const chat = state === "b" || state === "c" || state === "f" ? state : "a";
  return {
    state,
    persona: "grace-holloway",
    clock: SHL05_INSTANT,
    get handlers() {
      return {
        ...E0.handlers,
        "GET /v1/support/conversation": () => json(conversation(chat)),
        "GET /v1/help/articles": () => json(articles()),
        "GET /v1/help/articles/{slug}": () => json(article()),
        "GET /v1/status": () => json(status()),
      };
    },
  };
}

export const scenarios = defineScenarios({
  a: at("a"),
  b: at("b"),
  c: at("c"),
  d: at("d"),
  d2: at("d2"),
  e: at("e"),
  f: at("f"),
});

/** The tab (and article) each artboard opens on. */
export const OPENING: Record<Shl05State, { tab: "chat" | "help" | "status"; article?: string }> = {
  a: { tab: "chat" },
  b: { tab: "chat" },
  c: { tab: "chat" },
  d: { tab: "help" },
  d2: { tab: "help", article: CCH_ARTICLE },
  e: { tab: "status" },
  f: { tab: "chat" },
};
