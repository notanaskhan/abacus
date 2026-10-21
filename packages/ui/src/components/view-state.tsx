import type { JSX, ReactNode } from "react";
import { cn } from "../cn";
import type { IconName } from "../icons";
import { Button } from "./button";
import { EmptyLink, EmptyState, ErrorState, type SkeletonType, SkeletonRows } from "./states";

// ViewState (plan 04 section 5.1; F-05-T19): the one state every template takes. A template keeps
// its header and its column heads in every mode and swaps only the body, so a loading, empty,
// failed, restricted or switched-off view never changes the pane's frame (C-20). Routes map
// `pendingComponent` to `{ kind: "loading" }` and `errorComponent` to `{ kind: "error" }`.
//
// A restricted view shows no record data (INV-3, ADR-024): the body never calls `children`, so
// nothing the caller built from the record is rendered, and the reason is said in words. A view
// whose feature is off is a designed state in the T21e grammar, never a 404 (DEC-55).

/** Why a record is read-only or closed (the `read_only_reason` of an actionable payload). */
export type ReadOnlyReason =
  "archived" | "walled" | "gate_g2" | "role" | "mfa_required" | "flag_off" | "entitlement";

export const READ_ONLY_REASONS: readonly ReadOnlyReason[] = [
  "archived",
  "walled",
  "gate_g2",
  "role",
  "mfa_required",
  "flag_off",
  "entitlement",
];

/** A flag or entitlement key, as the API names it: `ff.insights`, `insights`. Generated later. */
export type FlagKey = string;

/** The one secondary button of an empty state. */
export interface StateAction {
  label: string;
  onSelect: () => void;
}

export type ViewState =
  /** Real header and columns, a skeleton body (9px bars at 62, 38 and 74 percent, after 200ms). */
  | { kind: "loading" }
  /** A 34px tile, a title, what will appear and one secondary button. */
  | { kind: "empty"; action?: StateAction }
  /** "No results for ‘…’." and Clear filters. */
  | { kind: "filtered-empty"; query?: string; clear?: () => void }
  | { kind: "ready" }
  /** The C-20 error: a brick tile, "Couldn’t load …", Retry. */
  | { kind: "error"; retry: () => void }
  /** Metadata only, a wall, a role or a gate: no record data, the reason in words. */
  | { kind: "restricted"; reason: ReadOnlyReason }
  /** The T21e grammar: the module is not turned on for this firm. Never a 404. */
  | { kind: "flag-off"; flag: FlagKey };

export type ViewStateKind = ViewState["kind"];

export const VIEW_STATE_KINDS: readonly ViewStateKind[] = [
  "loading",
  "empty",
  "filtered-empty",
  "ready",
  "error",
  "restricted",
  "flag-off",
];

// ---------------------------------------------------------------------------------------------
// Restricted

/**
 * The reasons in words. A wall is never named: a person behind one is told nothing about it, as
 * a hidden record is a 404 to them (DEC-43), so `walled` says only that the record cannot be
 * opened. These lines are inferred; the copy registry (F-05-T32) takes them over.
 */
export const RESTRICTED_COPY: Readonly<Record<ReadOnlyReason, { title: string; body: string }>> = {
  archived: {
    title: "This record is archived.",
    body: "Restore it to see its contents.",
  },
  walled: {
    title: "You can’t open this record.",
    body: "Your account does not have access to it. Ask your firm admin if it should.",
  },
  gate_g2: {
    title: "This record is waiting on a confirmation.",
    body: "Its contents open once the required confirmation is recorded.",
  },
  role: {
    title: "You can see this record’s name and counts only.",
    body: "Its contents open for the people on the engagement.",
  },
  mfa_required: {
    title: "Confirm it’s you to open this.",
    body: "Opening it needs a recent sign-in check.",
  },
  flag_off: {
    title: "This is not turned on for this firm.",
    body: "Your firm admin can turn it on.",
  },
  entitlement: {
    title: "This is not part of this firm’s plan.",
    body: "Your firm admin can review the plan.",
  },
};

export interface RestrictedStateProps {
  reason: ReadOnlyReason;
  /** Replaces the title when the screen knows more ("Ana Cruz must confirm independence"). */
  title?: string;
  /** Replaces the body. Never put record data here. */
  children?: ReactNode;
  /** One action, if the person can do something about it. */
  action?: ReactNode;
  className?: string;
}

/**
 * A closed record (INV-3, ADR-024): a lock tile and the reason in words. It takes no record, so
 * it cannot show one; the templates render it in place of the body and keep their headers.
 */
