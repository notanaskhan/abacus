// Attribution and human verbs (F-05-T30): formatActor, HumanAction, AgentFilledMarker.
export {
  AGENT_NAME,
  type Actor,
  HUMAN_VERBS,
  type HumanVerb,
  actorFromAudit,
  formatActor,
  isPerson,
} from "./actor";
export {
  AgentFilledMarker,
  type AgentFilledMarkerProps,
  type FilledState,
  type Suggestion,
  adoptSuggestion,
  editSuggestion,
  suggestionLines,
} from "./agent-filled";
export { HumanAction, type HumanActionProps } from "./human-action";
