// TXI-01 · Worksheet editor (T-04-T22; handoff TXI-01) in fixture mode, panes 300 · 566 · 490:
// the worksheet tree (Worksheets/Documents, TSJ tags, a green "+" for a worksheet the agent created
// this year, an amber pencil for one edited since the last checkpoint), 42-high field rows with a
// 96-wide value, the provenance line, an amber updated pill over the struck prior value, sign-off
// chips, and the source viewer. A cited field and its source region share one match id (line 20
// lights Box 18A on page 3). Edit needs a reason; the save is the host's (`PUT …/value` with
// `seen_seq`), so nothing here changes a value.
import { Button, Icon } from "@abacus/ui";
import { type JSX, useState } from "react";
import { COPY, type Field, type Frame, IT201, TREE, W2 } from "./copy";

export interface WorksheetEditorProps {
  frame: Frame;
  /** Save an edit: the host posts it with the reason, and answers with the next frame. */
  onSave?: (field: string, value: string, reason: string) => void;
  /** ⚑ on a field: TAX-06 with its review point (d). */
  onFlag?: (field: string) => void;
  /** A section's sign-off chip: SHL-12 for the section (L3). */
  onSignOff?: (section: string) => void;
}

function FieldRow({
  field,
  frame,
  lit,
  onLight,
  onFlag,
}: {
  field: Field;
  frame: Frame;
  lit: boolean;
  onLight: () => void;
  onFlag?: (() => void) | undefined;
}): JSX.Element {
  const amber = frame === "g" && (field.key === "nyc" || field.key === "47a");
  return (
    <div
      data-field={field.key}
      data-lit={lit}
      data-recomputed={amber}
      className={`flex min-h-[42px] items-center gap-[8px] px-[10px] text-[13px] ${lit ? "bg-match-bg" : ""} ${amber ? "bg-amber-tint" : ""}`}
    >
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate">
          {field.label}
          {field.added && frame === "e" ? (
            <span aria-label="New this year" className="pl-[4px] text-green-ink">
              +
            </span>
          ) : null}
        </span>
        <span className="truncate text-[11.5px] text-ink-3">
          {amber ? COPY.recomputed : field.note}
        </span>
      </div>
      <span className="w-[24px] text-[11.5px] text-ink-3">{field.tsj}</span>
      <button
        type="button"
        data-value={field.key}
        onClick={field.cited ? onLight : undefined}
        className="flex w-[96px] items-center justify-end gap-[4px] tabular-nums"
      >
        {field.prior !== undefined ? (
          <>
            <s className="text-ink-3">{field.prior}</s>
            <span
              data-updated
              className="rounded-[5px] bg-amber-tint px-[4px] font-medium text-amber-ink"
            >
              {field.value}
            </span>
          </>
        ) : (
          field.value
        )}
      </button>
      <span className="flex w-[110px] justify-end gap-[3px]">
        {(frame === "f" && field.chips === undefined ? ["✓ SI"] : (field.chips ?? [])).map((c) => (
          <span
            key={c}
            className="rounded-[5px] bg-green-tint px-[4px] text-[11px] text-green-ink"
          >
            {c}
          </span>
        ))}
        {field.flag ? (
          <button
            type="button"
            aria-label={`${field.flag} on ${field.label}`}
            onClick={onFlag}
            className="rounded-[5px] bg-amber-tint px-[4px] text-[11px] text-amber-ink"
          >
            {field.flag}
          </button>
        ) : null}
      </span>
    </div>
  );
}

