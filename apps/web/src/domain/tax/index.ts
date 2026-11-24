// The tax domain's public entry (T-02-T25).
export { useDraftK1Source } from "./k1";
export * from "./agents";
export { AgentsOffNote } from "./AgentsOffNote";
export { useEntityAgentGate } from "./useEntityAgentGate";
export * from "./entityReturn";
export * from "./instrument";
export {
  HANDOFF_BANNER_COPY,
  HandoffProvenanceBanner,
  type HandoffProvenanceBannerProps,
  handoffLine,
} from "./HandoffProvenanceBanner";
export { HANDOFF_GATE_COPY, type HandoffGate, useTaxHandoffGate } from "../tax-handoff";
