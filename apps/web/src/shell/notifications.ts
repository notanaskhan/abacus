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
  "review.assigned": "Evidence was assigned to you for review.",
  "evidence.uploaded": "The client uploaded a file to a request.",
  "connection.created": "The client connected their accounting system.",
  "connection.revoked": "An accounting system connection was ended.",
  "independence.requested": "Confirm your independence for an engagement.",
  "reminders.drafted": "Overdue reminders are waiting for you to send.",
  "agent.digest": "Items are overdue on an engagement: see its activity.",
  "comment.mentioned": "You were mentioned in a comment.", // SPEC-032 (TASK-063)
};

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
  if (n.kind === "comment.mentioned") {
    return { to: `/engagements/${n.engagement_id}/items/${n.subject_id}` };
  }
  const to = firmHref(n);
  return to === null ? null : { to };
}

function firmHref(n: NotificationOut): string | null {
  if (n.engagement_id === null) return null;
  if (n.kind === "review.assigned") return `/engagements/${n.engagement_id}/review`;
  if (n.kind === "evidence.uploaded") return `/engagements/${n.engagement_id}/requests`;
  return `/engagements/${n.engagement_id}`;
}
