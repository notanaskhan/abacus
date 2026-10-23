import { type JSX, type ReactNode, useState } from "react";
import { cn } from "../cn";
import { PRESS } from "../components/control-classes";
import { Pill } from "../components/pill";
import { Segmented, type Opt } from "../components/tabs";
import { SyncChip } from "../components/status";
import { Icon, type IconName } from "../icons";
import type { PillVariant, RegistryCode } from "../status";

// The RecordHeader (C-00 Shell Kit spec 04; F-05-T18): the bar under the toolbar on the shell
// ground, no fill and no border. Four variants:
//
//   default   42  Checkpoints, the sync chip, the title block, Assistant      tax returns, records
//   audit     59  back chip, the title block, Auto mode and the layout chip   audit cockpit
//   close     42 + 50  client · Close · period stepper, then Back and Segmented   monthly close
//   settings  42  Back, the title block, a slot on the right                  TPL-12, ADM-*
//
// The title block is centred on the window, whatever sits left and right of it. Plan 04 4.5 rule
// 5 says chrome takes slots, so `left` and `right` replace a variant's clusters when given.

/** The sync chip's states are the status registry's (return_sync_chip). */
export type SyncCode = RegistryCode<"return_sync_chip">;

export type RecordHeaderVariant = "default" | "audit" | "close" | "settings";

interface Common {
  /** The record's name; the client's for the close variant. */
  title: string;
  /** "A · B" is drawn as separate ink-2 runs with ink-4 separators. */
  context?: string | undefined;
  /** The amber state pill ("Working", "Planning", "In review · Partner"). Empty hides it. */
  state?: string | undefined;
  /** Replaces the variant's left cluster. */
  left?: ReactNode;
  /** Replaces the variant's right cluster. */
  right?: ReactNode;
  className?: string;
}

export interface DefaultRecordHeaderProps extends Common {
  variant?: "default";
  /** The Checkpoints chip. Default true. */
  checkpoints?: boolean;
  /** Its drawer is open. */
  checkpointsPressed?: boolean;
  onCheckpoints?: () => void;
  /** The sync chip's state; null hides it. Default `synced`. */
  sync?: SyncCode | null;
  /** "Mon D" of the last successful export or import, for `synced`. */
  syncDate?: string;
  onSync?: () => void;
  /** The Assistant chip. Default true. */
  assistant?: boolean;
  onAssistant?: () => void;
}

export interface AuditRecordHeaderProps extends Common {
  variant: "audit";
  backLabel?: string;
  onBack?: () => void;
  /** The methodology chip before the state pill. */
  chip?: string;
  onChip?: () => void;
  /** 13px ink-3 text before "Auto mode" ("Started 9:24 AM"). */
  meta?: string;
  /** Auto mode, default on. */
  autoMode?: boolean;
  onAutoMode?: (on: boolean) => void;
  onLayout?: () => void;
}

export interface CloseRecordHeaderProps extends Common {
  variant: "close";
  /** The periods, oldest first. The stepper shows the last and steps back, wrapping. */
  periods: readonly string[];
  period?: string;
  onPeriod?: (period: string) => void;
  tabs: readonly Opt[];
  activeTab?: string;
  onTab?: (label: string) => void;
  /** The tablist's accessible name. */
  tabsLabel?: string;
  onBack?: () => void;
  backLabel?: string;
}

export interface SettingsRecordHeaderProps extends Common {
  variant: "settings";
  /** The state pill's variant when it is a record status rather than the amber work state (a
   * binder reads Draft neutral, Published state, Complete green-tint). Default amber. */
  stateTone?: PillVariant;
  backLabel?: string;
  onBack?: () => void;
}

export type RecordHeaderProps =
  | DefaultRecordHeaderProps
  | AuditRecordHeaderProps
  | CloseRecordHeaderProps
  | SettingsRecordHeaderProps;

// ---- Parts ------------------------------------------------------------------------------------

// A white chip: 29 high, 13px, e1 (the ring), `nested` on hover; pressed (its drawer is open) is
// `sel-bg` at weight 500 with no shadow.
const CHIP = cn(
  "inline-flex h-[29px] flex-none items-center gap-[6px] rounded-pill bg-card pr-[9px] pl-[10px] text-body text-ink shadow-e1",
  "hover:bg-nested data-[force=hover]:bg-nested",
  "aria-pressed:bg-sel-bg aria-pressed:font-medium aria-pressed:shadow-none",
);

