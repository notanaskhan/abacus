// CLS-03 · Close › Intake (C-01-T35; handoff CLS-03 A–F + R2 G–H; C-01 §5 row a to h): T9
// close-review, 790 = request tree 310 + detail 480, then the viewer 576. The tree is the close's
// request tree (`GET /v1/closes/{id}/requests`): three indent levels, received rows with "Linked
// (n)" and a screening glyph; the questionnaire below it (d). The detail column is the request's
// Document Request and Uploaded Document cards with the summary's code totals (each cited to its
// sheet cell; hovering one lights the cell in the viewer within the 360 ms fade), the screening
// card (R2) and the pinned footer: only a person's click incorporates (b, with "Re-run affected
// tasks") or returns (a3, the reason picker). A requested row (c) offers Send reminder and Upload
// on behalf; dropping a file onto the tree (e) uploads on the client's behalf. Before BD1 (f) the
// tree is an EmptyState. The viewer is the uploaded file's text (`/evidence-versions/{id}/text`),
// the only zebra table; the browser sums nothing.
import type { IntakeSummaryOut, RequestNodeOut, ViewerTextSheetOut } from "@abacus/api-client";
import {
  closeIntakeSummaryOptions,
  closeQuestionnaireOptions,
  closeRequestsOptions,
  viewerTextOptions,
} from "@abacus/api-client/query";
import { Button, EmptyState, Icon, Skeleton, Spinner, StatusDisc, Toggle } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useMemo, useState } from "react";
import { COPY, RETURN_REASONS, subLineOf } from "./copy";

export type IntakeSelection = { kind: "request"; id: string } | { kind: "questionnaire" };

export interface CLS03Props {
  closeId: string;
  /** A scenario's starting selection and open surfaces (a2, a3, e, h). */
  initial?: {
    selected?: IntakeSelection;
    lit?: string | null;
    picker?: boolean;
    dropTarget?: boolean;
    rescreening?: boolean;
  };
  onIncorporate?: (requestItemId: string) => void;
  onUndo?: (requestItemId: string) => void;
  onReturn?: (requestItemId: string, reason: string) => void;
  onRerun?: (planRowIds: readonly string[]) => void;
  onSendReminder?: (requestItemId: string) => void;
  onUploadOnBehalf?: (requestItemId: string | null, files: readonly File[]) => void;
  onOpen?: (target: string) => void;
}

/** Every request node in tree order (categories flattened). */
export function requestsOf(nodes: readonly RequestNodeOut[]): RequestNodeOut[] {
  return nodes.flatMap((n) => (n.kind === "request" ? [n] : requestsOf(n.children ?? [])));
}

/** "7 received of 9" across the tree. */
export function receivedCount(nodes: readonly RequestNodeOut[]): { received: number; total: number } {
  const all = requestsOf(nodes);
  return { received: all.filter((r) => r.status !== "requested").length, total: all.length };
}

function money(value: string | null | undefined): string {
  if (value === null || value === undefined) return "";
  const [whole, cents = "00"] = value.split(".");
  return `$${Number(whole).toLocaleString("en-US")}.${cents.padEnd(2, "0").slice(0, 2)}`;
}

function Disc({ node }: { node: RequestNodeOut }): JSX.Element {
  return node.status === "requested" ? (
    <StatusDisc state="todo" size={15} />
  ) : (
    <StatusDisc state="done" size={15} />
  );
}

