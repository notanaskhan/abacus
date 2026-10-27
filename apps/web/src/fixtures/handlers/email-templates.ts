// POR-20 in fixture mode (R-01-T25; C16 v1.1): the firm's email templates, their drafts and
// versions, the preview, test send and publish, and the follow-up policy, over the scenario's own
// copy of the seed. The preview and the lint stand in for the server's (`seed/email-templates.ts`):
// a test send or publish of a draft with a finding answers 422 `template_lint_failed`, and a test
// send goes only to the acting admin ("[Test]" before the subject).

import type {
  EmailPreviewIn,
  EmailTemplateDraftIn,
  EmailTestSendIn,
  LintFindingOut,
} from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  FOLLOW_UP_POLICY,
  FROM_ADDRESS,
  FROM_DISPLAY,
  GRACE,
  GRACE_EMAIL,
  PREVIEW_LINK,
  TEMPLATES,
  type TemplateAction,
  type TemplateSeed,
  type TemplateState,
  draftOut,
  lintTemplate,
  renderEmail,
  rowOut,
  templateOut,
  templateSeed,
  versionOut,
} from "../seed/email-templates";
import { stableId } from "../seed/prng";

export interface EmailTemplatesSetup {
  /** Per key: the published version number (0: none) and whether a draft is saved. */
  states?: Readonly<Record<string, { published: number; draft: boolean; publishedAt?: string }>>;
  /** What the persona may do (POR-20: a firm admin; a practice leader reads only). */
  actions?: readonly TemplateAction[];
  /** The instant a publish stamps. */
  now: string;
}

const NEUTRAL: Record<string, string> = {
  client_first_name: "Sample",
  firm_name: FROM_DISPLAY,
  work_item: "sample engagement",
  open_items: "First sample document\nSecond sample document",
  due_date: "the due date",
  portal_link: PREVIEW_LINK,
  staff_name: GRACE.display_name,
  inviter_name: GRACE.display_name,
  organisation_name: "Sample Client",
  scope_summary: "a few documents",
  document_title: "sample document",
  deliverable_title: "sample deliverable",
  respondent_org: "Sample Respondent",
  connection_name: "sample connection",
};

function valuesFor(
  seed: TemplateSeed,
  contactId: string | null | undefined,
): Record<string, string> {
  const base = contactId === seed.sample.id ? seed.sample.values : NEUTRAL;
  return Object.fromEntries(seed.variables.map((v) => [v, base[v] ?? NEUTRAL[v] ?? ""]));
}

function lintFailed(findings: LintFindingOut[]): Response {
  const facts: Record<string, string | number> = { count: findings.length };
  findings.slice(0, 20).forEach((f, n) => {
    facts[`finding_${String(n)}`] = `${f.code}:${f.block_id ?? f.variable ?? ""}`;
  });
  return json({ detail: "template_lint_failed", facts }, 422);
}

