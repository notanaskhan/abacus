import { Check, RefreshCw, TriangleAlert, X } from "lucide-react";
import type { ButtonHTMLAttributes, HTMLAttributes, JSX, ReactNode } from "react";
import { cn } from "../cn";
import {
  DISC_LABEL,
  type DiscSize,
  type DiscState,
  type LineTone,
  type PillSize,
  type PillVariant,
  type RegistryCode,
  type RegistryContext,
  type RegistryObject,
  type StatusDomain,
  type SyncGlyph,
  status,
  statusWord,
} from "../status";
import { Pill, type PillProps, PillBody, Ring, pillClasses } from "./pill";
import type { Tone } from "./surfaces";

// The Status kit (C-06; F-05-T12). Pills, discs, the sub-line beside a disc, the sync chip, ticks
// and the tally pill. Every word, tone and disc comes from status() over the C2 registry; nothing
// here chooses a status colour by hand. Words plus colour, never colour alone. DEC-124: a pill is
// radius 999 (`rounded-pill`), the same token the controls take. The pill itself (variants, sizes,
// the ring) is components/pill.tsx; StatusPill is Pill plus the earlier `tone` prop and the sync
// chip's glyph. Classes are joined with cn(), which knows the type roles (F-05-T14), so a caller's
// class overrides the kit's.

// ---- Pills -------------------------------------------------------------------------------------

// A tone from before the kit reads as the variant that looks nearest to it.
const TONE_VARIANT: Record<Tone, PillVariant> = {
  neutral: "neutral",
  success: "green-tint",
  warning: "amber",
  danger: "red-tint",
  info: "amber",
};

export interface StatusPillProps extends Omit<PillProps, "lead" | "children"> {
  /** A tone from before the kit: success, warning, danger, info, neutral. Prefer `variant`. */
  tone?: Tone;
  /** The sync chip's leading glyph. */
  glyph?: SyncGlyph;
  /** The word. One to three words, no uppercase. */
  children: ReactNode;
}

function Glyph({ glyph }: { glyph: SyncGlyph }): JSX.Element {
  switch (glyph) {
    case "refresh":
      return <RefreshCw aria-hidden="true" size={13} strokeWidth={1.8} className="text-amber" />;
    case "spin":
      return <Ring size={12} width={1.4} track="stroke-rule" className="text-ink-2" />;
    case "synced":
      return <StatusDisc state="done" size={13} />;
    case "out":
      return (
        <TriangleAlert aria-hidden="true" size={13} strokeWidth={1.8} className="text-amber" />
      );
    case "pending":
      return <span aria-hidden="true" className="size-[8px] rounded-full bg-amber" />;
    case "failed":
      return <StatusDisc state="fail" size={13} />;
  }
}

/** A state as a pill (C-06): the word on its variant's colours at one of the kit's sizes. The
 * pieces that are not words are the check and the spinner only. A `Pill` that also reads the
 * earlier `tone` prop and draws the sync chip's glyph. */
export function StatusPill({
  variant,
  tone,
  glyph,
  children,
  ...props
}: StatusPillProps): JSX.Element {
  const resolved = variant ?? TONE_VARIANT[tone ?? "neutral"];
  return (
    <Pill
      variant={resolved}
      {...(glyph === undefined ? {} : { lead: <Glyph glyph={glyph} /> })}
      {...props}
    >
      {children}
    </Pill>
  );
}

// ---- Discs -------------------------------------------------------------------------------------

const DISC_BOX: Record<DiscSize, string> = {
  13: "size-[13px]",
  15: "size-[15px]",
  16: "size-[16px]",
  17: "size-[17px]",
};

/** The glyph inside a disc: 8 at 13 and under, 9 at 15 and 16, 10 at 17. */
function discGlyphSize(size: DiscSize): number {
  if (size >= 17) return 10;
  return size <= 13 ? 8 : 9;
}

export interface StatusDiscProps {
  state: DiscState;
  /** 13 in issue rows, 15 in rows and rails (the default), 17 in task rows. */
  size?: DiscSize;
  className?: string;
}

