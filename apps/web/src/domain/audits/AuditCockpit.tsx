import type { AuditCockpitOut, AuditSectionRowOut } from "@abacus/api-client";
import { type CockpitCanvas, RecordCockpit } from "@abacus/ui";
import { type JSX, useState } from "react";
import { type AuditBarOptions, auditBarProps } from "./AuditBar";
import { type DockHostOptions, dockHost } from "./DockHost";
import { SectionRail } from "./SectionRail";

// The audit cockpit host (A-01-T06; AUD-02, AUD-03, and every later AUD screen): F-05's T2
// RecordCockpit with the audit bar, the registered section rail and the dock host, from one cockpit
// projection. The canvas is the screen's (Source Documents, a workpaper, BlockedSectionCard). The
// layout chip shows or hides the dock in both bar variants.

export interface AuditCockpitProps {
  cockpit: AuditCockpitOut;
  canvas: CockpitCanvas;
  /** The selected rail row (`?section=`). */
  section?: string;
  onSection?: (row: AuditSectionRowOut) => void;
  onBegin?: (row: AuditSectionRowOut) => void;
  bar?: Omit<AuditBarOptions, "onLayout">;
  dock?: DockHostOptions;
  /** Inside the firm shell (a routed screen) the toolbar is the shell's. */
  embedded?: boolean;
}

export function AuditCockpit({
  cockpit,
  canvas,
  section,
  onSection,
  onBegin,
  bar = {},
  dock = {},
  embedded = true,
}: AuditCockpitProps): JSX.Element {
  const [open, setOpen] = useState(true);
  const processing = cockpit.audit_bar.run_started_at != null;
  const host = dockHost(cockpit, { ...(processing ? { live: true } : {}), ...dock });
  const record = auditBarProps(cockpit, {
    ...bar,
    onLayout: () => {
      setOpen((was) => !was);
    },
  });
  return (
    <RecordCockpit
      embedded={embedded}
      record={record}
      rail={
        <SectionRail
          cockpit={cockpit}
          processing={processing}
          {...(section === undefined ? {} : { selected: section })}
          {...(onSection === undefined ? {} : { onOpen: onSection })}
          {...(onBegin === undefined ? {} : { onBegin })}
        />
      }
      canvas={canvas}
      {...(host === undefined ? {} : { dock: host })}
      dockOpen={open}
      onDockOpenChange={setOpen}
    />
  );
}
