import type { EngineImportOut, EngineSyncEventOut, EngineSyncOut } from "@abacus/api-client";
import {
  approveImportMutation,
  engineSyncOptions,
  exportReturnMutation,
  markExportedMutation,
  rejectImportMutation,
  uploadImportMutation,
} from "@abacus/api-client/query";
import {
  Button,
  Checkbox,
  Dialog,
  FullSheet,
  Icon,
  type IconName,
  Pill,
  StatusDisc,
  SyncChip,
  Tooltip,
  prose,
  date,
  toast,
  useReducedMotion,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useCallback, useEffect, useRef, useState } from "react";
import { useNow } from "../../app-core/clock";
import type { OverlayRenderProps } from "../../app-core/overlays";
import { hrefOf, to } from "../../routes/to";
import { CAUSES, COPY, FIELDS } from "./copy";

// TAX-09 · Tax-engine sync (T-01-T15; docs/screens/TAX-09.md): the sync chip in the return's
// subbar, its O1 popover (Actions, History, Diagnostics, the file-bridge footer) and the O4
// import diff. CCH Axcess is the engine of record and the bridge is a file: Export generates the
// workbook, the person downloads it and marks it exported; Accrued never transmits or files.
//
//   a2 Ready for export (11:20 AM)          a  Exporting… then Synced Sep 16 (the motion)
//   b  Synced Sep 10; Export closed: final approval by Daniel Reyes (BH-TAX-02), a draft K-1
//   c  Out of sync: Accrued changed after the last import, 3 fields
//   d  Diagnostics returned (0 errors · 2 informational)   d2  Export failed (an IP PIN)
//   e  Import pending approval: the V3 diff, per-row Accept, Approve or Reject import
//   +  Not yet exported (non-artboard)
//
// Every chip state is the same white chip; only its glyph changes. The motion follows the
// cch-sync timing (Exporting… for 1,240 ms) and is skipped under reduced motion.

const EXPORTING_MS = 1240;
const UPLOAD_ID = "3f9a5e62-1c4d-4b8e-9f20-7a6b5c4d3e21";
// T-01-T19: an engine import posts the engine's values CSV as the request body. Artboard e opens on
// the fixture's pending import; its handler answers whatever file it is sent.
const SPECIMEN_FILE = "2025I_FeldJ_V3_values.csv";

type Chip = EngineSyncOut["state"];

/** "Form 1040 line 2a, IT-201 lines 20 and 33": a form's lines named once. */
function fieldsOf(keys: readonly string[]): string {
  const forms = new Map<string, string[]>();
  for (const key of keys) {
    const [form = "", line = ""] = (FIELDS[key] ?? key).split(" line ");
    forms.set(form, [...(forms.get(form) ?? []), line]);
  }
  return [...forms.entries()]
    .map(([form, lines]) =>
      lines.length === 1
        ? `${form} line ${lines[0] ?? ""}`
        : `${form} lines ${lines.slice(0, -1).join(", ")} and ${lines.at(-1) ?? ""}`,
    )
    .join(", ");
}

function HistoryRow({
  e,
  now,
  fresh,
}: {
  e: EngineSyncEventOut;
  now: Date;
  fresh?: boolean;
}): JSX.Element {
  const when = fresh === true ? COPY.justNow : date(e.at, { now });
  const version = e.engine_version ?? "";
  let title: string;
  let body: string;
  let glyph: IconName = "download";
  switch (e.kind) {
    case "marked_exported":
    case "export_generated":
      title = COPY.exportedTitle;
      body = `${version} · ${when}`;
      glyph = "upload";
      break;
    case "import_uploaded":
      title = COPY.uploadedTitle;
      body = `${version} · ${when}`;
      break;
    case "changed_after_import":
      title = COPY.changedTitle;
      body = COPY.changedBody((e.field_keys ?? []).length, fieldsOf(e.field_keys ?? []));
      glyph = "triangle-alert";
      break;
    case "diagnostics":
      title = COPY.diagnosticsTitle;
      body = `${version} · ${COPY.diagnosticsBody(e.errors ?? 0, e.informational ?? 0)}`;
      glyph = "info";
      break;
    default:
      title = COPY.importedTitle;
      body = `${version} · ${when}`;
  }
  return (
    <li className="flex items-start gap-[10px] px-[10px] py-[8px]">
      {fresh === true ? <StatusDisc state="done" /> : <Icon name={glyph} size={14} />}
      <span className="flex min-w-0 flex-col">
        <span className="text-body font-medium">{title}</span>
        <span className="truncate text-dense text-ink-2">{body}</span>
      </span>
    </li>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: JSX.Element | JSX.Element[];
}): JSX.Element {
  return (
    <section aria-label={title} className="rounded-[11px] bg-card shadow-e1">
      <h3 className="flex h-[38px] items-center gap-[6px] px-[12px] text-[13.5px] font-medium">
        {title}
        <Icon name="chevron-down" size={12} />
      </h3>
      {children}
    </section>
  );
}

