// Fixture handlers for POR-23, the component auditor's room (A-09-T36; A-09-T33's read model): the
// room list (empty for f, the expired invitation), the room, its instructions and thread, and the
// acknowledge, ask, drop and link the room's routes take. Another room answers 404 (INV-4). A drop
// answers no deliverable, so the room asks which one (the handoff's ambiguity picker).
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import {
  COMPONENT_ROOM,
  GROUP_IDS,
  type Por23State,
  ROOM_INSTRUCTIONS,
  ROOM_QUESTIONS,
} from "../seed/group-audit";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not found" };

export function componentRoomHandlers(state: Por23State): Record<string, FixtureHandler> {
  const room = state === "f" ? undefined : COMPONENT_ROOM[state];
  const thread = state === "f" ? { items: [] } : ROOM_QUESTIONS[state];
  const mine = (id: string | undefined): boolean => room !== undefined && id === GROUP_IDS.room;
  return {
    "GET /v1/portal/component-rooms": () =>
      json({ room_ids: room === undefined ? [] : [room.id] }),
    "GET /v1/portal/component-rooms/{room_id}": ({ params }) =>
      mine(params.room_id) ? json(room) : json(NOT_FOUND, 404),
    "GET /v1/portal/component-rooms/{room_id}/instructions": ({ params }) =>
      mine(params.room_id) ? json(ROOM_INSTRUCTIONS) : json(NOT_FOUND, 404),
    "GET /v1/portal/component-rooms/{room_id}/questions": ({ params }) =>
      mine(params.room_id) ? json(thread) : json(NOT_FOUND, 404),
    "POST /v1/portal/component-rooms/{room_id}/instructions/acknowledge": ({ params }) =>
      mine(params.room_id) ? json({ acknowledged_on: "2026-09-23" }) : json(NOT_FOUND, 404),
    "POST /v1/portal/component-rooms/{room_id}/questions": ({ params }) =>
      mine(params.room_id)
        ? json({ id: stableId("question:new"), at: "2026-09-23T16:20:00Z" }, 201)
        : json(NOT_FOUND, 404),
    "POST /v1/portal/component-rooms/{room_id}/drops": ({ params }) =>
      mine(params.room_id)
        ? json({ evidence_version_id: stableId("drop:1"), deliverable_id: null }, 201)
        : json(NOT_FOUND, 404),
    "POST /v1/portal/component-rooms/{room_id}/drops/{evidence_version_id}/deliverable": ({
      params,
    }) =>
      mine(params.room_id)
        ? json(
            { evidence_version_id: params.evidence_version_id, deliverable_id: stableId("x") },
            201,
          )
        : json(NOT_FOUND, 404),
  };
}
