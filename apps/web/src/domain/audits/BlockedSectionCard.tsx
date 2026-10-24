import { Button, EmptyState } from "@abacus/ui";
import type { JSX } from "react";
import { AUDIT_MESSAGES } from "./messages";

// The canvas of a section blocked on a person's decision (A-01-T06; AUD-02 d): "Waiting on
// Margaret Okonkwo" / "Planning materiality is reserved to the engagement partner." with "Open
// decision". The card names the person who decides; the agent never decides (INV-1). While the
// decision card (SHL-11, P-04; AUD-07) is unbuilt the action is a planned link: it is disabled and
// announced as unavailable rather than hidden, so the reason stays readable.

export interface BlockedSectionCardProps {
  /** The person the decision is reserved to ("Margaret Okonkwo"). */
  person: string;
  /** What is reserved and to whom, from the screen's copy (AUD-02 d). */
  body: string;
  /** Opens the decision; absent while its target is planned. */
  onOpenDecision?: () => void;
}

export function BlockedSectionCard({
  person,
  body,
  onOpenDecision,
}: BlockedSectionCardProps): JSX.Element {
  const planned = onOpenDecision === undefined;
  return (
    <div data-audit="blocked-section" className="flex flex-1">
      <EmptyState
        icon="triangle-alert"
        title={AUDIT_MESSAGES.blocked.title(person)}
        action={
          <Button
            variant="secondary"
            size="sm"
            disabled={planned}
            {...(planned
              ? { "aria-description": AUDIT_MESSAGES.blocked.unavailable }
              : { onClick: onOpenDecision })}
          >
            {AUDIT_MESSAGES.blocked.action}
          </Button>
        }
      >
        {body}
      </EmptyState>
    </div>
  );
}
