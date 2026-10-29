import type { DraftUpdateIn, EnvelopeOut, EnvelopePolicyOut, SignerOut } from "@abacus/api-client";
import {
  type Actor,
  Button,
  Dialog,
  FullSheet,
  HumanAction,
  Icon,
  SheetColumns,
  SourceViewer,
  StatusDisc,
  ValueRow,
  type ViewerFile,
  date,
  toast,
} from "@abacus/ui";
import { type DragEvent, type JSX, type KeyboardEvent, useMemo, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import {
  IDENTITY_METHODS,
  type IdentityMethod,
  useChecks,
  useEnvelope,
  useEnvelopeWrites,
  usePageUrls,
  usePolicy,
} from "../../domain/signatures";
import { COPY, gateSentence, retentionLine } from "./copy";

// SIG-02 · Envelope builder, part 1 (N-02-T21; docs/screens/SIG-02.md; SPEC-381 AC-7, AC-8): the
// O4 full sheet at `?ov=envelope:<id>`, three columns. Documents (drag or Alt+↑/↓ to reorder) over
// the server's Checks; the preview on the E5 page pipeline (zoom and the page bar) with the fields
// placed on the selected document; Signers (order, identity with the policy's refused methods
// disabled and their reason, role, sequential or parallel), Delivery, Dating and Retention. The
// footer states the gate the envelope unlocks; Save draft writes the draft (If-Match), Send is a
// HumanAction (the agent never sends, INV-1) and waits for the server, with Undo for 10 s
// (ADR-161). Escape on a changed draft asks to keep it. Frames built: a (Harborview 8879-PE), e
// (E13 with a countersigner) and f (a signer with no email: Send disabled).

type Draft = {
  order: string[];
  signers: SignerOut[];
  signerOrder: EnvelopeOut["signer_order"];
  message: string;
  reminder: string;
  fixedDate: boolean;
};

function draftOf(e: EnvelopeOut): Draft {
  return {
    order: [...e.documents].sort((a, b) => a.order - b.order).map((d) => d.id),
    signers: [...e.signers].sort((a, b) => a.order - b.order),
    signerOrder: e.signer_order,
    message: e.message ?? "",
    reminder: e.reminder_cadence ?? "",
    fixedDate: e.date_as_of_mode !== "none",
  };
}

function bodyOf(d: Draft, e: EnvelopeOut): DraftUpdateIn {
  return {
    signers: d.signers.map((s, i) => ({
      identity_method: s.identity_method,
      order: i + 1,
      role: s.role,
      routing_group: d.signerOrder === "parallel" ? 1 : i + 1,
    })),
    signer_order: d.signerOrder,
    message: d.message === "" ? null : d.message,
    reminder_cadence: d.reminder === "" ? null : d.reminder,
    expires_on: e.expires_at === null ? null : e.expires_at.slice(0, 10),
    date_as_of_mode: d.fixedDate
      ? e.date_as_of_mode === "none"
        ? "fixed_date"
        : e.date_as_of_mode
      : "none",
    date_as_of: d.fixedDate ? e.date_as_of : null,
    document_order: d.order,
  };
}

/** The 409's code (ADR-139), if the error is one. */
function codeOf(error: unknown): string | null {
  const detail = (error as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" ? detail : null;
}

/** A signer that will sign by email needs an email on file; a firm user signs through SSO. */
function needsEmail(s: SignerOut): boolean {
  return s.identity_method !== "firm_sso" && (s.email === null || s.email === undefined);
}

export interface EnvelopeBuilderProps {
  envelopeId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EnvelopeBuilder({
  envelopeId,
  open,
  onOpenChange,
}: EnvelopeBuilderProps): JSX.Element {
  const query = useEnvelope(envelopeId);
  const envelope = query.data;
  if (envelope === undefined) {
    return (
      <FullSheet open={open} onOpenChange={onOpenChange} title={COPY.documents}>
        <p className="p-[12px] text-meta text-ink-3">
          {query.isError ? COPY.missing : COPY.loading}
        </p>
      </FullSheet>
    );
  }
  return (
    <Builder
      key={`${envelope.row.id}:${String(envelope.version)}`}
      envelope={envelope}
      open={open}
      onOpenChange={onOpenChange}
    />
  );
}

function Builder({
  envelope,
  open,
  onOpenChange,
}: {
  envelope: EnvelopeOut;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  const session = useSession();
  const now = useNow();
  const tz = session.tz ?? undefined;
  const actor: Actor =
    session.user === null ? { kind: "system" } : { kind: "human", name: session.user.displayName };
  const policy = usePolicy(envelope.policy_family);
  const checks = useChecks(envelope.row.id, envelope.version);
  const writes = useEnvelopeWrites(envelope);
  const initial = useMemo(() => draftOf(envelope), [envelope]);
  const [draft, setDraft] = useState<Draft>(initial);
  const [selected, setSelected] = useState<string | null>(initial.order[0] ?? null);
  const [keeping, setKeeping] = useState(false);
  const [announce, setAnnounce] = useState("");
  const dirty = JSON.stringify(draft) !== JSON.stringify(initial);

  const docs = draft.order
    .map((id) => envelope.documents.find((d) => d.id === id))
    .filter((d): d is EnvelopeOut["documents"][number] => d !== undefined);
  const doc = docs.find((d) => d.id === selected) ?? docs[0];

  const serverMissing = new Set(
    (checks.data?.problems ?? [])
      .filter((p) => p.startsWith("signer_email_missing:"))
      .map((p) => p.slice("signer_email_missing:".length)),
  );
  const missingEmail = draft.signers.filter((s) => needsEmail(s) || serverMissing.has(s.id));
  const blocked =
    missingEmail.length > 0 || checks.data === undefined || !checks.data.ok || checks.isPending;

  const names = draft.signers
    .filter((s) => s.role === "signer")
    .map((s) => s.name)
    .join(", ");

  // Never optimistic: the sheet stays as it is until the server answers the send (ADR-161).
  const [sending, setSending] = useState(false);
  const send = async (): Promise<void> => {
    setSending(true);
    try {
      if (dirty) await writes.save(bodyOf(draft, envelope));
      await writes.send();
      toast.undoable({
        text: COPY.sent(names, envelope.row.number),
        undo: () => {
          void writes.undoSend().catch(() => {
            toast.show({ kind: "error", text: COPY.failed });
          });
        },
      });
      onOpenChange(false);
    } catch (error) {
      toast.show({
        kind: "error",
        text: codeOf(error) === "stale_version" ? COPY.changed : COPY.failed,
      });
    } finally {
      setSending(false);
    }
  };

  const save = async (): Promise<boolean> => {
    try {
      await writes.save(bodyOf(draft, envelope));
      toast.show({ kind: "success", text: COPY.saved });
      return true;
    } catch (error) {
      toast.show({
        kind: "error",
        text: codeOf(error) === "stale_version" ? COPY.changed : COPY.failed,
      });
      return false;
    }
  };

  const move = (id: string, by: number): void => {
    setDraft((d) => {
      const at = d.order.indexOf(id);
      const to = at + by;
      if (at < 0 || to < 0 || to >= d.order.length) return d;
      const order = [...d.order];
      order.splice(at, 1);
      order.splice(to, 0, id);
      const title = envelope.documents.find((x) => x.id === id)?.title ?? "";
      setAnnounce(COPY.moved(title, to + 1));
      return { ...d, order };
    });
  };

  const [dragging, setDragging] = useState<string | null>(null);
  const onDrop = (target: string) => (event: DragEvent<HTMLLIElement>) => {
    event.preventDefault();
    if (dragging === null || dragging === target) return;
    move(dragging, draft.order.indexOf(target) - draft.order.indexOf(dragging));
    setDragging(null);
  };

  const gateLine = gateSentence(
    envelope.policy_family,
    envelope.row.number,
    envelope.row.work_item_label,
  );

  return (
    <>
      <FullSheet
        open={open}
        onOpenChange={(next) => {
          if (!next && dirty) setKeeping(true);
          else onOpenChange(next);
        }}
        title={envelope.row.title}
      >
        <div className="flex min-h-0 flex-1 flex-col">
          <SheetColumns className="grid-cols-[300px_minmax(0,1fr)_360px]">
            <section aria-label={COPY.documents} className="flex flex-col gap-[10px] self-start">
              <div className="overflow-hidden rounded-pane bg-card shadow-e1">
                <h3 className="flex h-[33px] items-center px-[14px] text-section">
                  {COPY.documents}
                </h3>
                <ul aria-label={COPY.documents}>
                  {docs.map((d) => (
                    <li
                      key={d.id}
                      data-document={d.id}
                      draggable
                      onDragStart={() => {
                        setDragging(d.id);
                      }}
                      onDragOver={(event) => {
                        event.preventDefault();
                      }}
                      onDrop={onDrop(d.id)}
                      className={
                        d.id === doc?.id
                          ? "flex items-center gap-[8px] bg-sel-bg px-[14px] hairline-t"
                          : "flex items-center gap-[8px] px-[14px] hairline-t"
                      }
                    >
                      <Icon name="file-text" size={15} className="flex-none text-ink-3" />
                      <button
                        type="button"
                        aria-current={d.id === doc?.id ? "true" : undefined}
                        aria-keyshortcuts="Alt+ArrowUp Alt+ArrowDown"
                        onClick={() => {
                          setSelected(d.id);
                        }}
                        onKeyDown={(event: KeyboardEvent<HTMLButtonElement>) => {
                          if (!event.altKey) return;
                          if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                            event.preventDefault();
                            move(d.id, event.key === "ArrowUp" ? -1 : 1);
                          }
                        }}
                        className="flex min-h-[52px] min-w-0 flex-1 flex-col justify-center text-left"
                      >
                        <span className="truncate text-body font-medium">{d.title}</span>
                        <span className="text-cell text-ink-3">
                          {COPY.pages(d.page_count)}
                          {d.read_only ? ` · ${COPY.readOnly}` : ""}
                        </span>
                      </button>
                      <Icon
                        name="grip-vertical"
                        size={12}
                        aria-label={COPY.move(d.title)}
                        className="flex-none text-ink-4"
                      />
                    </li>
                  ))}
                </ul>
                <p aria-live="polite" className="sr-only">
                  {announce}
                </p>
              </div>
              <div className="overflow-hidden rounded-pane bg-card shadow-e1">
                <h3 className="flex h-[33px] items-center px-[14px] text-section">
                  {COPY.checks}
                </h3>
                <ul
                  aria-label={COPY.checks}
                  className="flex flex-col gap-[6px] px-[14px] pb-[12px]"
                >
                  {(checks.data?.checks ?? []).map((c) => (
                    <li
                      key={c.code}
                      data-check={c.code}
                      className="flex items-start gap-[8px] text-body"
                    >
                      <StatusDisc state={c.ok ? "done" : "fail"} />
                      {COPY.checkWords[c.code] ?? c.code}
                    </li>
                  ))}
                  {missingEmail.map((s) => (
                    <li
                      key={s.id}
                      role="alert"
                      className="flex items-start gap-[8px] text-body text-red-ink"
                    >
                      <StatusDisc state="fail" />
                      {COPY.noEmail(s.name)}
                    </li>
                  ))}
                </ul>
              </div>
            </section>
            <Preview envelope={envelope} doc={doc ?? null} signers={draft.signers} />
            <section aria-label={COPY.signers} className="flex flex-col gap-[10px] self-start">
              <Card title={COPY.signers}>
                <ValueRow
                  kind="select"
                  label={COPY.order}
                  value={draft.signerOrder}
                  options={(["sequential", "parallel"] as const).map((o) => ({
                    value: o,
                    label: COPY.orders[o],
                  }))}
                  onChange={(v) => {
                    setDraft((d) => ({ ...d, signerOrder: v as Draft["signerOrder"] }));
                  }}
                />
                {draft.signers.map((s, i) => (
                  <SignerRows
                    key={s.id}
                    signer={s}
                    n={i + 1}
                    policy={policy}
                    family={envelope.policy_family}
                    missing={missingEmail.includes(s)}
                    onChange={(next) => {
                      setDraft((d) => ({
                        ...d,
                        signers: d.signers.map((x) => (x.id === s.id ? next : x)),
                      }));
                    }}
                  />
                ))}
              </Card>
              <Card title={COPY.delivery}>
                <ValueRow kind="value" label={COPY.channel}>
                  {COPY.channelValue}
                </ValueRow>
                <ValueRow
                  kind="paragraph"
                  label={COPY.message}
                  value={draft.message}
                  rows={2}
                  onChange={(message) => {
                    setDraft((d) => ({ ...d, message }));
                  }}
                />
                <ValueRow
                  kind="select"
                  label={COPY.reminders}
                  value={draft.reminder}
                  options={(
                    policy?.reminder_cadences ?? (draft.reminder === "" ? [] : [draft.reminder])
                  ).map((c) => ({ value: c, label: COPY.cadences[c] ?? c }))}
                  onChange={(reminder) => {
                    setDraft((d) => ({ ...d, reminder }));
                  }}
                />
                <ValueRow kind="value" label={COPY.expires} trailing="calendar">
                  {envelope.expires_at === null
                    ? "—"
                    : date(envelope.expires_at, {
                        now,
                        withYear: true,
                        ...(tz === undefined ? {} : { tz }),
                      })}
                </ValueRow>
              </Card>
              <Card title={COPY.dating}>
                <ValueRow
                  kind="toggle"
                  label={COPY.fixedDate}
                  help={COPY.fixedHelp}
                  checked={draft.fixedDate}
                  onChange={(fixedDate) => {
                    setDraft((d) => ({ ...d, fixedDate }));
                  }}
                />
              </Card>
              <Card title={COPY.retention}>
                <p className="px-[14px] py-[9px] text-dense text-ink-2">
                  {retentionLine(
                    envelope.policy_family,
                    envelope.row.number,
                    envelope.row.client_name,
                    envelope.row.work_item_label,
                  )}
                </p>
              </Card>
            </section>
          </SheetColumns>
          <footer className="flex h-[56px] flex-none items-center gap-[8px] bg-card px-[12px] hairline-t">
            {gateLine !== null && (
              <p
                data-gate-line=""
                className="flex flex-1 items-center gap-[6px] text-dense text-ink-3"
              >
                <Icon name="lock" size={13} />
                {gateLine}
              </p>
            )}
            <span className="flex-1" />
            <Button
              variant="secondary"
              disabled={sending}
              onClick={() => {
                void save().then((ok) => {
                  if (ok) onOpenChange(false);
                });
              }}
            >
              {COPY.saveDraft}
            </Button>
            {envelope.row.allowed_actions.includes("envelope.send") && (
              <HumanAction
                verb="Send"
                actor={actor}
                disabled={blocked || sending}
                onClick={() => void send()}
              />
            )}
          </footer>
        </div>
      </FullSheet>
      <Dialog
        open={keeping}
        onOpenChange={setKeeping}
        title={COPY.keep.title}
        description={COPY.keep.body}
        size="sm"
      >
        <div className="flex justify-end gap-[8px]">
          <Button
            variant="secondary"
            onClick={() => {
              setKeeping(false);
              onOpenChange(false);
            }}
          >
            {COPY.keep.discard}
          </Button>
          <Button
            onClick={() => {
              void save().then((ok) => {
                setKeeping(false);
                if (ok) onOpenChange(false);
              });
            }}
          >
            {COPY.keep.save}
          </Button>
        </div>
      </Dialog>
    </>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }): JSX.Element {
  return (
    <section aria-label={title} className="overflow-hidden rounded-nested bg-card shadow-e1">
      <h3 className="flex h-[33px] items-center bg-band-hd px-[14px] text-section">{title}</h3>
      {children}
    </section>
  );
}

function SignerRows({
  signer,
  n,
  policy,
  family,
  missing,
  onChange,
}: {
  signer: SignerOut;
  n: number;
  policy: EnvelopePolicyOut | undefined;
  family: EnvelopeOut["policy_family"];
  missing: boolean;
  onChange: (next: SignerOut) => void;
}): JSX.Element {
  const allowed = new Set<IdentityMethod>(
    policy?.allowed_identity_methods ?? [signer.identity_method],
  );
  return (
    <div data-signer={signer.id} className="hairline-t">
      <div className="flex flex-col gap-[2px] px-[14px] py-[8px]">
        <span className="text-body font-medium">
          {String(n)} · {signer.name}
        </span>
        <span className="text-cell text-ink-3">
          {[signer.title, missing ? null : signer.email].filter((x) => x != null).join(" · ")}
          {missing && (
            <span className="text-red-ink">
              {signer.title == null ? "" : " · "}
              {COPY.emailRequired}
            </span>
          )}
        </span>
      </div>
      <ValueRow
        kind="select"
        label={COPY.identity}
        indented
        value={signer.identity_method}
        options={IDENTITY_METHODS.map((m) => ({
          value: m,
          label: COPY.identities[m],
          ...(allowed.has(m) ? {} : { disabled: true, hint: COPY.identityRefused(family) }),
        }))}
        onChange={(v) => {
          const m = v as IdentityMethod;
          if (allowed.has(m)) onChange({ ...signer, identity_method: m });
        }}
      />
      <ValueRow
        kind="select"
        label={COPY.role}
        indented
        value={signer.role}
        options={(["signer", "countersigner", "ero"] as const).map((r) => ({
          value: r,
          label: COPY.roles[r],
        }))}
        onChange={(v) => {
          onChange({ ...signer, role: v as SignerOut["role"] });
        }}
      />
    </div>
  );
}

function Preview({
  envelope,
  doc,
  signers,
}: {
  envelope: EnvelopeOut;
  doc: EnvelopeOut["documents"][number] | null;
  signers: readonly SignerOut[];
}): JSX.Element {
  const urls = usePageUrls(envelope.row.id, doc?.id ?? null, Math.min(doc?.page_count ?? 0, 2));
  const file: ViewerFile = {
    name: doc?.title ?? "",
    pages: Array.from({ length: Math.min(doc?.page_count ?? 0, 2) }, (_, i) => ({
      n: i + 1,
      width_pt: 612,
      height_pt: 792,
      rotation: 0 as const,
      src: urls[i + 1] ?? "",
    })),
    regions: [],
  };
  const placed = envelope.fields.filter((f) => f.document_id === doc?.id);
  return (
    <section
      aria-label={COPY.preview}
      className="min-w-0 self-stretch overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <SourceViewer
        file={file}
        status="ready"
        loading={doc !== null && Object.keys(urls).length === 0}
        afterPages={
          placed.length === 0 ? undefined : (
            <ul aria-label={COPY.placed} className="flex flex-col gap-[6px] pt-[8px]">
              {placed.map((f) => (
                <li
                  key={f.id}
                  data-field={f.kind}
                  className="flex items-center gap-[6px] text-dense"
                >
                  <span className="inline-flex h-[22px] items-center rounded-pill bg-espresso px-[8px] text-pill text-on-dark">
                    {COPY.field[f.kind]} · {signers.find((s) => s.id === f.signer_id)?.name ?? ""}
                  </span>
                  <span className="text-meta text-ink-3">p. {String(f.page)}</span>
                </li>
              ))}
            </ul>
          )
        }
      />
    </section>
  );
}
