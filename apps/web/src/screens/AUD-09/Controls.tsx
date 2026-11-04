import type {
  AuditCockpitOut,
  AuditSectionRowOut,
  ControlExceptionOut,
  ProcessOut,
} from "@abacus/api-client";
import {
  controlExceptionsOptions,
  convertToMisstatementMutation,
  exceptionProposeSeverityMutation,
  exceptionRequestEvidenceMutation,
  getCitationOptions,
  listAgentRunsOptions,
  processesOptions,
  sendToFindingsMutation,
  serviceOrgsOptions,
  workpaperDraftMutation,
} from "@abacus/api-client/query";
import {
  type CockpitCanvas,
  Button,
  Menu,
  PaneAction,
  Pill,
  Segmented,
  type ViewState,
  cn,
  useFormat,
} from "@abacus/ui";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// AUD-09 · Internal control & exceptions (A-04-T32; A-04 §3 AC6, SPEC-620; the handoff spec): the
// Internal Control row's canvas in the T2 cockpit. Exceptions is the workbook's own sheet: column
// letters B–E over the header row 1 and data rows 2–8, true `Exceptions!D2` addresses from the
// server (never recounted), a selected cell's citations in the footer. The severity column holds
// only AU-C 265 words or the disposition; COSO components sit in their own column. The O1 picker
// writes a proposal (`deficiency.propose_severity`) and never a conclusion: a concluded severity is
// the partner's (A-06), drawn bold, never amber. The row menu routes a row (hidden until A-06
// registers: 503 `route_not_available`). Internal Control lists processes × walkthrough, design,
// implementation and reliance. When the run's Internal Control step failed (the rail row reads
// "Failed — see run"), the grid keeps only its header row and the dock card quotes the run's
// reason verbatim with Retry and Fix in Knowledge (AUD-09 d).

export const INTERNAL_CONTROL = "internal_control";
const FLAG = "assurance.internal_control";
export type ControlsSheet = "exceptions" | "internal-control";

// Column B is the first: the handoff's letters are "B C D E" (column A is the workbook's margin).
const COLUMNS = [
  { key: "matter", letter: "B", width: 170 },
  { key: "description", letter: "C", width: 214 },
  { key: "severity", letter: "D", width: 150 },
  { key: "coso", letter: "E", width: 110 },
] as const;
const HAIR = "border-r-[0.5px] border-b-[0.5px] border-hair";

export interface ControlsOptions {
  /** The canvas is on screen: the reads run only then (the cockpit calls the hook always). */
  active?: boolean;
  sheet?: ControlsSheet;
  /** `?cell=D2`: the selected cell on the Exceptions sheet. */
  cell?: string | null;
  onSheet?: (sheet: ControlsSheet) => void;
  onCell?: (cell: string | null) => void;
  /** AUD-15 (Send to Findings, Open in Findings) once A-06 registers. */
  onFindings?: (ref: string | null) => void;
  /** AUD-16 (Convert to misstatement) once A-06 registers. */
  onMisstatement?: (ref: string) => void;
  /** SHL-14 with the server's prefill (`RequestDraftOut`). */
  onRequest?: (draftId: string) => void;
  /** Row 4 of Internal Control opens AUD-10 once A-04-T37 lands. */
  onServiceOrg?: (serviceOrganizationId: string) => void;
  /** Fix in Knowledge →: KNW-03 f at the failing step (the host knows the program). */
  onFix?: () => void;
  /** O1 opens on a cell (state c). */
  initialPicker?: string | null;
}

function idempotency(): { "Idempotency-Key": string } {
  return { "Idempotency-Key": crypto.randomUUID() };
}

function rowOf(cockpit: AuditCockpitOut): AuditSectionRowOut | undefined {
  return (cockpit.bands ?? [])
    .flatMap((b) => b.rows ?? [])
    .find((r) => r.key === INTERNAL_CONTROL);
}

/** The step failed on the run: the rail's own state, never inferred from the grid. */
export function controlsFailed(cockpit: AuditCockpitOut): boolean {
  return rowOf(cockpit)?.section_state === "failed";
}

