// The home domain (I-01 §5.1): HOME-01's and HOME-02's shared parts and reads.
export {
  BANDS,
  type Band,
  dueChip,
  dueRisk,
  glyphOf,
  summaryParts,
  visibleBands,
} from "./gateClasses";
export { HOME_SEGMENTS, HomeSegmented, homeSegmentOptions } from "./HomeSegmented";
export { HOME_MESSAGES } from "./messages";
export {
  HOME_POLL_MS,
  HOME_STALE_MS,
  invalidateGates,
  useGateCounts,
  useHome,
  useWaitingOnYou,
} from "./queries";
export { WaitingOnYou, type WaitingOnYouProps } from "./WaitingOnYou";