function Item({
  icon,
  title,
  body,
  disabled = false,
  onClick,
}: {
  icon: IconName;
  title: string;
  body: string;
  disabled?: boolean;
  onClick?: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="flex w-full items-start gap-[10px] rounded-[8px] px-[10px] py-[8px] text-left hover:bg-nested disabled:cursor-not-allowed"
    >
      <Icon name={disabled ? "lock" : icon} size={disabled ? 13 : 14} />
      <span className="flex min-w-0 flex-col">
        <span
          className={disabled ? "text-[14px] font-medium text-ink-4" : "text-[14px] font-medium"}
        >
          {title}
        </span>
        <span className="text-dense text-ink-2">{body}</span>
      </span>
    </button>
  );
}

function ImportSheet({
  open,
  onOpenChange,
  found,
  version,
  onDone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  found: EngineImportOut;
  version: string;
  onDone: (approved: boolean) => void;
}): JSX.Element {
  const [accepted, setAccepted] = useState<ReadonlySet<string>>(
    () => new Set(found.rows.map((r) => r.field_key)),
  );
  const approve = useMutation(approveImportMutation());
  const reject = useMutation(rejectImportMutation());
  const may = found.allowed_actions.includes("engine_import.approve");
  return (
    <FullSheet open={open} onOpenChange={onOpenChange} title={COPY.sheetTitle(version)}>
      <div className="flex min-h-0 flex-1 flex-col gap-[10px] p-[12px]">
        <p className="rounded-pane bg-card px-[12px] py-[10px] text-dense text-ink-2 shadow-e1">
          {COPY.summary(found.rows.length)}
        </p>
        <table className="w-full table-fixed text-body">
          <thead>
            <tr className="h-[30px] bg-band-hd text-meta font-medium text-ink-2">
              <th className="w-[360px] px-[12px] text-left">{COPY.columns.field}</th>
              <th className="w-[150px] px-[12px] text-right">{COPY.columns.accrued}</th>
              <th className="w-[150px] px-[12px] text-right">{COPY.columns.engine}</th>
              <th className="px-[12px] text-left">{COPY.columns.cause}</th>
              <th className="w-[70px] px-[12px] text-center">{COPY.columns.accept}</th>
            </tr>
          </thead>
          <tbody>
            {found.rows.map((r) => {
              const name = FIELDS[r.field_key] ?? r.field_key;
              const cause =
                r.cause_code === null ? "" : (CAUSES[r.cause_code]?.(r.cause_facts ?? {}) ?? "");
              return (
                <tr key={r.field_key} className="h-[44px] border-t-[0.5px] border-hair">
                  <td className="px-[12px]">{name}</td>
                  <td className="px-[12px] text-right tabular-nums text-ink-4">
                    {r.accrued === null ? "—" : prose(r.accrued, "whole")}
                  </td>
                  <td className="px-[12px] text-right tabular-nums">
                    {r.engine_display ?? (r.engine === null ? "—" : prose(r.engine, "whole"))}
                  </td>
                  <td className="px-[12px] text-dense text-ink-2">{cause}</td>
                  <td className="px-[12px] text-center">
                    <Checkbox
                      label={COPY.acceptRow(name)}
                      checked={accepted.has(r.field_key)}
                      disabled={!may}
                      onChange={(on) => {
                        setAccepted((prev) => {
                          const next = new Set(prev);
                          if (on) next.add(r.field_key);
                          else next.delete(r.field_key);
                          return next;
                        });
                      }}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="mt-auto flex h-[56px] items-center gap-[10px] border-t-[0.5px] border-hair bg-card px-[12px]">
          <span className="flex-1 text-meta text-ink-3">{COPY.helper}</span>
          <Button
            variant="secondary"
            disabled={!may || reject.isPending}
            onClick={() => {
              reject.mutate(
                {
                  path: { import_id: found.id },
                  body: { reason: COPY.rejectReason, seen_version: 1 },
                },
                {
                  onSuccess: () => {
                    toast.show(COPY.rejectedToast);
                    onDone(false);
                  },
                },
              );
            }}
          >
            {COPY.reject}
          </Button>
          <Button
            disabled={!may || approve.isPending}
            onClick={() => {
              approve.mutate(
                {
                  path: { import_id: found.id },
                  body: { accepted_field_keys: [...accepted], seen_version: 1 },
                },
                {
                  onSuccess: () => {
                    toast.show(COPY.approvedToast);
                    onDone(true);
                  },
                },
              );
            }}
          >
            {COPY.approve}
          </Button>
        </div>
      </div>
    </FullSheet>
  );
}

export interface TAX09Props {
  returnId: string;
  /** The artboard opens with the popover shown (TAX-09 frames). */
  defaultOpen?: boolean;
  /** e opens on the import diff. */
  defaultImportOpen?: boolean;
  /** Mounted over a real return (the `engine-sync` layer, DEC-1288): the chip and its panel
   * only, without the artboard's subbar words, and the panel in the flow rather than floating. */
  bare?: boolean;
}

export function TAX09({
  returnId,
  defaultOpen = false,
  defaultImportOpen = false,
  bare = false,
}: TAX09Props): JSX.Element {
  const now = useNow();
  const reduced = useReducedMotion();
  const sync = useQuery(engineSyncOptions({ path: { return_id: returnId } }));
  const exporting = useMutation(exportReturnMutation());
  const marking = useMutation(markExportedMutation());
  const uploading = useMutation(uploadImportMutation());
  const [open, setOpen] = useState(defaultOpen);
  const [chip, setChip] = useState<Chip | null>(null);
  const [exported, setExported] = useState<{ id: string; file: string } | null>(null);
  const [fresh, setFresh] = useState(false);
  const [importing, setImporting] = useState<EngineImportOut | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const asked = useRef(false);
  const picker = useRef<HTMLInputElement>(null);
  const data = sync.data;

  const upload = useCallback(
    (file: File) => {
      uploading.mutate(
        {
          path: { return_id: returnId },
          query: { kind: "values" },
          headers: { "X-File-Name": file.name, "Content-Type": file.type || "text/csv" },
          body: file as never,
          bodySerializer: null,
        },
        {
          onSuccess: (found) => {
            setImporting(found);
            setSheetOpen(true);
          },
        },
      );
    },
    [returnId, uploading],
  );

  useEffect(() => {
    if (!defaultImportOpen || data === undefined || asked.current) return;
    asked.current = true;
    upload(new File([], SPECIMEN_FILE, { type: "text/csv" }));
    // Open e's diff once, when the sync state has loaded.
  }, [defaultImportOpen, data, upload]);

  if (data === undefined) return <div className="h-[42px]" />;
  const state: Chip = chip ?? data.state;
  const blockers = data.blockers ?? [];
  const mayExport = data.allowed_actions.includes("tax_return.export") && blockers.length === 0;
  const blocked = COPY.blocked(
    data.approver_name ?? "",
    data.policy_code ?? "",
    data.draft_k1_source ?? null,
  );
  const syncedOn = fresh ? now.toISOString() : (data.synced_at ?? null);
  const vars = syncedOn === null ? undefined : { date: date(syncedOn, { now }) };
  const history = data.history;
  const notExported = !fresh && !history.some((h) => h.kind === "marked_exported");

  const runExport = (): void => {
    setChip("exporting");
    exporting.mutate(
      {
        path: { return_id: returnId },
        body: { checkpoint_id: UPLOAD_ID },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
      {
        onSuccess: (found) => {
          const finish = (): void => {
            setExported({ id: found.id, file: found.file_name });
          };
          if (reduced) finish();
          else window.setTimeout(finish, EXPORTING_MS);
        },
        onError: () => {
          setChip("failed");
          toast.show(COPY.exportFailed);
        },
      },
    );
  };

  return (
    <div className="relative">
      <div className="flex h-[42px] items-center gap-[10px] px-[12px]">
        {!bare && (
          <Pill variant="outline" lead={<StatusDisc state="done" size={15} />}>
            {COPY.noChanges}
          </Pill>
        )}
        <SyncChip
          code={state}
          {...(vars === undefined ? {} : { vars })}
          aria-expanded={open}
          aria-haspopup="dialog"
          onClick={() => {
            setOpen((o) => !o);
          }}
        />
        {!bare && (
          <span className="flex flex-1 items-center justify-center gap-[8px]">
            <span className="text-[15px] font-medium">{COPY.title}</span>
            <span className="text-dense text-ink-2">{COPY.client}</span>
            <Pill variant="green-tint">{COPY.approved}</Pill>
          </span>
        )}
      </div>
      {open && (
        <div
          role={bare ? "group" : "dialog"}
          aria-label={COPY.syncLabel}
          className={
            bare
              ? "flex w-full flex-col gap-[6px] rounded-[15px] bg-nested p-[6px]"
              : "absolute top-[50px] left-[170px] z-10 flex w-[462px] flex-col gap-[6px] rounded-[15px] bg-nested p-[6px] shadow-pop"
          }
        >
          <Section title={COPY.actions}>
            {mayExport ? (
              <Item
                icon="upload"
                title={COPY.exportTitle}
                body={COPY.exportBody}
                onClick={runExport}
              />
            ) : (
              <Item icon="upload" title={COPY.exportTitle} body={blocked} disabled />
            )}
            <Item
              icon="cloud-download"
              title={COPY.importTitle}
              body={COPY.importBody}
              disabled={!data.allowed_actions.some((a) => a.startsWith("engine_import"))}
              onClick={() => picker.current?.click()}
            />
            <input
              ref={picker}
              type="file"
              accept=".csv,text/csv"
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file !== undefined) upload(file);
              }}
            />
          </Section>
          <Section title={COPY.history}>
            <ul>
              {fresh && (
                <HistoryRow
                  fresh
                  now={now}
                  e={{
                    id: "fresh-export",
                    kind: "marked_exported",
                    actor_name: null,
                    at: now.toISOString(),
                    engine_version: data.engine_return_id,
                    field_keys: [],
                    errors: null,
                    informational: null,
                  }}
                />
              )}
              {notExported && state !== "exporting" && (
                <li className="flex items-start gap-[10px] px-[10px] py-[8px]">
                  <Icon name="refresh-cw" size={14} />
                  <span className="flex flex-col">
                    <span className="text-body font-medium">{COPY.notExportedTitle}</span>
                    <span className="text-dense text-ink-2">{COPY.notExportedBody}</span>
                  </span>
                </li>
              )}
              {history.map((e) => (
                <HistoryRow key={e.id} e={e} now={now} />
              ))}
            </ul>
          </Section>
          {data.diagnostics.length > 0 && (
            <Section title={COPY.diagnostics}>
              <ul>
                {data.diagnostics.map((d) => (
                  <li
                    key={d.code}
                    className={
                      d.severity === "error"
                        ? "flex items-start gap-[10px] rounded-[8px] bg-red-tint px-[10px] py-[8px] text-dense text-red-ink"
                        : "flex items-start gap-[10px] px-[10px] py-[8px] text-dense text-ink-2"
                    }
                  >
                    <Icon name={d.severity === "error" ? "circle-x" : "info"} size={13} />
                    {/* The engine's message is client-system content: shown as plain text only. */}
                    <span>{d.message_text}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}
          <footer className="flex h-[36px] items-center gap-[8px] px-[8px] text-meta text-ink-3">
            <span aria-hidden="true" className="inline-flex items-center gap-[4px]">
              <span className="size-[22px] rounded-[6px] bg-espresso" />
              <Icon name="refresh-cw" size={12} />
              <span className="size-[22px] rounded-[6px] bg-chip" />
            </span>
            <span className="flex-1">{COPY.connection}</span>
            {/* The return's binder, where the engine's import files are collected (TAX-09 →
                BND-01; DEC-1288). */}
            <a href={hrefOf(to.BND01())} className="font-medium text-ink hover:underline">
              {COPY.binder}
            </a>
            <Tooltip content={COPY.settingsTip}>
              <span className="font-medium text-ink">{COPY.settings} →</span>
            </Tooltip>
          </footer>
        </div>
      )}
      <Dialog
        open={exported !== null}
        onOpenChange={(next) => {
          if (!next) {
            setExported(null);
            setChip(null);
          }
        }}
        title={COPY.markTitle}
        description={exported === null ? "" : COPY.markBody(exported.file)}
      >
        <div className="flex justify-end gap-[8px]">
          {exported !== null && (
            <a
              className="inline-flex items-center gap-[6px] text-dense text-ink-2 hover:underline"
              href={`/v1/engine-exports/${exported.id}/file`}
              download={exported.file}
            >
              <Icon name="download" size={14} />
              {COPY.download}
            </a>
          )}
          <Button
            variant="secondary"
            onClick={() => {
              setExported(null);
              setChip(null);
            }}
          >
            {COPY.cancel}
          </Button>
          <Button
            loading={marking.isPending}
            onClick={() => {
              if (exported === null) return;
              marking.mutate(
                { path: { export_id: exported.id }, body: { seen_version: 1 } },
                {
                  onSuccess: () => {
                    setExported(null);
                    setChip("synced");
                    setFresh(true);
                  },
                },
              );
            }}
          >
            {COPY.markConfirm}
          </Button>
        </div>
      </Dialog>
      {importing !== null && (
        <ImportSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          found={importing}
          version={data.engine_return_id ?? ""}
          onDone={() => {
            setSheetOpen(false);
            void sync.refetch();
          }}
        />
      )}
    </div>
  );
}

/** The `engine-sync` layer (`?ov=engine-sync:<returnId>`, `ov.TAX09`; DEC-1288): TAX-01's row chip
 * and TAX-02's header chip open the return's sync chip and its panel as a sheet over the page. */
export function EngineSyncLayer({ ref, close }: OverlayRenderProps): JSX.Element | null {
  const returnId = ref.args[0];
  if (returnId === undefined) return null;
  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) close();
      }}
      title={COPY.syncLabel}
    >
      <TAX09 returnId={returnId} bare defaultOpen />
    </Dialog>
  );
}
