import type {
  FieldProvenanceOut,
  FieldReferenceOut,
  FieldTickIn,
  FieldTickOut,
  FieldVersionOut,
} from "@abacus/api-client";
import {
  fieldEditMutation,
  fieldProvenanceOptions,
  fieldProvenanceQueryKey,
  fieldReferenceMutation,
  fieldTickMutation,
  issueOptions,
} from "@abacus/api-client/query";
import {
  type Actor,
  AgentMonogram,
  Button,
  HumanAction,
  Icon,
  IconButton,
  Pill,
  Tooltip,
  amount,
  cn,
  date as formatDate,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useId, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useOpenOverlay } from "../../app-core/open";
import { useOpenSourceViewer } from "../../app-core/overlay-host";
import { useSession } from "../../app-core/session";
import { COPY } from "./copy";

// SHL-09 · Field provenance tray (P-04-T55; P-04 §3; the handoff's SHL-09, frames a–f): the O1 420
// tray variant the E2 AnchoredPopoverHost opens on a field's ⓘ, over C3's field provenance read
// (`GET /v1/fields/{type}/{id}/{key}/provenance`, P-04-T35). Two white sections on the #EFEEEB tray:
// Updated (the current version) and Previous (the one before), each a header ("<when> · <who>",
// the Accrued monogram for the agent, a person glyph for a person; ChevronDown collapses) and KV
// rows: Value (the amber updated pill, the prior value struck), Citation, References (a row opens
// SHL-08 on its page; ArrowRight jumps, CirclePlus adds), Sign-offs (a tick on an older hash is
// struck with "Changed after sign-off"; a flag shows its note). Frames:
//
//   a  agent-set, flagged, stale sign-off    d  signed off (both ticks current)
//   b  estimate: the ≈ badge and the issue   e  uncited agent value: Unsupported, Sign off field
//   c  human-edited: "Edited", person glyph     disabled with "Add a reference before signing off"
//                                            f  Previous collapsed
//
// Edit value (Pencil) makes the value editable with a required citation note; saving is C3's
// `PUT …/value` (a human checkpoint entry, SHL-16). Add reference picks from the documents the host
// hands in. Sign off field is the person's HumanAction on the current hash; a stale tick can only
// be re-signed. Every figure is the server's; nothing here signs or edits for the agent (INV-1).

export interface FieldRef {
  type: string;
  id: string;
  fieldKey: string;
}

export interface ProvenanceTrayProps {
  field: FieldRef;
  /** The level the viewer signs a field at (their SHL-12 level); the reviewer's by default. */
  level?: FieldTickIn["level"];
  /** The return's documents Add reference offers (the host's list). */
  documents?: readonly FieldReferenceOut[];
  /** Frame f: Previous opens collapsed. */
  initialCollapsed?: boolean;
  className?: string;
}

const TRAY = "flex w-[420px] flex-col gap-[6px] rounded-[15px] bg-nested p-[6px] shadow-menu";
const SECTION = "overflow-hidden rounded-[11px] bg-card shadow-e1";
const KEY = "w-[92px] flex-none text-dense text-ink-2";

function valueText(v: FieldVersionOut): string {
  const raw = v.value.v ?? "";
  return v.value.t === "decimal" ? amount(raw, "whole").text : raw;
}

function useActor(): Actor {
  const session = useSession();
  return session.user === null
    ? { kind: "system" }
    : { kind: "human", name: session.user.displayName };
}

