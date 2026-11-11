// A-07-T47 (DEC-3303): the live completion hooks, their own public root so the audits domain's
// shared chunk (AUD-06's routes) does not carry them; AUD-24 and AUD-25's hosts load them lazily.
export {
  COMPLETION_QUERIES,
  LIVE_POLL_MS,
  REFUSAL_PROBLEM,
  REFUSAL_WORDS,
  RUN_POLL_MS,
  asksForStepUp,
  governanceWords,
  invalidateCompletion,
  lockRunning,
  refusalWords,
  releaseRunning,
  useLiveArchive,
  useLiveRelease,
} from "./completionLive";
