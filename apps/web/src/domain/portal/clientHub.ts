// SPEC-031 (TASK-061), moved from the retired legacy client page by R-01-T18 (R-01 §8: the
// upload, history and send-back flows of ClientEngagement.tsx and ClientGuidance.tsx move into
// domain/portal): what a client reads about a request, as fixed templates (ADR-111). The only
// values in them are dates, account digits or names, and counts computed by the server. The
// legacy ClientHome still words "your part" with `yourPartMessage` until P-08-T28.
import type { GapOut, HistoryEntryOut, ProvidedOut, YourPartOut } from "@abacus/api-client";
import { longDate } from "@abacus/ui";

function day(iso: string): string {
  return longDate(iso.slice(0, 10));
}

export function providedMessage(provided: ProvidedOut): string {
  return provided.source === "connection"
    ? `Provided from your accounting system on ${day(provided.on)}. Nothing to do here.`
    : `Provided from your export of ${day(provided.on)}. Nothing to do here.`;
}

/** A history row for a version retrieved or imported, not uploaded. */
export function providedBy(provided: ProvidedOut | null): string {
  if (provided === null) return "Provided from your records";
  return provided.source === "connection"
    ? "Provided from your accounting system"
    : "Provided from your export";
}

const DIGITS = /^\d{4}$/;

function joined(parts: string[]): string {
  if (parts.length <= 1) return parts.join("");
  return `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1] ?? ""}`;
}

/** "accounts ending 2290 and 8812", or each named when some have no digits (D2). */
function accounts(labels: string[]): string {
  if (labels.every((l) => DIGITS.test(l))) {
    return `${labels.length > 1 ? "accounts" : "account"} ending ${joined(labels)}`;
  }
  return joined(labels.map((l) => (DIGITS.test(l) ? `account ending ${l}` : `the ${l} account`)));
}

/** The bank statement gap line, or null when nothing is missing (AC-5). */
export function gapMessage(gap: GapOut): string | null {
  if (gap.needed.length === 0) return null;
  if (gap.covered.length === 0) return `We still need statements for ${accounts(gap.needed)}.`;
  return `We have statements for ${accounts(gap.covered)}; we still need ${accounts(gap.needed)}.`;
}

const OUTCOME: Record<string, string> = {
  in_review: "In review",
  replaced: "Replaced",
  accepted: "Accepted",
  not_accepted: "Not accepted",
};

export function outcomeLabel(entry: HistoryEntryOut): string {
  if (entry.outcome === "sent_back") {
    return entry.reason_label != null ? `Sent back: ${entry.reason_label}` : "Sent back";
  }
  return OUTCOME[entry.outcome] ?? entry.outcome;
}

export function addedBy(entry: HistoryEntryOut): string {
  return entry.added_by === "client" ? entry.added_by_name || "Someone" : "Added by your auditor";
}

/** D2: under an hour in quarter hours, otherwise to the nearest half hour. */
export function estimate(minutes: number): string {
  if (minutes < 60) return `about ${String(Math.max(15, Math.round(minutes / 15) * 15))} minutes`;
  const halves = Math.round(minutes / 30);
  const whole = Math.floor(halves / 2);
  const half = halves % 2 === 1 ? "½" : "";
  return `about ${String(whole)}${half} ${whole === 1 && half === "" ? "hour" : "hours"}`;
}

export function yourPartMessage(part: YourPartOut): string {
  if (part.items_left === 0) return "Nothing left for you";
  const n = part.blocks_fieldwork;
  const blocks = n === 0 ? "" : ` · ${String(n)} ${n === 1 ? "blocks" : "block"} fieldwork`;
  return `${String(part.items_left)} left${blocks} · ${estimate(part.minutes)}`;
}
