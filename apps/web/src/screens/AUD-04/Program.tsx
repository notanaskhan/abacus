import type { CitationV2Out, WorkpaperCellOut, WorkpaperRecordOut } from "@abacus/api-client";
import { workpaperExport } from "@abacus/api-client";
import { listCitationsOptions, workpaperRecordOptions } from "@abacus/api-client/query";
import {
  type CitationView,
  Button,
  PaneAction,
  Pill,
  Segmented,
  type TableColumn,
  type TableRow,
  ViewStateBody,
  type ViewState,
  type WorkpaperKv,
  type WorkpaperSectionData,
  type WorkpaperTab,
  WorkpaperPane,
  toast,
  workpaperCell,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { AuditBar, isNotFound, useAuditCockpit } from "../../domain/audits";
import { COPY } from "./copy";

// AUD-04 · Audit program & workpaper, General Audit Planning › Service Organizations (A-04-T27;
// A-04 §3 AC1.1–AC1.5; the handoff spec): T2 without the dock over `GET …/workpapers/{id}/record`
// (A-04-T04) by tab and the paper's C4 citations. The record's sections become the C-02 workpaper
// (dark section bands, captions, key/value rows, the service-organization table, the after rows);
// a cited cell lights in the source-match purple and opens SHL-07 with a 1 / 2 stepper when it
// cites two sources. The header says where the paper stands: "Draft · Accrued Agent" while any
// value is the agent's suggestion, "Prepared · MD" once adopted, "Signed off" with the rung chips
// after L2. Adopt (L1) opens SHL-12 at L1; Sign off… opens it at L2 and stays disabled until the
// draft is adopted. Agent-written values are never offered as signed (ADR-005).

export type ProgramTab = "service_organizations" | "linkage" | "approach";
const LABEL: Record<ProgramTab, (typeof COPY.tabs)[number]> = {
  service_organizations: COPY.tabs[0],
  linkage: COPY.tabs[1],
  approach: COPY.tabs[2],
};

function textOf(cell: WorkpaperCellOut): string {
  const v: unknown = cell.value.v;
  return typeof v === "string" ? v : v === null || v === undefined ? "" : JSON.stringify(v);
}

function sheetOf(tab: ProgramTab): string {
  return tab === "service_organizations" ? "main" : tab;
}

/** C4 citations as the popover's views: each lights the workpaper cell that cites it. */
export function citationViews(
  record: WorkpaperRecordOut,
  citations: readonly CitationV2Out[],
  tab: ProgramTab,
): CitationView[] {
  const sheet = sheetOf(tab);
  return citations.map((c, i) => {
    const cell = record.cells.find((x) => x.citation_ids.includes(c.id));
    const table = cell?.col_key != null && cell.col_key !== "value" && cell.row_key != null;
    return {
      n: i + 1,
      title: c.title,
      quote: c.quote ?? "",
      loc: c.loc,
      match: table ? workpaperCell(sheet, cell.row_key ?? "", cell.col_key ?? "") : null,
      kind: "workpaper",
    };
  });
}

/** A cell's citation markers: their numbers in the C4 list (1-based, as `citationViews`). */
function numberOf(order: readonly string[], ids: readonly string[]): number[] {
  return ids.flatMap((id) => {
    const at = order.indexOf(id);
    return at < 0 ? [] : [at + 1];
  });
}

/** The record's sections as the C-02 kit draws them (TPL-02's workpaper grammar). */
export function tabOf(
  record: WorkpaperRecordOut,
  views: readonly CitationView[],
  order: readonly string[],
  tab: ProgramTab,
): WorkpaperTab {
  const adopted = !record.cells.some((c) => c.value_state === "suggested");
  const sections: WorkpaperSectionData[] = record.sections.map((s) => {
    const cells = record.cells.filter((c) => c.section_key === s.key);
    const kv = (after: boolean): WorkpaperKv[] =>
      cells
        .filter(
          (c) =>
            c.col_key === "value" &&
            (COPY.after as readonly string[]).includes(c.row_key ?? "") === after,
        )
        .map((c) => ({
          key: COPY.keys[c.row_key ?? ""] ?? c.row_key ?? "",
          text: textOf(c),
          ...(c.value_source === "agent" ? { agent: true } : {}),
          cites: numberOf(order, c.citation_ids),
        }));
    const grid = cells.filter((c) => c.col_key !== null && c.col_key !== "value");
    const cols = [...new Set(grid.map((c) => c.col_key ?? ""))];
    const rowKeys = [...new Set(grid.map((c) => c.row_key ?? ""))];
    const columns: TableColumn[] = cols.map((key, i) => ({
      key,
      header: COPY.columns[key] ?? key,
      type: i === 0 ? ("label" as const) : ("text" as const),
      ...(COPY.widths[key] === undefined ? {} : { width: COPY.widths[key] }),
    }));
    const rows: TableRow[] = rowKeys.map((row) => {
      const mine = grid.filter((c) => c.row_key === row);
      return {
        id: row,
        ...(() => {
          const first = mine.find((c) => c.col_key === cols[0]) ?? mine[0];
          return first === undefined
            ? { label: "" }
            : {
                label: textOf(first),
                ...(first.value_source === "agent" ? { labelAgent: true } : {}),
              };
        })(),
        cells: Object.fromEntries(
          mine
            .filter((c) => c.col_key !== cols[0])
            .map((c) => [
              c.col_key ?? "",
              {
                value: textOf(c),
                ...(c.value_source === "agent" ? { agent: true } : {}),
                // A-04-T27: ✓ once adopted; an outlined ring while the agent's value waits.
                ...(adopted
                  ? { tick: "check" as const }
                  : c.value_source === "agent"
                    ? { tick: "drafted" as const }
                    : {}),
              },
            ]),
        ),
      };
    });
    const before = kv(false);
    const after = kv(true);
    return {
      id: s.key,
      title: s.title,
      label: s.title,
      ...(COPY.captions[s.key] === undefined ? {} : { caption: COPY.captions[s.key] }),
      ...(before.length === 0 ? {} : { rows: before }),
      ...(rows.length === 0 ? {} : { table: { columns, rows } }),
      ...(after.length === 0 ? {} : { after }),
    };
  });
  return {
    label: LABEL[tab],
    sheet: sheetOf(tab),
    sections,
    citations: views,
    procedures: record.program_step_keys.map((ref) => ({ ref, title: ref })),
  };
}

/** A-04-T27: the paper's XLSX (the export route, audited `workpaper.exported`); Excel opens it. */
async function exportWorkpaper(
  engagementId: string | undefined,
  workpaperId: string,
): Promise<void> {
  if (engagementId === undefined) return;
  try {
    const { data, response } = await workpaperExport({
      path: { engagement_id: engagementId, workpaper_id: workpaperId },
      parseAs: "blob",
      throwOnError: true,
    });
    const header = response.headers.get("Content-Disposition") ?? "";
    const name = /filename="([^"]+)"/u.exec(header)?.[1] ?? "workpaper.xlsx";
    const url = URL.createObjectURL(data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.click();
    URL.revokeObjectURL(url);
  } catch {
    toast.show({ kind: "error", text: COPY.exportFailed });
  }
}

