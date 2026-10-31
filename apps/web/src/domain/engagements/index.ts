// The engagements domain's public entry (P-07 §5): what screens import.
export { GATE_NAMES, GateBlock, type GateBlockProps, gateLine } from "./GateBlock";
export {
  feesIn,
  useComposedLetter,
  useLetterCompare,
  useLetterWrites,
  withClause,
} from "./letter";
export {
  allows,
  bandRows,
  conflictOf,
  gateOf,
  useEngagementRecord,
  useEngagementTeam,
  useEngagementWorkItems,
  useHoldEngagement,
  useRecordLetter,
  waitsOnLetter,
} from "./record";
export {
  type TeamRole,
  type TeamRouteRole,
  hoursText,
  hoursTotal,
  tenthsOf,
  useEqrCandidates,
  useTeamApproval,
  useTeamCandidates,
  useTeamRoster,
  useTeamWrites,
} from "./team";
export { type ConsentPreview, useDraft, useDraftWrites, useEngagementTypes } from "./wizard";
export {
  DEFAULT_ENGAGEMENT_FILTERS,
  ENGAGEMENT_LINES,
  ENGAGEMENT_TILES,
  type EngagementFilters,
  type EngagementLine,
  type EngagementPeriod,
  type NextDueWindow,
  isEngagementLine,
  isEngagementTile,
  isNarrowedIndex,
  useEngagementIndex,
} from "./list";
export {
  type AcceptanceOption,
  CONCLUSION,
  type FlagSeverity,
  type NewCondition,
  answerText,
  fieldOf,
  isClear,
  isLocked,
  mayOn,
  needsStepUp,
  openChecks,
  refusalOf,
  unanswered,
  useAcceptance,
  useAcceptanceWrites,
  useReviewCandidates,
} from "./acceptance";
export {
  DecisionDock,
  DecisionDockFooter,
  type DecisionDockOption,
  type DecisionDockProps,
} from "./DecisionDock";
export {
  declinedMembers,
  mayConclude,
  pendingMembers,
  useConflictCheck,
  useIndependence,
  useIndependenceWrites,
  useNas,
  useRotation,
} from "./independence";