function Row({ k, children }: { k: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex items-start gap-[10px] px-[12px] py-[6px] text-dense hairline-t">
      <span className={KEY}>{k}</span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

function Who({ v }: { v: FieldVersionOut }): JSX.Element {
  if (v.actor_kind === "agent") return <AgentMonogram size={14} label={v.actor_name} />;
  if (v.actor_kind === "human") {
    return <Icon name="circle-user-round" size={14} aria-label={v.actor_name} />;
  }
  return <Icon name="download" size={14} aria-label={v.actor_name} />;
}

function Ticks({
  ticks,
  flags,
  now,
}: {
  ticks: FieldProvenanceOut["ticks"];
  flags: FieldProvenanceOut["flags"];
  now: Date;
}): JSX.Element | null {
  if (ticks.length === 0 && flags.length === 0) return null;
  const on = (iso: string): string => formatDate(iso, { now });
  return (
    <ul className="flex flex-col gap-[4px]">
      {ticks.map((t: FieldTickOut) => (
        <li
          key={t.sign_off_id}
          data-tick={t.stale ? "stale" : "current"}
          className="flex flex-wrap items-center gap-[6px]"
        >
          <span
            className={cn(
              "rounded-pill px-[6px] text-meta",
              t.stale ? "bg-nested text-ink-3 line-through" : "bg-green-tint text-green-ink",
            )}
          >
            {`${COPY.tick(t.initials, on(t.signed_at))}${t.stale ? ` ${COPY.beforeChange}` : ""}`}
          </span>
          {t.stale && (
            <Pill variant="amber" size="sm">
              {COPY.changedAfter}
            </Pill>
          )}
        </li>
      ))}
      {flags.map((f) => (
        <li key={f.note_id} data-flag="" className="flex flex-col gap-[2px]">
          <span className="self-start rounded-pill bg-amber-tint px-[6px] text-meta text-amber-ink">
            {COPY.flag(f.raised_by_initials, on(f.raised_at))}
          </span>
          <span className="text-meta text-ink-2">{f.body}</span>
        </li>
      ))}
    </ul>
  );
}

function References({
  refs,
  onAdd,
}: {
  refs: readonly FieldReferenceOut[];
  onAdd?: () => void;
}): JSX.Element {
  const openViewer = useOpenSourceViewer();
  return (
    <ul className="flex flex-col">
      {refs.map((r) => (
        <li
          key={r.id}
          data-reference={r.kind}
          className="group flex min-h-[34px] items-start gap-[8px] rounded-nested py-[4px] hover:bg-match-bg"
        >
          <Icon
            name={r.kind === "document" ? "file-text" : "download"}
            size={13}
            className="mt-[2px] flex-none text-ink-3"
          />
          <span className="flex min-w-0 flex-1 flex-col">
            <span>{r.label}</span>
            {r.detail !== null && <span className="text-meta text-ink-3">{r.detail}</span>}
          </span>
          {r.document_id !== null && (
            <IconButton
              icon="arrow-right"
              label={COPY.jump(r.label)}
              onClick={() => {
                openViewer({
                  evidenceVersionId: r.document_id ?? "",
                  ...(r.citation_id === null ? {} : { matchId: r.citation_id }),
                });
              }}
            />
          )}
          {onAdd !== undefined && (
            <IconButton icon="circle-plus" label={COPY.addTo(r.label)} onClick={onAdd} />
          )}
        </li>
      ))}
    </ul>
  );
}

function IssueLink({ issueId }: { issueId: string }): JSX.Element {
  const issue = useQuery(issueOptions({ path: { issue_id: issueId } }));
  const openOverlay = useOpenOverlay();
  const title = issue.data?.title;
  return (
    <button
      type="button"
      data-issue-link={issueId}
      onClick={() => {
        openOverlay({ key: "issue", args: [issueId] });
      }}
      className="mt-[6px] flex w-full items-center gap-[6px] rounded-nested bg-red-tint px-[8px] py-[5px] text-left text-dense text-red-ink"
    >
      <Icon name="circle-alert" size={13} className="flex-none" />
      <span className="flex-1">
        {title === undefined ? COPY.openIssueBare : COPY.openIssue(title)}
      </span>
      <Icon name="arrow-right" size={13} className="flex-none" />
    </button>
  );
}

function Section({
  title,
  v,
  prior,
  open,
  onToggle,
  tray,
  current,
  onEdit,
  onAdd,
  now,
}: {
  title: string;
  v: FieldVersionOut;
  prior: FieldVersionOut | undefined;
  open: boolean;
  onToggle: () => void;
  tray: FieldProvenanceOut;
  current: boolean;
  onEdit?: () => void;
  onAdd?: () => void;
  now: Date;
}): JSX.Element {
  const when = `${formatDate(v.recorded_at, { now })}, ${time(v.recorded_at)}`;
  const edited = v.actor_kind === "human" && v.cause === "edit";
  return (
    <section
      data-version={v.seq}
      data-current={current ? "" : undefined}
      className={SECTION}
      aria-label={title}
    >
      <header className="flex h-[38px] items-center gap-[8px] px-[12px]">
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-[13.5px] leading-[1.2] font-medium">{title}</span>
          <span className="flex items-center gap-[5px] text-meta text-ink-3">
            <Who v={v} />
            {COPY.sub(when, v.actor_name)}
          </span>
        </span>
        <IconButton
          icon={open ? "chevron-down" : "chevron-right"}
          label={open ? COPY.collapse : COPY.expand}
          aria-expanded={open}
          onClick={onToggle}
        />
        {onEdit !== undefined && (
          <IconButton icon="pencil" label={COPY.editValue} onClick={onEdit} />
        )}
      </header>
      {open && (
        <>
          <Row k={COPY.value}>
            <span className="flex flex-wrap items-center gap-[8px]">
              {v.value_kind === "estimate" && (
                <span
                  aria-label={COPY.estimateLabel}
                  className="flex size-[16px] items-center justify-center rounded-full bg-amber-tint text-[11px] font-medium text-amber-ink"
                >
                  {COPY.estimate}
                </span>
              )}
              <span
                data-value=""
                className={cn(
                  "tabular-nums",
                  current &&
                    prior !== undefined &&
                    "rounded-pill bg-amber-tint px-[6px] font-medium text-amber-ink",
                )}
              >
                {valueText(v)}
              </span>
              {current && prior !== undefined && (
                <span
                  data-prior=""
                  className="text-ink-3 tabular-nums line-through decoration-ink-4"
                >
                  {valueText(prior)}
                </span>
              )}
              {current && edited && (
                <Pill variant="amber" size="sm">
                  {COPY.edited}
                </Pill>
              )}
            </span>
          </Row>
          <Row k={COPY.citation}>
            {v.unsupported || v.citation === null ? (
              <span
                data-unsupported=""
                className="flex flex-wrap items-center gap-[6px] text-red-ink"
              >
                {COPY.noSource}
                <Pill variant="red-tint" size="sm">
                  {COPY.unsupported}
                </Pill>
              </span>
            ) : (
              <span>{v.citation}</span>
            )}
            {v.issue_id !== null && <IssueLink issueId={v.issue_id} />}
          </Row>
          {v.references.length > 0 && (
            <Row k={COPY.references}>
              <References
                refs={v.references}
                {...(current && onAdd !== undefined ? { onAdd } : {})}
              />
            </Row>
          )}
          {current && (tray.ticks.length > 0 || tray.flags.length > 0) && (
            <Row k={COPY.signOffs}>
              <Ticks ticks={tray.ticks} flags={tray.flags} now={now} />
            </Row>
          )}
        </>
      )}
    </section>
  );
}

function EditForm({
  tray,
  v,
  onDone,
}: {
  tray: FieldProvenanceOut;
  v: FieldVersionOut;
  onDone: () => void;
}): JSX.Element {
  const ids = useId();
  const queryClient = useQueryClient();
  const [value, setValue] = useState(v.value.v ?? "");
  const [note, setNote] = useState("");
  const path = {
    target_type: tray.target_type,
    target_id: tray.target_id,
    field_key: tray.field_key,
  };
  const edit = useMutation({
    ...fieldEditMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: fieldProvenanceQueryKey({ path }) });
    },
  });
  const ready = note.trim() !== "" && value.trim() !== "" && !edit.isPending;
  return (
    <form
      data-shl09="edit"
      className={cn(SECTION, "flex flex-col gap-[8px] p-[12px]")}
      onSubmit={(event) => {
        event.preventDefault();
        if (!ready) return;
        edit.mutate(
          {
            path,
            body: {
              value: { t: v.value.t, v: value.trim() },
              value_kind: v.value_kind,
              citation_note: note.trim(),
              seen_seq: tray.current_seq,
            },
          },
          {
            onSuccess: () => {
              toast.show({ kind: "success", text: COPY.toasts.saved });
              onDone();
            },
            onError: () => {
              toast.show({ kind: "error", text: COPY.edit.failed });
            },
          },
        );
      }}
    >
      <label htmlFor={`${ids}-v`} className="text-dense text-ink-2">
        {COPY.edit.value}
      </label>
      <input
        id={`${ids}-v`}
        value={value}
        onChange={(event) => {
          setValue(event.target.value);
        }}
        className="h-[30px] rounded-nested bg-nested px-[10px] text-right text-body tabular-nums"
      />
      <label htmlFor={`${ids}-n`} className="text-dense text-ink-2">
        {COPY.edit.note}
      </label>
      <textarea
        id={`${ids}-n`}
        required
        value={note}
        onChange={(event) => {
          setNote(event.target.value);
        }}
        className="h-[56px] resize-none rounded-nested bg-nested p-[8px] text-body"
      />
      <span className="flex justify-end gap-[8px]">
        <Button variant="ghost" size="sm" onClick={onDone}>
          {COPY.edit.cancel}
        </Button>
        <Button variant="secondary" size="sm" type="submit" disabled={!ready}>
          {COPY.edit.save}
        </Button>
      </span>
    </form>
  );
}

