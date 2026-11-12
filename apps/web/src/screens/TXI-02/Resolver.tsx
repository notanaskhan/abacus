// TXI-02 · K-1 treatment resolver (T-04-T40; handoff TXI-02) in fixture mode, the T3 two-pane
// variant: treatments flex 876 · viewer 490. The K-1 card and its chip cloud, the treatment table
// in the evidence grammar (Resolved, Rationale with its citation chip, 2024 SALY, Status), the
// approval card, and the PTET statement in the viewer. Only the PTET row is amber ("Changed vs
// 2024", with its reason). Approve opens SHL-10 (the host's); the agent never approves, so no
// control here decides anything: the override needs a reason and is the host's save too.
import { AgentText, Button, Picker } from "@abacus/ui";
import { type JSX, useState } from "react";
import {
  CHIPS,
  COPY,
  type Frame,
  K1_ROWS,
  RELEASED_BASIS,
  STATEMENT,
  TREATMENTS,
  type Treatment,
} from "./copy";

export interface K1ResolverProps {
  frame: Frame;
  /** "✓ Approve treatments": SHL-10 for the seven proposed treatments (the host's modal). */
  onApprove?: () => void;
  /** Save an override: the host posts it with the reason. */
  onOverride?: (treatment: string, value: string, reason: string) => void;
  /** The source row or a citation chip: SHL-08 with the cited region lit. */
  onSource?: (chip: string) => void;
}

function statusOf(t: Treatment, frame: Frame, overridden: string | null): JSX.Element {
  if (overridden === t.key) {
    return (
      <span
        data-status="overridden"
        className="rounded-[5px] bg-green-tint px-[5px] text-green-ink"
      >
        {COPY.overridden}
      </span>
    );
  }
  if (t.approved && frame !== "b" && frame !== "e") {
    return (
      <span data-status="approved" className="rounded-[5px] bg-green-tint px-[5px] text-green-ink">
        {t.approved}
      </span>
    );
  }
  if (frame === "b" || frame === "e") {
    return (
      <span data-status="approved" className="rounded-[5px] bg-green-tint px-[5px] text-green-ink">
        {COPY.approvedRow}
      </span>
    );
  }
  if (t.changed) {
    return (
      <span
        data-status="changed"
        className="rounded-[999px] bg-amber-tint px-[6px] text-amber-ink"
      >
        {COPY.changed}
      </span>
    );
  }
  return (
    <span data-status="proposed" className="rounded-[999px] bg-surface-2 px-[6px] text-ink-2">
      {COPY.proposed}
    </span>
  );
}

function Row({
  t,
  frame,
  selected,
  overridden,
  reasonShown,
  onSelect,
  onSource,
}: {
  t: Treatment;
  frame: Frame;
  selected: boolean;
  overridden: string | null;
  reasonShown: string | null;
  onSelect: () => void;
  onSource?: ((chip: string) => void) | undefined;
}): JSX.Element {
  const resolved = frame === "e" && t.key === "basis" ? RELEASED_BASIS : t.resolved;
  return (
    <>
      <tr
        data-treatment={t.n}
        data-selected={selected}
        data-changed={t.changed === true}
        onClick={onSelect}
        className={`h-[52px] cursor-pointer border-t border-hair align-middle text-[13px] ${
          selected ? "bg-match-bg" : ""
        } ${t.changed && !selected ? "bg-amber-tint" : ""}`}
      >
        <td className="w-[200px] px-[10px]">
          <span className="text-ink-3 tabular-nums">{t.n}</span> {t.label}
        </td>
        <td className="w-[230px] px-[10px] font-medium" data-resolved={t.n}>
          {overridden === t.key && reasonShown !== null ? COPY.overrideOptions[1] : resolved}
        </td>
        <td className="px-[10px] text-[12px] text-ink-2">
          <AgentText inline text={t.rationale} />
          {t.chip ? (
            <button
              type="button"
              data-chip={t.chip}
              onClick={(e) => {
                e.stopPropagation();
                onSource?.(t.chip ?? "");
              }}
              className="ml-[6px] rounded-[5px] bg-surface-2 px-[5px] text-[11px] text-ink-2"
            >
              {t.chip}
            </button>
          ) : null}
          {overridden === t.key && reasonShown ? (
            <span data-override-reason className="block text-ink-2">
              {reasonShown}
            </span>
          ) : null}
        </td>
        <td className="w-[150px] px-[10px] text-ink-2">{t.saly}</td>
        <td className="w-[110px] px-[10px] text-[11.5px]">{statusOf(t, frame, overridden)}</td>
      </tr>
      {frame === "c" && t.changed ? (
        <tr data-note={t.n}>
          <td colSpan={5} className="bg-amber-tint px-[10px] py-[6px] text-[12px] text-amber-ink">
            {COPY.changedNote}
          </td>
        </tr>
      ) : null}
    </>
  );
}

