// W-01-T17 (WB-10, WB-11): the Connect flow as a state machine, the screens' one source of truth.
// Enable on a WB-10 tile → WB-10 e (confirm) → WB-11 b (consent) → the provider → the callback
// (/workbench/connect/callback) → "✓ Connected as you" (a personal connection) or Connected.
// Reconnect starts at consent. A session older than the fresh-MFA window steps up first, before
// any act; a refused or failed callback ends in an error state the person can retry from.
export type FlowState =
  "idle" | "confirm" | "step_up" | "consent" | "provider" | "connecting" | "connected" | "error";
export type FlowEvent =
  | { type: "enable" }
  | { type: "reconnect" }
  | { type: "confirm" }
  | { type: "mfa_done" }
  | { type: "continue" }
  | { type: "callback"; ok: boolean }
  | { type: "settled" }
  | { type: "cancel" }
  | { type: "retry" };

export const FRESH_MFA_SECONDS = 15 * 60;

export function needsStepUp(mfaAt: Date | null, now: Date): boolean {
  return mfaAt === null || (now.getTime() - mfaAt.getTime()) / 1000 > FRESH_MFA_SECONDS;
}

export function next(state: FlowState, event: FlowEvent, stale: boolean): FlowState {
  if (event.type === "cancel") return "idle";
  switch (state) {
    case "idle":
      if (event.type === "enable") return stale ? "step_up" : "confirm";
      if (event.type === "reconnect") return stale ? "step_up" : "consent";
      return state;
    case "step_up":
      return event.type === "mfa_done" ? "confirm" : state;
    case "confirm":
      return event.type === "confirm" ? "consent" : state;
    case "consent":
      return event.type === "continue" ? "provider" : state;
    case "provider":
      if (event.type === "callback") return event.ok ? "connecting" : "error";
      return state;
    case "connecting":
      return event.type === "settled" ? "connected" : state;
    case "error":
      return event.type === "retry" ? "consent" : state;
    case "connected":
      return state;
  }
}

/** The badge after a personal connection settles (WB-11 b, after return). */
export const CONNECTED_AS_YOU = "✓ Connected as you";