function Picker({
  tray,
  documents,
  onDone,
}: {
  tray: FieldProvenanceOut;
  documents: readonly FieldReferenceOut[];
  onDone: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = {
    target_type: tray.target_type,
    target_id: tray.target_id,
    field_key: tray.field_key,
  };
  const add = useMutation({
    ...fieldReferenceMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: fieldProvenanceQueryKey({ path }) });
    },
  });
  const pickable = documents.filter((d) => d.document_id !== null);
  return (
    <section
      data-shl09="pick"
      aria-label={COPY.pick.title}
      className={cn(SECTION, "flex flex-col")}
    >
      <p className="flex h-[32px] items-center px-[12px] text-dense font-medium">
        {COPY.pick.title}
      </p>
      {pickable.length === 0 ? (
        <p className="px-[12px] pb-[10px] text-meta text-ink-3">{COPY.pick.none}</p>
      ) : (
        <ul>
          {pickable.map((d) => (
            <li key={d.id} className="hairline-t">
              <button
                type="button"
                disabled={add.isPending}
                onClick={() => {
                  add.mutate(
                    {
                      path,
                      body: {
                        document_id: d.document_id ?? "",
                        page: d.page,
                        seen_seq: tray.current_seq,
                      },
                    },
                    {
                      onSuccess: () => {
                        toast.show({ kind: "success", text: COPY.toasts.referenced });
                        onDone();
                      },
                    },
                  );
                }}
                className="flex w-full items-center gap-[8px] px-[12px] py-[7px] text-left text-dense hover:bg-match-bg"
              >
                <Icon name="file-text" size={13} className="flex-none text-ink-3" />
                <span className="flex-1">{d.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Tray({
  tray,
  level,
  documents,
  initialCollapsed,
  className,
}: {
  tray: FieldProvenanceOut;
  level: FieldTickIn["level"];
  documents: readonly FieldReferenceOut[];
  initialCollapsed: boolean;
  className?: string | undefined;
}): JSX.Element {
  const now = useNow();
  const actor = useActor();
  const queryClient = useQueryClient();
  const [openPrevious, setOpenPrevious] = useState(!initialCollapsed);
  const [openCurrent, setOpenCurrent] = useState(true);
  const [editing, setEditing] = useState(false);
  const [picking, setPicking] = useState(false);
  const current = tray.versions.find((v) => v.seq === tray.current_seq) ?? tray.versions[0];
  const prior = tray.versions.find((v) => v.seq < (current?.seq ?? 0));
  const allowed = tray.allowed_actions;
  const path = {
    target_type: tray.target_type,
    target_id: tray.target_id,
    field_key: tray.field_key,
  };
  const tick = useMutation({
    ...fieldTickMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: fieldProvenanceQueryKey({ path }) });
    },
  });
  if (current === undefined) return <div className={cn(TRAY, className)} />;
  const unsupported = current.unsupported || current.citation === null;
  const canSign = allowed.includes("field.sign_off");
  const blocked = unsupported || !canSign;
  const signOff = (
    <HumanAction
      verb="Sign off"
      label={COPY.signOffField}
      actor={actor}
      variant="secondary"
      size="sm"
      icon="check"
      disabled={blocked || tick.isPending}
      onClick={() => {
        tick.mutate(
          { path, body: { level, seen_hash: tray.content_hash } },
          {
            onSuccess: () => {
              toast.show({ kind: "success", text: COPY.toasts.signed });
            },
          },
        );
      }}
    />
  );
  return (
    <div
      data-shl09="tray"
      data-field={tray.field_key}
      role="dialog"
      aria-label={`${COPY.label}: ${tray.label}`}
      className={cn(TRAY, className)}
    >
      <Section
        title={COPY.updated}
        v={current}
        prior={prior}
        open={openCurrent}
        onToggle={() => {
          setOpenCurrent((o) => !o);
        }}
        tray={tray}
        current
        {...(allowed.includes("field.edit")
          ? {
              onEdit: () => {
                setEditing((e) => !e);
              },
            }
          : {})}
        {...(allowed.includes("field.add_reference")
          ? {
              onAdd: () => {
                setPicking(true);
              },
            }
          : {})}
        now={now}
      />
      {editing && (
        <EditForm
          tray={tray}
          v={current}
          onDone={() => {
            setEditing(false);
          }}
        />
      )}
      {prior !== undefined && (
        <Section
          title={COPY.previous}
          v={prior}
          prior={undefined}
          open={openPrevious}
          onToggle={() => {
            setOpenPrevious((o) => !o);
          }}
          tray={tray}
          current={false}
          now={now}
        />
      )}
      {picking && (
        <Picker
          tray={tray}
          documents={documents}
          onDone={() => {
            setPicking(false);
          }}
        />
      )}
      <footer className="flex items-center gap-[8px] px-[8px] pt-[8px] pb-[4px]">
        <span className="flex-1 text-meta text-ink-3">{COPY.versions(tray.versions.length)}</span>
        {unsupported ? (
          <Tooltip content={COPY.addReferenceFirst}>
            <span tabIndex={0} data-shl09="sign-disabled">
              {signOff}
            </span>
          </Tooltip>
        ) : (
          signOff
        )}
        {allowed.includes("field.add_reference") && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setPicking((p) => !p);
            }}
          >
            {COPY.addReference}
          </Button>
        )}
      </footer>
    </div>
  );
}

/** SHL-09's tray for one field: what the E2 AnchoredPopoverHost renders for a field's ⓘ. */
export function ProvenanceTray({
  field,
  level = "L2_reviewer",
  documents = [],
  initialCollapsed = false,
  className,
}: ProvenanceTrayProps): JSX.Element {
  const query = useQuery(
    fieldProvenanceOptions({
      path: { target_type: field.type, target_id: field.id, field_key: field.fieldKey },
    }),
  );
  if (query.data === undefined) {
    return (
      <div
        aria-busy={query.isError ? undefined : true}
        className={cn(TRAY, "min-h-[120px]", className)}
      />
    );
  }
  return (
    <Tray
      tray={query.data}
      level={level}
      documents={documents}
      initialCollapsed={initialCollapsed}
      className={className}
    />
  );
}