export function WorksheetEditor({
  frame,
  onSave,
  onFlag,
  onSignOff,
}: WorksheetEditorProps): JSX.Element {
  const [lit, setLit] = useState<string | null>(frame === "a" || frame === "b" ? "20" : null);
  const [editing, setEditing] = useState<string | null>(null);
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [refused, setRefused] = useState(false);
  const w2 = frame === "c";
  return (
    <div data-screen="TXI-01" data-frame={frame} className="flex flex-col">
      <header className="flex h-[42px] items-center justify-center gap-[8px]">
        <span className="text-[15px] font-medium">{COPY.title}</span>
        <span className="text-ink-2">{COPY.client}</span>
        <span className="text-[12px] text-amber-ink">{COPY.sync}</span>
      </header>
      <div className="flex gap-[10px] px-[12px] pb-[12px]">
        <nav
          aria-label="Worksheets"
          style={{ width: 300 }}
          className="flex flex-col rounded-pane bg-card shadow-e1"
        >
          <div role="tablist" className="flex h-[46px] items-center justify-center gap-[6px]">
            {COPY.toggle.map((t) => (
              <span
                key={t}
                role="tab"
                aria-selected={t === "Worksheets"}
                className={`text-[12.5px] ${t === "Worksheets" ? "font-medium" : "text-ink-2"}`}
              >
                {t}
              </span>
            ))}
          </div>
          <ul className="flex flex-col px-[8px]">
            {TREE.map((w) => (
              <li
                key={w.key}
                data-worksheet={w.key}
                aria-selected={w.key === (w2 ? "w2" : "it201")}
                className={`flex h-[29px] items-center gap-[6px] rounded-[6px] px-[8px] text-[12.5px] ${w.key === (w2 ? "w2" : "it201") ? "bg-sel-bg font-medium" : ""}`}
              >
                <Icon name="table-2" size={13} className="text-ink-3" />
                <span className="truncate">{w.title}</span>
                {"added" in w ? (
                  <span aria-label="Created this year" className="text-green-ink">
                    +
                  </span>
                ) : null}
                {"edited" in w ? (
                  <Icon
                    name="pencil"
                    size={12}
                    className="text-amber-ink"
                    aria-label="Edited since the last checkpoint"
                  />
                ) : null}
                <span className="ml-auto text-[11.5px] text-ink-3">{w.tsj}</span>
              </li>
            ))}
            {frame === "g" ? (
              <li
                data-worksheet="it3601"
                className="flex h-[29px] items-center gap-[6px] px-[8px] text-[12.5px]"
              >
                <Icon name="table-2" size={13} className="text-ink-3" />
                <span className="truncate">{COPY.it3601}</span>
                <span aria-label="Created this year" className="text-green-ink">
                  +
                </span>
              </li>
            ) : null}
          </ul>
          <p className="mt-auto p-[10px] text-[11.5px] text-ink-3">{COPY.footer}</p>
        </nav>
        <section
          aria-label="Fields"
          style={{ width: 566 }}
          className="flex flex-col rounded-pane bg-card shadow-e1"
        >
          <div className="flex h-[46px] items-center gap-[8px] px-[10px]">
            <span className="flex-1 rounded-[8px] bg-nested px-[8px] py-[4px] text-[12.5px] text-ink-3">
              {COPY.search}
            </span>
            <span className="text-[12.5px]">{w2 ? "W-2" : COPY.picker}</span>
            <Button
              variant="secondary"
              size="sm"
              icon="pencil"
              onClick={() => {
                setEditing("20");
              }}
            >
              {COPY.edit}
            </Button>
          </div>
          {w2 ? (
            <div data-sheet="w2">
              {W2.map(([label, v]) => (
                <div key={label} className="flex h-[42px] items-center px-[10px] text-[13px]">
                  <span>{label}</span>
                  <span className="ml-auto tabular-nums">{v}</span>
                  <span className="ml-[8px] rounded-[5px] bg-green-tint px-[4px] text-[11px] text-green-ink">
                    ✓ KO · ✓ OB
                  </span>
                </div>
              ))}
            </div>
          ) : (
            IT201.map((s) => (
              <div key={s.key} data-section={s.key}>
                <div className="flex h-[31px] items-center bg-surface px-[10px] text-[13.5px] font-medium">
                  {s.title}
                  {frame === "f" && s.key === "payments" ? (
                    <span
                      data-signed="payments"
                      className="ml-auto text-[11.5px] font-normal text-green-ink"
                    >
                      {COPY.signedOff}
                    </span>
                  ) : (
                    <button
                      type="button"
                      aria-label={`Sign off ${s.title}`}
                      className="ml-auto text-[11.5px] font-normal text-ink-3"
                      onClick={() => onSignOff?.(s.key)}
                    >
                      ✓
                    </button>
                  )}
                </div>
                {s.fields.map((f) => (
                  <FieldRow
                    key={f.key}
                    field={f}
                    frame={frame}
                    lit={lit === f.key}
                    onLight={() => {
                      setLit(f.key);
                    }}
                    onFlag={
                      onFlag
                        ? () => {
                            onFlag(f.key);
                          }
                        : undefined
                    }
                  />
                ))}
              </div>
            ))
          )}
          {frame === "b" ? (
            <div
              role="dialog"
              aria-label="Field provenance"
              data-popover="provenance"
              className="m-[10px] rounded-[10px] bg-card p-[10px] text-[12px] shadow-e3"
            >
              {COPY.provenance}
            </div>
          ) : null}
          {editing !== null ? (
            <form
              aria-label={COPY.edit}
              className="m-[10px] flex flex-col gap-[6px]"
              onSubmit={(e) => {
                e.preventDefault();
                if (!reason.trim()) {
                  setRefused(true);
                  return;
                }
                onSave?.(editing, value, reason.trim());
                setEditing(null);
              }}
            >
              <input
                aria-label="Value"
                value={value}
                onChange={(e) => {
                  setValue(e.target.value);
                }}
                className="h-[30px] rounded-[8px] bg-nested px-[8px]"
              />
              <input
                aria-label={COPY.reason}
                value={reason}
                onChange={(e) => {
                  setReason(e.target.value);
                  setRefused(false);
                }}
                className="h-[30px] rounded-[8px] bg-nested px-[8px]"
              />
              {refused ? (
                <p role="alert" className="text-[11.5px] text-red-ink">
                  {COPY.reasonRequired}
                </p>
              ) : null}
              <Button type="submit" variant="primary" size="sm">
                {COPY.save}
              </Button>
            </form>
          ) : null}
        </section>
        <section
          aria-label={COPY.viewer}
          style={{ width: 490 }}
          className="flex flex-col rounded-pane bg-card shadow-e1"
        >
          <h2 className="flex h-[46px] items-center justify-center text-[13px] font-medium">
            {COPY.viewer}
          </h2>
          <div className="m-[10px] rounded-[4px] bg-surface p-[12px] text-[11.5px]">
            <p className="text-ink-3">Page 3</p>
            <span
              data-region="18A"
              data-page={3}
              data-lit={lit === "20"}
              className={`mt-[8px] inline-block rounded-[3px] px-[4px] ${lit === "20" ? "bg-match-bg inset-ring-1 inset-ring-match-line" : ""}`}
            >
              {COPY.box18a}
            </span>
          </div>
        </section>
      </div>
    </div>
  );
}
