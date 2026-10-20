import type { JSX } from "react";
import type { Tone } from "./components/surfaces";
import { StatusPill } from "./components/workspace";
import { STATUS_REGISTRY } from "./status.gen";

// The status vocabulary (TASK-101, the plan's §3.3.1): every state the product shows, with its
// word and tone, in one place, so the same state never reads two ways on two screens.

export interface StatusWord {
  label: string;
  tone: Tone;
}

export const STATUS = {
  // The plan's firm-side request words (S19 §3; TASK-105): asked, uploaded and waiting for the
  // team, screened and ready for a decision, or returned to the client. ("Received" means accepted
  // in the plan, so an upload is never called received.)
  // F-03-T15: request status v2 (chapter 09 §9.5.6): a firm-only draft, asked of the client,
  // uploaded and waiting for the team, returned, received (accepted), or not applicable.
  request: {
    draft: { label: "Draft", tone: "neutral" },
    requested: { label: "Requested", tone: "neutral" },
    uploaded: { label: "Uploaded", tone: "warning" },
    returned: { label: "Returned", tone: "danger" },
    received: { label: "Received", tone: "success" },
    not_applicable: { label: "Not applicable", tone: "neutral" },
  },
  // The client's words for their requests (the plan's POR-03; TASK-106): never the firm's states.
  clientRequest: {
    requested: { label: "To do", tone: "neutral" },
    uploaded: { label: "Done", tone: "success" },
    returned: { label: "Returned", tone: "danger" },
    received: { label: "Done", tone: "success" },
    not_applicable: { label: "Doesn't apply", tone: "neutral" },
  },
  engagement: {
    active: { label: "Active", tone: "success" },
    archived: { label: "Archived", tone: "neutral" },
  },
  workpaper: {
    not_started: { label: "Not started", tone: "neutral" },
    draft: { label: "Draft", tone: "warning" },
    ready: { label: "Prepared", tone: "warning" },
    reviewed: { label: "Reviewed", tone: "success" },
  },
  result: {
    supported: { label: "Supported", tone: "success" },
    exception: { label: "Exception", tone: "danger" },
    not_tested: { label: "Not tested", tone: "neutral" },
  },
  decision: {
    accept: { label: "Accepted", tone: "success" },
    reject: { label: "Sent back", tone: "warning" },
  },
} as const satisfies Record<string, Record<string, StatusWord>>;

export type StatusDomain = keyof typeof STATUS;

/** The word and tone for a state; an unknown state reads as itself, neutral. */
export function statusWord(domain: StatusDomain, value: string): StatusWord {
  const words: Record<string, StatusWord> = STATUS[domain];
  return words[value] ?? { label: value, tone: "neutral" };
}

/** A state as a pill. */
export function Status({ domain, value }: { domain: StatusDomain; value: string }): JSX.Element {
  const word = statusWord(domain, value);
  return <StatusPill tone={word.tone}>{word.label}</StatusPill>;
}

// C2 (F-03-T09): the registry generated from docs/product/status-vocabulary.yaml. New screens read
// words from here; STATUS above stays for the legacy request codes until request status v2.

export type RegistryObject = keyof typeof STATUS_REGISTRY;
export type RegistryCode<O extends RegistryObject> = keyof (typeof STATUS_REGISTRY)[O] & string;

const VARIANT_TONE: Record<string, Tone> = {
  green: "success",
  "green-tint": "success",
  red: "danger",
  "red-tint": "danger",
  amber: "warning",
  state: "info",
};

interface RegistryEntry {
  label: string;
  variant: string | null;
  clientLabel?: string;
}

/** The registry's word and tone for a code; `client` uses the portal wording when there is one.
 * Placeholders ({date}, {reason}) are filled from `fill`, or dropped with their separator. */
export function registryWord(
  object: RegistryObject,
  code: string,
  options: { client?: boolean; fill?: Record<string, string> } = {},
): StatusWord {
  const codes: Record<string, RegistryEntry> = STATUS_REGISTRY[object];
  const entry = codes[code];
  if (entry === undefined) return { label: code, tone: "neutral" };
  const raw =
    options.client === true && entry.clientLabel !== undefined ? entry.clientLabel : entry.label;
  const label = raw
    .replace(/\{(\w+)\}/g, (_m, key: string) => options.fill?.[key] ?? "")
    .replace(/\s*·\s*$/, "")
    .trim();
  return { label, tone: VARIANT_TONE[entry.variant ?? ""] ?? "neutral" };
}