export function emailTemplateHandlers(setup: EmailTemplatesSetup): Record<string, FixtureHandler> {
  const actions: readonly TemplateAction[] = setup.actions ?? ["edit", "test_send", "publish"];
  const states = new Map<string, TemplateState>(
    TEMPLATES.map((seed) => {
      const given = setup.states?.[seed.key] ?? { published: seed.published, draft: false };
      return [
        seed.key,
        {
          published:
            given.published === 0 ? null : versionOut(seed, given.published, given.publishedAt),
          draft: given.draft ? draftOut(seed) : null,
        },
      ];
    }),
  );
  const seedOf = (key: string | undefined): TemplateSeed | undefined =>
    key === undefined ? undefined : templateSeed(key);
  const stateOf = (seed: TemplateSeed): TemplateState =>
    states.get(seed.key) ?? { published: null, draft: null };
  const missing = (): Response => json({ detail: "not_found" }, 404);
  const contentOf = (seed: TemplateSeed, source: "draft" | "published" | null) => {
    const state = stateOf(seed);
    if (source === "published") return state.published;
    return state.draft ?? (source === "draft" ? null : state.published);
  };

  return {
    "GET /v1/firm/email-templates": () =>
      json({ items: TEMPLATES.map((seed) => rowOut(seed, stateOf(seed))) }),
    "GET /v1/firm/email-templates/{key}": ({ params }) => {
      const seed = seedOf(params.key);
      return seed === undefined ? missing() : json(templateOut(seed, stateOf(seed), actions));
    },
    "PUT /v1/firm/email-templates/{key}/draft": ({ params, body }) => {
      const seed = seedOf(params.key);
      if (seed === undefined || !actions.includes("edit")) return missing();
      const given = body as EmailTemplateDraftIn;
      const state = stateOf(seed);
      const have = state.draft?.expected_version ?? 0;
      if (given.expected_version !== have) return json({ detail: "stale_version" }, 409);
      const draft = {
        expected_version: have + 1,
        base_version: state.published?.version ?? null,
        subject: given.subject,
        preheader: given.preheader ?? "",
        blocks: given.blocks,
        cta_label: given.cta_label ?? null,
        cta_target: given.cta_target ?? null,
        saved_at: setup.now,
        saved_by: GRACE,
      };
      states.set(seed.key, { ...state, draft });
      return json(draft);
    },
    "DELETE /v1/firm/email-templates/{key}/draft": ({ params }) => {
      const seed = seedOf(params.key);
      const state = seed === undefined ? undefined : stateOf(seed);
      if (seed === undefined || state?.draft === null || state === undefined) return missing();
      const next = { ...state, draft: null };
      states.set(seed.key, next);
      return json(templateOut(seed, next, actions));
    },
    "POST /v1/firm/email-templates/{key}/preview": ({ params, body }) => {
      const seed = seedOf(params.key);
      const given = (body ?? {}) as EmailPreviewIn;
      if (seed === undefined) return missing();
      const content = contentOf(seed, given.source ?? "draft");
      if (content === null) return missing();
      const rendered = renderEmail(
        content,
        valuesFor(seed, given.sample_contact_id),
        given.width ?? 600,
      );
      return json({
        ...rendered,
        from_display: FROM_DISPLAY,
        from_address: FROM_ADDRESS,
        reply_to: null,
        findings: lintTemplate(content, seed.variables),
      });
    },
    "POST /v1/firm/email-templates/{key}/test-send": ({ params, body }) => {
      const seed = seedOf(params.key);
      if (seed === undefined || !actions.includes("test_send")) return missing();
      const content = contentOf(seed, null);
      if (content === null) return missing();
      const findings = lintTemplate(content, seed.variables);
      if (findings.length > 0) return lintFailed(findings);
      const given = (body ?? {}) as EmailTestSendIn;
      const rendered = renderEmail(content, valuesFor(seed, given.sample_contact_id), 600);
      return json(
        {
          message_id: stableId(`test-send:${seed.key}`),
          sent_to: GRACE_EMAIL, // the acting admin's own address, never one from the request
          subject: `[Test] ${rendered.subject}`,
        },
        202,
      );
    },
    "POST /v1/firm/email-templates/{key}/publish": ({ params }) => {
      const seed = seedOf(params.key);
      if (seed === undefined || !actions.includes("publish")) return missing();
      const state = stateOf(seed);
      if (state.draft === null) return json({ detail: "stale_version" }, 409);
      const findings = lintTemplate(state.draft, seed.variables);
      if (findings.length > 0) return lintFailed(findings);
      const version = (state.published?.version ?? 0) + 1;
      const published = {
        ...versionOut(seed, version, setup.now),
        subject: state.draft.subject,
        preheader: state.draft.preheader,
        blocks: state.draft.blocks,
        cta_label: state.draft.cta_label,
        cta_target: state.draft.cta_target,
      };
      states.set(seed.key, { published, draft: null });
      return json(published, 201);
    },
    "GET /v1/firm/follow-up-policy": () => json(FOLLOW_UP_POLICY),
  };
}
