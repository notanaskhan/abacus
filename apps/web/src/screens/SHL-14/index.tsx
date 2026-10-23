import type { RequestItemPatchIn } from "@abacus/api-client";
import {
  Button,
  DEFAULT_TZ,
  Drawer,
  DrawerCard,
  Fieldset,
  Icon,
  Segmented,
  StatusPill,
  ValueRow,
  count,
  date,
  status,
  time,
  toast,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import {
  useBinder,
  useBinderRequests,
  useClientContacts,
  useClientPreview,
  useComposerSave,
  useItemComments,
  useRequestDetail,
  useRequestItems,
  useStaffNames,
} from "../../domain/requests";
import { COPY } from "./copy";

// SHL-14 · Request composer drawer (P-06-T13; docs/screens/SHL-14.md): the O2 drawer 480 with the
// R2 tabs row (Details · Comments · Activity), opened as `?ov=request:new:<binderId>` or
// `?ov=request:<requestItemId>:<binderId>` over its host (BND-02 here). Details holds the
// fieldset cards "Document request", "People" and "Links", the client preview when the binder's
// client projection holds the request, and the sticky footer. States (fixtures/scenarios/SHL-14.ts):
//
//   a  a new request on the Northwind PY2025 binder (Marcus Delaney; due from the binder default)
//   b  the existing "Bridge letter — Keystone, Oct–Dec 2025", requested Sep 1, due Sep 25
//   e  a with no due date: "Save & send" disabled with "Add a due date to send"
//   f  the agent-drafted Granite Peak SURL Draft (Cole Hart): "Approve & send to Luis Ferrante"
//
// c (sample-driven bulk) is A-03's and d (the close variant) P-06-T24's. A person sends; the
// agent never does (INV-1): every send here is this person's click.

export type Wave = NonNullable<RequestItemPatchIn["wave"]>;
const WAVES: readonly Wave[] = ["planning", "year_end", "sample"];
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;
type Tab = "details" | "comments" | "activity";

export interface RequestComposerProps {
  binderId: string;
  /** Null composes a new request. */
  requestId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function onDay(day: string): string {
  return `${day}T12:00:00Z`;
}

function errorCode(error: unknown): string | null {
  const detail = (error as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" ? detail : null;
}

export function RequestComposer({
  binderId,
  requestId,
  open,
  onOpenChange,
}: RequestComposerProps): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const binder = useBinder(binderId).data;
  const engagementId = binder?.engagement_id;
  const rows = useBinderRequests(binderId).data?.items ?? [];
  const row = requestId === null ? undefined : rows.find((r) => r.id === requestId);
  const preview = (useClientPreview(binderId).data?.items ?? []).find((i) => i.id === requestId);
  const item = (useRequestItems(engagementId).data ?? []).find((i) => i.id === requestId);
  const contacts = useClientContacts(engagementId).data ?? [];
  const staff = useStaffNames();
  const detail = useRequestDetail(engagementId, requestId);
  const comments = useItemComments(engagementId, requestId).data ?? [];
  const save = useComposerSave();

  const categories = binder?.categories ?? [];
  const isNew = requestId === null;
  const isDraft = isNew || row?.status === "draft";
  const [tab, setTab] = useState<Tab>("details");
  const [title, setTitle] = useState<string | null>(null);
  const [categoryId, setCategoryId] = useState<string | null>(null);
  const [description, setDescription] = useState<string | null>(null);
  const [due, setDue] = useState<string | null>(null);
  const [wave, setWave] = useState<Wave | null>(null);
  const [assignee, setAssignee] = useState<string | null>(null);
  const [owner, setOwner] = useState<string | null>(null);
  const [thirdParty, setThirdParty] = useState(false);
  const [delegate, setDelegate] = useState<string | null>(null);
  const [supports, setSupports] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  // What the fields hold: the person's edits over the request's own facts.
  const vTitle = title ?? row?.title ?? "";
  const vCategory = categoryId ?? row?.category_id ?? null;
  const vDescription = description ?? item?.description ?? "";
  const vDue = due ?? row?.due_on ?? (isNew ? (binder?.default_due_on ?? "") : "");
  const vAssignee = assignee ?? item?.client_assignee_user_id ?? null;
  const dirty =
    [title, categoryId, description, due, wave, assignee, owner, delegate, supports].some(
      (v) => v !== null,
    ) || thirdParty;

  const nameOfContact = (id: string | null): string | undefined =>
    contacts.find((c) => c.id === id)?.display_name ?? undefined;
  const assigneeName = nameOfContact(vAssignee);
  const delegateName = thirdParty ? nameOfContact(delegate) : undefined;
  const recipient = delegateName ?? assigneeName;
  const dueValid = ISO_DAY.test(vDue);
  const canSave = vTitle.trim() !== "" && vCategory !== null && vDescription.trim() !== "";
  const sendable = row === undefined || row.status === "draft" || dirty;

  let primary: string;
  if (thirdParty && delegateName !== undefined) primary = COPY.footer.sendTo(delegateName);
  else if (isDraft && !isNew) {
    primary =
      assigneeName === undefined
        ? COPY.footer.approveSend
        : COPY.footer.approveSendTo(assigneeName);
  } else primary = COPY.footer.saveSend;

  const close = (): void => {
    setTitle(null);
    setCategoryId(null);
    setDescription(null);
    setDue(null);
    setWave(null);
    setAssignee(null);
    setOwner(null);
    setThirdParty(false);
    setDelegate(null);
    setSupports(null);
    setProblem(null);
    setTab("details");
    onOpenChange(false);
  };

  const submit = async (send: boolean): Promise<void> => {
    if (engagementId === undefined || vCategory === null) return;
    const category = categories.find((c) => c.id === vCategory)?.name ?? "";
    const patch: RequestItemPatchIn = {
      title: vTitle.trim(),
      category_id: vCategory,
      description: vDescription.trim(),
      ...(dueValid ? { due_on: vDue } : {}),
      ...(wave === null ? (isNew ? { wave: "planning" as const } : {}) : { wave }),
      ...(vAssignee === null ? {} : { client_assignee_user_id: vAssignee }),
      ...(owner === null ? {} : { firm_owner_user_id: owner }),
      ...(supports === null ? {} : { supports_ref: supports }),
    };
    try {
      await save.run({
        engagementId,
        itemId: requestId,
        create: { audit_area: category, description: vDescription.trim() },
        patch,
        delegateTo: thirdParty ? delegate : null,
        send,
      });
      toast.show({
        kind: "success",
        text: send && recipient !== undefined ? COPY.toast.sent(recipient) : COPY.toast.saved,
      });
      close();
    } catch (error) {
      const code = errorCode(error);
      setProblem(
        code === "due_date_required"
          ? COPY.validation.due
          : code === "model_text_not_permitted"
            ? COPY.footer.modelText
            : COPY.toast.failed,
      );
    }
  };

  const statusPill = isDraft ? (
    <StatusPill variant="outline">{COPY.pill.draft}</StatusPill>
  ) : row !== undefined ? (
    <StatusPill variant={status("request", row.status).variant ?? "outline"}>
      {[
        status("request", row.status, {
          vars: { date: row.requested_at == null ? "" : date(row.requested_at, { now, tz }) },
        }).label,
        ...(row.due_on == null ? [] : [`due ${date(onDay(row.due_on), { now, tz })}`]),
      ].join(" · ")}
    </StatusPill>
  ) : null;

  const done = binder?.done_count ?? 0;
  const total = binder?.total_count ?? 0;
  const footer = (
    <div className="flex w-full items-center gap-[8px]">
      <span className="min-w-0 flex-1 text-meta text-ink-3">
        {problem ?? (isNew ? COPY.footer.adds(count(done), count(total + 1)) : "")}
      </span>
      <Button
        variant="secondary"
        size="sm"
        disabled={!canSave || save.pending}
        onClick={() => void submit(false)}
      >
        {COPY.footer.saveDraft}
      </Button>
      <Button
        variant="primary"
        size="sm"
        disabled={!canSave || !dueValid || !sendable || save.pending}
        loading={save.pending}
        onClick={() => void submit(true)}
      >
        {primary}
      </Button>
    </div>
  );

  const reminderDays = binder?.follow_up_override?.every_days ?? null;

  return (
    <Drawer
      open={open}
      onOpenChange={(next) => {
        if (next) onOpenChange(true);
        else close();
      }}
      title={isNew ? COPY.title.new : COPY.title.existing}
      size="md"
      bare
      dirty={dirty}
      meta={
        <span className="flex items-center gap-[6px]">
          {statusPill}
          {binder !== undefined && <span className="text-meta text-ink-3">{binder.name}</span>}
        </span>
      }
      footer={footer}
    >
      <div className="flex h-[40px] flex-none items-center justify-center bg-card hairline-b">
        <Segmented
          size="small"
          label={COPY.tabs.label}
          options={[COPY.tabs.details, COPY.tabs.comments, COPY.tabs.activity]}
          active={COPY.tabs[tab]}
          onChange={(label) => {
            setTab(
              label === COPY.tabs.comments
                ? "comments"
                : label === COPY.tabs.activity
                  ? "activity"
                  : "details",
            );
          }}
        />
      </div>
      {tab === "details" && (
        <div className="flex flex-col p-[10px]">
          <Fieldset title={COPY.card.documentRequest} flush>
            <ValueRow
              kind="text"
              label={COPY.keys.request}
              value={vTitle}
              onChange={(v) => {
                setTitle(v);
              }}
            />
            <ValueRow
              kind="select"
              label={COPY.keys.category}
              placeholder={COPY.choose}
              options={categories.map((c) => ({ value: c.id, label: c.name }))}
              {...(vCategory === null ? {} : { value: vCategory })}
              onChange={setCategoryId}
            />
            <ValueRow
              kind="paragraph"
              label={COPY.keys.description}
              value={vDescription}
              onChange={(v) => {
                setDescription(v);
              }}
            />
            <ValueRow
              kind="text"
              label={COPY.keys.due}
              value={vDue}
              placeholder={COPY.datePlaceholder}
              onChange={(v) => {
                setProblem(null);
                setDue(v);
              }}
              {...(vDue === ""
                ? { error: COPY.validation.due }
                : !dueValid
                  ? { error: COPY.validation.date }
                  : {})}
            />
            <ValueRow kind="info" label={COPY.keys.wave}>
              <Segmented
                size="small"
                label={COPY.keys.wave}
                options={WAVES.map((w) => COPY.wave[w])}
                active={COPY.wave[wave ?? "planning"]}
                onChange={(label) => {
                  setWave(WAVES.find((w) => COPY.wave[w] === label) ?? "planning");
                }}
              />
            </ValueRow>
          </Fieldset>
          <Fieldset title={COPY.card.people} flush>
            <ValueRow
              kind="select"
              label={COPY.keys.clientAssignee}
              placeholder={COPY.choose}
              options={contacts.map((c) => ({
                value: c.id,
                label: c.display_name ?? c.email ?? c.id,
                hint: c.role,
              }))}
              {...(vAssignee === null ? {} : { value: vAssignee })}
              onChange={setAssignee}
            />
            <ValueRow
              kind="toggle"
              label={COPY.keys.thirdParty}
              checked={thirdParty}
              onChange={setThirdParty}
            />
            {thirdParty && (
              <ValueRow
                kind="select"
                indented
                label={COPY.keys.delegate}
                placeholder={COPY.choose}
                options={contacts
                  .filter((c) => c.id !== vAssignee)
                  .map((c) => ({ value: c.id, label: c.display_name ?? c.email ?? c.id }))}
                {...(delegate === null ? {} : { value: delegate })}
                onChange={setDelegate}
              />
            )}
            {thirdParty && delegateName !== undefined && assigneeName !== undefined && (
              <p className="px-[24px] py-[6px] text-meta text-ink-3">
                {COPY.thirdPartyHelp(
                  delegateName.split(" ")[0] ?? delegateName,
                  assigneeName.split(" ")[0] ?? assigneeName,
                )}
              </p>
            )}
            <ValueRow
              kind="select"
              label={COPY.keys.firmOwner}
              placeholder={COPY.choose}
              options={[...staff].map(([id, name]) => ({ value: id, label: name }))}
              {...(owner === null ? {} : { value: owner })}
              onChange={setOwner}
            />
            <ValueRow kind="info" label={COPY.keys.visibility}>
              <span className="flex flex-col items-end gap-[2px]">
                <Segmented
                  size="small"
                  label={COPY.keys.visibility}
                  options={[
                    { label: COPY.visibility.owners, disabled: !isDraft },
                    { label: COPY.visibility.client, disabled: isDraft },
                  ]}
                  active={
                    isDraft || row?.client_visible === false
                      ? COPY.visibility.owners
                      : COPY.visibility.client
                  }
                />
                {isDraft && (
                  <span className="text-meta text-ink-3">{COPY.visibilityDraftHelp}</span>
                )}
              </span>
            </ValueRow>
            {reminderDays !== null && (
              <ValueRow kind="info" label={COPY.keys.reminders}>
                <span className="flex flex-col items-end">
                  <span>{COPY.reminders(reminderDays)}</span>
                  <span className="text-meta text-ink-3">{COPY.remindersHelp}</span>
                </span>
              </ValueRow>
            )}
          </Fieldset>
          <Fieldset title={COPY.card.links} flush>
            <ValueRow
              kind="text"
              label={COPY.keys.supports}
              value={supports ?? ""}
              onChange={setSupports}
            />
            <ValueRow kind="info" label={COPY.keys.relatedRows}>
              <span className="text-ink-4">{COPY.controlsNone}</span>
            </ValueRow>
            <ValueRow kind="info" label={COPY.keys.controls}>
              <span className="text-ink-4">{COPY.controlsNone}</span>
            </ValueRow>
            <ValueRow kind="info" label={COPY.keys.attachments}>
              <span className="text-ink-3">{COPY.attachmentsEmpty}</span>
            </ValueRow>
          </Fieldset>
          {preview !== undefined && recipient !== undefined && (
            <Fieldset title={COPY.card.preview(recipient.split(" ")[0] ?? recipient)}>
              <div
                data-preview=""
                className="flex flex-col gap-[6px] rounded-pane bg-card p-[12px] shadow-e1"
              >
                {preview.category_name != null && (
                  <span className="text-section font-medium">{preview.category_name}</span>
                )}
                <span className="text-section font-medium">{preview.title}</span>
                <span className="text-cell text-ink-2">{preview.description}</span>
                <span className="flex items-center gap-[10px]">
                  <span className="text-body font-medium text-ink">{COPY.preview.upload}</span>
                  <StatusPill variant="outline">{COPY.preview.ignore}</StatusPill>
                </span>
                {preview.due_on != null && (
                  <span className="text-meta text-ink-3">
                    {COPY.preview.due(date(onDay(preview.due_on), { now, tz }))}
                  </span>
                )}
              </div>
            </Fieldset>
          )}
        </div>
      )}
      {tab === "comments" && (
        <div className="flex flex-col p-[10px]">
          {comments.length === 0 ? (
            <p className="p-[12px] text-cell text-ink-3">{COPY.comments.empty}</p>
          ) : (
            comments.map((c) => (
              <DrawerCard key={c.id}>
                <p className="text-cell font-medium">{c.author_name}</p>
                <p className="text-cell">{c.text}</p>
                <p className="text-meta text-ink-3">{time(c.created_at, { tz })}</p>
              </DrawerCard>
            ))
          )}
        </div>
      )}
      {tab === "activity" && (
        <ul aria-label={COPY.tabs.activity} className="flex flex-col p-[10px]">
          {detail.activity.length === 0 && (
            <li className="p-[12px] text-cell text-ink-3">{COPY.activity.empty}</li>
          )}
          {detail.activity.map((e) => {
            const who = e.actor_user_id == null ? undefined : staff.get(e.actor_user_id);
            const words =
              e.event_type === "request_item.drafted" && e.actor_kind === "agent"
                ? COPY.activity.drafted
                : e.event_type === "request_item.sent" && who !== undefined
                  ? COPY.activity.sent(who)
                  : null;
            if (words === null) return null;
            return (
              <li key={e.id} className="flex items-center gap-[8px] px-[12px] py-[8px] hairline-b">
                <Icon name="file-text" size={12} className="text-ink-3" />
                <span className="min-w-0 flex-1 text-cell">{words}</span>
                <span className="text-meta text-ink-3">{time(e.at, { tz })}</span>
              </li>
            );
          })}
        </ul>
      )}
    </Drawer>
  );
}
