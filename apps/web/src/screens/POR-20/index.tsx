import type {
  EmailPreviewOut,
  EmailTemplateDraftIn,
  EmailTemplateOut,
  EmailTemplateRowOut,
  LintFindingOut,
  TemplateBlock,
} from "@abacus/api-client";
import { previewEmailTemplate } from "@abacus/api-client";
import {
  discardEmailTemplateDraftMutation,
  getEmailTemplateOptions,
  getEmailTemplateQueryKey,
  getFollowUpPolicyOptions,
  listEmailTemplatesOptions,
  listEmailTemplatesQueryKey,
  publishEmailTemplateMutation,
  saveEmailTemplateDraftMutation,
  testSendEmailTemplateMutation,
} from "@abacus/api-client/query";
import {
  Alert,
  Button,
  ChevronLeft,
  Dialog,
  ErrorState,
  Pane,
  Pill,
  RadioGroup,
  RestrictedState,
  Segmented,
  SkeletonRows,
  ValueRow,
  cn,
  date,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useRef, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import {
  EmailPreview,
  type PreviewWidth,
  insertAt,
  segments,
  token,
  variableLabel,
} from "../../domain/communications";
import { COPY, LINT, whereOf } from "./copy";

// POR-20 · Transactional email templates (R-01-T25; R-01 Story 7.1–7.3; docs/screens/POR-20.md).
// A T10 document on a well: the 470 structure pane (the templates, the Reminder schedule, the
// variables and the rules) and the paper pane, whose well renders the server's deterministic
// email through R-01's interim EmailPreview (sandboxed, no fetches). Every artboard is a data
// condition of one screen:
//
//   a  the Reminder's v4 draft at 600 for Claire Feld;  b  the body clicked: inline editing
//   c  ?w=390;  d  ?w=phone (the phone mail-client frame)
//   e–i  the other five keys, each previewed for its sample recipient
//   j  "Send test…" opened;  k  the test sent (toast);  l  v4 published, Publish disabled
//
// The lint is the server's: preview lists the findings on their blocks, and Publish stays
// disabled while any finding remains (test send and publish also answer 422 on the server).
// Template words are firm content from the API; nothing here holds them.

export type Por20Width = PreviewWidth;

export interface SampleOption {
  id: string;
  name: string;
  line: string;
  email: string;
}

export interface POR20Props {
  templateKey: string;
  width: Por20Width;
  /** The sample contact the preview fills in (`sample_contact_id`); "" for the sample client. */
  sample: string;
  /** The Send test sheet's sample recipients. */
  samples?: readonly SampleOption[];
  onWidth?: (width: Por20Width) => void;
  onOpenTemplate?: (key: string) => void;
  onBack?: () => void;
}

type Problem = { detail?: unknown } | null | undefined;
const detailOf = (error: unknown): string | undefined => {
  const detail = (error as Problem)?.detail;
  return typeof detail === "string" ? detail : undefined;
};
const idempotency = (): { "Idempotency-Key": string } => ({
  "Idempotency-Key": crypto.randomUUID(),
});

interface EditState {
  subject: string;
  preheader: string;
  blocks: TemplateBlock[];
  cta_label: string | null;
  cta_target: NonNullable<EmailTemplateDraftIn["cta_target"]> | null;
}

function editable(t: EmailTemplateOut): EditState | null {
  const from = t.draft ?? t.published ?? null;
  if (from === null) return null;
  return {
    subject: from.subject,
    preheader: from.preheader,
    blocks: from.blocks.map((b) => ({ ...b })),
    cta_label: from.cta_label ?? null,
    cta_target: from.cta_target ?? null,
  };
}

function Band({ title, children }: { title: string; children: React.ReactNode }): JSX.Element {
  return (
    <section aria-label={title} className="flex flex-col">
      <h3 className="bg-band-hd px-4 py-2 text-section text-ink-3">{title}</h3>
      <div className="flex flex-col">{children}</div>
    </section>
  );
}

function TemplatePills({ row }: { row: EmailTemplateRowOut }): JSX.Element {
  return (
    <span className="flex flex-wrap gap-1">
      {row.published === null || row.published === undefined ? (
        <Pill variant="muted" size="sm">
          {COPY.pill.notPublished}
        </Pill>
      ) : (
        <Pill variant="green-tint" size="sm">
          {COPY.pill.published(row.published.version)}
        </Pill>
      )}
      {row.draft === null || row.draft === undefined ? null : (
        <Pill variant="amber" size="sm">
          {COPY.pill.draft(row.draft.version)}
        </Pill>
      )}
    </span>
  );
}

function TemplateRow({
  row,
  active,
  onOpen,
}: {
  row: EmailTemplateRowOut;
  active: boolean;
  onOpen: () => void;
}): JSX.Element {
  return (
    <li>
      <button
        type="button"
        aria-current={active ? "page" : undefined}
        onClick={onOpen}
        className={cn(
          "flex w-full flex-col items-start gap-1 border-b border-hair px-4 py-3 text-left",
          active ? "bg-sel-bg" : "hover:bg-nested",
        )}
      >
        <span className="text-body text-ink">{row.name}</span>
        <span className="text-meta text-ink-3">{COPY.usedBy(row.used_by_label)}</span>
        <TemplatePills row={row} />
      </button>
    </li>
  );
}

function ValueLine({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <ValueRow kind="value" label={label}>
      {value}
    </ValueRow>
  );
}

function Schedule(): JSX.Element | null {
  const policy = useQuery(getFollowUpPolicyOptions());
  if (policy.data === undefined) return null;
  const p = policy.data.policy;
  const [h = "09", m = "00"] = (p.send_local_time ?? "09:00").split(":");
  const at = new Date(Date.UTC(2026, 0, 1, Number(h), Number(m)));
  const clock = time(at.toISOString(), { tz: "UTC" });
  const onOff = (on: boolean | undefined): string => (on === true ? COPY.on : COPY.off);
  return (
    <Band title={COPY.band.schedule}>
      <ValueLine
        label={COPY.schedule.cadence}
        value={COPY.schedule.cadenceValue(p.cadence_days ?? 7)}
      />
      <ValueLine label={COPY.schedule.max} value={String(p.max_reminders ?? 4)} />
      <ValueLine
        label={COPY.schedule.sendAt}
        value={COPY.schedule.sendAtValue(clock, p.weekdays_only ?? true)}
      />
      <ValueLine label={COPY.schedule.stopWhenDone} value={onOff(p.stop_on_binder_done)} />
      <ValueLine label={COPY.schedule.copyPreparer} value={onOff(p.cc_assigned_preparer)} />
    </Band>
  );
}

function Findings({ findings }: { findings: readonly LintFindingOut[] }): JSX.Element | null {
  if (findings.length === 0) return null;
  return (
    <Alert title={COPY.findingsTitle}>
      <ul aria-label={COPY.findingsTitle} className="flex flex-col gap-1">
        {findings.map((f, i) => (
          <li key={`${f.code}:${f.block_id ?? ""}:${f.variable ?? ""}:${String(i)}`}>
            <span className="text-ink">{whereOf(f.block_id, f.variable)}</span>
            {" · "}
            {LINT[f.code]}
          </li>
        ))}
      </ul>
    </Alert>
  );
}

function Chips({ text }: { text: string }): JSX.Element {
  return (
    <span className="text-meta text-ink-2">
      {segments(text).map((s, i) =>
        s.kind === "text" ? (
          <span key={String(i)}>{s.text}</span>
        ) : (
          <span
            key={String(i)}
            title={token(s.name)}
            aria-label={variableLabel(s.name)}
            className="mx-0.5 inline-flex rounded-pill bg-chip px-2 text-ink-2"
          >
            {s.name.replaceAll("_", " ")}
          </span>
        ),
      )}
    </span>
  );
}

interface Caret {
  field: string; // "subject" or a block id
  start: number;
  end: number;
}

function Editor({
  state,
  findings,
  onChange,
  onCaret,
}: {
  state: EditState;
  findings: readonly LintFindingOut[];
  onChange: (next: EditState) => void;
  onCaret: (caret: Caret) => void;
}): JSX.Element {
  const track =
    (field: string) =>
    (event: React.SyntheticEvent<HTMLTextAreaElement | HTMLInputElement>): void => {
      const el = event.currentTarget;
      onCaret({ field, start: el.selectionStart ?? 0, end: el.selectionEnd ?? 0 });
    };
  return (
    <div className="flex w-full max-w-[600px] flex-col gap-3 rounded-pane bg-card p-6 shadow-e1">
      <p role="status" className="text-meta text-ink-3">
        {COPY.editing.bar}
      </p>
      <textarea
        aria-label={COPY.editing.subject}
        rows={1}
        className="w-full rounded-control border border-stroke bg-card p-2 text-body text-ink"
        value={state.subject}
        onChange={(e) => {
          onChange({ ...state, subject: e.currentTarget.value });
          track("subject")(e);
        }}
        onSelect={track("subject")}
        onKeyUp={track("subject")}
        onClick={track("subject")}
      />
      {state.blocks.map((block, i) => {
        const mine = findings.filter((f) => f.block_id === block.id);
        return (
          <div key={block.id} className="flex flex-col gap-1">
            <textarea
              aria-label={COPY.editing.blockLabel(block.id)}
              value={block.text}
              rows={block.kind === "paragraph" ? 3 : 2}
              className="w-full rounded-control border border-stroke bg-card p-2 text-body text-ink"
              onChange={(e) => {
                const blocks = state.blocks.map((b, j) =>
                  j === i ? { ...b, text: e.currentTarget.value } : b,
                );
                onChange({ ...state, blocks });
                track(block.id)(e);
              }}
              onSelect={track(block.id)}
              onKeyUp={track(block.id)}
              onClick={track(block.id)}
            />
            <Chips text={block.text} />
            {mine.map((f, n) => (
              <p
                key={`${f.code}:${String(n)}`}
                className="text-meta text-amber-ink"
                data-finding={f.code}
              >
                {LINT[f.code]}
              </p>
            ))}
          </div>
        );
      })}
    </div>
  );
}

function PhoneFrame({
  subject,
  from,
  at,
  children,
}: {
  subject: string;
  from: string;
  at: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div
      data-frame="phone"
      className="flex w-[470px] flex-col gap-3 rounded-phone bg-card p-4 shadow-e2"
    >
      <span className="text-meta text-ink-3">‹ {COPY.phone.back}</span>
      <h2 className="text-title text-ink">{subject}</h2>
      <p className="text-meta text-ink-3">
        {from} · {COPY.phone.toMe} · {at}
      </p>
      {children}
    </div>
  );
}

function SendTestSheet({
  open,
  onOpenChange,
  email,
  samples,
  sample,
  onSample,
  onSend,
  sending,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  email: string;
  samples: readonly SampleOption[];
  sample: string;
  onSample: (id: string) => void;
  onSend: () => void;
  sending: boolean;
}): JSX.Element {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.testSheet.title}
      action={
        <Button onClick={onSend} loading={sending}>
          {COPY.testSheet.send}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <ValueRow kind="value" label={`${COPY.testSheet.sendTo} · ${COPY.testSheet.email}`}>
          <span data-testid="por20-send-to">{email}</span>
        </ValueRow>
        <RadioGroup
          label={COPY.testSheet.sample}
          value={sample}
          onChange={onSample}
          options={[
            ...samples.map((s) => ({ value: s.id, label: `${s.name} · ${s.line}` })),
            { value: "", label: COPY.meta.sampleClient },
          ]}
        />
        <p className="text-meta text-ink-3">{COPY.testSheet.note}</p>
        <div className="flex justify-end">
          <Button
            variant="secondary"
            onClick={() => {
              onOpenChange(false);
            }}
          >
            {COPY.testSheet.cancel}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

export function POR20({
  templateKey,
  width,
  sample,
  samples = [],
  onWidth,
  onOpenTemplate,
  onBack,
}: POR20Props): JSX.Element {
  const now = useNow();
  const session = useSession();
  const queries = useQueryClient();
  const list = useQuery(listEmailTemplatesOptions());
  const path = { path: { key: templateKey } };
  const template = useQuery(getEmailTemplateOptions(path));
  const [editing, setEditing] = useState<EditState | null>(null);
  const [stale, setStale] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [stepUp, setStepUp] = useState(false);
  const [testSample, setTestSample] = useState(sample);
  const caret = useRef<Caret | null>(null);
  const t = template.data;
  const source = t?.draft ? "draft" : "published";
  const previewWidth = width === "600" ? 600 : 390;
  const preview = useQuery({
    queryKey: [
      "por20-preview",
      templateKey,
      source,
      previewWidth,
      sample,
      t?.draft?.expected_version ?? 0,
      t?.published?.version ?? 0,
    ],
    enabled: t !== undefined && (t.draft !== null || t.published !== null),
    queryFn: async (): Promise<EmailPreviewOut> =>
      (
        await previewEmailTemplate({
          ...path,
          body: {
            source,
            width: previewWidth,
            ...(sample === "" ? {} : { sample_contact_id: sample }),
          },
          throwOnError: true,
        })
      ).data,
  });
  const refresh = async (): Promise<void> => {
    await queries.invalidateQueries({ queryKey: getEmailTemplateQueryKey(path) });
    await queries.invalidateQueries({ queryKey: listEmailTemplatesQueryKey() });
    await queries.invalidateQueries({ queryKey: ["por20-preview", templateKey] });
  };
  const failed = (error: unknown): void => {
    const detail = detailOf(error);
    if (detail === "forbidden") setStepUp(true);
    else if (detail === "stale_version") setStale(true);
    void refresh();
  };
  const save = useMutation({
    ...saveEmailTemplateDraftMutation(),
    onSuccess: async () => {
      setEditing(null);
      setStale(false);
      await refresh();
    },
    onError: failed,
  });
  const discard = useMutation({
    ...discardEmailTemplateDraftMutation(),
    onSuccess: refresh,
    onError: failed,
  });
  const publish = useMutation({
    ...publishEmailTemplateMutation(),
    onSuccess: refresh,
    onError: failed,
  });
  const testSend = useMutation({
    ...testSendEmailTemplateMutation(),
    onSuccess: (sent) => {
      setSheet(false);
      toast.show(COPY.toastTestSent(sent.sent_to));
    },
    onError: (error) => {
      setSheet(false);
      failed(error);
    },
  });

  if (template.isError && detailOf(template.error) === "forbidden") {
    return <RestrictedState reason="role" />;
  }
  if (template.isError) {
    return (
      <ErrorState
        noun={COPY.loadError}
        onRetry={() => {
          void template.refetch();
        }}
      />
    );
  }

  const rows = list.data?.items ?? [];
  const designed = rows.filter((r) => r.group === "designed");
  const registered = rows.filter((r) => r.group === "registered");
  const actions = new Set(t?.allowed_actions ?? []);
  const canEdit = actions.has("edit");
  const findings = preview.data?.findings ?? [];
  const nextVersion = t?.draft ? (t.published?.version ?? 0) + 1 : null;
  const publishDisabled =
    !actions.has("publish") || t?.draft === null || findings.length > 0 || publish.isPending;
  const sampleRow = samples.find((s) => s.id === sample);
  const insert = (name: string): void => {
    if (editing === null) return;
    const at = caret.current;
    if (at === null) return;
    if (at.field === "subject") {
      const done = insertAt(editing.subject, name, at.start, at.end);
      setEditing({ ...editing, subject: done.text });
      caret.current = { field: "subject", start: done.caret, end: done.caret };
      return;
    }
    const blocks = editing.blocks.map((b) => {
      if (b.id !== at.field) return b;
      const done = insertAt(b.text, name, at.start, at.end);
      caret.current = { field: b.id, start: done.caret, end: done.caret };
      return { ...b, text: done.text };
    });
    setEditing({ ...editing, blocks });
  };
  const header = ((): JSX.Element | null => {
    if (t === undefined) return null;
    if (t.draft)
      return <Pill variant="amber">{COPY.pill.draft((t.published?.version ?? 0) + 1)}</Pill>;
    if (t.published) {
      const by = t.published.published_by?.display_name;
      return (
        <Pill variant="green-tint">
          {by === undefined
            ? COPY.pill.published(t.published.version)
            : COPY.pill.publishedBy(
                t.published.version,
                date(t.published.published_at, { now }),
                by,
              )}
        </Pill>
      );
    }
    return <Pill variant="muted">{COPY.pill.notPublished}</Pill>;
  })();

  const body = ((): JSX.Element => {
    if (template.isPending || preview.isPending) {
      return <SkeletonRows type="list" count={4} />;
    }
    if (editing !== null) {
      return (
        <Editor
          state={editing}
          findings={findings}
          onChange={setEditing}
          onCaret={(c) => {
            caret.current = c;
          }}
        />
      );
    }
    if (preview.data === undefined) {
      return <ErrorState noun={COPY.loadError} onRetry={() => void preview.refetch()} />;
    }
    const email = (
      <div className="relative">
        <EmailPreview
          html={preview.data.html}
          text={preview.data.text}
          width={width}
          title={COPY.previewTitle}
          showText={COPY.showText}
          hideText={COPY.hideText}
        />
        {canEdit ? (
          <button
            type="button"
            aria-label={COPY.editing.bar}
            className="absolute inset-x-0 top-0 h-[640px] cursor-text"
            onClick={() => {
              if (t !== undefined) setEditing(editable(t));
            }}
          />
        ) : null}
      </div>
    );
    if (width === "phone") {
      return (
        <PhoneFrame
          subject={preview.data.subject}
          from={preview.data.from_display}
          at={time(now.toISOString())}
        >
          {email}
        </PhoneFrame>
      );
    }
    return email;
  })();

  return (
    <div className="flex min-h-0 flex-1 flex-col" data-screen="POR-20">
      <div className="flex items-center gap-3 border-b border-hair px-4 py-2">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ChevronLeft size={14} aria-hidden />
          {COPY.subbar.back}
        </Button>
        <h1 className="text-pane text-ink">{COPY.subbar.title}</h1>
        <span className="text-meta text-ink-3">{COPY.subbar.context}</span>
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px] bg-shell p-[10px]">
        <Pane
          width={470}
          title={COPY.structureHeader}
          titleAlign="left"
          scrollLabel={COPY.structureHeader}
        >
          <Band title={COPY.band.templates}>
            {list.isPending ? (
              <SkeletonRows type="list" count={6} />
            ) : (
              <ul aria-label={COPY.band.templates}>
                {designed.map((row) => (
                  <TemplateRow
                    key={row.key}
                    row={row}
                    active={row.key === templateKey}
                    onOpen={() => onOpenTemplate?.(row.key)}
                  />
                ))}
              </ul>
            )}
          </Band>
          {registered.length > 0 ? (
            <Band title={COPY.band.registered}>
              <ul aria-label={COPY.band.registered}>
                {registered.map((row) => (
                  <TemplateRow
                    key={row.key}
                    row={row}
                    active={row.key === templateKey}
                    onOpen={() => onOpenTemplate?.(row.key)}
                  />
                ))}
              </ul>
            </Band>
          ) : null}
          {templateKey === "reminder" ? <Schedule /> : null}
          <Band title={COPY.band.variables}>
            <div className="flex flex-wrap gap-2 px-4 py-3">
              {(t?.variables ?? []).map((v) => (
                <button
                  key={v.name}
                  type="button"
                  title={token(v.name)}
                  aria-label={variableLabel(v.name)}
                  disabled={editing === null}
                  onMouseDown={(e) => {
                    e.preventDefault(); // keep the caret where it is
                  }}
                  onClick={() => {
                    insert(v.name);
                  }}
                  className="rounded-pill bg-chip px-2 py-0.5 text-meta text-ink-2 disabled:cursor-default"
                >
                  {token(v.name)}
                </button>
              ))}
            </div>
          </Band>
          <Band title={COPY.band.rules}>
            <p className="px-4 py-3 text-body text-ink-2">{COPY.rulesBody}</p>
          </Band>
        </Pane>
        <Pane
          well
          title={t?.name ?? ""}
          titleAlign="left"
          left={header}
          right={
            <div className="flex items-center gap-2">
              <Segmented
                label={COPY.paper.widthLabel}
                size="small"
                options={[COPY.paper.w600, COPY.paper.w390, COPY.paper.phone]}
                active={width === "phone" ? COPY.paper.phone : width}
                onChange={(label) => {
                  onWidth?.(label === COPY.paper.phone ? "phone" : (label as Por20Width));
                }}
              />
              {editing !== null ? (
                <Button
                  size="sm"
                  loading={save.isPending}
                  onClick={() => {
                    save.mutate({
                      ...path,
                      body: {
                        ...editing,
                        expected_version: t?.draft?.expected_version ?? 0,
                      },
                    });
                  }}
                >
                  {COPY.editing.done}
                </Button>
              ) : null}
              {actions.has("test_send") && editing === null ? (
                <Button
                  size="sm"
                  variant="secondary"
                  opensDialog
                  onClick={() => {
                    setTestSample(sample);
                    setSheet(true);
                  }}
                >
                  {COPY.paper.sendTest}
                </Button>
              ) : null}
              {canEdit && t?.draft && editing === null ? (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    discard.mutate(path);
                  }}
                >
                  {COPY.paper.discard}
                </Button>
              ) : null}
              {canEdit ? (
                <Button
                  size="sm"
                  disabled={publishDisabled || editing !== null}
                  onClick={() => {
                    publish.mutate({ ...path, headers: idempotency() });
                  }}
                >
                  {COPY.paper.publish(nextVersion)}
                </Button>
              ) : null}
            </div>
          }
        >
          <div className="flex flex-col items-center gap-4 p-6">
            {canEdit || t === undefined ? null : (
              <p className="text-meta text-ink-3">{COPY.flagOffNote}</p>
            )}
            {stale ? <Alert title={COPY.staleDraft} /> : null}
            <Findings findings={findings} />
            {preview.data === undefined ? null : (
              <dl className="grid w-full max-w-[600px] grid-cols-[80px_1fr] gap-x-3 gap-y-1 text-body">
                <dt className="text-ink-3">{COPY.meta.from}</dt>
                <dd className="text-ink">
                  {preview.data.from_display} &lt;{preview.data.from_address}&gt;
                </dd>
                {preview.data.reply_to ? (
                  <>
                    <dt className="text-ink-3">{COPY.meta.replyTo}</dt>
                    <dd className="text-ink">{preview.data.reply_to}</dd>
                  </>
                ) : null}
                <dt className="text-ink-3">{COPY.meta.recipient}</dt>
                <dd className="text-ink">{sampleRow?.email ?? COPY.meta.sampleClient}</dd>
                <dt className="text-ink-3">{COPY.meta.subject}</dt>
                <dd className="text-ink" data-testid="por20-subject">
                  {preview.data.subject}
                </dd>
              </dl>
            )}
            {body}
          </div>
        </Pane>
      </div>
      <SendTestSheet
        open={sheet}
        onOpenChange={setSheet}
        email={session.user?.email ?? ""}
        samples={samples}
        sample={testSample}
        onSample={setTestSample}
        sending={testSend.isPending}
        onSend={() => {
          testSend.mutate({
            ...path,
            headers: idempotency(),
            body: testSample === "" ? {} : { sample_contact_id: testSample },
          });
        }}
      />
      <Dialog
        open={stepUp}
        onOpenChange={setStepUp}
        title={COPY.stepUpTitle}
        description={COPY.stepUpBody}
      >
        <div className="flex justify-end gap-2">
          <Button
            onClick={() => {
              signIn(currentRoute(), { forceLogin: true });
            }}
          >
            {COPY.signInAgain}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