export function ProgramPage({
  auditId,
  workpaperId,
  tab,
  onTab,
  onSignOff,
  onBack,
}: {
  auditId: string;
  workpaperId: string;
  tab: ProgramTab;
  onTab: (tab: ProgramTab) => void;
  /** SHL-12 at L1 (Adopt) or L2 (Sign off). */
  onSignOff: (workpaperId: string, level: "L1" | "L2") => void;
  onBack?: () => void;
}): JSX.Element {
  const cockpit = useAuditCockpit(auditId);
  const engagementId = cockpit.data?.engagement_id;
  const record = useQuery({
    ...workpaperRecordOptions({
      path: { engagement_id: engagementId ?? "", workpaper_id: workpaperId },
      query: { tab },
    }),
    enabled: engagementId !== undefined,
  });
  const cites = useQuery(
    listCitationsOptions({ query: { anchor_type: "workpaper", anchor_id: workpaperId } }),
  );
  let state: ViewState = { kind: "ready" };
  if (cockpit.isError || record.isError) {
    const error = cockpit.error ?? record.error;
    state = isNotFound(error)
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry: () => void record.refetch() };
  } else if (record.data === undefined) state = { kind: "loading" };
  const data = record.data;
  const items = cites.data?.items ?? [];
  const views = data === undefined ? [] : citationViews(data, items, tab);
  const order = items.map((c) => c.id);
  const drafted = (data?.cells ?? []).some((c) => c.value_state === "suggested");
  const rungs = (data?.sign_offs ?? []).filter((s) => s.initials != null && !s.stale);
  const prepared = rungs.find((s) => s.level === "L1");
  const signed = rungs.some((s) => s.level !== "L1");
  return (
    <div data-screen="AUD-04" data-tab={tab} className="flex min-h-0 flex-1 flex-col">
      {cockpit.data !== undefined && (
        <AuditBar cockpit={cockpit.data} {...(onBack === undefined ? {} : { onBack })} />
      )}
      <ViewStateBody state={state} empty={{ title: COPY.title }}>
        {data !== undefined && (
          <div className="flex min-h-0 flex-1 flex-col rounded-pane bg-card shadow-e2">
            <header className="flex h-[46px] items-center gap-[8px] px-[12px] hairline-b">
              <span className="flex flex-1 items-center gap-[6px]">
                {drafted ? (
                  <Pill data-aud04="state" variant="neutral" size="micro">
                    {COPY.draft}
                  </Pill>
                ) : signed ? (
                  <>
                    <Pill data-aud04="state" variant="green" size="micro">
                      {COPY.signedOff}
                    </Pill>
                    {rungs.map((r) => (
                      <Pill key={r.level} data-aud04="rung" variant="tag" size="micro">
                        {COPY.check(r.initials ?? "")}
                      </Pill>
                    ))}
                  </>
                ) : prepared?.initials != null ? (
                  <Pill data-aud04="state" variant="neutral" size="micro">
                    {COPY.prepared(prepared.initials)}
                  </Pill>
                ) : null}
              </span>
              <h2 className="text-[14.5px] font-medium">{COPY.title}</h2>
              <span className="flex flex-1 items-center justify-end gap-[6px]">
                {drafted && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => {
                      onSignOff(data.id, "L1");
                    }}
                  >
                    {COPY.adopt}
                  </Button>
                )}
                <Button
                  data-aud04="sign-off"
                  variant="secondary"
                  size="sm"
                  icon="check"
                  disabled={drafted || signed}
                  {...(drafted ? { title: COPY.adoptFirst } : {})}
                  onClick={() => {
                    onSignOff(data.id, "L2");
                  }}
                >
                  {COPY.signOff}
                </Button>
                <PaneAction
                  kind="icon"
                  icon="download"
                  label={COPY.download}
                  onClick={() => {
                    void exportWorkpaper(engagementId, workpaperId);
                  }}
                />
              </span>
            </header>
            <div className="flex h-[42px] items-center gap-[8px] px-[12px]">
              <Segmented
                size="small"
                label={COPY.title}
                options={COPY.tabs}
                active={LABEL[tab]}
                onChange={(label) => {
                  const next = (Object.keys(LABEL) as ProgramTab[]).find(
                    (k) => LABEL[k] === label,
                  );
                  if (next !== undefined) onTab(next);
                }}
              />
              <span className="flex-1" />
              <PaneAction
                kind="icon"
                icon="download"
                label={COPY.openInExcel}
                onClick={() => {
                  void exportWorkpaper(engagementId, workpaperId);
                }}
              />
            </div>
            <WorkpaperPane
              chrome={false}
              tabs={[tabOf(data, views, order, tab)]}
              active={LABEL[tab]}
              className="min-h-0 flex-1"
            />
          </div>
        )}
      </ViewStateBody>
    </div>
  );
}
