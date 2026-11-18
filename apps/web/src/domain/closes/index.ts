// The closes domain's public entry (C-01 §5): what screens import.
export {
  CLOSE_PERIODS,
  CLOSE_STATUS_FILTERS,
  CLOSE_TILES,
  type CloseFilters,
  type ClosePeriod,
  type CloseStatus,
  type CloseStatusFilter,
  DEFAULT_CLOSE_FILTERS,
  isClosePeriod,
  isCloseStatusFilter,
  isNarrowedCloses,
  useCloses,
  useRunningCloses,
} from "./queries";
export { closeReadFrame } from "./ReadFrame";
export { RUN_POLL_MS, closeReadState, runIsLive } from "./states";
