// P-05-T03: comments v2 and to-dos in fixture mode, one artboard state at a time
// (seed/collaboration.ts). P-05-T10: the thread writes answer the state's thread as the live
// routes do since P-05-T05 (the gallery never persists); to-do writes stay 501 here (SHL-17).
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  componentThread,
  dividendsThread,
  mentionCandidates,
  myTodos,
  NORTHWIND_TEAM,
  row3Thread,
  type Shl17State,
  type Shl18State,
  todoFor,
} from "../seed/collaboration";

export interface CollaborationState {
  shl17?: Shl17State;
  shl18?: Shl18State;
}

const notYet = () => json({ detail: "not_implemented" }, 501);

function threadsFor(state: Shl18State) {
  if (state === "d") return [dividendsThread()];
  if (state === "e") return [];
  if (state === "f") return [componentThread()];
  return [row3Thread()];
}

export function collaborationHandlers(
  state: CollaborationState = {},
): Record<string, FixtureHandler> {
  const shl18 = state.shl18 ?? "a";
  const shl17 = state.shl17 ?? "a";
  return {
    "GET /v1/comment-threads": () => {
      const items = threadsFor(shl18);
      const open = items.filter((t) => t.status === "open").length;
      return json({
        items,
        total: items.length,
        counts: { open, resolved: items.length - open },
      });
    },
    "GET /v1/engagements/{engagement_id}/mention-candidates": () =>
      json(mentionCandidates(shl18 === "b" || shl18 === "c" ? shl18 : "b2")),
    "GET /v1/engagements/{engagement_id}/assignee-candidates": () =>
      json({ items: NORTHWIND_TEAM }),
    "GET /v1/todos": () => json(myTodos()),
    "GET /v1/todos/{todo_id}": () => {
      const todo = todoFor(shl17);
      return todo ? json(todo) : json({ detail: "not_found" }, 404);
    },
    "POST /v1/comment-threads": () => json(threadsFor(shl18)[0] ?? row3Thread(), 201),
    "POST /v1/comment-threads/{thread_id}/comments": () =>
      json(threadsFor(shl18)[0] ?? row3Thread(), 201),
    "POST /v1/comment-threads/{thread_id}/resolve": () =>
      json(threadsFor(shl18)[0] ?? row3Thread()),
    "POST /v1/comment-threads/{thread_id}/reopen": () =>
      json(threadsFor(shl18)[0] ?? row3Thread()),
    "POST /v1/comment-threads/{thread_id}/mute": () => json(threadsFor(shl18)[0] ?? row3Thread()),
    "POST /v1/comment-threads/{thread_id}/convert-to-review-note": () =>
      json({ thread: row3Thread(), review_note_id: "00000000-0000-4000-8000-0000000017a3" }, 201),
    "POST /v1/todos": notYet,
    "POST /v1/todos/{todo_id}/complete": notYet,
    "POST /v1/todos/{todo_id}/reopen": notYet,
  };
}
