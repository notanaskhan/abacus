import type { NotificationOut } from "@abacus/api-client";

/** Display text per kind (SPEC-013 AC-7): the API returns identifiers, never text. */
const TEXT: Record<string, string> = {
  "support_session.requested": "Platform support asked for access to your firm.",
  "support_session.emergency_approved":
    "Platform support opened emergency access to your firm. Please review it.",
  "budget.soft_crossed": "Model spend passed its soft limit.",
  "budget.anomaly": "Unusual model spend on an engagement in the last hour.",
  "engagement.member_self_joined": "A firm admin joined an engagement to view its content.",
  "engagement_member.added": "You were added to an engagement's team.",
  review_assigned: "Evidence was assigned to you for review.",
  client_uploaded: "The client uploaded a file to a request.",
  "connection.created": "The client connected their accounting system.",
  "connection.revoked": "An accounting system connection was ended.",
  "independence.requested": "Confirm your independence for an engagement.",
  "reminders.drafted": "Overdue reminders are waiting for you to send.",
  "agent.digest": "Items are overdue on an engagement: see its activity.",
  mention: "You were mentioned in a comment.", // SPEC-032 (TASK-063)
  // SPEC-305 (TASK-306): decisions reserved to the engagement partner.
  "materiality.proposed": "Materiality is waiting for your decision.",
  "risk.approval_requested": "A risk is waiting for your approval.",
  "finding.severity_proposed": "A deficiency is waiting for you to conclude its severity.",
};

export type Category = "needs_you" | "mentions" | "client" | "updates";

const CATEGORY: Record<string, Category> = {
  review_assigned: "needs_you",
  "independence.requested": "needs_you",
  "reminders.drafted": "needs_you",
  "support_session.requested": "needs_you",
  "materiality.proposed": "needs_you",
  "risk.approval_requested": "needs_you",
  "finding.severity_proposed": "needs_you",
  mention: "mentions",
  client_uploaded: "client",
  "connection.created": "client",
  "connection.revoked": "client",
};

/** SPEC-305: which drawer tab a kind belongs to. */
export function categoryOf(kind: string): Category {
  return CATEGORY[kind] ?? "updates";
}

/** SPEC-305: the day group a notification falls in, relative to `now`. */
export function dayGroup(iso: string, now: Date): string {
  const day = (d: Date): number => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((day(now) - day(new Date(iso))) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "Earlier this week";
  return "Older";
}

export function notificationText(kind: string): string {
  return TEXT[kind] ?? "You have a new notification.";
}

export type Destination = { to: string; hash?: string };

/** Where a notification leads, when it concerns something with its own page. Client users go
 * to their engagement page, at the request (SPEC-032 Q2). */
export function notificationHref(
  n: NotificationOut,
  portal: "firm" | "client" = "firm",
): Destination | null {
  if (n.engagement_id === null) return null;
  if (portal === "client") {
    return {
      to: `/client/engagements/${n.engagement_id}`,
      ...(n.subject_type === "request_item" ? { hash: `request-${n.subject_id}` } : {}),
    };
  }
  if (n.kind === "mention") {
    return { to: `/engagements/${n.engagement_id}/items/${n.subject_id}` };
  }
  const to = firmHref(n);
  return to === null ? null : { to };
}

function firmHref(n: NotificationOut): string | null {
  if (n.engagement_id === null) return null;
  if (n.kind === "review_assigned") return `/engagements/${n.engagement_id}/review`;
  if (n.kind === "client_uploaded") return `/engagements/${n.engagement_id}/requests`;
  if (n.kind === "reminders.drafted") return `/engagements/${n.engagement_id}/requests`;
  if (n.kind === "materiality.proposed" || n.kind === "risk.approval_requested")
    return `/engagements/${n.engagement_id}/planning`;
  if (n.kind === "finding.severity_proposed") return `/engagements/${n.engagement_id}/findings`;
  return `/engagements/${n.engagement_id}`;
}
