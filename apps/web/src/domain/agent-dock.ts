// The cockpits' entry to the agents domain (S32 partials end pass): the SHL-13 dock alone, so a
// cockpit's route chunk carries the dock without the barrel's run pane, trace drawer and run
// source (they load when a run or trace opens). Everything else still comes from `domain/agents`.
export { AgentDock } from "./agents/AgentDock";
