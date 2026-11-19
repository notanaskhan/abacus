// Status incidents (G-04-T17; G-04 §5.1 `/status` · `?ov=incident:<id|new>` O3; DEC-32, DEC-5701):
// open and resolved incidents with their updates, a post sheet and an update-or-resolve sheet. The
// public note is what SHL-05's Status tab shows firms; nothing here names a firm or a client.
import type { StatusIncidentIn, StatusIncidentOut, StatusIncidentsOut } from "@abacus/api-client";
import {
  Button,
  EmptyState,
  Picker,
  Pill,
  type PillVariant,
  Segmented,
  SheetModal,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { SECTIONS_COPY } from "./copy";

const C = SECTIONS_COPY.status;
const SEVERITY: Record<StatusIncidentOut["severity"], PillVariant> = {
  outage: "red-tint",
  degraded: "amber",
  maintenance: "neutral",
};
const SEVERITIES = ["degraded", "outage", "maintenance"] as const;

export interface StatusProps {
  data: StatusIncidentsOut;
  /** The status component keys a new incident may name (the platform catalogue, G-04-T20). */
  components: readonly string[];
  onPost?: (body: StatusIncidentIn) => void;
  onUpdate?: (incident: StatusIncidentOut, note: string) => void;
  onResolve?: (incident: StatusIncidentOut, note: string) => void;
  /** `?ov=incident:new` or `incident:<id>` on arrival. */
  open?: string | null;
}

function Field({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  multiline?: boolean;
}): JSX.Element {
  return (
    <label className="flex flex-col gap-[4px] text-[12.5px] text-ink-2">
      {label}
      {multiline ? (
        <textarea
          className="min-h-[72px] bg-card px-[8px] py-[6px] text-[13px] text-ink hairline"
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
          }}
        />
      ) : (
        <input
          className="h-[30px] bg-card px-[8px] text-[13px] text-ink hairline"
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
          }}
        />
      )}
    </label>
  );
}

function PostSheet({
  components,
  onClose,
  onPost,
}: {
  components: readonly string[];
  onClose: () => void;
  onPost?: ((body: StatusIncidentIn) => void) | undefined;
}): JSX.Element {
  const [component, setComponent] = useState(components[0] ?? "");
  const [severity, setSeverity] = useState<StatusIncidentIn["severity"]>("degraded");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const ready = component !== "" && title.trim() !== "" && note.trim() !== "";
  return (
    <SheetModal
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={C.sheet.postTitle}
      dirty={title !== "" || note !== ""}
      footer={
        <div className="flex justify-end gap-[8px]">
          <Button variant="secondary" onClick={onClose}>
            {C.sheet.cancel}
          </Button>
          <Button
            disabled={!ready}
            onClick={() => {
              onPost?.({ component_key: component, severity, title, public_note: note });
              onClose();
            }}
          >
            {C.sheet.post}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-[12px]">
        <Picker
          label={C.sheet.component}
          options={components.map((k) => ({ value: k, label: k }))}
          value={component}
          onChange={setComponent}
        />
        <Segmented
          label={C.sheet.severity}
          size="small"
          options={SEVERITIES.map((s) => C.severity[s] ?? s)}
          active={C.severity[severity] ?? ""}
          onChange={(label) => {
            const found = SEVERITIES.find((s) => C.severity[s] === label);
            if (found !== undefined) setSeverity(found);
          }}
        />
        <Field label={C.sheet.title} value={title} onChange={setTitle} />
        <Field label={C.sheet.note} value={note} onChange={setNote} multiline />
      </div>
    </SheetModal>
  );
}

function IncidentSheet({
  incident,
  onClose,
  onUpdate,
  onResolve,
}: {
  incident: StatusIncidentOut;
  onClose: () => void;
  onUpdate?: StatusProps["onUpdate"] | undefined;
  onResolve?: StatusProps["onResolve"] | undefined;
}): JSX.Element {
  const [note, setNote] = useState("");
  const open = incident.resolved_at === null;
  return (
    <SheetModal
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={incident.title}
      description={C.sheet.updateTitle}
      dirty={note !== ""}
      footer={
        open ? (
          <div className="flex justify-end gap-[8px]">
            <Button
              variant="secondary"
              disabled={note.trim() === ""}
              onClick={() => {
                onUpdate?.(incident, note);
                onClose();
              }}
            >
              {C.sheet.update}
            </Button>
            <Button
              disabled={note.trim() === ""}
              onClick={() => {
                onResolve?.(incident, note);
                onClose();
              }}
            >
              {C.sheet.resolve}
            </Button>
          </div>
        ) : undefined
      }
    >
      <div className="flex flex-col gap-[10px] text-[13px]">
        <p className="text-ink-2">{incident.public_note}</p>
        <ol className="flex flex-col gap-[6px]">
          {incident.updates.map((u) => (
            <li key={`${u.at}-${u.posted_by}`} className="text-ink-2">
              <span className="text-ink-3">{u.posted_by} · </span>
              {u.note}
            </li>
          ))}
        </ol>
        {open ? (
          <Field label={C.sheet.updateNote} value={note} onChange={setNote} multiline />
        ) : null}
      </div>
    </SheetModal>
  );
}

export function Status({
  data,
  components,
  onPost,
  onUpdate,
  onResolve,
  open = null,
}: StatusProps): JSX.Element {
  const [overlay, setOverlay] = useState<string | null>(open);
  const shown = data.items.find((i) => overlay === `incident:${i.id}`);
  return (
    <section
      aria-labelledby="console-status"
      data-console-section="status"
      className="flex flex-col gap-[12px]"
    >
      <div className="flex items-center justify-between">
        <h2 id="console-status" className="text-pane font-medium text-ink">
          {C.title}
        </h2>
        <Button
          opensDialog
          onClick={() => {
            setOverlay("incident:new");
          }}
        >
          {C.post}
        </Button>
      </div>
      {data.items.length === 0 ? (
        <EmptyState title={C.empty} />
      ) : (
        <ul className="flex flex-col bg-card">
          {data.items.map((i) => (
            <li key={i.id} className="hairline-t first:border-t-0">
              <button
                type="button"
                className="flex w-full items-center gap-[10px] px-[12px] py-[9px] text-left text-[13px]"
                onClick={() => {
                  setOverlay(`incident:${i.id}`);
                }}
              >
                <Pill variant={SEVERITY[i.severity]} size="sm">
                  {C.severity[i.severity]}
                </Pill>
                <span className="flex-1 text-ink">{i.title}</span>
                <span className="text-ink-3">{i.component_key}</span>
                <span className="text-ink-3">{i.resolved_at === null ? C.open : C.resolved}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {overlay === "incident:new" ? (
        <PostSheet
          components={components}
          onPost={onPost}
          onClose={() => {
            setOverlay(null);
          }}
        />
      ) : null}
      {shown !== undefined ? (
        <IncidentSheet
          incident={shown}
          onUpdate={onUpdate}
          onResolve={onResolve}
          onClose={() => {
            setOverlay(null);
          }}
        />
      ) : null}
    </section>
  );
}
