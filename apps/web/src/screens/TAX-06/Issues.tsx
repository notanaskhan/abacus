// TAX-06 · Return › Issues (T-04-T26; handoff TAX-06) in fixture mode on T9 issues-individual
// (546 = 262 queue + ≈260 detail · viewer 433 · sheets 377). Selecting a row lights its linked
// file chip, the viewer's K-1 region and the worksheet fields together (purple only through the
// match tokens). The 18A ghost values are the agent's proposal: Accept opens SHL-10 (the host),
// Reject asks a reason, and nothing changes here until the server answers. The agent never
// resolves: Mark as Resolved is a person's and needs a note; the Draft K-1 issue resolves only
// when the final K-1 is released.
import { Button, Pill } from "@abacus/ui";
import { type JSX, useState } from "react";
import {
  COPY,
  DETAILS,
  type Frame,
  type IssueRow,
  issuesCsv,
  OPEN,
  RESOLVED,
  SELECTED,
  SHEET_ROWS,
  STATE_ROWS,
} from "./copy";

export interface IssuesProps {
  frame: Frame;
  /** Issues after SHL-10 approved the 18A proposal (4 → 3); the host passes the server's count. */
  openCount?: number;
  /** Accept on a ghost value: SHL-10 approve with the two-field diff. */
  onAccept?: (issue: string) => void;
  /** Reject on a ghost value, with its reason. */
  onReject?: (issue: string, reason: string) => void;
  /** Set Fix Instructions: SHL-15 with the suggested instruction. */
  onSetFix?: (issue: string, suggested: string) => void;
  /** Explain…: `POST /v1/tax/issues/{id}/explanations` (T-04-T31). */
  onExplain?: (issue: string) => void;
  /** Mark as Resolved with the person's note. */
  onResolve?: (issue: string, note: string) => void;
  /** Ask the client…: POR-04 request preview. */
  onAskClient?: (issue: string) => void;
  /** Download: the CSV of the issues shown. */
  onDownload?: (csv: string) => void;
}

function Flag({ severity }: { severity: IssueRow["severity"] }): JSX.Element {
  return (
    <span
      aria-hidden
      data-severity={severity}
      className={severity === "high" ? "text-red" : "text-amber"}
    >
      ⚑
    </span>
  );
}

