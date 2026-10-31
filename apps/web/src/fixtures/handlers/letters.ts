// ENG-04's C7 composer routes in fixture mode (N-02-T34): the letter is state, so a clause toggle
// in Draft answers a new version with the server's redline rule (the template's non-standard
// clauses, plus each clause switched from its default, plus each overridden section). An edit to a
// partner-approved letter returns it to Draft; a sent letter refuses (409 `letter_locked`), as
// `engagements/letters.py` does. Send answers E13's C7 draft for SIG-02.
import type { ComposerLetterOut, LetterDraftIn, LetterSendOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { E13_ENVELOPE, RIDGELINE_CLAUSES } from "../seed/letters";

const DEFAULT_ON = new Map(RIDGELINE_CLAUSES.map((c) => [c.key, c.state !== "off"]));

export function redlineCount(letter: ComposerLetterOut, overrides: number): number {
  const flagged = letter.clauses.filter((c) => c.non_standard).length;
  const changed = letter.clauses.filter(
    (c) => (c.state !== "off") !== (DEFAULT_ON.get(c.key) ?? true),
  ).length;
  return flagged + changed + overrides;
}

export function letterHandlers(initial: ComposerLetterOut): Record<string, FixtureHandler> {
  let letter = initial;
  const own = (params: Readonly<Record<string, string>>) =>
    params["engagement_id"] === letter.engagement_id;
  const missing = json({ detail: "not_found" }, 404);
  return {
    "GET /v1/engagements/{engagement_id}/letter/composer": ({ params }) =>
      own(params) ? json(letter) : missing,
    "PUT /v1/engagements/{engagement_id}/letter/composer": ({ params, body }) => {
      if (!own(params)) return missing;
      if (letter.status !== "draft" && letter.status !== "partner_approved") {
        return json({ detail: { code: "letter_locked" } }, 409);
      }
      const draft = body as LetterDraftIn;
      const clauses = letter.clauses.map((c) => {
        const state = draft.clause_states[c.key];
        return state === undefined ? c : { ...c, state };
      });
      const next = letter.version + 1;
      letter = {
        ...letter,
        status: "draft",
        clauses,
        version: next,
        version_no: next,
        approved_by_name: null,
        approved_at: null,
        approval_content_hash: null,
        allowed_actions: ["letter.read", "letter.draft"],
      };
      letter = {
        ...letter,
        redline_count: redlineCount(letter, Object.keys(draft.section_overrides ?? {}).length),
      };
      return json(letter);
    },
    "POST /v1/engagements/{engagement_id}/letter/request-approval": ({ params }) =>
      own(params) ? json(letter) : missing,
    "POST /v1/engagements/{engagement_id}/letter/send": ({ params }) =>
      own(params) ? json({ envelope_id: E13_ENVELOPE } satisfies LetterSendOut) : missing,
  };
}
