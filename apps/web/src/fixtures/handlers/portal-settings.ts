// ADM-10 in fixture mode (R-01-T28; C16 v1.1; docs/contracts/portal-settings.md and
// email-templates.md §sending domains): Brightwater Hale's published portal settings, the draft,
// publish, the read-only preview as a contact or the sample client, and the sender domain, over
// the scenario's own copy. The next reminder comes from the same rule the server uses: the last
// send (Mon Sep 14, 9:00 AM) plus the cadence, a weekend moved to Monday (R-01-T24, DEC-563).

import type {
  ClientExperienceFields,
  FollowUpPolicyFields,
  NextSendOut,
  PortalBrandFields,
  PortalBrandOut,
  PortalHomeOut,
  PortalSettingsDraftIn,
  PortalSettingsDraftOut,
  PortalSettingsOut,
  PortalSettingsVersionOut,
  SendingDomainIn,
  SendingDomainOut,
} from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { FOLLOW_UP_POLICY, FROM_DISPLAY, GRACE } from "../seed/email-templates";
import { claireHome, tessHome } from "../seed/portal-home";
import { stableId } from "../seed/prng";

/** The neutral portal host and the neutral sender's domain (DEC-59, ADR-163): never "accrued". */
export const NEUTRAL_HOST = "brightwaterhale.example-portal.test";
export const NEUTRAL_SENDER = "brightwaterhale@example-mail.test";
export const DOMAIN = "brightwaterhale.com";
export const LAST_SENT_AT = "2026-09-14T14:00:00Z";

/** The people "Preview as" lists (the TS seed's personas; DEC-20: only visible contacts). */
export const PREVIEW_CONTACTS = [
  { id: stableId("contact:claire-feld"), name: "Claire Feld" },
  { id: stableId("contact:tess-moreno"), name: "Tess Moreno" },
  { id: stableId("contact:dana-kowalski"), name: "Dana Kowalski" },
  { id: stableId("contact:meera-shah"), name: "Meera Shah" },
] as const;
const CLAIRE = PREVIEW_CONTACTS[0].id;
const TESS = PREVIEW_CONTACTS[1].id;

const BRAND: PortalBrandOut = {
  portal_name: "Brightwater Hale",
  sender_display_name: FROM_DISPLAY,
  secured_footer: false,
  accent: "espresso",
  logo_url: null,
  portal_host: NEUTRAL_HOST,
};
const EXPERIENCE: ClientExperienceFields = {
  allow_upload_something_else: true,
  phone_capture: true,
  show_team_card: true,
  show_progress_per_item: true,
  support_contact_user_id: GRACE.user_id,
};

/** The published settings (version 3, Aug 2026) every scenario starts from. */
export const PUBLISHED: PortalSettingsVersionOut = {
  version: 3,
  brand: BRAND,
  client_experience: EXPERIENCE,
  follow_up_policy: FOLLOW_UP_POLICY.policy,
  content_sha256: "3".repeat(64),
  published_at: "2026-08-17T15:10:00Z",
  published_by: { user_id: GRACE.user_id, display_name: GRACE.display_name },
};

const DAY = 86_400_000;

/** The next reminder after Mon Sep 14, 9:00 AM for a cadence, Saturday or Sunday moved on. */
export function nextReminder(cadenceDays: number, last: string = LAST_SENT_AT): NextSendOut {
  const due = new Date(Date.parse(last) + cadenceDays * DAY);
  const weekday = due.getUTCDay();
  const shift = weekday === 6 ? 2 : weekday === 0 ? 1 : 0;
  const at = new Date(due.getTime() + shift * DAY);
  return {
    sample_contact_id: null,
    last_sent_at: last,
    next_send_at: at.toISOString().replace(".000Z", "Z"),
    shifted_from: shift === 0 ? null : due.toISOString().slice(0, 10),
  };
}

export function domainOut(status: "verified" | "pending_dns" | "failed"): SendingDomainOut {
  const record: "verified" | "pending" = status === "verified" ? "verified" : "pending";
  const tokens = ["k7c2", "p4w9", "x1m6"].map((t) => `${t}${"0".repeat(28)}`);
  return {
    id: stableId(`sending-domain:${DOMAIN}`),
    domain: DOMAIN,
    from_local_part: "clients",
    mail_from_domain: `bounce.${DOMAIN}`,
    status,
    records: [
      ...tokens.map((t) => ({
        type: "CNAME" as const,
        name: `${t}._domainkey.${DOMAIN}`,
        value: `${t}.dkim.amazonses.com`,
        status: record,
      })),
      {
        type: "MX" as const,
        name: `bounce.${DOMAIN}`,
        value: "10 feedback-smtp.us-east-2.amazonses.com",
        status: record,
      },
      {
        type: "TXT" as const,
        name: `bounce.${DOMAIN}`,
        value: "v=spf1 include:amazonses.com ~all",
        status: record,
      },
    ],
    failure_reason: status === "failed" ? "dkim_not_verified" : null,
    requested_at: "2026-08-12T15:02:00Z",
    verified_at: status === "verified" ? "2026-08-12T16:47:00Z" : null,
    last_checked_at: "2026-09-14T14:15:00Z",
  };
}

