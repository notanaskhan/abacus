// The workbench's realtime topics (W-02 §4.5; ADR-232): `session:<id>` refetches that session's
// snapshot and the list (a row's state, its spinner and its dot change with its items);
// `user:<id>` events from the session outbox (`workbench_session.created`, `.renamed`, `.deleted`,
// `.context_changed`) refetch the list. TAX-08 registers `session` too; the keys compose.

import { getSessionQueryKey, listSessionsQueryKey } from "@abacus/api-client/query";
import { registerTopicKeys } from "../../app-core/realtime";

const LIST_KEY = [listSessionsQueryKey()[0]] as const;

registerTopicKeys("session", (topic) => [
  getSessionQueryKey({ path: { session_id: topic.slice("session:".length) } }),
  LIST_KEY,
]);
registerTopicKeys("user", () => [LIST_KEY]);

/** The topics WB-01 subscribes to while it shows `sessionId` (and the viewer's own). */
export function workbenchTopics(userId: string | null, sessionId: string | null): string[] {
  return [
    ...(userId === null ? [] : [`user:${userId}`]),
    ...(sessionId === null ? [] : [`session:${sessionId}`]),
  ];
}
