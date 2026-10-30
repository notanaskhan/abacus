import type { JSX } from "react";
import { Button, type ButtonProps } from "../components/button";
import { type Actor, type HumanVerb, isPerson } from "./actor";

// HumanAction (F-05-T30; INV-1): the only control that may carry Approve, Sign off, Release, Send,
// Post, Decide or Adopt. It names who is about to act; when that is not a named person (the
// agent, a policy, the system), it renders nothing, so a human gate can never sit on an
// agent-owned control.

export interface HumanActionProps extends Omit<ButtonProps, "children"> {
  verb: HumanVerb;
  /** What the verb acts on: "Document" makes "Approve Document". */
  object?: string;
  /** Who would perform it: the signed-in person, never the agent. */
  actor: Actor;
  /** The control opens a dialog first: the label ends in "…". */
  opensDialog?: boolean;
  /** The whole label when the verb's sentence reads otherwise ("Re-sign as Reviewer (L2)",
   * "Resolve 11 issues to approve" on a blocked gate); the verb still marks the control. */
  label?: string;
}

export function HumanAction({
  verb,
  object,
  actor,
  opensDialog = false,
  label: whole,
  ...button
}: HumanActionProps): JSX.Element | null {
  if (!isPerson(actor)) return null;
  const label =
    whole ?? `${verb}${object === undefined ? "" : ` ${object}`}${opensDialog ? "…" : ""}`;
  return (
    <Button {...button} opensDialog={opensDialog} data-human-verb={verb}>
      {label}
    </Button>
  );
}