/** The sample client (DEC-379): POR-02's shape with nothing of a firm's clients in it. */
function sampleHome(): PortalHomeOut {
  return {
    scope: {
      kind: "client",
      id: stableId("scope:sample"),
      label: "Sample client",
      role_label: "Owner",
    },
    first_visit: false,
    welcome_dismissed: true,
    all_done: true,
  };
}

export interface PortalSettingsSetup {
  /** A saved draft's follow-up cadence (b), or none. */
  draftCadence?: number;
  domain?: "verified" | "pending_dns" | "failed" | "none";
  /** What the persona may do (a firm admin; a practice leader reads only). */
  actions?: readonly NonNullable<PortalSettingsOut["allowed_actions"]>[number][];
  /** The preview contact's last reminder (g: Tess, Fri Sep 11, 9:00 AM MT). */
  lastSentAt?: string;
  /** The instant a publish stamps. */
  now: string;
}

export function portalSettingsHandlers(
  setup: PortalSettingsSetup,
): Record<string, FixtureHandler> {
  let published: PortalSettingsVersionOut = PUBLISHED;
  let draft: PortalSettingsDraftOut | null =
    setup.draftCadence === undefined
      ? null
      : {
          base_version: PUBLISHED.version,
          expected_version: 1,
          brand: brandFields(PUBLISHED.brand),
          client_experience: EXPERIENCE,
          follow_up_policy: { ...PUBLISHED.follow_up_policy, cadence_days: setup.draftCadence },
          saved_at: "2026-09-14T14:23:00Z",
          saved_by: { user_id: GRACE.user_id, display_name: GRACE.display_name },
        };
  let domains: SendingDomainOut[] =
    setup.domain === undefined || setup.domain === "none" ? [] : [domainOut(setup.domain)];
  const actions = setup.actions ?? ["edit", "publish", "preview"];

  const policy = (): FollowUpPolicyFields => draft?.follow_up_policy ?? published.follow_up_policy;
  const cadence = (): number => policy().cadence_days ?? 7;
  const settings = (): PortalSettingsOut => ({
    published,
    draft,
    next_reminder: nextReminder(cadence(), setup.lastSentAt),
    allowed_actions: [...actions],
  });

  return {
    "GET /v1/firm/portal-settings": () => json(settings()),
    "PUT /v1/firm/portal-settings/draft": ({ body }) => {
      const given = body as PortalSettingsDraftIn;
      const expected = draft?.expected_version ?? 0;
      if (given.expected_version !== expected) return json({ detail: "stale_version" }, 409);
      draft = {
        base_version: published.version,
        expected_version: expected + 1,
        brand: given.brand,
        client_experience: given.client_experience,
        follow_up_policy: given.follow_up_policy,
        saved_at: setup.now,
        saved_by: { user_id: GRACE.user_id, display_name: GRACE.display_name },
      };
      return json(draft);
    },
    "DELETE /v1/firm/portal-settings/draft": () => {
      draft = null;
      return json(settings());
    },
    "POST /v1/firm/portal-settings/publish": () => {
      if (draft === null) return json({ detail: "stale_version" }, 409);
      published = {
        ...published,
        version: published.version + 1,
        brand: { ...published.brand, ...draft.brand },
        client_experience: draft.client_experience,
        follow_up_policy: draft.follow_up_policy,
        published_at: setup.now,
        published_by: { user_id: GRACE.user_id, display_name: GRACE.display_name },
      };
      draft = null;
      return json(published, 201);
    },
    "GET /v1/firm/portal-settings/preview": ({ query }) => {
      const as = query.get("as");
      const device = query.get("device") === "phone" ? "phone" : "desktop";
      const known = as === CLAIRE || as === TESS;
      if (as !== null && as !== "" && as !== "sample" && !known) {
        return json({ detail: "not_found" }, 404); // a contact the viewer can't see (DEC-20)
      }
      const home = as === CLAIRE ? claireHome(2) : as === TESS ? tessHome() : sampleHome();
      return json({
        brand: { ...published.brand, ...(draft === null ? {} : draft.brand) },
        contact_id: known ? as : null,
        device,
        home,
        read_only: true,
        sample: !known,
        source: draft === null ? "published" : "draft",
      });
    },
    "GET /v1/firm/sending-domains": () => json({ items: domains }),
    "POST /v1/firm/sending-domains": ({ body }) => {
      const given = body as SendingDomainIn;
      if (domains.some((d) => d.status === "pending_dns" || d.status === "verified")) {
        return json({ detail: "sending_domain_exists" }, 409);
      }
      const created = { ...domainOut("pending_dns"), domain: given.domain };
      domains = [created, ...domains];
      return json(created, 201);
    },
    "POST /v1/firm/sending-domains/{domain_id}/check": ({ params }) => {
      const found = domains.find((d) => d.id === params.domain_id);
      return found === undefined ? json({ detail: "not_found" }, 404) : json(found);
    },
    "DELETE /v1/firm/sending-domains/{domain_id}": ({ params }) => {
      const found = domains.find((d) => d.id === params.domain_id);
      if (found === undefined) return json({ detail: "not_found" }, 404);
      const revoked: SendingDomainOut = { ...found, status: "revoked" };
      domains = domains.map((d) => (d.id === found.id ? revoked : d));
      return json(revoked);
    },
  };
}

function brandFields(brand: PortalBrandOut): PortalBrandFields {
  return {
    portal_name: brand.portal_name,
    sender_display_name: brand.sender_display_name,
    secured_footer: brand.secured_footer ?? false,
  };
}