function SeverityCell({ row }: { row: ControlExceptionOut }): JSX.Element {
  if (row.concluded_severity !== null) {
    // A-06's conclusion: solid for the two severities that report, bold always, never amber.
    const word = COPY.severity[row.concluded_severity] ?? row.concluded_severity;
    return (
      <Pill
        variant={row.concluded_severity === "deficiency" ? "red-tint" : "red"}
        size="sm"
        bold
        data-concluded={row.concluded_severity}
      >
        {word}
      </Pill>
    );
  }
  if (row.proposed_severity === null) {
    return (
      <Pill variant="amber" size="sm" data-disposition={row.disposition}>
        {COPY.disposition[row.disposition] ?? row.disposition}
      </Pill>
    );
  }
  return (
    <Pill
      variant={row.proposed_severity === "deficiency" ? "red-tint" : "red"}
      size="sm"
      bold={row.proposed_severity === "material_weakness"}
      data-proposed={row.proposed_severity}
    >
      {COPY.severity[row.proposed_severity] ?? row.proposed_severity}
    </Pill>
  );
}

function Picker({
  row,
  engagementId,
  onClose,
  onFindings,
}: {
  row: ControlExceptionOut;
  engagementId: string;
  onClose: () => void;
  onFindings?: ((ref: string | null) => void) | undefined;
}): JSX.Element {
  const qc = useQueryClient();
  const propose = useMutation({
    ...exceptionProposeSeverityMutation(),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: controlExceptionsOptions({ path: { engagement_id: engagementId } }).queryKey,
      });
      onClose();
    },
  });
  const choices = ["deficiency", "significant_deficiency", "material_weakness"] as const;
  return (
    <div
      role="dialog"
      aria-label={COPY.picker.label}
      data-aud09="picker"
      className="absolute top-[28px] left-0 z-[4] flex w-[240px] flex-col rounded-[10px] bg-card p-[4px] shadow-e2"
    >
      <ul role="listbox" aria-label={COPY.picker.label} className="flex flex-col">
        {choices.map((c) => (
          <li key={c}>
            <button
              type="button"
              role="option"
              aria-selected={row.proposed_severity === c}
              data-choice={c}
              className={cn(
                "flex h-[30px] w-full items-center rounded-[6px] px-[8px] text-left text-dense hover:bg-tonal-hover",
                c === "material_weakness" && "font-medium",
              )}
              onClick={() => {
                propose.mutate({
                  path: { engagement_id: engagementId, sheet_row: row.sheet_row },
                  body: { proposed_severity: c },
                  headers: idempotency(),
                });
              }}
            >
              {c === "material_weakness" ? (
                <Pill variant="red" size="sm" bold>
                  {COPY.severity[c]}
                </Pill>
              ) : (
                COPY.severity[c]
              )}
            </button>
          </li>
        ))}
      </ul>
      <p className="px-[8px] pt-[6px] pb-[4px] text-meta text-ink-3 hairline-t">
        {COPY.picker.note}{" "}
        {onFindings !== undefined && (
          <button
            type="button"
            className="font-medium text-ink"
            onClick={() => {
              onFindings(row.routed_kind === "finding" ? row.routed_ref : null);
            }}
          >
            {COPY.picker.openInFindings}
          </button>
        )}
      </p>
    </div>
  );
}

function RowMenu({
  row,
  engagementId,
  routable,
  onUnavailable,
  onFindings,
  onMisstatement,
  onRequest,
}: {
  row: ControlExceptionOut;
  engagementId: string;
  routable: boolean;
  onUnavailable: () => void;
  onFindings?: ((ref: string | null) => void) | undefined;
  onMisstatement?: ((ref: string) => void) | undefined;
  onRequest?: ((draftId: string) => void) | undefined;
}): JSX.Element | null {
  const qc = useQueryClient();
  const refresh = (): void => {
    void qc.invalidateQueries({
      queryKey: controlExceptionsOptions({ path: { engagement_id: engagementId } }).queryKey,
    });
  };
  const refused = (error: unknown): void => {
    if ((error as { status?: number } | null)?.status === 503) onUnavailable();
  };
  const send = useMutation({
    ...sendToFindingsMutation(),
    onError: refused,
    onSuccess: (out) => {
      refresh();
      onFindings?.(out.routed_ref);
    },
  });
  const convert = useMutation({
    ...convertToMisstatementMutation(),
    onError: refused,
    onSuccess: (out) => {
      refresh();
      onMisstatement?.(out.routed_ref);
    },
  });
  const request = useMutation({
    ...exceptionRequestEvidenceMutation(),
    onSuccess: (out) => {
      onRequest?.(out.draft_id);
    },
  });
  const path = { engagement_id: engagementId, sheet_row: row.sheet_row };
  const items = [];
  // Routing hides until A-06 registers the targets (503 `route_not_available`, DV of the contract).
  if (routable && row.allowed_actions.includes("exception.route") && row.routed_kind === null) {
    items.push({
      label: COPY.menu.sendToFindings,
      onSelect: () => {
        send.mutate({ path, headers: idempotency() });
      },
    });
    if (row.misstatement_candidate_amount !== null) {
      items.push({
        label: COPY.menu.convert,
        onSelect: () => {
          convert.mutate({ path, headers: idempotency() });
        },
      });
    }
  }
  items.push({
    label: COPY.menu.requestEvidence,
    opensDialog: true,
    onSelect: () => {
      request.mutate({ path, headers: idempotency() });
    },
  });
  return (
    <Menu
      label={COPY.menu.label(`${COPY.sheet}!B${String(row.sheet_row)}`)}
      align="end"
      sections={[items]}
      trigger={
        <button
          type="button"
          data-row-menu={row.sheet_row}
          aria-label={COPY.menu.label(`${COPY.sheet}!B${String(row.sheet_row)}`)}
          className="flex h-[20px] w-[22px] items-center justify-center rounded-[5px] text-ink-3 hover:bg-tonal-hover"
        >
          ···
        </button>
      }
    />
  );
}

