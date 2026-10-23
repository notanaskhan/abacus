// E1 MatchProvider, E2 anchored popover host and the C-07 Cite kit (F-05-T41).
export {
  CitationChip,
  type CitationChipProps,
  CitationFooter,
  CitationPopover,
  CitationPopoverHost,
  type CitationPopoverHostProps,
  type CitationPopoverProps,
  CiteMarker,
  type CiteMarkerProps,
  type ProcedureRef,
  citationMatch,
} from "./cite";
export {
  MATCH_CELL,
  MATCH_REGION,
  MATCH_ROW,
  type MatchBind,
  MatchScope,
  type MatchScopeProps,
  Matchable,
  type MatchableProps,
  type UseMatch,
  useMatch,
  useMatchState,
  useMatchStore,
} from "./match";
export {
  INTENT_MS,
  MARKER_INTENT_MS,
  MARKER_RELEASE_MS,
  MATCH_LIGHT_MS,
  type MatchState,
  type MatchStore,
  RELEASE_MS,
  contractMatchId,
  createMatchStore,
  matchIdOf,
} from "./match-store";
export { AnchoredPopoverHost, type AnchoredPopoverHostProps } from "./popover-host";
export {
  type CitationPayload,
  type CitationView,
  type ContractMatch,
  type Locator,
  type LocatorKind,
  type MatchId,
  type MatchKind,
} from "./types";