function Chip({
  icon,
  chevron = false,
  pressed,
  className,
  children,
  ...props
}: {
  icon?: IconName;
  chevron?: boolean;
  pressed?: boolean;
  className?: string;
  children?: ReactNode;
  onClick?: (() => void) | undefined;
  "aria-label"?: string;
}): JSX.Element {
  return (
    <button
      type="button"
      {...(pressed === undefined ? {} : { "aria-pressed": pressed })}
      className={cn(CHIP, PRESS, className)}
      {...props}
    >
      {icon !== undefined && <Icon name={icon} size={14} />}
      {children}
      {chevron && <Icon name="chevron-down" size={12} className="text-ink-3" />}
    </button>
  );
}

function Back({
  label,
  onClick,
}: {
  label: string;
  onClick?: (() => void) | undefined;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className="absolute top-1/2 left-(--edge-app) inline-flex -translate-y-1/2 items-center gap-[3px] py-1 pr-1.5 text-tab text-ink"
    >
      <Icon name="chevron-left" size={14} className="text-ink-3" />
      {label}
    </button>
  );
}

/** The title, its context runs and the state pill, centred on the window. */
function Centre({
  title,
  context,
  state,
  chip,
  onChip,
  tone = "amber",
}: Pick<Common, "title" | "context" | "state"> & {
  chip?: string | undefined;
  onChip?: (() => void) | undefined;
  tone?: PillVariant | undefined;
}): JSX.Element {
  const parts = context === undefined || context === "" ? [] : context.split(" · ");
  return (
    <div className="absolute top-1/2 left-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center gap-[8px] text-title tracking-[-0.012em] whitespace-nowrap">
      <span className="font-medium text-ink">{title}</span>
      {parts.map((part, i) => (
        <span key={`${part}:${String(i)}`} className="contents">
          {i > 0 && (
            <span aria-hidden="true" className="text-ink-4">
              ·
            </span>
          )}
          <span className="text-ink-2">{part}</span>
        </span>
      ))}
      {chip !== undefined && (
        <Chip icon="notebook-text" onClick={onChip} className="pr-[11px] text-body">
          {chip}
        </Chip>
      )}
      {state !== undefined && state !== "" && (
        <Pill variant={tone} size="state">
          {state}
        </Pill>
      )}
    </div>
  );
}

/** The Auto mode switch (36 by 21): a `switch` that slides a 17px knob over 220ms. */
function AutoSwitch({
  on,
  onChange,
}: {
  on: boolean;
  onChange: (on: boolean) => void;
}): JSX.Element {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label="Auto mode"
      onClick={() => {
        onChange(!on);
      }}
      className={cn(
        "relative inline-block h-[21px] w-[36px] flex-none rounded-pill forced-edge",
        "transition-[background-color] duration-[180ms]",
        on ? "bg-green" : "bg-surface-deep",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "absolute top-[2px] size-[17px] rounded-full bg-card shadow-lift transition-[left] duration-[220ms] ease-out",
          on ? "left-[17px]" : "left-[2px]",
        )}
      />
    </button>
  );
}

// ---- RecordHeader -----------------------------------------------------------------------------

const ROW = "relative flex flex-none items-center gap-[8px] px-(--edge-app)";

export function RecordHeader(props: RecordHeaderProps): JSX.Element {
  switch (props.variant) {
    case "audit":
      return <AuditHeader {...props} />;
    case "close":
      return <CloseHeader {...props} />;
    case "settings":
      return <SettingsHeader {...props} />;
    default:
      return <DefaultHeader {...props} />;
  }
}

function DefaultHeader({
  title,
  context,
  state,
  left,
  right,
  className,
  checkpoints = true,
  checkpointsPressed = false,
  onCheckpoints,
  sync = "synced",
  syncDate,
  onSync,
  assistant = true,
  onAssistant,
}: DefaultRecordHeaderProps): JSX.Element {
  return (
    <div
      data-shell="record-header"
      data-variant="default"
      className={cn(ROW, "h-(--subbar-h)", className)}
    >
      {left ?? (
        <>
          {checkpoints && (
            <Chip icon="history" chevron pressed={checkpointsPressed} onClick={onCheckpoints}>
              Checkpoints
            </Chip>
          )}
          {sync !== null && (
            <SyncChip
              code={sync}
              {...(syncDate === undefined ? {} : { vars: { date: syncDate } })}
              {...(onSync === undefined ? {} : { onClick: onSync })}
            />
          )}
        </>
      )}
      <Centre title={title} context={context} state={state} />
      {right ??
        (assistant && (
          <Chip icon="message-circle" onClick={onAssistant} className="ml-auto pr-[11px]">
            Assistant
          </Chip>
        ))}
    </div>
  );
}