export function K1Resolver({
  frame,
  onApprove,
  onOverride,
  onSource,
}: K1ResolverProps): JSX.Element {
  const [selected, setSelected] = useState<string>(frame === "c" ? "ptet" : "passive");
  const [editing, setEditing] = useState(frame === "d");
  const [choice, setChoice] = useState<string>(COPY.overrideOptions[1]);
  const [reason, setReason] = useState("");
  const [refused, setRefused] = useState(false);
  const [overridden, setOverridden] = useState<string | null>(null);
  const [savedReason, setSavedReason] = useState<string | null>(null);
  const approved = frame === "b" || frame === "e";
  const released = frame === "e";
  const lit = selected === "ptet" ? new Set(["IL", "CO", "NY", "total"]) : new Set<string>();
  const save = (): void => {
    if (reason.trim().length === 0) {
      setRefused(true);
      return;
    }
    onOverride?.("passive", choice, reason.trim());
    setOverridden("passive");
    setSavedReason(reason.trim());
    setEditing(false);
  };
  return (
    <div data-screen="TXI-02" data-frame={frame} className="flex flex-col bg-canvas">
      <div className="flex h-[42px] items-center gap-[10px] px-[12px] text-[13px]">
        <span className="text-ink-2">{COPY.subbar.checkpoints}</span>
        <span className="rounded-[7px] bg-surface px-[6px] text-amber-ink shadow-e1">
          {COPY.subbar.sync}
        </span>
        <span className="flex-1 text-center">
          <span className="font-medium">{COPY.subbar.form}</span>{" "}
          <span className="text-ink-2">{COPY.subbar.client}</span>{" "}
          <span className="rounded-[999px] bg-surface-2 px-[6px] text-[11.5px]">
            {COPY.subbar.state}
          </span>
        </span>
        <span className="text-ink-2">{COPY.subbar.assistant}</span>
      </div>
      <nav aria-label="Return tabs" className="flex h-[44px] items-center gap-[4px] px-[12px]">
        {COPY.tabs.map((tab) => (
          <span
            key={tab}
            data-active={tab.startsWith("Review")}
            className={`rounded-[7px] px-[10px] py-[4px] text-[13px] ${
              tab.startsWith("Review") ? "bg-surface font-medium shadow-e1" : "text-ink-2"
            }`}
          >
            {tab}
          </span>
        ))}
      </nav>
      <div className="flex gap-[10px] px-[12px] pb-[12px]">
        <section
          aria-label="K-1 treatments"
          className="flex min-w-0 flex-1 flex-col rounded-[12px] bg-surface shadow-e1"
        >
          <header className="flex h-[46px] items-center px-[12px]">
            <span className="text-[13px] text-ink-2">{COPY.back}</span>
            <span className="flex-1 text-center text-[14.5px] font-medium">{COPY.title}</span>
            {released ? (
              <span
                data-chip-state="released"
                className="rounded-[999px] bg-green-tint px-[8px] text-[12px] text-green-ink"
              >
                {COPY.releasedChip}
              </span>
            ) : (
              <span
                data-chip-state="draft"
                className="rounded-[999px] bg-amber-tint px-[8px] text-[12px] text-amber-ink"
              >
                {COPY.draftChip}
              </span>
            )}
          </header>
          <div className="flex flex-col gap-[12px] bg-well p-[12px]">
            {released ? (
              <div
                role="status"
                data-banner="released"
                className="rounded-[10px] bg-green-tint px-[12px] py-[8px] text-[12.5px] text-green-ink"
              >
                {COPY.released}
              </div>
            ) : null}
            <div className="flex gap-[12px]">
              <div className="w-[380px] rounded-[12px] bg-surface shadow-e2">
                <div className="flex h-[40px] items-center px-[12px] text-[13px] font-medium">
                  {COPY.cardTitle}
                </div>
                {K1_ROWS.map(([label, value]) => (
                  <div key={label} className="flex h-[34px] items-center px-[12px] text-[12.5px]">
                    <span className="flex-1 text-ink-2">{label}</span>
                    <span className="font-medium tabular-nums">{value}</span>
                  </div>
                ))}
              </div>
              <div className="flex flex-1 flex-wrap content-start gap-[6px]">
                {CHIPS.map((c) => (
                  <span
                    key={c.label}
                    data-chip-changed={c.changed === true}
                    className={`h-[24px] rounded-[999px] px-[10px] text-[12px] font-medium leading-[24px] ${
                      c.changed ? "bg-amber-tint text-amber-ink" : "bg-surface-2 text-ink-2"
                    }`}
                  >
                    {c.label}
                  </span>
                ))}
              </div>
            </div>
            <div className="overflow-hidden rounded-[12px] bg-surface shadow-e1">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="h-[34px] text-left text-[11.5px] text-ink-3">
                    {COPY.columns.map((c) => (
                      <th key={c} className="px-[10px] font-medium">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {TREATMENTS.map((t) => (
                    <Row
                      key={t.key}
                      t={t}
                      frame={frame}
                      selected={selected === t.key}
                      overridden={overridden}
                      reasonShown={savedReason}
                      onSelect={() => {
                        setSelected(t.key);
                      }}
                      onSource={onSource}
                    />
                  ))}
                </tbody>
              </table>
              {editing ? (
                <form
                  aria-label="Override treatment 1"
                  className="flex items-end gap-[8px] border-t border-hair p-[10px] text-[12.5px]"
                  onSubmit={(e) => {
                    e.preventDefault();
                    save();
                  }}
                >
                  <label className="flex flex-col">
                    <span className="text-ink-3">{TREATMENTS[0]?.label}</span>
                    <Picker
                      label="Treatment"
                      value={choice}
                      onChange={setChoice}
                      options={COPY.overrideOptions.map((o) => ({ value: o, label: o }))}
                    />
                  </label>
                  <label className="flex flex-1 flex-col">
                    <span className="text-ink-3">{COPY.reasonLabel}</span>
                    <input
                      aria-label={COPY.reasonLabel}
                      aria-invalid={refused}
                      value={reason}
                      onChange={(e) => {
                        setReason(e.target.value);
                        setRefused(false);
                      }}
                      className="h-[30px] rounded-[7px] bg-surface-2 px-[6px]"
                    />
                    {refused ? (
                      <span role="alert" className="text-amber-ink">
                        {COPY.reasonRequired}
                      </span>
                    ) : null}
                  </label>
                  <Button type="submit">{COPY.save}</Button>
                </form>
              ) : null}
            </div>
            {approved ? (
              <div
                data-approval="collapsed"
                className="rounded-[12px] bg-surface px-[12px] py-[10px] text-[13px] text-green-ink shadow-e1"
              >
                {COPY.approvedLine}
              </div>
            ) : (
              <div data-approval="card" className="rounded-[12px] bg-surface shadow-e2">
                <div className="flex h-[40px] items-center px-[12px] text-[13px] font-medium">
                  {COPY.approvalTitle}
                </div>
                <div className="bg-surface-2 px-[12px] py-[4px] text-[11.5px] text-ink-3">
                  {COPY.reasoningLabel}
                </div>
                <p className="px-[12px] py-[8px] text-[12.5px] leading-[1.55]">{COPY.reasoning}</p>
                <button
                  type="button"
                  onClick={() => onSource?.("draft")}
                  className="flex w-full items-center px-[12px] py-[6px] text-left text-[12.5px] text-ink-2"
                >
                  <span className="flex-1">{COPY.source}</span>›
                </button>
                <div className="flex justify-end gap-[8px] px-[12px] py-[10px]">
                  <Button variant="secondary">{COPY.reject}</Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setEditing(true);
                    }}
                  >
                    {COPY.edit}
                  </Button>
                  <Button onClick={onApprove}>{COPY.approve}</Button>
                </div>
              </div>
            )}
          </div>
        </section>
        <aside
          aria-label="Source viewer"
          className="flex w-[490px] flex-col rounded-[12px] bg-surface shadow-e1"
        >
          <header className="flex h-[46px] items-center px-[12px] text-[12.5px]">
            <span className="flex-1 truncate">{COPY.viewerFile}</span>
            <span className="text-ink-3">{COPY.pages}</span>
          </header>
          <div className="m-[12px] rounded-[6px] bg-paper p-[16px] text-[12.5px]">
            <div className="pb-[8px] font-medium">{COPY.viewerPage}</div>
            {STATEMENT.map((row) => (
              <div
                key={row.key}
                data-statement={row.key}
                data-lit={lit.has(row.key)}
                className={`flex h-[28px] items-center px-[6px] ${lit.has(row.key) ? "bg-match-bg" : ""}`}
              >
                <span className="flex-1">{row.label}</span>
                <span className="tabular-nums">{row.figure}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
