import type { EngagementExportOut } from "@abacus/api-client";
import { Button, Checkbox, SheetModal, StatusPill, bytes, status, toast } from "@abacus/ui";
import { type JSX, useState } from "react";
import {
  downloadBundle,
  errorCode,
  expiryLabel,
  needsStepUp,
  useExportActions,
  useExportHistory,
  useExportStatus,
} from "./exports";
import { AUDIT_MESSAGES } from "./messages";
import { RevealStepUp } from "./reveal";

// The O3 export sheet (A-01-T24; DV-9: composed from kits, no artboard; DEC-541). "Export binder…"
// opens it (`?ov=export`, or `?ov=export:<exportId>` on one export). Export asks the API with an
// Idempotency-Key; a stale second factor opens the shell's step-up; the 10-second Undo toast
// voids the grant (P-35). While open the sheet polls the export every 3 s: Queued, Packaging…,
// Ready ("Download · 12 files · 1.2 MB · expires Mon Sep 21"), Export failed, Expired, Undone (C2
// words). Download streams through the API; its own refusals (410 expired) read in words.

const W = AUDIT_MESSAGES.export;

export interface ExportSheetProps {
  workItemId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** `?ov=export:<exportId>`: the export the sheet follows. */
  exportId?: string | null;
  /** The person holds `export.create` on the work item (`allowed_actions`). */
  canExport: boolean;
}

function readyLabel(view: EngagementExportOut): string {
  return W.download(
    view.file_count ?? 0,
    bytes(view.size_bytes ?? 0),
    view.expires_at == null ? "" : expiryLabel(view.expires_at),
  );
}

function Detail({ view }: { view: EngagementExportOut }): JSX.Element | null {
  if (view.status === "failed" && view.failure_code != null) {
    return <p className="text-meta text-ink-3">{W.failure[view.failure_code]}</p>;
  }
  if (view.status === "expired" && view.void_reason != null) {
    return <p className="text-meta text-ink-3">{W.voided[view.void_reason]}</p>;
  }
  if (view.status === "queued" || view.status === "packaging") {
    return <p className="text-meta text-ink-3">{W.building}</p>;
  }
  return null;
}

function Current({
  view,
  onDownload,
  downloading,
}: {
  view: EngagementExportOut;
  onDownload: () => void;
  downloading: boolean;
}): JSX.Element {
  const word = status("engagement_export", view.status);
  return (
    <section data-export={view.status} className="flex flex-col gap-[8px]">
      <div className="flex items-center gap-[8px]">
        <StatusPill variant={word.variant ?? "neutral"}>{word.label}</StatusPill>
      </div>
      <Detail view={view} />
      {view.status === "ready" && (view.allowed_actions ?? []).includes("download") && (
        <Button
          variant="primary"
          size="md"
          icon="download"
          disabled={downloading}
          onClick={onDownload}
        >
          {readyLabel(view)}
        </Button>
      )}
    </section>
  );
}

export function ExportSheet({
  workItemId,
  open,
  onOpenChange,
  exportId = null,
  canExport,
}: ExportSheetProps): JSX.Element {
  const [followed, setFollowed] = useState<string | null>(exportId);
  const [unaccepted, setUnaccepted] = useState(false);
  const [trail, setTrail] = useState(true);
  const [stepUp, setStepUp] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const actions = useExportActions(workItemId);
  const history = useExportHistory(workItemId, open);
  const current = followed ?? exportId ?? history.data?.items[0]?.id ?? null;
  const status = useExportStatus(current, open);

  const start = async (): Promise<void> => {
    setProblem(null);
    try {
      const view = await actions.create({
        include_unaccepted: unaccepted,
        include_audit_trail: trail,
      });
      setFollowed(view.id);
      toast.undoable({
        text: W.requested,
        undo: () => {
          void actions.undo(view.id).catch((error: unknown) => {
            toast.show({ kind: "error", text: W.problem(errorCode(error)) });
          });
        },
      });
    } catch (error) {
      if (needsStepUp(error)) setStepUp(true);
      else setProblem(W.problem(errorCode(error)));
    }
  };

  const download = async (id: string): Promise<void> => {
    setProblem(null);
    setDownloading(true);
    try {
      await downloadBundle(id);
    } catch (error) {
      if (needsStepUp(error)) setStepUp(true);
      else setProblem(W.problem(errorCode(error)));
    } finally {
      setDownloading(false);
      void status.refetch();
    }
  };

  const view = status.data;
  return (
    <>
      <SheetModal
        open={open}
        onOpenChange={onOpenChange}
        title={W.title}
        description={W.description}
        footer={
          canExport ? (
            <div className="flex w-full items-center gap-[8px]">
              <span className="text-meta text-ink-3">{W.footer}</span>
              <span className="ml-auto flex items-center gap-[8px]">
                <Button
                  variant="ghost"
                  size="md"
                  onClick={() => {
                    onOpenChange(false);
                  }}
                >
                  {W.cancel}
                </Button>
                <Button
                  variant="primary"
                  size="md"
                  disabled={actions.creating}
                  onClick={() => void start()}
                >
                  {W.export}
                </Button>
              </span>
            </div>
          ) : undefined
        }
      >
        <div data-export-sheet="" className="flex flex-col gap-[12px]">
          {canExport && (
            <fieldset className="flex flex-col gap-[8px]">
              <legend className="text-body font-medium text-ink">{W.options}</legend>
              <Checkbox
                label={W.includeUnaccepted}
                showLabel
                checked={unaccepted}
                onChange={setUnaccepted}
              />
              <Checkbox label={W.includeTrail} showLabel checked={trail} onChange={setTrail} />
            </fieldset>
          )}
          {view !== undefined && (
            <Current
              view={view}
              downloading={downloading}
              onDownload={() => void download(view.id)}
            />
          )}
          {problem !== null && (
            <p role="alert" className="text-meta text-red-ink">
              {problem}
            </p>
          )}
        </div>
      </SheetModal>
      <RevealStepUp open={stepUp} onOpenChange={setStepUp} />
    </>
  );
}