function AuditHeader({
  title,
  context,
  state,
  left,
  right,
  className,
  backLabel = "All Audits",
  onBack,
  chip,
  onChip,
  meta,
  autoMode = true,
  onAutoMode,
  onLayout,
}: AuditRecordHeaderProps): JSX.Element {
  const [on, setOn] = useState(autoMode);
  const [seen, setSeen] = useState(autoMode);
  if (seen !== autoMode) {
    setSeen(autoMode);
    setOn(autoMode);
  }
  return (
    <div
      data-shell="record-header"
      data-variant="audit"
      className={cn(ROW, "h-(--auditbar-h)", className)}
    >
      {left ?? (
        <Chip onClick={onBack} className="px-[12px]">
          {backLabel}
        </Chip>
      )}
      <Centre title={title} context={context} state={state} chip={chip} onChip={onChip} />
      {right ?? (
        <div className="ml-auto flex items-center gap-[8px]">
          {meta !== undefined && <span className="mr-[8px] text-body text-ink-3">{meta}</span>}
          <span className="text-body text-ink-2">Auto mode</span>
          <AutoSwitch
            on={on}
            onChange={(next) => {
              setOn(next);
              onAutoMode?.(next);
            }}
          />
          <Chip
            icon="layout-grid"
            chevron
            aria-label="Layout"
            onClick={onLayout}
            className="gap-[5px]"
          />
        </div>
      )}
    </div>
  );
}

function CloseHeader({
  title,
  context = "Close",
  left,
  right,
  className,
  periods,
  period,
  onPeriod,
  tabs,
  activeTab,
  onTab,
  tabsLabel = "Sections",
  onBack,
  backLabel = "Back",
}: CloseRecordHeaderProps): JSX.Element {
  const last = Math.max(periods.length - 1, 0);
  const [index, setIndex] = useState(last);
  const current = period ?? periods[index] ?? "";
  const step = (): void => {
    const at = periods.indexOf(current);
    const from = at < 0 ? index : at;
    const next = (from - 1 + periods.length) % periods.length;
    setIndex(next);
    const label = periods[next];
    if (label !== undefined) onPeriod?.(label);
  };
  return (
    <div
      data-shell="record-header"
      data-variant="close"
      className={cn("flex flex-none flex-col", className)}
    >
      <div
        data-row="line"
        className="flex h-(--subbar-h) flex-none items-center justify-center gap-[8px] text-title tracking-[-0.012em] whitespace-nowrap"
      >
        {left}
        <span className="font-medium text-ink">{title}</span>
        <span aria-hidden="true" className="text-ink-4">
          ·
        </span>
        <span className="text-ink-2">{context}</span>
        <span aria-hidden="true" className="text-ink-4">
          ·
        </span>
        <button
          type="button"
          title="Change period"
          aria-label={`Change period, ${current}`}
          onClick={step}
          className="inline-flex items-center gap-[4px] rounded-pill text-ink-2"
        >
          {current}
          <Icon name="chevrons-up-down" size={12} className="text-ink-3" />
        </button>
        {right}
      </div>
      <div
        data-row="tabs"
        className="relative flex h-(--tabs-h) flex-none items-center justify-center"
      >
        <Back label={backLabel} onClick={onBack} />
        <Segmented
          options={tabs}
          label={tabsLabel}
          {...(activeTab === undefined ? {} : { active: activeTab })}
          {...(onTab === undefined ? {} : { onChange: onTab })}
        />
      </div>
    </div>
  );
}

function SettingsHeader({
  title,
  context,
  state,
  left,
  right,
  className,
  backLabel = "Back",
  onBack,
  stateTone,
}: SettingsRecordHeaderProps): JSX.Element {
  return (
    <div
      data-shell="record-header"
      data-variant="settings"
      className={cn(ROW, "h-(--subbar-h)", className)}
    >
      {left ?? <Back label={backLabel} onClick={onBack} />}
      <Centre title={title} context={context} state={state} tone={stateTone} />
      {right !== undefined && <div className="ml-auto flex items-center gap-[8px]">{right}</div>}
    </div>
  );
}
