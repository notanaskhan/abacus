// C-28 presence kit (F-08-T24; DEC-5932): the store, its sources and the markers.
export {
  CardPresence,
  CellPresenceRing,
  RecordPresence,
  SectionEditingBanner,
  usePresence,
} from "./markers";
export {
  HEARTBEAT_MS,
  PollingPresenceSource,
  type PresenceEvent,
  type PresenceSource,
  type ScriptedFrame,
  ScriptedPresenceSource,
  SsePresenceSource,
} from "./sources";
export {
  IDLE_MS,
  type PresenceActivity,
  type PresenceAnchorKind,
  type PresenceHeartbeat,
  type PresencePeer,
  PresenceStore,
  TTL_MS,
} from "./store";