function TreeRow({
  node,
  level,
  selected,
  onSelect,
}: {
  node: RequestNodeOut;
  level: number;
  selected: boolean;
  onSelect: () => void;
}): JSX.Element {
  const received = node.status !== "requested";
  return (
    <li>
      <button
        type="button"
        data-request={node.request_item_id}
        data-status={node.status}
        aria-current={selected ? "true" : undefined}
        onClick={onSelect}
        style={{ paddingLeft: [12, 30, 48][Math.min(level, 2)] }}
        className={`flex min-h-[34px] w-full items-start gap-[8px] py-[6px] pr-[12px] text-left ${
          selected ? "bg-selected font-medium" : "hover:bg-nested"
        }`}
      >
        <Disc node={node} />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-[13px]">{node.title}</span>
          <span className="flex items-center gap-[4px] text-[11.5px] font-normal text-ink-3">
            {subLineOf(node)}
            {received && node.screening === "flagged" ? (
              <Icon name="triangle-alert" size={12} className="text-amber" />
            ) : received ? (
              <Icon name="check" size={12} className="text-green" />
            ) : null}
          </span>
        </span>
        <span className="flex items-center gap-[3px] text-[11.5px] text-ink-3">
          {received ? (
            <>
              <Icon name="link-2" size={12} />
              {`${COPY.linked} (${String(node.linked ?? 0)})`}
            </>
          ) : (
            <span className="text-ink-4">—</span>
          )}
        </span>
      </button>
    </li>
  );
}

function TreeNodes({
  nodes,
  level,
  selected,
  onSelect,
}: {
  nodes: readonly RequestNodeOut[];
  level: number;
  selected: string | null;
  onSelect: (id: string) => void;
}): JSX.Element {
  return (
    <ul>
      {nodes.map((n) =>
        n.kind === "category" ? (
          <li key={n.node_id} data-category={n.node_id}>
            <div
              style={{ paddingLeft: [12, 30, 48][Math.min(level, 2)] }}
              className="flex h-[34px] items-center gap-[6px] pr-[12px] text-[13px] font-medium"
            >
              <Icon name={(n.children ?? []).length > 0 ? "chevron-down" : "chevron-right"} size={12} className="text-ink-3" />
              {n.title}
            </div>
            <TreeNodes nodes={n.children ?? []} level={level + 1} selected={selected} onSelect={onSelect} />
          </li>
        ) : (
          <TreeRow
            key={n.node_id}
            node={n}
            level={level + 1}
            selected={selected === n.request_item_id}
            onSelect={() => onSelect(n.request_item_id ?? "")}
          />
        ),
      )}
    </ul>
  );
}

function Card({ icon, title, children }: { icon: "file-text" | "file"; title: string; children: JSX.Element | JSX.Element[] }): JSX.Element {
  return (
    <section className="m-[10px] overflow-hidden rounded-card bg-card shadow-e1" aria-label={title}>
      <h3 className="flex h-[36px] items-center gap-[8px] bg-band-hd px-[13px] text-[13.5px] font-medium">
        <Icon name={icon} size={15} className="text-ink-3" />
        {title}
      </h3>
      {children}
    </section>
  );
}

function Field({ k, children }: { k: string; children: JSX.Element | string }): JSX.Element {
  return (
    <div className="flex min-h-[35px] items-center gap-[10px] px-[13px] py-[6px] hairline-t">
      <span className="flex-1 text-[13px] text-ink-2">{k}</span>
      <span className="text-right text-[13px] font-medium">{children}</span>
    </div>
  );
}