/** A status disc (C-06): nine states, always next to words, in one left-aligned column. */
export function StatusDisc({ state, size = 15, className }: StatusDiscProps): JSX.Element {
  const glyph = discGlyphSize(size);
  const label = DISC_LABEL[state];
  const box = cn("inline-flex shrink-0 items-center justify-center", DISC_BOX[size], className);
  const round = cn(box, "rounded-full");
  switch (state) {
    case "done":
      return (
        <span role="img" aria-label={label} className={cn(round, "bg-green text-on-dark")}>
          <Check aria-hidden="true" size={glyph} strokeWidth={1.9} />
        </span>
      );
    case "prepared":
      return (
        <span
          role="img"
          aria-label={label}
          className={cn(round, "text-ink-3 inset-ring-[1.3px] inset-ring-ink-4")}
        >
          <Check aria-hidden="true" size={glyph} strokeWidth={1.9} />
        </span>
      );
    case "todo":
      return (
        <span
          role="img"
          aria-label={label}
          className={cn(round, "inset-ring-[1.3px] inset-ring-ink-4")}
        />
      );
    case "half": {
      const mid = size / 2;
      return (
        <span role="img" aria-label={label} className={box}>
          <svg
            aria-hidden="true"
            width={size}
            height={size}
            viewBox={`0 0 ${String(size)} ${String(size)}`}
          >
            <path
              d={`M ${String(mid)} 0 A ${String(mid)} ${String(mid)} 0 0 0 ${String(mid)} ${String(size)} Z`}
              className="fill-ink"
            />
            <circle
              cx={mid}
              cy={mid}
              r={(size - 1.4) / 2}
              fill="none"
              className="stroke-ink-2"
              strokeWidth={1.4}
            />
          </svg>
        </span>
      );
    }
    case "run":
      return (
        <span role="img" aria-label={label} className={box}>
          <Ring size={size} width={1.5} track="stroke-chip" rotate={-140} className="text-ink-2" />
        </span>
      );
    case "warn":
      return (
        <span role="img" aria-label={label} className={cn(box, "text-amber")}>
          <TriangleAlert aria-hidden="true" size={size} strokeWidth={2} />
        </span>
      );
    case "fail":
      return (
        <span role="img" aria-label={label} className={cn(round, "bg-red text-on-dark")}>
          <X aria-hidden="true" size={glyph} strokeWidth={1.9} />
        </span>
      );
    case "off":
      return (
        <span role="img" aria-label={label} className={cn(round, "bg-ink-4 text-on-dark")}>
          <X aria-hidden="true" size={glyph} strokeWidth={1.9} />
        </span>
      );
    case "wait":
      return <span role="img" aria-label={label} className={cn(round, "bg-amber")} />;
  }
}

// ---- The line beside a disc -------------------------------------------------------------------

const LINE: Record<LineTone, string> = {
  text: "text-ink-3",
  "text-amber": "text-amber-ink",
};

export interface SubLineProps extends Omit<HTMLAttributes<HTMLSpanElement>, "children"> {
  /** Ink-3, or amber ink for a line that wants a person. */
  tone?: LineTone;
  /** The disc before the line. */
  disc?: DiscState;
  discSize?: DiscSize;
  bold?: boolean;
  children: ReactNode;
}

/** A status as a disc and an 11.5px line, not a pill (C-06 `text` and `text-amber`): the queued
 * ring with its ink-3 words, "Blocked on a Partner decision" in amber ink. */
export function SubLine({
  tone = "text",
  disc,
  discSize,
  bold,
  className,
  children,
  ...props
}: SubLineProps): JSX.Element {
  return (
    <span
      className={cn("inline-flex items-center gap-[6px] text-meta", LINE[tone], className)}
      {...props}
    >
      {disc !== undefined && (
        <StatusDisc state={disc} {...(discSize === undefined ? {} : { size: discSize })} />
      )}
      <span className={cn(bold === true && "font-medium")}>{children}</span>
    </span>
  );
}

// ---- The sync chip ----------------------------------------------------------------------------

export interface SyncChipProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** A return sync state: `synced`, `out_of_sync`, `failed` and the rest. */
  code: RegistryCode<"return_sync_chip">;
  /** Where it is shown (`tile` reads "Ready"). */
  context?: RegistryContext;
  /** Fills `{date}` in "Synced {date}". */
  vars?: Readonly<Record<string, string | number>>;
}

/** The record header's sync chip (C-00, C-06): white, 29 high, a glyph, the word and a chevron.
 * Every state is the same white chip; only the glyph changes. A button when it has an action,
 * otherwise plain text. */
export function SyncChip({
  code,
  context,
  vars,
  className,
  onClick,
  type = "button",
  ...props
}: SyncChipProps): JSX.Element {
  const resolved = status("return_sync_chip", code, {
    ...(context === undefined ? {} : { context }),
    ...(vars === undefined ? {} : { vars }),
  });
  const classes = pillClasses("outline", "chip", className);
  const body = (
    <PillBody
      size="chip"
      lead={resolved.glyph === null ? undefined : <Glyph glyph={resolved.glyph} />}
    >
      {resolved.label}
    </PillBody>
  );
  if (onClick === undefined) {
    return (
      <span className={classes} data-code={code}>
        {body}
      </span>
    );
  }
  return (
    <button type={type} onClick={onClick} className={classes} data-code={code} {...props}>
      {body}
    </button>
  );
}

