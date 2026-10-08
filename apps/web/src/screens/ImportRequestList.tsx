import type { ImportCountsOut, SheetPreviewOut } from "@abacus/api-client";
import { import_, previewImport } from "@abacus/api-client";
import { engagementGraphOptions } from "@abacus/api-client/query";
import { Button, Dialog, Label, StatusPill, Table, Td, Th } from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { XLSX, type Problem, workbookProblems } from "./methodologyUpload";

const UNASSIGNED = "Unassigned";
const TIERS = new Set(["A", "B", "C", "D", "E"]);

/** The same normalisation the server uses (SPEC-018 Q2, Q3; TASK-033 D2). */
function normalise(text: string): string {
  return text.replace(/\s+/g, " ").trim().toLocaleLowerCase();
}

type Step = "file" | "map" | "done";

/** SPEC-018: a firm's own request list, mapped by column, previewed, then imported. */
export function ImportRequestList({ engagementId }: { engagementId: string }): JSX.Element {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="outline"
        onClick={() => {
          setOpen(true);
        }}
      >
        Import from Excel
      </Button>
      {open && (
        <ImportDialog
          engagementId={engagementId}
          onClose={() => {
            setOpen(false);
          }}
        />
      )}
    </>
  );
}

function ImportDialog({
  engagementId,
  onClose,
}: {
  engagementId: string;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const graph = useQuery(engagementGraphOptions({ path: { engagement_id: engagementId } }));
  const [step, setStep] = useState<Step>("file");
  const [file, setFile] = useState<File | null>(null);
  const [headerRow, setHeaderRow] = useState(1);
  const [sheets, setSheets] = useState<SheetPreviewOut[]>([]);
  const [sheet, setSheet] = useState(0);
  const [description, setDescription] = useState<number | null>(null);
  const [area, setArea] = useState<number | null>(null);
  const [tier, setTier] = useState<number | null>(null);
  const [problems, setProblems] = useState<Problem[] | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [counts, setCounts] = useState<ImportCountsOut | null>(null);

  const path = { engagement_id: engagementId };
  const fail = (error: unknown): void => {
    const found = workbookProblems(error);
    setProblems(found);
    setFailure(found === null ? errorMessage(error) : null);
  };

  const loadPreview = async (chosen: File, row: number): Promise<void> => {
    setBusy(true);
    setProblems(null);
    setFailure(null);
    try {
      const { data } = await previewImport({
        path,
        query: { header_row: row },
        body: chosen as never,
        bodySerializer: null,
        headers: { "Content-Type": XLSX },
        throwOnError: true,
      });
      setSheets(data);
      const first = data[0];
      setSheet(0);
      setDescription(first?.suggested_description ?? null);
      setArea(first?.suggested_area ?? null);
      setTier(first?.suggested_tier ?? null);
      setStep("map");
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  };

  const runImport = async (): Promise<void> => {
    const chosen = sheets[sheet];
    if (file === null || chosen === undefined || description === null || area === null) return;
    setBusy(true);
    setProblems(null);
    setFailure(null);
    try {
      const { data } = await import_({
        path,
        query: {
          sheet: chosen.name,
          header_row: headerRow,
          description,
          area,
          ...(tier === null ? {} : { tier }),
        },
        body: file as never,
        bodySerializer: null,
        headers: { "Content-Type": XLSX },
        throwOnError: true,
      });
      setCounts(data);
      setStep("done");
      void queryClient.invalidateQueries();
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  };

  // The preview mirrors the server's matching on the sample rows (AC-6).
  const areas = new Map<string, string>();
  for (const a of graph.data?.areas ?? []) {
    if (a.code !== null) {
      areas.set(normalise(a.name), a.name);
      areas.set(normalise(a.code), a.name);
    }
  }
  const seen = new Set(
    (graph.data?.areas ?? []).flatMap((a) =>
      a.items.map((i) => `${normalise(a.name)}|${normalise(i.description)}`),
    ),
  );
  const chosen = sheets[sheet];
  const planned = (chosen?.rows ?? []).map((row) => {
    const text = description === null ? "" : (row[description] ?? "");
    const raw = area === null ? "" : (row[area] ?? "");
    const matched = areas.get(normalise(raw));
    const areaName = matched ?? (raw === "" ? UNASSIGNED : raw);
    const tierText = tier === null ? "" : (row[tier] ?? "").toUpperCase();
    const key = `${normalise(areaName)}|${normalise(text)}`;
    const status = text === "" ? "empty" : seen.has(key) ? "duplicate" : "new";
    if (status === "new") seen.add(key);
    return {
      text,
      areaName,
      areaIsNew: matched === undefined && raw !== "",
      tier: TIERS.has(tierText) ? tierText : "—",
      status,
    };
  });

  const columnSelect = (
    id: string,
    label: string,
    value: number | null,
    set: (value: number | null) => void,
    optional: boolean,
  ): JSX.Element => (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id}>{label}</Label>
      <select
        id={id}
        value={value === null ? "" : String(value)}
        onChange={(event) => {
          set(event.target.value === "" ? null : Number(event.target.value));
        }}
        className="h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm"
      >
        <option value="">{optional ? "None" : "Choose a column…"}</option>
        {(chosen?.headers ?? []).map((h, index) => (
          <option key={`${h}-${String(index)}`} value={index}>
            {h}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title="Import a request list"
      description="Your own spreadsheet: pick the columns, check the preview, then import. Duplicates are skipped."
    >
      <ol aria-label="Steps" className="mb-3 flex gap-3 text-xs text-muted">
        <li className={step === "file" ? "font-semibold text-ink" : ""}>1 · File</li>
        <li className={step === "map" ? "font-semibold text-ink" : ""}>2 · Columns and preview</li>
        <li className={step === "done" ? "font-semibold text-ink" : ""}>3 · Done</li>
      </ol>

      {step === "file" && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="list-file">Workbook (.xlsx)</Label>
            <input
              id="list-file"
              type="file"
              accept={`.xlsx,${XLSX}`}
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
              }}
              className="text-sm"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              disabled={file === null || busy}
              onClick={() => {
                if (file !== null) void loadPreview(file, headerRow);
              }}
            >
              {busy ? "Reading…" : "Next"}
            </Button>
          </div>
        </div>
      )}

      {step === "map" && chosen !== undefined && (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="list-sheet">Sheet</Label>
              <select
                id="list-sheet"
                value={sheet}
                onChange={(event) => {
                  const index = Number(event.target.value);
                  const next = sheets[index];
                  setSheet(index);
                  setDescription(next?.suggested_description ?? null);
                  setArea(next?.suggested_area ?? null);
                  setTier(next?.suggested_tier ?? null);
                }}
                className="h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm"
              >
                {sheets.map((s, index) => (
                  <option key={s.name} value={index}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="list-header">Header row</Label>
              <input
                id="list-header"
                type="number"
                min={1}
                max={50}
                value={headerRow}
                onChange={(event) => {
                  const row = Math.min(50, Math.max(1, Number(event.target.value) || 1));
                  setHeaderRow(row);
                  if (file !== null) void loadPreview(file, row);
                }}
                className="h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm"
              />
            </div>
            {columnSelect(
              "list-description",
              "Request column",
              description,
              setDescription,
              false,
            )}
            {columnSelect("list-area", "Audit area column", area, setArea, false)}
            {columnSelect("list-tier", "Tier column (optional)", tier, setTier, true)}
          </div>
          <p className="text-xs text-muted">Preview of the first {planned.length} rows</p>
          <div className="max-h-64 overflow-auto rounded-[var(--radius-control)] border border-line">
            <Table>
              <thead>
                <tr>
                  <Th>Request</Th>
                  <Th>Area</Th>
                  <Th>Tier</Th>
                  <Th>Result</Th>
                </tr>
              </thead>
              <tbody>
                {planned.map((p, index) => (
                  <tr key={`${p.text}-${String(index)}`}>
                    <Td>{p.text === "" ? <span className="text-muted">—</span> : p.text}</Td>
                    <Td>
                      <span className="inline-flex items-center gap-1.5">
                        {p.areaName}
                        {p.areaIsNew && <StatusPill tone="info">New area</StatusPill>}
                      </span>
                    </Td>
                    <Td>{p.tier}</Td>
                    <Td>
                      {p.status === "new" ? (
                        <StatusPill tone="success">Will import</StatusPill>
                      ) : p.status === "duplicate" ? (
                        <StatusPill tone="neutral">Duplicate</StatusPill>
                      ) : (
                        <StatusPill tone="neutral">Empty</StatusPill>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setStep("file");
              }}
            >
              Back
            </Button>
            <Button
              disabled={description === null || area === null || busy}
              onClick={() => void runImport()}
            >
              {busy ? "Importing…" : "Import"}
            </Button>
          </div>
        </div>
      )}

      {step === "done" && counts !== null && (
        <div className="flex flex-col gap-3">
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-muted">Created</dt>
            <dd className="font-semibold tabular-nums">{counts.created}</dd>
            <dt className="text-muted">Duplicates skipped</dt>
            <dd className="tabular-nums">{counts.duplicates}</dd>
            <dt className="text-muted">Empty rows skipped</dt>
            <dd className="tabular-nums">{counts.empty}</dd>
            <dt className="text-muted">Items with new areas</dt>
            <dd className="tabular-nums">{counts.unmatched_areas}</dd>
          </dl>
          <div className="flex justify-end">
            <Button onClick={onClose}>Close</Button>
          </div>
        </div>
      )}

      {problems !== null && problems.length > 0 && (
        <div role="alert" className="mt-3 flex flex-col gap-1 text-sm">
          <p className="font-semibold text-danger">
            Nothing was imported. Fix these and try again:
          </p>
          <ul className="list-disc pl-5">
            {problems.map((p, index) => (
              <li key={`${p.where}-${String(index)}`}>
                {p.where}: {p.message}
              </li>
            ))}
          </ul>
        </div>
      )}
      {failure !== null && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {failure}
        </p>
      )}
    </Dialog>
  );
}