function SummaryFigures({
  summary,
  onLight,
}: {
  summary: IntakeSummaryOut;
  onLight: (cell: string | null) => void;
}): JSX.Element {
  return (
    <div className="px-[13px] pt-[9px] pb-[11px] hairline-t">
      <div className="mb-[6px] text-[12px] text-ink-3">
        {summary.label === "totals_from_file" ? COPY.totalsFromFile : COPY.summary}
      </div>
      {summary.paragraph ? <p className="text-[12.5px] leading-[1.5]">{summary.paragraph}</p> : null}
      <ul className="mt-[8px] flex flex-col gap-[4px]">
        {summary.figures.map((f) => (
          <li key={f.key}>
            <button
              type="button"
              data-figure={f.key}
              data-cite={f.citation_id}
              onMouseEnter={() => onLight(f.key)}
              onMouseLeave={() => onLight(null)}
              onFocus={() => onLight(f.key)}
              onBlur={() => onLight(null)}
              className="flex w-full items-center justify-between rounded-[4px] px-[4px] text-[12.5px] hover:bg-nested"
            >
              <span className="text-ink-2">{f.label}</span>
              <span className="tabular-nums">
                {f.amount !== null && f.amount !== undefined ? money(f.amount) : (f.count ?? 0).toLocaleString("en-US")}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// The summary figure → the total row's column (C23..F23 in the sheet).
const FIGURE_COLUMN: Readonly<Record<string, number>> = { transactions: 2, gross: 3, fees: 4, net: 5 };

function SheetView({ sheet, lit }: { sheet: ViewerTextSheetOut; lit: string | null }): JSX.Element {
  const [header, ...rows] = sheet.rows;
  const litColumn = lit === null ? null : (FIGURE_COLUMN[lit] ?? null);
  return (
    <div className="m-[6px_14px_14px] overflow-auto rounded-[4px] bg-card px-[16px] pt-[26px] pb-[22px] shadow-e1">
      <table className="w-full border-collapse text-[9px] tabular-nums" aria-label={sheet.name}>
        <thead>
          <tr className="bg-espresso text-on-dark">
            {(header ?? []).map((h) => (
              <th key={h} className="px-[4px] py-[3px] text-left font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const total = i === rows.length - 1;
            return (
              <tr key={`${r[0] ?? ""}-${String(i)}`} className={`${i % 2 === 1 ? "bg-zebra" : ""} ${total ? "border-t border-ink font-medium" : ""}`}>
                {r.map((cell, j) => (
                  <td
                    key={`${String(j)}-${cell}`}
                    data-cell={`${String.fromCharCode(65 + j)}${String(i + 2)}`}
                    data-lit={total && litColumn === j ? "true" : undefined}
                    className={`px-[4px] py-[2px] transition-[background-color] duration-[360ms] ${
                      j >= 2 ? "text-right" : ""
                    } ${total && litColumn === j ? "bg-lit" : ""}`}
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function CLS03(props: CLS03Props): JSX.Element {
  const tree = useQuery(closeRequestsOptions({ path: { close_id: props.closeId } }));
  const all = useMemo(() => requestsOf(tree.data?.nodes ?? []), [tree.data]);
  const initial = props.initial ?? {};
  const [selection, setSelection] = useState<IntakeSelection | null>(initial.selected ?? null);
  const [lit, setLit] = useState<string | null>(initial.lit ?? null);
  const [picker, setPicker] = useState(initial.picker === true);
  const [dragging, setDragging] = useState(initial.dropTarget === true);
  const chosen =
    selection?.kind === "request"
      ? all.find((r) => r.request_item_id === selection.id)
      : selection === null
        ? all[0]
        : undefined;
  const version = chosen?.evidence_version_id ?? null;
  const summary = useQuery({
    ...closeIntakeSummaryOptions({ path: { evidence_version_id: version ?? "" } }),
    enabled: version !== null,
  });
  const text = useQuery({
    ...viewerTextOptions({ path: { version_id: version ?? "" } }),
    enabled: version !== null,
  });
  const questionnaire = useQuery({
    ...closeQuestionnaireOptions({ path: { close_id: props.closeId } }),
    enabled: selection?.kind === "questionnaire",
  });
  if (tree.data === undefined) {
    return (
      <div className="flex flex-1 items-center justify-center p-[20px]">
        <Skeleton className="h-[9px] w-[320px]" />
      </div>
    );
  }
  if (!tree.data.published) {
    return (
      <div data-screen="CLS-03" data-state="f" className="flex flex-1 items-center justify-center">
        <EmptyState icon="calendar" title={COPY.notPublished(tree.data.publishes_on ?? null, tree.data.plan_version ?? null)} />
      </div>
    );
  }
  const id = chosen?.request_item_id ?? null;
  const received = chosen !== undefined && chosen.status !== "requested";
  const incorporated = chosen?.status === "incorporated";
  const sheet = text.data?.sheets[0];
  return (
    <div data-screen="CLS-03" className="flex min-h-0 flex-1 gap-[10px] p-[10px]">
      <section
        aria-label={COPY.intake}
        style={{ width: 790 }}
        className="flex flex-none flex-col overflow-hidden rounded-pane bg-card shadow-e2"
      >
        <header className="relative flex h-[46px] flex-none items-center justify-center text-[14.5px] font-medium hairline-b">
          {COPY.intake}
          <span className="absolute right-[10px] flex gap-[6px]">
            <button type="button" aria-label={COPY.sendReminder} onClick={() => id && props.onSendReminder?.(id)} className="flex size-[29px] items-center justify-center rounded-pill bg-card shadow-e1">
              <Icon name="mail" size={14} />
            </button>
            <button type="button" aria-label={COPY.uploadOnBehalf} onClick={() => setDragging(true)} className="flex size-[29px] items-center justify-center rounded-pill bg-card shadow-e1">
              <Icon name="upload" size={14} />
            </button>
          </span>
        </header>
        <div className="flex min-h-0 flex-1">
          <nav
            aria-label={COPY.requested}
            data-drop-target={dragging ? "on" : undefined}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              props.onUploadOnBehalf?.(id, [...e.dataTransfer.files]);
            }}
            style={{ width: 310 }}
            className={`flex-none overflow-y-auto hairline-r ${dragging ? "bg-chip ring-2 ring-inset ring-espresso" : ""}`}
          >
            <h3 className="flex h-[36px] items-center px-[12px] text-[13.5px] font-medium">{COPY.requested}</h3>
            <TreeNodes
              nodes={tree.data.nodes}
              level={-1}
              selected={selection?.kind === "questionnaire" ? null : id}
              onSelect={(rid) => {
                setSelection({ kind: "request", id: rid });
                setPicker(false);
              }}
            />
            <h3 className="flex h-[36px] items-center px-[12px] text-[13.5px] font-medium hairline-t">{COPY.questionnaire}</h3>
            <button
              type="button"
              data-questionnaire
              aria-current={selection?.kind === "questionnaire" ? "true" : undefined}
              onClick={() => setSelection({ kind: "questionnaire" })}
              className={`flex w-full flex-col px-[30px] py-[6px] text-left ${selection?.kind === "questionnaire" ? "bg-selected font-medium" : "hover:bg-nested"}`}
            >
              <span className="text-[13px]">{COPY.questionnaireTitle}</span>
            </button>
          </nav>
          <div style={{ width: 480 }} className="flex min-w-0 flex-none flex-col">
            <div className="min-h-0 flex-1 overflow-y-auto">
              {selection?.kind === "questionnaire" ? (
                <Card icon="file-text" title={COPY.questionnaireTitle}>
                  <div className="px-[13px] py-[8px] text-[12px] text-ink-3">
                    {questionnaire.data ? `${String(questionnaire.data.answered)} of ${String(questionnaire.data.total)} answered` : ""}
                  </div>
                  <ul>
                    {(questionnaire.data?.items ?? []).map((q) => (
                      <li key={q.question} data-question className="flex flex-col gap-[2px] px-[13px] py-[8px] hairline-t">
                        <span className="text-[13px] font-medium">{q.question}</span>
                        {q.answer === null || q.answer === undefined ? (
                          <span className="text-[12.5px] text-amber-ink">{COPY.awaitingAnswer}</span>
                        ) : (
                          <>
                            <span className="text-[12.5px] text-ink-2">{q.answer}</span>
                            <span className="text-[11.5px] text-ink-3">{q.answered_by}</span>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                </Card>
              ) : chosen !== undefined ? (
                <>
                  <Card icon="file-text" title={COPY.documentRequest}>
                    <Field k={COPY.fields.request}>{chosen.title}</Field>
                    <Field k={COPY.fields.visible}>
                      <Toggle checked={chosen.client_visible === true} label={COPY.fields.visible} onChange={() => undefined} />
                    </Field>
                    <Field k={COPY.fields.due}>{chosen.due_on ?? "—"}</Field>
                  </Card>
                  {received ? (
                    <Card icon="file" title={COPY.uploadedDocument}>
                      <Field k={COPY.fields.status}>
                        <span
                          data-pill={chosen.status}
                          className={`inline-flex h-[21px] items-center rounded-pill px-[8px] text-[12px] ${
                            incorporated ? "bg-green text-on-dark" : "bg-amber-tint text-amber-ink"
                          }`}
                        >
                          {incorporated ? COPY.incorporated : COPY.pendingIncorporation}
                        </span>
                      </Field>
                      {initial.rescreening === true ? (
                        <div data-rescreening className="flex items-center gap-[6px] px-[13px] py-[10px] text-[12.5px] text-ink-3 hairline-t">
                          <Spinner size={12} label={COPY.screening} showLabel={false} />
                          {COPY.screening}
                        </div>
                      ) : summary.data ? (
                        <SummaryFigures summary={summary.data} onLight={setLit} />
                      ) : (
                        <div className="px-[13px] py-[10px] hairline-t">
                          <Skeleton className="h-[9px] w-[200px]" />
                        </div>
                      )}
                    </Card>
                  ) : (
                    <Card icon="file" title={COPY.uploadedDocument}>
                      <EmptyState icon="upload" title={COPY.nothingUploaded} />
                      <div className="flex gap-[8px] px-[13px] py-[10px] hairline-t">
                        <Button variant="secondary" size="sm" onClick={() => id && props.onSendReminder?.(id)}>
                          {COPY.sendReminderEllipsis}
                        </Button>
                        <Button variant="secondary" size="sm" onClick={() => setDragging(true)}>
                          {COPY.uploadOnBehalfEllipsis}
                        </Button>
                      </div>
                    </Card>
                  )}
                </>
              ) : null}
            </div>
            {chosen !== undefined && received && selection?.kind !== "questionnaire" ? (
              <footer className="flex flex-col gap-[8px] p-[10px] hairline-t">
                {incorporated ? (
                  <>
                    {(chosen.rerun_plan_row_ids ?? []).length > 0 ? (
                      <Button variant="secondary" size="lg" onClick={() => props.onRerun?.(chosen.rerun_plan_row_ids ?? [])}>
                        {COPY.rerunAffected}
                      </Button>
                    ) : null}
                    <Button variant="ghost" size="lg" onClick={() => id && props.onUndo?.(id)}>
                      {COPY.undoIncorporation}
                    </Button>
                  </>
                ) : picker ? (
                  <div role="menu" aria-label={COPY.returnToClient} data-picker className="flex flex-col gap-[4px]">
                    {RETURN_REASONS.map((r) => (
                      <Button key={r} variant="secondary" size="sm" onClick={() => id && props.onReturn?.(id, r)}>
                        {r}
                      </Button>
                    ))}
                  </div>
                ) : (
                  <>
                    <Button variant="primary" size="lg" onClick={() => id && props.onIncorporate?.(id)}>
                      <Icon name="check" size={14} />
                      {COPY.incorporate}
                    </Button>
                    <Button variant="secondary" size="lg" onClick={() => setPicker(true)}>
                      {COPY.returnToClient}
                    </Button>
                  </>
                )}
              </footer>
            ) : null}
          </div>
        </div>
      </section>
      <section aria-label={COPY.viewer} className="flex min-w-0 flex-1 flex-col rounded-pane bg-card shadow-e2">
        <header className="flex h-[46px] flex-none items-center justify-center text-[14px] font-medium hairline-b">
          {received && sheet !== undefined ? sheet.name : ""}
        </header>
        <div className="min-h-0 flex-1 overflow-auto bg-shell">
          {received && sheet !== undefined ? <SheetView sheet={sheet} lit={lit} /> : null}
        </div>
      </section>
    </div>
  );
}