function Queue({
  rows,
  selected,
  fixing,
  onSelect,
}: {
  rows: readonly IssueRow[];
  selected: string | null;
  fixing: boolean;
  onSelect: (key: string) => void;
}): JSX.Element {
  const groups = [...new Set(rows.map((r) => r.group))];
  return (
    <div role="listbox" aria-label={COPY.queueHead} className="flex flex-col">
      {groups.map((group) => (
        <div key={group}>
          <div className="flex h-[31px] items-center px-[12px] text-[13.5px] font-medium">
            {group} ⌄
          </div>
          {[...new Set(rows.filter((r) => r.group === group).map((r) => r.sub))].map((sub) => (
            <div key={sub}>
              <div className="px-[20px] text-[12.5px] text-ink-2">{sub} ⌄</div>
              {rows
                .filter((r) => r.group === group && r.sub === sub)
                .map((r) => (
                  <button
                    key={r.key}
                    type="button"
                    role="option"
                    data-issue={r.key}
                    aria-selected={selected === r.key}
                    onClick={() => {
                      onSelect(r.key);
                    }}
                    className={`flex w-full items-start gap-[6px] py-[8px] pl-[32px] pr-[10px] text-left ${selected === r.key ? "bg-nested font-medium" : ""} ${r.resolved ? "text-ink-2" : ""}`}
                  >
                    <Flag severity={r.severity} />
                    <span className="flex min-w-0 flex-col">
                      <span className="line-clamp-2 text-[12.5px] leading-[1.32]">{r.title}</span>
                      <span className="text-[11.5px] text-ink-3">
                        {r.resolved ? `${r.resolved.on}` : r.kind}
                      </span>
                    </span>
                    {r.resolved ? (
                      <Pill variant="green-tint" size="state">
                        {COPY.resolvedPill}
                      </Pill>
                    ) : null}
                    {r.agentCanFix ? (
                      <span
                        aria-label={fixing ? "The agent is fixing this" : "The agent can fix this"}
                        data-fixing={fixing ? "true" : "false"}
                        className="ml-auto text-[13px] text-ink-3"
                      >
                        ⚛
                        {fixing ? (
                          <span aria-hidden className="ml-[2px] text-ink-2">
                            ◌
                          </span>
                        ) : null}
                      </span>
                    ) : null}
                  </button>
                ))}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function GhostField({
  label,
  ghost,
  value,
  lit,
  onAccept,
  onReject,
}: {
  label: string;
  ghost?: string | undefined;
  value?: string | undefined;
  lit: boolean;
  onAccept?: (() => void) | undefined;
  onReject?: ((reason: string) => void) | undefined;
}): JSX.Element {
  const [asking, setAsking] = useState(false);
  return (
    <div
      data-field={label}
      data-lit={lit && ghost ? "true" : "false"}
      className="flex min-h-[42px] items-center justify-between gap-[8px] px-[12px]"
    >
      <span className={`text-[13px] ${ghost ? "font-medium" : ""}`}>{label}</span>
      {ghost ? (
        <span className="flex flex-col items-end gap-[4px]">
          <span
            data-ghost="true"
            className={`w-[96px] rounded-[6px] border border-dashed px-[6px] text-right text-[13px] tabular-nums ${lit ? "border-match-line bg-match-bg" : "border-match-line"}`}
          >
            {ghost}
          </span>
          <span className="flex gap-[4px]">
            <Button variant="primary" size="sm" onClick={onAccept}>
              {COPY.accept}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              aria-expanded={asking}
              onClick={() => {
                setAsking(!asking);
              }}
            >
              {COPY.reject}
            </Button>
          </span>
          {asking ? (
            <span role="menu" aria-label="Reject reason" className="flex flex-col">
              {COPY.rejectReasons.map((reason) => (
                <button
                  key={reason}
                  type="button"
                  role="menuitem"
                  className="text-left text-[12.5px]"
                  onClick={() => {
                    setAsking(false);
                    onReject?.(reason);
                  }}
                >
                  {reason}
                </button>
              ))}
            </span>
          ) : null}
        </span>
      ) : (
        <span className="w-[96px] text-right text-[13px] tabular-nums">{value}</span>
      )}
    </div>
  );
}

export function Issues({
  frame,
  openCount,
  onAccept,
  onReject,
  onSetFix,
  onExplain,
  onResolve,
  onAskClient,
  onDownload,
}: IssuesProps): JSX.Element {
  const [selected, setSelected] = useState<string | null>(SELECTED[frame]);
  const [note, setNote] = useState("");
  if (frame === "loading") {
    return (
      <div data-screen="TAX-06" data-frame="loading" aria-busy="true" className="flex gap-[10px]">
        {[546, 433, 377].map((w) => (
          <div
            key={w}
            data-skeleton
            className="h-[700px] rounded-pane bg-nested"
            style={{ width: w }}
          />
        ))}
        <span className="sr-only">{COPY.loading}</span>
      </div>
    );
  }
  const empty = frame === "g";
  const rows = frame === "f" ? RESOLVED : empty ? [] : OPEN;
  const open = openCount ?? (empty ? 0 : OPEN.length);
  const detail = selected ? DETAILS[selected] : undefined;
  const lit = selected === "box18a";
  const fixing = frame === "e";
  const resolveBlocked = detail?.resolveDisabled;
  return (
    <div data-screen="TAX-06" data-frame={frame} className="flex flex-col">
      <header className="flex h-[42px] items-center justify-center gap-[8px]">
        <span className="text-[15px] font-medium">{COPY.title}</span>
        <span className="text-ink-2">{COPY.client}</span>
      </header>
      <nav aria-label="Return" className="flex h-[44px] items-center justify-center gap-[6px]">
        {COPY.tabs(open).map((t) => (
          <span
            key={t}
            data-tab={t}
            aria-current={t.startsWith("Issues") ? "page" : undefined}
            className={`rounded-[8px] px-[10px] py-[4px] text-[13px] ${t.startsWith("Issues") ? "bg-card font-medium shadow-e1" : "text-ink-2"}`}
          >
            {t.startsWith("Issues") ? (
              <>
                Issues{" "}
                <span className="rounded-[6px] bg-red-tint px-[4px] text-red-ink">{open}</span>
              </>
            ) : (
              t
            )}
          </span>
        ))}
      </nav>
      <div className="flex gap-[10px] px-[12px] pb-[12px]">
        <section
          aria-label={COPY.pane}
          className="flex w-[546px] flex-col rounded-pane bg-card shadow-e1"
        >
          <div className="flex h-[46px] items-center justify-between px-[12px]">
            <span className="text-[12.5px] text-ink-3">Search</span>
            <span className="font-medium">{COPY.pane}</span>
            <span className="flex gap-[6px]">
              <Button
                variant="ghost"
                size="sm"
                aria-label={COPY.download}
                onClick={() => onDownload?.(issuesCsv(rows))}
              >
                ⤓
              </Button>
              <Button variant="secondary" size="sm">
                {COPY.addIssue}
              </Button>
            </span>
          </div>
          <div className="flex gap-[8px] bg-nested p-[8px]">
            <div className="flex w-[262px] flex-col rounded-[10px] bg-card shadow-e1">
              <div className="flex items-start justify-between px-[12px] py-[10px]">
                <span className="flex flex-col">
                  <span className="text-[14px] font-medium">{COPY.queueHead}</span>
                  <span className="text-[11.5px] text-ink-3">{COPY.queueSub}</span>
                </span>
                <Button variant="secondary" size="sm">
                  {COPY.addInstructions}
                </Button>
              </div>
              {empty ? (
                <div className="flex flex-col gap-[4px] px-[12px] py-[24px]">
                  <span className="text-[13px] font-medium">{COPY.emptyTitle}</span>
                  <span className="text-[12.5px] text-ink-2">{COPY.emptyBody}</span>
                </div>
              ) : (
                <Queue rows={rows} selected={selected} fixing={fixing} onSelect={setSelected} />
              )}
            </div>
            <div
              className={`flex flex-1 flex-col rounded-[10px] shadow-e1 ${detail ? "bg-card" : "bg-nested"}`}
            >
              {detail && selected ? (
                <>
                  <div className="flex items-center gap-[6px] px-[14px] py-[12px] text-[15px] font-medium leading-[1.3]">
                    {OPEN.find((r) => r.key === selected)?.title}
                    {fixing && selected === "box18a" ? (
                      <Pill variant="amber" size="state">
                        {COPY.inProgress}
                      </Pill>
                    ) : null}
                  </div>
                  {detail.body ? (
                    <p className="px-[14px] text-[12.5px] leading-[1.55] text-ink-2">
                      {detail.body}
                    </p>
                  ) : null}
                  {fixing && selected === "box18a" ? (
                    <div data-run-row className="px-[14px] py-[6px] text-[12.5px] text-ink-2">
                      <span aria-hidden>◌ </span>
                      {COPY.running}
                    </div>
                  ) : null}
                  <dl className="flex flex-col px-[14px]">
                    {[
                      ["Assigned to", detail.assignedTo],
                      ["Priority", detail.priority],
                      ...(detail.kindPill ? [["Kind", detail.kindPill]] : []),
                      ["Created by", detail.createdBy],
                    ].map(([k, v]) => (
                      <div key={k} className="flex h-[35px] items-center justify-between">
                        <dt className="text-ink-2">{k}</dt>
                        <dd>
                          {k === "Kind" ? (
                            <Pill variant="amber" size="state">
                              {v}
                            </Pill>
                          ) : (
                            v
                          )}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  {detail.blocks ? (
                    <>
                      <div className="flex h-[31px] items-center bg-band-hd px-[14px] text-[13.5px] font-medium">
                        {COPY.whatItBlocks}
                      </div>
                      <p className="px-[14px] py-[6px] text-[12.5px] text-ink-2">
                        {detail.blocks}
                      </p>
                    </>
                  ) : null}
                  <div className="flex h-[31px] items-center bg-band-hd px-[14px] text-[13.5px] font-medium">
                    {COPY.linkedEntities}
                  </div>
                  <p className="px-[14px] text-[12.5px]">{detail.linked}</p>
                  {detail.chip ? (
                    <span
                      data-chip={detail.chip}
                      data-lit={lit ? "true" : "false"}
                      className={`mx-[14px] my-[6px] inline-flex h-[28px] items-center rounded-[6px] px-[8px] text-[12.5px] ${lit ? "bg-match-bg ring-1 ring-match-line" : "bg-nested"}`}
                    >
                      {detail.chip}
                    </span>
                  ) : null}
                  <div className="mt-auto flex flex-col gap-[8px] p-[10px]">
                    {detail.note ? (
                      <span className="text-[12.5px] text-ink-3">{detail.note}</span>
                    ) : null}
                    <Button
                      variant="primary"
                      onClick={() => {
                        if (detail.primary === "Set Fix Instructions") {
                          onSetFix?.(selected, COPY.fixInstruction);
                        } else if (detail.primary === "Ask the client…") {
                          onAskClient?.(selected);
                        }
                      }}
                    >
                      {detail.primary}
                    </Button>
                    {selected === "box18a" ? (
                      <Button variant="tonal" onClick={() => onExplain?.(selected)}>
                        {COPY.explain}
                      </Button>
                    ) : null}
                    {resolveBlocked ? null : (
                      <input
                        aria-label="Resolution note"
                        value={note}
                        onChange={(e) => {
                          setNote(e.target.value);
                        }}
                        className="rounded-[6px] border border-hairline px-[6px] text-[12.5px]"
                      />
                    )}
                    <Button
                      variant="tonal"
                      disabled={Boolean(resolveBlocked) || note.trim() === ""}
                      title={
                        resolveBlocked ??
                        (note.trim() === "" ? COPY.resolveNoteRequired : undefined)
                      }
                      onClick={() => onResolve?.(selected, note.trim())}
                    >
                      ✓ {COPY.resolve}
                    </Button>
                    {resolveBlocked ? (
                      <span className="text-[12.5px] text-ink-3">{resolveBlocked}</span>
                    ) : null}
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </section>
        <section
          aria-label="Viewer"
          className="flex w-[433px] flex-col rounded-pane bg-card shadow-e1"
        >
          <div className="flex h-[46px] items-center px-[12px] text-[13px]">{COPY.viewer}</div>
          <div
            data-region="18A"
            data-lit={lit ? "true" : "false"}
            className={`mx-[12px] rounded-[4px] px-[6px] py-[4px] text-[12px] ${lit ? "bg-match-bg ring-1 ring-match-line" : ""}`}
          >
            {COPY.region}
          </div>
        </section>
        <section
          aria-label="Worksheets"
          className="flex w-[377px] flex-col rounded-pane bg-card shadow-e1"
        >
          <div className="flex h-[31px] items-center bg-band-hd px-[12px] text-[13.5px] font-medium">
            {COPY.sheetsSection} ⌄
          </div>
          {SHEET_ROWS.map((r) => (
            <GhostField
              key={r.label}
              label={r.label}
              ghost={r.ghost}
              value={r.value}
              lit={lit}
              onAccept={() => onAccept?.("box18a")}
              onReject={(reason) => onReject?.("box18a", reason)}
            />
          ))}
          <div className="flex h-[31px] items-center bg-band-hd px-[12px] text-[13.5px] font-medium">
            {COPY.stateSection} ⌄
          </div>
          {STATE_ROWS.map((r) => (
            <GhostField
              key={r.label}
              label={r.label}
              ghost={r.ghost}
              value={r.value}
              lit={lit}
              onAccept={() => onAccept?.("box18a")}
              onReject={(reason) => onReject?.("box18a", reason)}
            />
          ))}
        </section>
      </div>
    </div>
  );
}
