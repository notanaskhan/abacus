// SHL-09 a–f (P-04-T55): one scenario per frame from the C3 stub-3 fixtures (seed/review.ts,
// P-04-T34), on the Feld 2025 Form 1040; b's estimate also answers the issue its version links to
// (the Feld estimated-payments issue; SHL-15's issue shape, its title from the SHL-09 b frame).
// `OPENS` names the field each frame's tray opens on and the documents Add reference offers.
import type {
  FieldEditIn,
  FieldProvenanceOut,
  FieldReferenceIn,
  FieldReferenceOut,
  FieldTickIn,
  IssueDetailOut,
} from "@abacus/api-client";
import { type FixtureHandler, type Scenario, json } from "../../app-core/fixture-mode";
import { reviewScenarios } from "../handlers/review";
import { SAMUEL, SHL09, SHL15, digest, updated } from "../seed/review";
import { stableId } from "../seed/prng";

export const STATES = ["a", "b", "c", "d", "e", "f"] as const;
export type Shl09State = (typeof STATES)[number];

const ESTIMATE_ISSUE = SHL09.b.versions[0]?.issue_id ?? "";
const estimateIssue: IssueDetailOut = {
  ...SHL15.a,
  issue: { ...SHL15.a.issue, id: ESTIMATE_ISSUE },
  title: "Obtain 2025 federal and NY estimated tax payment confirmations",
};

/** The return's documents the tray's Add reference offers (the host's list). */
export const DOCUMENTS: readonly FieldReferenceOut[] = updated.references.filter(
  (r) => r.document_id !== null,
);

const FIELD = "/v1/fields/{target_type}/{target_id}/{field_key}";

/** The tray's writes, each answering the field after the person's act (never the agent's): a
 * tick on the current hash, an edit with its note (a new human version), a verified reference. */
function writes(start: FieldProvenanceOut): Record<string, FixtureHandler> {
  let tray = start;
  return {
    [`GET ${FIELD}/provenance`]: () => json(tray),
    [`POST ${FIELD}/ticks`]: ({ body }) => {
      const sent = body as FieldTickIn;
      if (sent.seen_hash !== tray.content_hash) return json({ detail: "stale_hash" }, 409);
      tray = {
        ...tray,
        ticks: [
          ...tray.ticks,
          {
            sign_off_id: stableId(`shl09:tick:${String(tray.ticks.length)}`),
            level: sent.level,
            signer_user_id: SAMUEL,
            signer_name: "Samuel Ito",
            initials: "SI",
            signed_at: "2026-09-14T14:24:00Z",
            content_hash: tray.content_hash,
            stale: false,
          },
        ],
      };
      return json(tray, 201);
    },
    [`PUT ${FIELD}/value`]: ({ body }) => {
      const sent = body as FieldEditIn;
      if (sent.citation_note.trim() === "") return json({ detail: "citation_note_required" }, 422);
      const head = tray.versions.find((v) => v.seq === tray.current_seq) ?? updated;
      const seq = tray.current_seq + 1;
      tray = {
        ...tray,
        current_seq: seq,
        content_hash: digest("ed17", String(seq).padStart(4, "0")),
        versions: [
          {
            ...head,
            seq,
            value: sent.value,
            value_kind: sent.value_kind ?? head.value_kind,
            value_source: "human",
            cause: "edit",
            actor_kind: "human",
            actor_name: "Samuel Ito",
            actor_user_id: SAMUEL,
            citation: sent.citation_note,
            unsupported: false,
            suggestion_id: null,
          },
          ...tray.versions,
        ],
        ticks: tray.ticks.map((t) => ({ ...t, stale: true })),
      };
      return json(tray);
    },
    [`POST ${FIELD}/references`]: ({ body }) => {
      const sent = body as FieldReferenceIn;
      const doc = DOCUMENTS.find((d) => d.document_id === sent.document_id);
      if (doc === undefined) return json({ detail: "citation_unverified" }, 422);
      tray = {
        ...tray,
        versions: tray.versions.map((v) =>
          v.seq === tray.current_seq
            ? {
                ...v,
                references: [...v.references, doc],
                citation: v.citation ?? doc.detail ?? doc.label,
                unsupported: false,
              }
            : v,
        ),
        allowed_actions: [...new Set([...tray.allowed_actions, "field.sign_off"])],
      };
      return json(tray, 201);
    },
  };
}

const all = reviewScenarios("SHL-09");
export const scenarios = Object.fromEntries(
  STATES.map((s) => {
    const base = all[s] as Scenario;
    return [
      s,
      {
        ...base,
        handlers: {
          ...base.handlers,
          ...writes(SHL09[s]),
          ...(s === "b"
            ? {
                "GET /v1/issues/{issue_id}": ({ params }) =>
                  params.issue_id === ESTIMATE_ISSUE
                    ? json(estimateIssue)
                    : json({ detail: "not_found" }, 404),
              }
            : {}),
        },
      },
    ];
  }),
) as Record<Shl09State, Scenario>;

export const OPENS: Record<
  Shl09State,
  { type: string; id: string; fieldKey: string; collapsed?: boolean }
> = Object.fromEntries(
  STATES.map((s) => [
    s,
    {
      type: SHL09[s].target_type,
      id: SHL09[s].target_id,
      fieldKey: SHL09[s].field_key,
      ...(s === "f" ? { collapsed: true } : {}),
    },
  ]),
) as Record<Shl09State, { type: string; id: string; fieldKey: string; collapsed?: boolean }>;