function Footer({
  address,
  citationIds,
  failed,
}: {
  address: string;
  citationIds: readonly string[];
  failed: boolean;
}): JSX.Element {
  const citations = useQueries({
    queries: citationIds.map((id) => ({
      ...getCitationOptions({ path: { citation_id: id } }),
      enabled: !failed,
    })),
  });
  let text: string;
  if (failed) text = COPY.footer.noEvidence;
  else if (citationIds.length === 0) text = COPY.footer.none(address);
  else {
    const names = citations
      .map((c) => c.data)
      .filter((c) => c !== undefined)
      .map((c) => (c.quote === null ? c.title : `${c.title} (${c.quote})`));
    const head = COPY.footer.cited(address, citationIds.length);
    text = names.length === 0 ? head : `${head} — ${names.join(" · ")}`;
  }
  return (
    <p
      data-aud09="footer"
      className="flex h-[30px] shrink-0 items-center gap-[6px] truncate px-[12px] text-meta text-ink-3 hairline-t"
    >
      {text}
    </p>
  );
}

function ExceptionsSheet({
  rows,
  engagementId,
  failed,
  cell,
  onCell,
  options,
}: {
  rows: readonly ControlExceptionOut[];
  engagementId: string;
  failed: boolean;
  cell: string;
  onCell: (cell: string) => void;
  options: ControlsOptions;
}): JSX.Element {
  const [picker, setPicker] = useState<string | null>(options.initialPicker ?? null);
  // The routes hide once the server answers 503 `route_not_available` (A-06 not registered).
  const [routable, setRoutable] = useState(true);
  const shown = failed ? [] : rows;
  const picked = /^[B-E](\d+)$/.exec(cell)?.[1];
  const selectedRow = shown.find((r) => String(r.sheet_row) === picked);
  const at = (letter: string, n: number): string => `${letter}${String(n)}`;
  const td = (address: string, children: JSX.Element | string, extra?: string): JSX.Element => (
    <td
      key={address}
      role="gridcell"
      data-cell={address}
      aria-selected={cell === address}
      className={cn(
        "relative h-[28px] max-w-0 truncate px-[8px] text-cell whitespace-nowrap",
        HAIR,
        cell === address && "inset-ring-[1.5px] inset-ring-espresso",
        extra,
      )}
      onClick={() => {
        onCell(address);
      }}
    >
      {children}
    </td>
  );
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-auto">
        <table
          role="grid"
          aria-label={`${COPY.sheet}.xlsx`}
          data-aud09="grid"
          className="table-fixed border-collapse"
        >
          <colgroup>
            <col style={{ width: 34 }} />
            {COLUMNS.map((c) => (
              <col key={c.key} style={{ width: c.width }} />
            ))}
          </colgroup>
          <thead>
            <tr className="h-[20px] bg-band-hd">
              <th aria-hidden className={HAIR} />
              {COLUMNS.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  className={cn("text-center text-micro font-normal text-ink-3", HAIR)}
                >
                  {c.letter}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr data-sheet-row={1} className="bg-nested font-medium">
              <td role="rowheader" className={cn("text-center text-micro text-ink-3", HAIR)}>
                1
              </td>
              {COLUMNS.map((c) => td(at(c.letter, 1), COPY.headers[c.key]))}
            </tr>
            {shown.map((r) => (
              <tr key={r.sheet_row} data-sheet-row={r.sheet_row} className="bg-card">
                <td role="rowheader" className={cn("text-center text-micro text-ink-3", HAIR)}>
                  {r.sheet_row}
                </td>
                {td(
                  at("B", r.sheet_row),
                  <span className="flex items-center justify-between gap-[4px]">
                    <span className="truncate">{r.matter}</span>
                    <RowMenu
                      row={r}
                      engagementId={engagementId}
                      routable={routable}
                      onUnavailable={() => {
                        setRoutable(false);
                      }}
                      onFindings={options.onFindings}
                      onMisstatement={options.onMisstatement}
                      onRequest={options.onRequest}
                    />
                  </span>,
                )}
                {td(at("C", r.sheet_row), r.description)}
                <td
                  role="gridcell"
                  data-cell={at("D", r.sheet_row)}
                  aria-selected={cell === at("D", r.sheet_row)}
                  className={cn(
                    "relative h-[28px] px-[8px] whitespace-nowrap",
                    HAIR,
                    cell === at("D", r.sheet_row) && "inset-ring-[1.5px] inset-ring-espresso",
                  )}
                  onClick={() => {
                    onCell(at("D", r.sheet_row));
                  }}
                  onDoubleClick={() => {
                    if (r.allowed_actions.includes("deficiency.propose_severity"))
                      setPicker(at("D", r.sheet_row));
                  }}
                >
                  <span className="flex items-center gap-[4px]">
                    <SeverityCell row={r} />
                    {r.concluded_severity !== null && r.routed_kind === "finding" && (
                      <Pill variant="tag" size="sm" data-communicated>
                        {COPY.communicated}
                      </Pill>
                    )}
                  </span>
                  {picker === at("D", r.sheet_row) && r.concluded_severity === null && (
                    <Picker
                      row={r}
                      engagementId={engagementId}
                      onClose={() => {
                        setPicker(null);
                      }}
                      onFindings={options.onFindings}
                    />
                  )}
                </td>
                {td(
                  at("E", r.sheet_row),
                  r.coso_component === null ? (
                    <span className="text-ink-4">{COPY.none}</span>
                  ) : (
                    <Pill variant="tag" size="sm">
                      {COPY.coso[r.coso_component] ?? r.coso_component}
                    </Pill>
                  ),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Footer
        address={`${COPY.sheet}!${cell}`}
        citationIds={selectedRow?.citation_ids ?? []}
        failed={failed}
      />
    </div>
  );
}

function ProcessesSheet({
  processes,
  names,
  onServiceOrg,
}: {
  processes: readonly ProcessOut[];
  /** Service organization names by id: a SOC 1 row's walkthrough is "<name> SOC 1". */
  names: Readonly<Record<string, string>>;
  onServiceOrg?: ((serviceOrganizationId: string) => void) | undefined;
}): JSX.Element {
  const P = COPY.processes;
  const fmt = useFormat();
  return (
    <table data-aud09="processes" className="w-full table-fixed border-collapse text-cell">
      <thead>
        <tr className="h-[28px] bg-nested text-left font-medium">
          {[P.process, P.walkthrough, P.design, P.implementation, P.reliance].map((h) => (
            <th key={h} scope="col" className={cn("px-[8px] font-medium", HAIR)}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {processes.map((p) => {
          const soc = p.service_organization_id;
          return (
            <tr key={p.id} data-process={p.process_name} className="h-[28px] bg-card">
              <td className={cn("truncate px-[8px]", HAIR)}>
                {soc !== null && onServiceOrg !== undefined ? (
                  <button
                    type="button"
                    className="truncate text-left font-medium"
                    onClick={() => {
                      onServiceOrg(soc);
                    }}
                  >
                    {p.process_name}
                  </button>
                ) : (
                  p.process_name
                )}
              </td>
              <td className={cn("px-[8px]", HAIR)}>
                {p.walkthrough_on !== null
                  ? P.done(fmt.date(p.walkthrough_on))
                  : soc !== null && names[soc] !== undefined
                    ? P.viaSoc(names[soc])
                    : COPY.none}
              </td>
              <td className={cn("px-[8px]", HAIR)}>
                {p.design === "deficient" ? (
                  <Pill variant="red-tint" size="sm">
                    {P.design_status.deficient}
                  </Pill>
                ) : (
                  P.design_status[p.design]
                )}
              </td>
              <td className={cn("px-[8px]", HAIR)}>{P.implementation_status[p.implementation]}</td>
              <td className={cn("px-[8px]", HAIR)}>{P.reliance_status[p.reliance]}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** AUD-09's canvas for the cockpit (AUD-02 renders it for `?section=internal_control`). */
export function useControlsCanvas(
  cockpit: AuditCockpitOut,
  options: ControlsOptions = {},
): CockpitCanvas {
  const on = useFlag(FLAG) === true;
  const active = options.active ?? true;
  const engagementId = cockpit.engagement_id;
  const failed = controlsFailed(cockpit);
  const [ownSheet, setOwnSheet] = useState<ControlsSheet>(options.sheet ?? "exceptions");
  const [ownCell, setOwnCell] = useState<string>(options.cell ?? "C1");
  const sheet = options.sheet ?? ownSheet;
  const cell = options.cell ?? ownCell;
  const exceptions = useQuery({
    ...controlExceptionsOptions({ path: { engagement_id: engagementId } }),
    enabled: on && active && sheet === "exceptions" && !failed,
  });
  const processes = useQuery({
    ...processesOptions({ path: { engagement_id: engagementId } }),
    enabled: on && active && sheet === "internal-control",
  });
  const orgs = useQuery({
    ...serviceOrgsOptions({ path: { engagement_id: engagementId } }),
    enabled: on && active && sheet === "internal-control",
  });
  const names = Object.fromEntries((orgs.data?.items ?? []).map((o) => [o.id, o.name]));
  const read = sheet === "exceptions" ? exceptions : processes;

  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: FLAG };
  else if (read.isError) {
    const status = (read.error as { status?: number } | null)?.status;
    state =
      status === 404
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry: () => void read.refetch() };
  } else if (!failed && read.data === undefined) state = { kind: "loading" };

  return {
    title: COPY.title,
    state,
    empty: { title: COPY.states.empty },
    actions: <PaneAction kind="icon" icon="download" label={COPY.download} />,
    controls: (
      <>
        <Segmented
          size="small"
          label={COPY.title}
          options={[COPY.tabs.internal_control, COPY.tabs.exceptions]}
          active={sheet === "exceptions" ? COPY.tabs.exceptions : COPY.tabs.internal_control}
          onChange={(next) => {
            const s: ControlsSheet =
              next === COPY.tabs.exceptions ? "exceptions" : "internal-control";
            setOwnSheet(s);
            options.onSheet?.(s);
          }}
        />
        <span className="flex-1" />
        <Button variant="secondary" size="sm" icon="cloud-download">
          {COPY.openInExcel}
        </Button>
      </>
    ),
    children:
      sheet === "exceptions" ? (
        <ExceptionsSheet
          rows={exceptions.data?.items ?? []}
          engagementId={engagementId}
          failed={failed}
          cell={cell}
          onCell={(next) => {
            setOwnCell(next);
            options.onCell?.(next);
          }}
          options={options}
        />
      ) : (
        <ProcessesSheet
          processes={processes.data?.items ?? []}
          names={names}
          onServiceOrg={options.onServiceOrg}
        />
      ),
  };
}

/** AUD-09 d: the failed Internal Control step on the run, its reason quoted verbatim. */
export function FailedStepCard({
  cockpit,
  onFix,
}: {
  cockpit: AuditCockpitOut;
  onFix?: () => void;
}): JSX.Element | null {
  const runs = useQuery({
    ...listAgentRunsOptions({
      path: { engagement_id: cockpit.engagement_id },
      query: { limit: 10 },
    }),
    retry: false,
  });
  const retry = useMutation(workpaperDraftMutation());
  const row = rowOf(cockpit);
  const run = runs.data?.find((r) => r.state === "failed");
  if (!controlsFailed(cockpit) || run === undefined || row === undefined) return null;
  return (
    <div
      data-aud09="failed-step"
      className="flex flex-col gap-[6px] rounded-[8px] bg-red-tint px-[10px] pt-[8px] pb-[9px] shadow-e1"
    >
      <span className="text-dense font-medium text-red-ink">{COPY.failed.execute}</span>
      <span className="text-dense hairline-t pt-[4px]">{COPY.failed.card}</span>
      <p data-aud09="run-error" className="text-dense text-red-ink">
        {run.state_reason ?? ""}
      </p>
      <div className="flex items-center gap-[8px]">
        <Button
          variant="secondary"
          size="xs"
          disabled={retry.isPending}
          onClick={() => {
            retry.mutate({
              path: { engagement_id: cockpit.engagement_id, workpaper_id: row.work_item_ref },
              body: { mode: "ic", section_key: INTERNAL_CONTROL },
              headers: idempotency(),
            });
          }}
        >
          {COPY.failed.retry}
        </Button>
        {onFix !== undefined && (
          <button type="button" className="text-dense font-medium text-ink" onClick={onFix}>
            {COPY.failed.fix} <span className="text-ink-3">{COPY.failed.arrow}</span>
          </button>
        )}
      </div>
    </div>
  );
}
