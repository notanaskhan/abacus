import type { AuditCockpitOut, AuditEngagementStatus } from "@abacus/api-client";
import { IconButton, Menu, type MenuItem } from "@abacus/ui";
import { type JSX, useState } from "react";
import { ExportSheet } from "./ExportSheet";
import { AUDIT_MESSAGES } from "./messages";
import { RECORDABLE, RecordDialog, type RecordKind } from "./RecordDialogs";

// The cockpit's audit actions (A-01-T24; DV-9): "Export binder…" and the record-mode entries in
// one "···" menu on the canvas header, each shown only when the projection's `allowed_actions`
// holds its action (a metadata-only reader such as Grace Holloway sees none; ADR-024, DEC-20). The
// export sheet (`?ov=export[:<id>]`) and the record dialogs are overlays this hook owns.

export type AuditOverlay =
  { kind: "export"; exportId?: string | null } | { kind: "record"; record: RecordKind } | null;

const RECORD_ACTION = "assurance.record_phase";
const EXPORT_ACTION = "export.create";

function currentPhase(cockpit: AuditCockpitOut): AuditEngagementStatus {
  const phase = cockpit.overview.phase;
  return RECORDABLE.includes(phase) ? phase : "planning";
}

export interface AuditActions {
  /** The "···" menu, or null when the person may do none of these here. */
  menu: JSX.Element | null;
  overlays: JSX.Element;
}

export function useAuditActions(
  cockpit: AuditCockpitOut,
  initial: AuditOverlay = null,
  onOverlay?: (overlay: AuditOverlay) => void,
): AuditActions {
  const [overlay, setOverlayState] = useState<AuditOverlay>(initial);
  const setOverlay = (next: AuditOverlay): void => {
    setOverlayState(next);
    onOverlay?.(next);
  };
  const allowed = new Set(cockpit.allowed_actions ?? []);
  const canExport = allowed.has(EXPORT_ACTION);
  const canRecord = allowed.has(RECORD_ACTION) && cockpit.phase_mode === "recorded";
  const W = AUDIT_MESSAGES;
  const sections: MenuItem[][] = [];
  if (canExport) {
    sections.push([
      {
        label: W.export.entry,
        icon: "download",
        opensDialog: true,
        onSelect: () => {
          setOverlay({ kind: "export" });
        },
      },
    ]);
  }
  if (canRecord) {
    sections.push(
      (["phase", "release", "archive"] as const).map((record) => ({
        label: W.record[record].entry,
        opensDialog: true,
        onSelect: () => {
          setOverlay({ kind: "record", record });
        },
      })),
    );
  }
  const menu =
    sections.length === 0 ? null : (
      <Menu
        label={W.record.menu}
        align="end"
        sections={sections}
        trigger={<IconButton icon="ellipsis" label={W.record.menu} />}
      />
    );
  const overlays = (
    <>
      <ExportSheet
        workItemId={cockpit.work_item_id}
        open={overlay?.kind === "export"}
        onOpenChange={(open) => {
          if (!open) setOverlay(null);
        }}
        exportId={overlay?.kind === "export" ? (overlay.exportId ?? null) : null}
        canExport={canExport}
      />
      <RecordDialog
        kind={overlay?.kind === "record" ? overlay.record : null}
        workItemId={cockpit.work_item_id}
        current={currentPhase(cockpit)}
        onClose={() => {
          setOverlay(null);
        }}
      />
    </>
  );
  return { menu, overlays };
}
