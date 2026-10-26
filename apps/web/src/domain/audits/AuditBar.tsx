import type { AuditCockpitOut } from "@abacus/api-client";
import { type AuditRecordHeaderProps, IconButton, RecordHeader, time } from "@abacus/ui";
import type { JSX } from "react";
import { AUDIT_MESSAGES } from "./messages";

// The audit bar (A-01-T06; AUD-02 and AUD-03, 59 px): "All Audits" chip, the centred title with the
// methodology chip, and the right cluster. "Started 9:24 AM" renders only for a C6 engagement run
// (DV-11). The Auto mode toggle renders only when the person holds `engagement_run.auto_mode`
// (A-01 Story 2.1; P-10-T39 provides it): a screen that reads `/v1/me` passes `autoMode` (null
// without the capability, else the switch's value; AUD-02 f, A-01-T31), otherwise the projection's
// non-null `auto_mode` says so. Without it the right cluster is the run time and the layout chip.

export interface AuditBarOptions {
  onBack?: () => void;
  onChip?: () => void;
  /** The switch's value from the caller's `/v1/me` read: null hides it. Undefined falls back to the
   * projection's `auto_mode`. */
  autoMode?: boolean | null;
  onAutoMode?: (on: boolean) => void;
  /** The layout chip: shows or hides the dock. */
  onLayout?: () => void;
}

type BarProps = Omit<AuditRecordHeaderProps, "variant" | "onLayout">;

function started(bar: AuditCockpitOut["audit_bar"]): string | undefined {
  return bar.run_started_at == null ? undefined : AUDIT_MESSAGES.started(time(bar.run_started_at));
}

/** The RecordCockpit's `record` prop for an audit, from the cockpit projection. */
export function auditBarProps(
  cockpit: Pick<AuditCockpitOut, "audit_bar">,
  options: AuditBarOptions = {},
): BarProps {
  const bar = cockpit.audit_bar;
  const meta = started(bar);
  const base: BarProps = {
    title: bar.title,
    backLabel: AUDIT_MESSAGES.back,
    ...(options.onBack === undefined ? {} : { onBack: options.onBack }),
    ...(bar.methodology_label == null ? {} : { chip: bar.methodology_label }),
    ...(options.onChip === undefined ? {} : { onChip: options.onChip }),
  };
  const autoMode = options.autoMode === undefined ? bar.auto_mode : options.autoMode;
  if (autoMode != null) {
    return {
      ...base,
      autoMode,
      ...(meta === undefined ? {} : { meta }),
      ...(options.onAutoMode === undefined ? {} : { onAutoMode: options.onAutoMode }),
    };
  }
  return {
    ...base,
    right: (
      <div data-audit-bar="right" className="ml-auto flex items-center gap-[8px]">
        {meta !== undefined && <span className="mr-[8px] text-body text-ink-3">{meta}</span>}
        <IconButton
          icon="layout-grid"
          label={AUDIT_MESSAGES.layout}
          {...(options.onLayout === undefined ? {} : { onClick: options.onLayout })}
        />
      </div>
    ),
  };
}

/** The audit bar on its own (outside a RecordCockpit). */
export function AuditBar({
  cockpit,
  ...options
}: { cockpit: Pick<AuditCockpitOut, "audit_bar"> } & AuditBarOptions): JSX.Element {
  const props = auditBarProps(cockpit, options);
  return (
    <RecordHeader
      {...props}
      variant="audit"
      {...(options.onLayout === undefined ? {} : { onLayout: options.onLayout })}
    />
  );
}