// ---- Marks ------------------------------------------------------------------------------------

/** The tickmarks of a workpaper cell. "MS" and "Received" are agreed-to-source ticks: micro green.
 * F, CF and PY are micro neutral. A bare check is an ink-3 glyph. */
export type TickCode = "MS" | "Received" | "check" | "F" | "CF" | "PY";

export function Tick({ code }: { code: TickCode }): JSX.Element {
  if (code === "check") {
    return (
      <span role="img" aria-label="Agreed" className="inline-flex text-ink-3">
        <Check aria-hidden="true" size={11} strokeWidth={2} />
      </span>
    );
  }
  const green = code === "MS" || code === "Received";
  return (
    <StatusPill variant={green ? "green" : "neutral"} size="micro" check={green}>
      {code}
    </StatusPill>
  );
}

export interface TallyPillProps {
  /** `tie`, `off`, `check`, `pending`, `reconciled` or `ties_once_posted`. */
  code: RegistryCode<"tie_out_tally">;
  /** Fills `{amount}` in "off {amount}". */
  vars?: Readonly<Record<string, string | number>>;
}

/** A tie-out tally on the tally strip (C-06): tie in green, off and check in amber, pending muted.
 * Its words come from the registry. */
export function TallyPill({ code, vars }: TallyPillProps): JSX.Element {
  const resolved = status("tie_out_tally", code, vars === undefined ? {} : { vars });
  if (resolved.variant === null) {
    const beside = resolved.disc === null ? {} : { disc: resolved.disc.state };
    return (
      <SubLine tone={resolved.line} {...beside}>
        {resolved.label}
      </SubLine>
    );
  }
  return (
    <StatusPill variant={resolved.variant} size="tally">
      {resolved.label}
    </StatusPill>
  );
}

// ---- A state from the registry ----------------------------------------------------------------

export interface RegistryStatusProps<O extends RegistryObject> {
  object: O;
  code: RegistryCode<O>;
  /** Where it is shown, when the registry words it differently there. */
  context?: RegistryContext;
  /** The client portal's wording. */
  client?: boolean;
  /** Fills `{date}`, `{n}` and the other placeholders. */
  vars?: Readonly<Record<string, string | number>>;
  /** Draw the disc the registry gives the state (default). */
  withDisc?: boolean;
  /** Override the size C-06 gives the object. */
  size?: PillSize;
}

/** A state as the kit draws it: a disc if the registry gives one, then a pill, or a line beside the
 * disc when the registry gives no pill variant. The one component screens use for a registry state. */
export function RegistryStatus<O extends RegistryObject>({
  object,
  code,
  context,
  client,
  vars,
  withDisc = true,
  size,
}: RegistryStatusProps<O>): JSX.Element {
  const resolved = status(object, code, {
    ...(context === undefined ? {} : { context }),
    ...(client === undefined ? {} : { client }),
    ...(vars === undefined ? {} : { vars }),
  });
  if (resolved.glyph !== null) {
    return (
      <SyncChip
        code={code as RegistryCode<"return_sync_chip">}
        {...(context === undefined ? {} : { context })}
        {...(vars === undefined ? {} : { vars })}
      />
    );
  }
  const disc = withDisc ? resolved.disc : null;
  if (resolved.variant === null) {
    const beside = disc === null ? {} : { disc: disc.state, discSize: disc.size };
    return (
      <SubLine tone={resolved.line} bold={resolved.bold} {...beside}>
        {resolved.label}
      </SubLine>
    );
  }
  const pill = (
    <StatusPill
      variant={resolved.variant}
      size={size ?? resolved.size}
      check={resolved.check}
      bold={resolved.bold}
    >
      {resolved.label}
    </StatusPill>
  );
  if (disc === null) return pill;
  return (
    <span className="inline-flex items-center gap-[6px]">
      <StatusDisc state={disc.state} size={disc.size} />
      {pill}
    </span>
  );
}

// ---- The earlier components -------------------------------------------------------------------

/** A legacy state (the TASK-101 request, workpaper and result codes) as a pill. */
export function Status({ domain, value }: { domain: StatusDomain; value: string }): JSX.Element {
  const word = statusWord(domain, value);
  return <StatusPill tone={word.tone}>{word.label}</StatusPill>;
}
