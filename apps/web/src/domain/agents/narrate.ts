// The engagement agent's actions in plain words (SPEC-027; P-09 Story 8.1): code words in,
// copy out, never model text. Shared by the legacy Activity feed, the trace and the dock.

// SPEC-027 (TASK-050): each automatic action in plain words. References only, never content.
export const ACTION: Record<string, string> = {
  "agent.started": "The engagement agent started",
  "agent.paused": "The agent was paused",
  "agent.resumed": "The agent was resumed",
  "agent.resume_checked": "Checked the engagement after resuming",
  "screening.start": "Screen new evidence",
  "screening.replayed": "Screened evidence that arrived while paused",
  "retrieval.start": "Retrieve from the client's system",
  "match.suggested": "Suggested request items for a file in the inbox",
  "agent.tick": "Daily check",
  "agent.self_paused": "The agent paused itself: the engagement has no active partner",
  "agent.self_resumed": "The agent resumed: the engagement has a partner again",
  "reminders.sent": "Sent overdue reminders",
  "reminders.drafted": "Drafted overdue reminders for you to send",
  "reminders.check": "Remind about overdue items",
  "reminders.restarted": "Due dates changed: reminders start again",
  "digest.sent": "Told the team about overdue items",
  "upload_review.start": "Review an upload",
  "inbox_match.start": "Match a file in the inbox",
};
export const REASON: Record<string, string> = {
  paused: "the agent is paused on this engagement",
  firm_paused: "your firm has paused every agent",
  advise: "your firm's autonomy is Advise, so a person starts it",
  agent_off: "the engagement agent is off for your firm",
  auto_retrieval_off: "automatic retrieval is off for your firm",
  not_open: "the engagement isn't open to client data yet",
  no_connection: "the client hasn't connected an accounting system",
  no_consenting_member: "no one who can retrieve has consented",
  nothing: "nothing was waiting for data",
  unavailable: "retrieval isn't available",
  malformed_event: "the event couldn't be read",
  self_paused: "the engagement has no active partner",
  no_partner: "the engagement has no active partner",
  no_real_model: "no AI model is available here",
  matching_off: "inbox matching is off for your firm",
  upload_review_off: "upload review is off for your firm",
  not_due: "nothing was due yet",
};

/** A run item's narration from code words only (P-09 Story 8.1): no counts, no model text. */
export function narrate(action: string, outcome: string | null, reason: string | null): string {
  const what = ACTION[action] ?? action;
  if (outcome === "done" || outcome === null) return what;
  const why = reason != null ? (REASON[reason] ?? reason) : "";
  return outcome === "skipped"
    ? `Skipped: ${what.toLowerCase()}, because ${why}`
    : `Failed: ${what.toLowerCase()}`;
}