export function RestrictedState({
  reason,
  title,
  children,
  action,
  className,
}: RestrictedStateProps): JSX.Element {
  const copy = RESTRICTED_COPY[reason];
  return (
    <div data-restricted={reason} className={cn("flex flex-1 flex-col", className)}>
      <EmptyState
        icon="lock"
        title={title ?? copy.title}
        {...(action === undefined ? {} : { action })}
      >
        {children ?? copy.body}
      </EmptyState>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Flag off

/** "office_addins" reads "Office addins"; a screen passes `label` for anything the key spells badly. */
export function flagLabel(flag: FlagKey): string {
  const words = flag
    .replace(/^ff\./, "")
    .split(/[._-]+/u)
    .join(" ")
    .trim();
  return words === "" ? "This" : words.charAt(0).toUpperCase() + words.slice(1);
}

export interface FlagOffStateProps {
  flag: FlagKey;
  /** The module as the product names it: "Insights". Defaults to the key in words. */
  label?: string;
  /** The module's registry icon. */
  icon?: IconName;
  /** One line more, if the screen has one. */
  children?: ReactNode;
  /** One action, such as the way back. */
  action?: ReactNode;
  className?: string;
}

/**
 * A module that is off for this firm (the T21e grammar): a tile and one line, "Insights is not
 * turned on for this firm." It is a state of the view, drawn inside the frame the route already
 * has. Never a 404 and never a blank page.
 */
export function FlagOffState({
  flag,
  label,
  icon = "layers",
  children,
  action,
  className,
}: FlagOffStateProps): JSX.Element {
  return (
    <div data-flag-off={flag} className={cn("flex flex-1 flex-col", className)}>
      <EmptyState
        icon={icon}
        title={`${label ?? flagLabel(flag)} is not turned on for this firm.`}
        {...(action === undefined ? {} : { action })}
      >
        {children}
      </EmptyState>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// The body

/** What an empty body says. The words are the screen's: what will appear and what to do. */
export interface EmptyContent {
  icon?: IconName;
  title: string;
  /** What will appear, and what to do. */
  body?: ReactNode;
  /** A secondary button; `ViewState.empty.action` takes its place when present. */
  action?: ReactNode;
}

export interface ViewStateBodyProps {
  state: ViewState;
  /** The shape of the rows while loading: the same type and height as the loaded rows. */
  rows?: SkeletonType;
  /** A table's grid template, so its skeleton matches its real header. */
  columns?: string;
  /** The column heads. Always drawn, in every mode. */
  head?: ReactNode;
  /** What an empty body says. */
  empty: EmptyContent;
  /** What failed to load, lower case ("sessions"), for "Couldn’t load sessions." */
  noun?: string;
  audience?: "firm" | "portal";
  /** The module's name, when the state is flag-off. */
  flagLabel?: string;
  flagIcon?: IconName;
  /** Draw the skeleton at once (a forced state, a test). */
  immediate?: boolean;
  /** The reduced-motion form whatever the preference. */
  still?: boolean;
  className?: string;
  /**
   * The loaded body. A function is called only for `ready`, so a restricted or switched-off view
   * never builds it.
   */
  children?: ReactNode | (() => ReactNode);
}

/**
 * The body of a template for any `ViewState` (C-20). The header and `head` stay; the body is a
 * skeleton, an empty state, the error, a restricted notice, the flag-off line, or the content.
 * It fills the space under the head in every mode (`flex-1`), so the frame never changes size.
 * Only `ready` renders `children`: that is what keeps restricted free of record data.
 */
export function ViewStateBody({
  state,
  rows = "list",
  columns,
  head,
  empty,
  noun,
  audience = "firm",
  flagLabel: flagName,
  flagIcon,
  immediate = false,
  still = false,
  className,
  children,
}: ViewStateBodyProps): JSX.Element {
  let body: ReactNode;
  switch (state.kind) {
    case "loading":
      body = (
        <SkeletonRows
          type={rows}
          immediate={immediate}
          still={still}
          {...(columns === undefined ? {} : { columns })}
        />
      );
      break;
    case "empty": {
      const action =
        state.action === undefined ? (
          empty.action
        ) : (
          <Button variant="secondary" size="md" onClick={state.action.onSelect}>
            {state.action.label}
          </Button>
        );
      body = (
        <EmptyState
          title={empty.title}
          {...(empty.icon === undefined ? {} : { icon: empty.icon })}
          {...(action === undefined ? {} : { action })}
        >
          {empty.body}
        </EmptyState>
      );
      break;
    }
    case "filtered-empty":
      body = (
        <EmptyState
          icon="search"
          title={state.query === undefined ? "No results." : `No results for ‘${state.query}’.`}
          link={
            <EmptyLink {...(state.clear === undefined ? {} : { onClick: state.clear })}>
              Clear filters
            </EmptyLink>
          }
        />
      );
      break;
    case "error":
      body = (
        <ErrorState
          audience={audience}
          onRetry={state.retry}
          {...(noun === undefined ? {} : { noun })}
        />
      );
      break;
    case "restricted":
      body = <RestrictedState reason={state.reason} />;
      break;
    case "flag-off":
      body = (
        <FlagOffState
          flag={state.flag}
          {...(flagName === undefined ? {} : { label: flagName })}
          {...(flagIcon === undefined ? {} : { icon: flagIcon })}
        />
      );
      break;
    case "ready":
      body = typeof children === "function" ? children() : children;
      break;
  }
  return (
    <div data-view-state={state.kind} className={cn("flex min-h-0 flex-1 flex-col", className)}>
      {head}
      <div className="relative flex min-h-0 flex-1 flex-col overflow-y-auto">{body}</div>
    </div>
  );
}
