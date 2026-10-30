// The T10 DocumentOnWell kit's prop API (F-06-T14; F-06.md §5.2, SPEC-400 AC-19, AC-21): the
// contract F-06-T15 (DocBlocks), F-06-T17 (acceptance tests) and the 2027 consumers (ENG-04,
// NOT-03, AUD-21, POR-20) build against. L2 rule: generic shapes, no @abacus/api-client types.
// The document's status is the server's (DF-31, computed by P-11 through C11); the kit composes no
// text and performs no write: Approve, Edit, Regenerate, the clause toggles and the variables are
// callbacks.

import type { Actor } from "../../attribution/actor";
import type { MatchId } from "../../tracing/types";

/** DF-31's `generated_document` status (status-vocabulary.yaml). */
export type DocumentStatus = "drafting" | "draft" | "approved" | "locked";

/** `paper` is firm-internal; `letter` and `email` reach clients and carry no agent prose and no
 * agent Drafting state unless the consumer passes `modelTextToClients` (ADR P-25, off). */
export type DocumentVariant = "paper" | "letter" | "email";

/** One key-value row of a structure sheet: 33 high, key ink-2 left, value right. */
export interface KvRowVM {
  key: string;
  /** null renders "—" (ink-4). */
  value: string | null;
  /** The value links to a record: ink with an ink-3 "→"; the callback gets `linkId`. */
  linkId?: string;
  /** What a citation marker on the paper lights (E1 MatchProvider). */
  match?: MatchId;
}

export interface KvSectionVM {
  title: string;
  rows: readonly KvRowVM[];
}

/** A sheet of the KV structure: the 32 crumb header ("Partnership › General Information") over
 * its 31 section bands. */
export interface KvSheetVM {
  crumb: string;
  sections: readonly KvSectionVM[];
}

/** A letter's clause or a report's section that can be turned off: 34 high with a 34 × 20 Toggle
 * and a 12.5 ink-3 reason. */
export interface ClauseVM {
  id: string;
  label: string;
  on: boolean;
  /** Why it is on or off ("Required for every engagement letter"). */
  reason?: string;
  /** The clause can't be turned off (a required clause). */
  required?: boolean;
}

/** A template variable in the Variables fieldset (T12 ValueRow, text). */
export interface VariableVM {
  id: string;
  label: string;
  value: string;
}

export type StructureVM =
  | { kind: "kv"; sheets: readonly KvSheetVM[] }
  | { kind: "clauses"; clauses: readonly ClauseVM[]; variables: readonly VariableVM[] };

/** The approval control: a HumanAction (INV-1) that only calls `onApprove`; SHL-12 is P-04's. */
export interface ApproveVM {
  /** Who would approve: the signed-in person. An agent or system actor renders nothing. */
  actor: Actor;
  /** What is approved: "memo" makes "Approve memo…"; none makes "Approve…" (the T10 board). */
  object?: string;
  /** The server's `allowed_actions` lacks `document.approve`: drawn disabled with this reason. */
  disabledReason?: string;
}

export interface DocumentVM {
  status: DocumentStatus;
  variant: DocumentVariant;
  /** ADR P-25: omitted = off. Letter and email drop agent prose and the agent Drafting state. */
  modelTextToClients?: boolean;
  structure: StructureVM;
  /** The paper pane's centred title ("Return Summary", "Preparer memo"). */
  title: string;
  /** The DRAFT watermark (draft documents). */
  watermark: boolean;
  /** "Adopted by Olivia Brandt": a sub-line under the Draft pill, never a status (F-06 Q6). */
  adoptedBy?: string;
  /** "Approved by Samuel Ito · Sep 14, 9:40 AM" (F-06-T15 renders the approved header). */
  approvedBy?: { actor: Actor; when: string };
  /** Why the document is locked (F-06-T15, T10d). */
  lockedReason?: string;
  actions: { approve?: ApproveVM; edit?: boolean; regenerate?: boolean };
}

export interface DocumentOnWellCopy {
  edit: string;
  /** "Regenerate…" (it opens a confirmation). */
  regenerate: string;
  /** "Accrued Agent is drafting the memo" (paper only). */
  drafting: string;
  /** The render-in-progress line of a letter or email without model text ("Preparing the letter"). */
  rendering: string;
  /** "DRAFT" */
  watermark: string;
  /** "Variables" */
  variables: string;
  /** T10c's disabled control once approved (F-06-T15); default "Approved". */
  approved?: string;
}
