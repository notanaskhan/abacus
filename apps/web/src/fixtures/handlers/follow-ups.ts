// Follow-ups v2 in fixture mode (P-06-T16; C5 v1.2 §12): the drafts a screen's selection asks
// for, and the person's edit, send and Undo, over the scenario's own copy. The drafts' wording is
// BND-04 c's (the designed follow-up sheet; DEC-221), never invented: each scenario passes the
// recipient, the opening text and the requests it names.

import type { FollowUpDraftsIn, FollowUpEditIn, FollowUpOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { DEMO_INSTANT } from "../seed/clock";
import { stableId } from "../seed/prng";

export interface FollowUpItemSpec {
  id: string;
  title: string;
  due_on: string | null;
  overdue: boolean;
}

export interface FollowUpSpec {
  engagementId: string;
  binderId: string | null;
  recipientUserId: string;
  recipientName: string;
  body: string;
  items: FollowUpItemSpec[];
}

const UNDO_MS = 10_000;
const ACTIONS = ["follow_up.draft", "follow_up.send"];

function draftOf(spec: FollowUpSpec): FollowUpOut {
  return {
    id: stableId(`follow-up:${spec.recipientUserId}:${spec.items.map((i) => i.id).join(",")}`),
    engagement_id: spec.engagementId,
    binder_id: spec.binderId,
    kind: "chase",
    status: "drafted",
    recipient_user_id: spec.recipientUserId,
    recipient_contact_id: null,
    recipient_name: spec.recipientName,
    items: spec.items.map((i) => ({
      request_item_id: i.id,
      title: i.title,
      due_on: i.due_on,
      overdue: i.overdue,
    })),
    subject: "",
    body: spec.body,
    edited: false,
    drafted_by_kind: "agent",
    template_key: "notification.follow_up_sent",
    created_at: DEMO_INSTANT,
    sent_by: null,
    sent_at: null,
    undo_until: null,
    allowed_actions: ACTIONS,
  };
}

/** `drafts` answers a selection with the follow-ups to draft (one per contact). */
export function followUpHandlers(
  drafts: (asked: FollowUpDraftsIn) => FollowUpSpec[],
  senderUserId: () => string,
): Record<string, FixtureHandler> {
  const made = new Map<string, FollowUpOut>();
  const find = (id: string | undefined): FollowUpOut | undefined =>
    id === undefined ? undefined : made.get(id);
  const put = (next: FollowUpOut): FollowUpOut => {
    made.set(next.id, next);
    return next;
  };
  return {
    "POST /v1/follow-ups/drafts": ({ body }) => {
      const asked = (body ?? {}) as FollowUpDraftsIn;
      const waiting = new Set(
        [...made.values()]
          .filter((d) => d.status === "drafted")
          .flatMap((d) => d.items.map((i) => `${d.recipient_user_id}:${i.request_item_id}`)),
      );
      const fresh = drafts(asked)
        .map((spec) => ({
          ...spec,
          items: spec.items.filter((i) => !waiting.has(`${spec.recipientUserId}:${i.id}`)),
        }))
        .filter((spec) => spec.items.length > 0)
        .map((spec) => put(draftOf(spec)));
      return json({ items: fresh }, 201);
    },
    "GET /v1/follow-ups/{follow_up_id}": ({ params }) => {
      const found = find(params.follow_up_id);
      return found === undefined ? json({ detail: "not found" }, 404) : json(found);
    },
    "PATCH /v1/follow-ups/{follow_up_id}": ({ params, body }) => {
      const found = find(params.follow_up_id);
      if (found === undefined) return json({ detail: "not found" }, 404);
      if (found.status !== "drafted") return json({ detail: "follow_up_already_sent" }, 409);
      const text = (body as Partial<FollowUpEditIn> | null)?.body?.trim() ?? "";
      if (text === "") return json({ detail: "invalid" }, 422);
      return json(put({ ...found, body: text, edited: true }));
    },
    "POST /v1/follow-ups/send": ({ body }) => {
      const ids = (body as { ids?: string[] } | null)?.ids ?? [];
      const all = ids.map((id) => find(id));
      if (all.some((d) => d === undefined)) return json({ detail: "not found" }, 404);
      if (all.some((d) => d?.status !== "drafted")) {
        return json({ detail: "follow_up_already_sent" }, 409);
      }
      const until = new Date(Date.parse(DEMO_INSTANT) + UNDO_MS).toISOString();
      const sent = all.map((d) =>
        put({
          ...(d as FollowUpOut),
          status: "sent",
          sent_by: senderUserId(),
          sent_at: DEMO_INSTANT,
          undo_until: until,
        }),
      );
      return json({ items: sent });
    },
    "POST /v1/follow-ups/{follow_up_id}/undo": ({ params }) => {
      const found = find(params.follow_up_id);
      if (found?.status !== "sent") return json({ detail: "undo_window_closed" }, 409);
      return json(
        put({ ...found, status: "drafted", sent_by: null, sent_at: null, undo_until: null }),
      );
    },
    "POST /v1/follow-ups/{follow_up_id}/dismiss": ({ params }) => {
      const found = find(params.follow_up_id);
      if (found?.status !== "drafted") return json({ detail: "follow_up_not_waiting" }, 409);
      return json(put({ ...found, status: "dismissed" }));
    },
  };
}
