import type {
  IntakeCategoryOut,
  IntakeQuestionnaireOut,
  IntakeRequestOut,
  IntakeWaitingFileOut,
  K1DependencyOut,
  LiveItemOut,
  TaxReturnIntakeOut,
  TriageDecisionIn,
} from "@abacus/api-client";
import {
  acceptMutation,
  attachOrganizerMutation,
  binderLiveOptions,
  createQuestionnaireMutation,
  draftQuestionMutation,
  questionnaireListTemplatesOptions,
  questionnaireOptions,
  resolveDuplicateMutation,
  returnIntakeOptions,
  returnRecordOptions,
  sendQuestionMutation,
  triageApplyMutation,
  unpublishBinderMutation,
} from "@abacus/api-client/query";
import {
  AgentText,
  Button,
  ConfirmDialog,
  Dialog,
  Drawer,
  EmptyState,
  GroupBand,
  Icon,
  type IconName,
  Menu,
  OverviewCard,
  Picker,
  Pill,
  ProgressBar,
  RecordCockpit,
  RecordHeader,
  SearchField,
  Skeleton,
  StatusDisc,
  Tabsbar,
  type ToolbarProps,
  Tooltip,
  type ViewState,
  date as formatDate,
  time as formatTime,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useMemo, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { useOpenOverlay } from "../../app-core/open";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { hrefOf, ov, to } from "../../routes/to";
import { ViewerPane } from "../SHL-08";
import { FORM_LABEL, type Tax02Tab, stateOf } from "../TAX-02";
import { COPY } from "./copy";

// TAX-03 · Return › Intake (T-02-T19; docs/screens/TAX-03.md) on T2 RecordCockpit with the dock,
// over `GET /v1/tax-returns/{id}/intake` (T-02-T18, DEC-1470) and BND-02's live poll. Every
// artboard is a data condition:
//
//   a  Waiting on client: 5 of 7, two 1095-C forms in the dock (one for 2024)
//   a2 a received request open in the dock (SHL-08) with Approve Document
//   b  Filed: the 1095-C filed, the 2024 copy ignored · c Complete: marked done by the client
//   d  K-1 released: the final replaces the draft · e Duplicate upload under the W-2
//   f  Empty binder (Meera Shah)
//
// Every filing, ignore and discard is a person's click on its owner's route, which writes the
// audit row: File to request, Not this… and Ignore are N-01's triage apply on the file's message;
// Approve Document is C5's `evidence.accept` on the row's version; Keep newer / Discard duplicate is
// T-02-T17's resolution. The agent only proposes (the suggestion line, through AgentText); nothing
// here files on its own. The dock shows suggestions only when the read says `shown` (DV-7).

const CATEGORY_ICON: Readonly<Record<string, IconName>> = {
  "Personal & Household Information": "circle-user-round",
  "Income Sources": "banknote",
  "Home & Property": "house",
  "Health & Medical": "heart",
  "Charitable & Donations": "hand-heart",
  "Other Activity": "ellipsis",
};
const CARD = "rounded-pane bg-card shadow-e1";
const OPEN = new Set(["requested", "returned"]);
const DONE = new Set(["received", "accepted"]);
type IgnoreReason = keyof typeof COPY.reasons;

function day(iso: string | null | undefined, now: Date): string | null {
  return iso == null ? null : formatDate(iso, { now });
}

function k1For(
  row: IntakeRequestOut,
  handoffs: readonly K1DependencyOut[],
): K1DependencyOut | null {
  return handoffs.find((h) => row.title.includes(h.issuer_name)) ?? null;
}

// ---- Rail -------------------------------------------------------------------------------------

function Rail({
  intake,
  now,
  category,
  onCategory,
  onQuestion,
  onAddOrganizer,
  onAsk,
  onUnpublish,
}: {
  intake: TaxReturnIntakeOut | undefined;
  now: Date;
  category: string | null;
  onCategory: (key: string | null) => void;
  onQuestion: (q: IntakeQuestionnaireOut) => void;
  onAddOrganizer: () => void;
  onAsk: () => void;
  onUnpublish: () => void;
}): JSX.Element {
  const [catsOpen, setCatsOpen] = useState(true);
  const [qsOpen, setQsOpen] = useState(true);
  const header = (
    <div className="flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
      <h2 className="text-pane font-medium tracking-[-0.012em]">{COPY.rail}</h2>
    </div>
  );
  if (intake === undefined) {
    return (
      <section aria-label={COPY.rail} className="pane flex min-h-0 flex-1 flex-col">
        {header}
        <div className="flex flex-col gap-[10px] p-[12px]">
          <Skeleton className="h-[150px]" />
          <Skeleton className="h-[12px] w-[70%]" />
        </div>
      </section>
    );
  }
  const binder = intake.binder ?? null;
  const total = intake.requests_total ?? 0;
  const done = intake.requests_received ?? 0;
  const allowed = new Set(intake.allowed_actions ?? []);
  const complete = binder?.status === "complete";
  const last = binder?.last_upload_at == null ? null : formatTime(binder.last_upload_at);
  return (
    <section aria-label={COPY.rail} className="pane flex min-h-0 flex-1 flex-col">
      {header}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        {binder !== null && (
          <>
            <div className="p-[12px] pb-0">
              <OverviewCard
                icon="folder-open"
                title={binder.name}
                sub={
                  binder.published_at === null
                    ? COPY.binderDraft
                    : COPY.binderSub(day(binder.published_at, now) ?? "", binder.published_by_name)
                }
                state={complete ? COPY.binderComplete : COPY.binderPublished}
              />
            </div>
            <div className="flex flex-col gap-[6px] px-[16px] py-[12px] hairline-b">
              <p className="text-body font-medium">{COPY.satisfied(done, total)}</p>
              <ProgressBar done={done} total={total} left="" />
              <p className="text-meta text-ink-3">{COPY.openLine(total - done, last)}</p>
            </div>
          </>
        )}
        {intake.categories.length > 0 && (
          <>
            <GroupBand
              title={COPY.categories}
              open={catsOpen}
              controls="tax03-categories"
              onToggle={() => {
                setCatsOpen((o) => !o);
              }}
            />
            {catsOpen && (
              <ul id="tax03-categories" aria-label={COPY.categoriesList}>
                {intake.categories.map((c) => (
                  <CategoryRow
                    key={c.key}
                    category={c}
                    selected={category === c.key}
                    onSelect={() => {
                      onCategory(category === c.key ? null : c.key);
                    }}
                  />
                ))}
              </ul>
            )}
          </>
        )}
        {binder !== null && (
          <>
            <GroupBand
              title={COPY.questions}
              open={qsOpen}
              controls="tax03-questions"
              onToggle={() => {
                setQsOpen((o) => !o);
              }}
            />
            {qsOpen && (
              <ul id="tax03-questions" aria-label={COPY.questions}>
                {(intake.questionnaires ?? []).map((q) => (
                  <li key={q.id}>
                    <Tooltip content={COPY.questionsReadOnly}>
                      <button
                        type="button"
                        onClick={() => {
                          onQuestion(q);
                        }}
                        className="flex min-h-[44px] w-full items-center gap-[10px] px-[16px] py-[6px] text-left hairline-b hover:bg-nav-hover"
                      >
                        <StatusDisc state={q.submitted_at === null ? "todo" : "done"} />
                        <span className="flex min-w-0 flex-1 flex-col">
                          <span className="truncate text-body">{q.title}</span>
                          <span className="truncate text-meta text-ink-3">
                            {q.submitted_at === null
                              ? q.answered > 0
                                ? COPY.answeredOf(q.answered, q.total)
                                : COPY.notAnswered
                              : COPY.answered(day(q.submitted_at, now) ?? "", q.submitted_by_name)}
                          </span>
                        </span>
                        <Icon name="chevron-right" size={14} className="text-ink-3" />
                      </button>
                    </Tooltip>
                  </li>
                ))}
                <li className="flex gap-[8px] px-[16px] py-[8px]">
                  {allowed.has("request_item.create") && (
                    <Button
                      variant="ghost"
                      size="xs"
                      icon="plus"
                      opensDialog
                      onClick={onAddOrganizer}
                    >
                      {COPY.addOrganizer}
                    </Button>
                  )}
                  {allowed.has("questionnaire.ask") && (
                    <Button
                      variant="ghost"
                      size="xs"
                      icon="message-square-plus"
                      opensDialog
                      onClick={onAsk}
                    >
                      {COPY.askClient}
                    </Button>
                  )}
                </li>
              </ul>
            )}
          </>
        )}
      </div>
      {binder !== null && binder.published_at !== null && allowed.has("request_item.create") && (
        <div className="flex flex-none justify-center py-[10px] hairline-t">
          <Button variant="ghost" size="sm" opensDialog={false} onClick={onUnpublish}>
            {COPY.unpublish}
          </Button>
        </div>
      )}
    </section>
  );
}

function CategoryRow({
  category,
  selected,
  onSelect,
}: {
  category: IntakeCategoryOut;
  selected: boolean;
  onSelect: () => void;
}): JSX.Element {
  const label = category.label ?? category.key;
  const open = category.requested - category.received;
  return (
    <li>
      <button
        type="button"
        aria-pressed={selected}
        onClick={onSelect}
        className={`flex h-[39px] w-full items-center gap-[10px] px-[16px] text-left hairline-b hover:bg-nav-hover ${selected ? "bg-sel-bg font-medium" : ""}`}
      >
        <Icon name={CATEGORY_ICON[label] ?? "file"} size={15} className="text-ink-3" />
        <span className="min-w-0 flex-1 truncate text-nav">{label}</span>
        {open > 0 ? (
          <span className="text-meta text-ink-3">{COPY.open(open)}</span>
        ) : (
          <StatusDisc state="done" />
        )}
      </button>
    </li>
  );
}

// ---- Canvas -----------------------------------------------------------------------------------

function Banner({ intake, now }: { intake: TaxReturnIntakeOut; now: Date }): JSX.Element | null {
  const binder = intake.binder ?? null;
  if (binder?.marked_done_at != null && binder.marked_done_by_name != null) {
    const when = `${formatDate(binder.marked_done_at, { now })}, ${formatTime(binder.marked_done_at)}`;
    return (
      <p
        role="status"
        className="mx-[12px] mt-[10px] flex min-h-[36px] items-center gap-[8px] rounded-nested bg-green-tint px-[12px] text-dense font-medium text-green-ink"
      >
        <Icon name="circle-check" size={14} />
        {COPY.markedDone(binder.marked_done_by_name, when)}
      </p>
    );
  }
  const draft = intake.k1_handoffs.find((h) => h.blocking && h.status === "awaiting");
  if (draft === undefined) return null;
  const label = draft.source_label ?? draft.issuer_name;
  const short = draft.short_name ?? draft.issuer_name;
  return (
    <div
      role="status"
      className="mx-[12px] mt-[10px] flex min-h-[36px] items-center gap-[10px] rounded-nested bg-amber-tint px-[12px] py-[6px] text-dense font-medium text-amber-ink"
    >
      <Icon name="triangle-alert" size={14} className="flex-none" />
      <span className="flex-1">{COPY.banner(label, short)}</span>
      {draft.source_return_id !== null && (
        // TXP-01 is planned: the link names it and waits for its build.
        <Tooltip content={COPY.bannerLinkHint}>
          <span className="flex flex-none items-center gap-[4px] text-ink-3">
            {COPY.bannerLink(label)}
            <Icon name="arrow-right" size={12} />
          </span>
        </Tooltip>
      )}
    </div>
  );
}

function RowStatus({
  row,
  k1,
  live,
  now,
}: {
  row: IntakeRequestOut;
  k1: K1DependencyOut | null;
  live: LiveItemOut | undefined;
  now: Date;
}): JSX.Element {
  if (k1 !== null && k1.status === "awaiting") {
    return (
      <span className="flex flex-col items-end gap-[4px]">
        <Pill variant="amber" size="sm">
          {COPY.draftK1}
        </Pill>
        <span className="text-meta text-amber-ink">
          {COPY.draftK1Sub(k1.short_name ?? k1.issuer_name)}
        </span>
      </span>
    );
  }
  if (k1 !== null) {
    return (
      <Pill variant="green-tint" size="sm">
        {COPY.released(day(row.uploaded_on, now) ?? "")}
      </Pill>
    );
  }
  if (DONE.has(row.status)) {
    return (
      <span className="flex items-center gap-[6px]">
        {row.linked_count != null && row.linked_count > 0 && (
          <span
            className="rounded-pill bg-nested px-[6px] text-micro text-ink"
            aria-label={COPY.approvedCountLabel(row.linked_count)}
          >
            {COPY.approvedCount(row.linked_count)}
          </span>
        )}
        <Pill variant="green" size="sm" check>
          {COPY.received}
        </Pill>
      </span>
    );
  }
  const waiting = live?.inbox_waiting ?? 0;
  const uploading = live?.uploading_files ?? 0;
  return (
    <span className="flex flex-col items-end gap-[4px]">
      <span className="flex items-center gap-[6px] text-dense text-ink-3">
        <StatusDisc state="todo" />
        {COPY.requested}
      </span>
      {uploading > 0 ? (
        <span className="flex items-center gap-[6px] text-dense text-amber-ink">
          <StatusDisc state="run" size={13} />
          {COPY.uploading(uploading)}
        </span>
      ) : waiting > 0 ? (
        <span className="flex items-center gap-[6px] text-dense text-amber-ink">
          <span aria-hidden="true" className="size-[8px] rounded-full bg-amber" />
          {COPY.waiting(waiting)}
        </span>
      ) : null}
    </span>
  );
}

function rowSub(
  row: IntakeRequestOut,
  k1: K1DependencyOut | null,
  live: LiveItemOut | undefined,
  now: Date,
): string {
  if (k1 !== null) {
    const parts = [COPY.handedOff(k1.source_label ?? k1.issuer_name)];
    if (row.linked_count != null && row.linked_count > 1)
      parts.push(`${String(row.linked_count)} files`);
    return parts.join(" · ");
  }
  if (row.file_name !== null) {
    const channel = row.channel === null ? "" : (COPY.channel[row.channel] ?? row.channel);
    const when = day(row.uploaded_on, now);
    return [row.file_name, [channel, when].filter((s) => s !== "" && s !== null).join(" ")]
      .filter((s) => s !== "")
      .join(" · ");
  }
  const parts: string[] = [];
  const asked = day(row.requested_at, now);
  if (asked !== null) parts.push(COPY.requestedOn(asked));
  if ((live?.inbox_waiting ?? 0) > 0) parts.push(COPY.waitingInInbox(live?.inbox_waiting ?? 0));
  return parts.join(" · ");
}

function RequestList({
  intake,
  live,
  now,
  category,
  query,
  openFirst,
  selected,
  onOpen,
  onResolve,
  resolving,
}: {
  intake: TaxReturnIntakeOut;
  live: ReadonlyMap<string, LiveItemOut>;
  now: Date;
  category: string | null;
  query: string;
  openFirst: boolean;
  selected: string | null;
  onOpen: (row: IntakeRequestOut) => void;
  onResolve: (row: IntakeRequestOut, decision: "keep_newer" | "discard_duplicate") => void;
  resolving: boolean;
}): JSX.Element {
  const rows = intake.requests ?? [];
  const q = query.trim().toLowerCase();
  const shown = rows.filter(
    (r) =>
      (category === null || r.category === category) &&
      (q === "" ||
        r.title.toLowerCase().includes(q) ||
        (r.file_name ?? "").toLowerCase().includes(q)),
  );
  const bands = intake.categories
    .map((c) => {
      // Bands keep the binder's category order; "Open first" lifts open requests within each.
      const mine = shown
        .filter((r) => r.category === c.key)
        .sort((a, b) =>
          openFirst ? Number(!OPEN.has(a.status)) - Number(!OPEN.has(b.status)) : 0,
        );
      return { c, rows: mine };
    })
    .filter((b) => b.rows.length > 0);
  if (bands.length === 0) {
    return <EmptyState title={COPY.noMatches} icon="search" />;
  }
  return (
    <div className="flex flex-col">
      {bands.map(({ c, rows: mine }) => (
        <section key={c.key} aria-label={c.label ?? c.key}>
          <h3 className="flex h-[31px] items-center justify-between bg-band-hd px-[14px] text-nav font-medium hairline-b">
            <span>{c.label ?? c.key}</span>
            <span className="text-meta font-normal text-ink-3">
              {COPY.bandCount(c.received, c.requested)}
            </span>
          </h3>
          <ul>
            {mine.map((row) => {
              const k1 = k1For(row, intake.k1_handoffs);
              const facts = live.get(row.id);
              const openable = row.latest_version_id !== null;
              return (
                <li key={row.id} data-request={row.title} className="hairline-b">
                  <button
                    type="button"
                    disabled={!openable}
                    aria-current={selected === row.id ? "true" : undefined}
                    onClick={() => {
                      onOpen(row);
                    }}
                    className={`flex min-h-[56px] w-full items-center gap-[12px] px-[14px] py-[8px] text-left ${openable ? "hover:bg-nav-hover" : "cursor-default"} ${selected === row.id ? "bg-sel-bg" : ""}`}
                  >
                    <Icon name="file" size={15} className="flex-none text-ink-3" />
                    <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
                      <span className="truncate text-nav">{row.title}</span>
                      <span className="truncate text-cell text-ink-3">
                        {rowSub(row, k1, facts, now)}
                      </span>
                    </span>
                    <RowStatus row={row} k1={k1} live={facts} now={now} />
                  </button>
                  {row.duplicate != null && (
                    <div className="flex items-center gap-[10px] py-[8px] pl-[41px] pr-[14px]">
                      <Icon name="copy" size={14} className="text-ink-3" />
                      <span className="min-w-0 flex-1 truncate text-cell">
                        {row.duplicate.file_name}
                      </span>
                      <Pill variant="red-tint" size="micro">
                        {COPY.duplicate}
                      </Pill>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={resolving}
                        onClick={() => {
                          onResolve(row, "keep_newer");
                        }}
                      >
                        {COPY.keepNewer}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={resolving}
                        onClick={() => {
                          onResolve(row, "discard_duplicate");
                        }}
                      >
                        {COPY.discardDuplicate}
                      </Button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

// ---- Dock -------------------------------------------------------------------------------------

function sizeOf(bytes: number): string {
  return `${String(Math.round(bytes / 1024))} KB PDF`;
}

function WaitingCard({
  file,
  intake,
  busy,
  onFile,
  onIgnore,
}: {
  file: IntakeWaitingFileOut;
  intake: TaxReturnIntakeOut;
  busy: boolean;
  onFile: (file: IntakeWaitingFileOut, requestId: string) => void;
  onIgnore: (file: IntakeWaitingFileOut, reason: IgnoreReason) => void;
}): JSX.Element {
  const allowed = new Set(intake.allowed_actions ?? []);
  const open = (intake.requests ?? []).filter((r) => OPEN.has(r.status));
  const year = intake.tax_year ?? null;
  const suggestion = intake.suggestions === "shown" ? file.suggestion : null;
  const others = open.filter((r) => r.id !== suggestion?.request_id);
  const reasonMenu = (Object.keys(COPY.reasons) as IgnoreReason[]).map((reason) => ({
    label: COPY.reasons[reason],
    onSelect: () => {
      onIgnore(file, reason);
    },
  }));
  return (
    <li data-waiting={file.file_name} className="flex flex-col gap-[8px]">
      <div className="flex items-start gap-[10px]">
        <span
          aria-hidden="true"
          className="relative flex h-[150px] w-[126px] flex-none items-center justify-center rounded-[6px] bg-nested"
        >
          <Icon name="file-text" size={22} className="text-ink-3" />
          <span className="absolute -right-[4px] -top-[4px] size-[10px] rounded-full bg-amber ring-2 ring-card" />
        </span>
        <span className="flex min-w-0 flex-col gap-[4px]">
          <span className="text-dense font-medium [overflow-wrap:anywhere]">{file.file_name}</span>
          <span className="text-meta text-ink-3">{sizeOf(file.size_bytes)}</span>
          {file.wrong_year && file.tax_year !== null && year !== null && (
            <Pill variant="red-tint" size="micro">
              {COPY.wrongYear(file.tax_year, year)}
            </Pill>
          )}
        </span>
      </div>
      <div className={`${CARD} flex flex-col gap-[8px] p-[10px] text-dense`}>
        {file.wrong_year ? (
          <>
            <p>{COPY.wrongYearSuggest}</p>
            {allowed.has("inbox.triage") && (
              <span>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={() => {
                    onIgnore(file, "wrong_tax_year");
                  }}
                >
                  {COPY.ignoreWrongYear}
                </Button>
              </span>
            )}
          </>
        ) : (
          <>
            {suggestion != null && (
              <p className="flex items-start gap-[6px]">
                <Icon name="sparkles" size={13} className="mt-[2px] flex-none text-ink-3" />
                <AgentText
                  inline
                  className="text-dense text-ink"
                  text={COPY.suggests(suggestion.label, suggestion.confidence)}
                />
              </p>
            )}
            {suggestion == null &&
              intake.suggestions !== "shown" &&
              intake.suggestions !== "hidden" && (
                <p className="text-meta text-ink-3">
                  {COPY.suggestionsOff[intake.suggestions ?? "agents_off"]}
                </p>
              )}
            <span className="flex flex-wrap gap-[6px]">
              {suggestion != null && allowed.has("inbox.file") && (
                <Button
                  variant="primary"
                  size="sm"
                  disabled={busy}
                  onClick={() => {
                    onFile(file, suggestion.request_id);
                  }}
                >
                  {COPY.fileTo}
                </Button>
              )}
              {allowed.has("inbox.file") && others.length > 0 && (
                <Menu
                  label={COPY.notThisLabel}
                  trigger={
                    <Button variant="ghost" size="sm" disabled={busy}>
                      {COPY.notThis}
                    </Button>
                  }
                  sections={[
                    others.map((r) => ({
                      label: r.title,
                      onSelect: () => {
                        onFile(file, r.id);
                      },
                    })),
                  ]}
                />
              )}
              {allowed.has("inbox.triage") && (
                <Menu
                  label={COPY.ignoreLabel}
                  trigger={
                    <Button variant="ghost" size="sm" disabled={busy}>
                      {COPY.ignore}
                    </Button>
                  }
                  sections={[reasonMenu]}
                />
              )}
            </span>
          </>
        )}
      </div>
    </li>
  );
}

function WaitingDock({
  intake,
  busy,
  ignored,
  onFile,
  onIgnore,
}: {
  intake: TaxReturnIntakeOut;
  busy: boolean;
  ignored: readonly { name: string; reason: IgnoreReason }[];
  onFile: (file: IntakeWaitingFileOut, requestId: string) => void;
  onIgnore: (file: IntakeWaitingFileOut, reason: IgnoreReason) => void;
}): JSX.Element {
  const files = intake.waiting ?? [];
  const first = files[0];
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      {files.length === 0 ? (
        <EmptyState title={COPY.dockEmpty} />
      ) : (
        <div className="flex flex-col gap-[12px] p-[12px]">
          <ul className="flex flex-col gap-[16px]">
            {files.map((f) => (
              <WaitingCard
                key={f.attachment_id}
                file={f}
                intake={intake}
                busy={busy}
                onFile={onFile}
                onIgnore={onIgnore}
              />
            ))}
          </ul>
          {first !== undefined && (
            <p className="text-meta text-ink-3">
              {COPY.from(first.sender, first.subject, formatTime(first.received_at))}{" "}
              <a
                href={hrefOf(to.INB01(), { thread: first.thread_id })}
                className="font-medium text-ink hover:underline"
              >
                {COPY.openInbox}
                <span className="text-ink-3"> →</span>
              </a>
            </p>
          )}
        </div>
      )}
      {ignored.length > 0 && (
        <ul className="flex flex-col gap-[6px] px-[12px] pb-[12px]">
          {ignored.map((i) => (
            <li key={i.name} className="flex items-center gap-[6px] text-meta text-ink-3">
              <Icon name="x" size={12} />
              <span className="line-through">{i.name}</span>
              <span>{COPY.ignoredAs(COPY.reasons[i.reason])}</span>
            </li>
          ))}
        </ul>
      )}
      <h3 className="flex h-[31px] flex-none items-center bg-band-hd px-[14px] text-nav font-medium hairline-y">
        {COPY.unmatched}
      </h3>
      <p className="px-[14px] py-[10px] text-dense text-ink-3">{COPY.nothingUnmatched}</p>
    </div>
  );
}

// ---- Overlays ---------------------------------------------------------------------------------

function QuestionsDrawer({
  questionnaire,
  onClose,
}: {
  questionnaire: IntakeQuestionnaireOut;
  onClose: () => void;
}): JSX.Element {
  const read = useQuery(questionnaireOptions({ path: { questionnaire_id: questionnaire.id } }));
  return (
    <Drawer
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.questionsDrawer(questionnaire.title)}
      description={COPY.questionsReadOnly}
    >
      {read.data === undefined ? (
        <div className="flex flex-col gap-[8px] p-[16px]">
          <Skeleton className="h-[12px] w-[70%]" />
          <Skeleton className="h-[12px] w-[60%]" />
        </div>
      ) : (
        <dl className="flex flex-col">
          {read.data.questions.map((q) => (
            <div key={q.id} className="flex flex-col gap-[2px] px-[16px] py-[10px] hairline-b">
              {/* Client wording and answers are client content: rendered as text only. */}
              <dt className="text-dense text-ink-2">{q.client_wording}</dt>
              <dd className="text-body">
                {q.answer === null
                  ? COPY.noAnswer
                  : typeof q.answer === "string"
                    ? q.answer
                    : JSON.stringify(q.answer)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </Drawer>
  );
}

function OrganizerDialog({
  binderId,
  onClose,
}: {
  binderId: string;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const templates = useQuery(questionnaireListTemplatesOptions());
  const attach = useMutation(attachOrganizerMutation());
  const options = (templates.data ?? []).filter((t) => t.current_version_id != null);
  const [pick, setPick] = useState<string | null>(null);
  const chosen = options.find((t) => t.id === pick);
  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.organizerTitle}
      action={
        <Button
          variant="primary"
          disabled={chosen?.current_version_id == null || attach.isPending}
          onClick={() => {
            if (chosen?.current_version_id == null) return;
            attach.mutate(
              {
                path: { request_list_id: binderId },
                body: { template_version_id: chosen.current_version_id },
              },
              {
                onSuccess: () => {
                  toast.show({ kind: "success", text: COPY.organizerAttached(chosen.name) });
                  void queryClient.invalidateQueries();
                  onClose();
                },
                onError: () => {
                  toast.show({ kind: "error", text: COPY.actionFailed });
                },
              },
            );
          }}
        >
          {COPY.organizerAttach}
        </Button>
      }
    >
      {options.length === 0 ? (
        <p className="text-para text-ink-2">{COPY.organizerNone}</p>
      ) : (
        <Picker
          label={COPY.organizerPick}
          options={options.map((t) => ({ value: t.id, label: t.name }))}
          {...(pick === null ? {} : { value: pick })}
          onChange={setPick}
        />
      )}
    </Dialog>
  );
}

function AskDialog({
  workItemId,
  onClose,
}: {
  workItemId: string;
  onClose: () => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const create = useMutation(createQuestionnaireMutation());
  const draft = useMutation(draftQuestionMutation());
  const send = useMutation(sendQuestionMutation());
  const [text, setText] = useState("");
  const busy = create.isPending || draft.isPending || send.isPending;
  const submit = async (): Promise<void> => {
    try {
      const made = await create.mutateAsync({
        body: { kind: "team_questions", title: COPY.askTeamTitle, work_item_id: workItemId },
      });
      const question = await draft.mutateAsync({
        path: { questionnaire_id: made.id },
        body: { client_wording: text.trim(), section: COPY.askSection, type: "long_text" },
      });
      await send.mutateAsync({ path: { question_id: question.id } });
      toast.show({ kind: "success", text: COPY.askSent });
      void queryClient.invalidateQueries();
      onClose();
    } catch {
      toast.show({ kind: "error", text: COPY.actionFailed });
    }
  };
  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.askTitle}
      action={
        <Button
          variant="primary"
          disabled={text.trim() === "" || busy}
          onClick={() => {
            void submit();
          }}
        >
          {COPY.askSend}
        </Button>
      }
    >
      <label className="flex flex-col gap-[6px] text-dense text-ink-2">
        {COPY.askQuestion}
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value);
          }}
          rows={4}
          className="rounded-nested bg-nested p-[10px] text-body text-ink"
        />
      </label>
    </Dialog>
  );
}

// ---- Screen -----------------------------------------------------------------------------------

export interface TAX03Props {
  returnId: string;
  /** The tabs: Overview opens TAX-02. */
  onTab?: (tab: Tax02Tab) => void;
  /** The request whose document opens in the dock (a2). */
  initialDocument?: string | null;
  toolbar?: ToolbarProps;
  frame?: boolean;
}

export function TAX03({
  returnId,
  onTab,
  initialDocument = null,
  toolbar,
  frame = false,
}: TAX03Props): JSX.Element {
  const now = useNow();
  const queryClient = useQueryClient();
  const openOverlay = useOpenOverlay();
  const checkpointsOn = useFlag("review.checkpoints") === true;
  const record = useQuery(returnRecordOptions({ path: { return_id: returnId } }));
  const intakeQuery = useQuery(returnIntakeOptions({ path: { return_id: returnId } }));
  const intake = intakeQuery.data;
  const binderId = intake?.binder_id ?? null;
  // The uploading row and the waiting counts move live while POR-03 finishes (BND-02's 5-s poll).
  const live = useQuery({
    ...binderLiveOptions({ path: { binder_id: binderId ?? "" } }),
    enabled: binderId !== null,
    refetchInterval: 5000,
  });
  const liveBy = useMemo(
    () => new Map((live.data?.items ?? []).map((i) => [i.request_item_id, i])),
    [live.data],
  );

  const [category, setCategory] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [openFirst, setOpenFirst] = useState(true);
  const [docRow, setDocRow] = useState<string | null>(initialDocument);
  const [question, setQuestion] = useState<IntakeQuestionnaireOut | null>(null);
  const [dialog, setDialog] = useState<"organizer" | "ask" | "unpublish" | null>(null);
  const [ignored, setIgnored] = useState<{ name: string; reason: IgnoreReason }[]>([]);

  const triage = useMutation(triageApplyMutation());
  const accept = useMutation(acceptMutation());
  const resolve = useMutation(resolveDuplicateMutation());
  const unpublish = useMutation(unpublishBinderMutation());
  const refresh = (): void => {
    void queryClient.invalidateQueries();
  };
  const failed = (): void => {
    toast.show({ kind: "error", text: COPY.actionFailed });
  };

  const data = record.data;
  const engagementId = data?.engagement_id ?? null;
  const rows = intake?.requests ?? [];
  const open = rows.find((r) => r.id === docRow && r.latest_version_id !== null) ?? null;

  const apply = (file: IntakeWaitingFileOut, decision: TriageDecisionIn, done: string): void => {
    triage.mutate(
      {
        path: { message_id: file.message_id },
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: {
          decisions: [decision],
          ...(file.suggestion == null ? {} : { seen_proposals: [file.attachment_id] }),
        },
      },
      {
        onSuccess: () => {
          toast.show({ kind: "success", text: done });
          refresh();
        },
        onError: failed,
      },
    );
  };
  const fileTo = (file: IntakeWaitingFileOut, requestId: string): void => {
    const target = rows.find((r) => r.id === requestId);
    apply(
      file,
      {
        attachment_id: file.attachment_id,
        decision: "file",
        destination: { kind: "request", id: requestId },
      },
      COPY.filed(file.file_name, target?.title ?? ""),
    );
  };
  const ignore = (file: IntakeWaitingFileOut, reason: IgnoreReason): void => {
    setIgnored((prev) => [
      ...prev.filter((i) => i.name !== file.file_name),
      { name: file.file_name, reason },
    ]);
    apply(
      file,
      { attachment_id: file.attachment_id, decision: "ignore", reason_codes: [reason] },
      COPY.ignored(file.file_name),
    );
  };

  const state: ViewState = intakeQuery.isError
    ? { kind: "error", retry: () => void intakeQuery.refetch() }
    : intake === undefined || data === undefined
      ? { kind: "loading" }
      : { kind: "ready" };

  const subbar =
    data === undefined ? (
      <RecordHeader title="" checkpoints={false} sync={null} assistant={false} />
    ) : (
      (() => {
        const s = stateOf(data.row);
        return (
          <RecordHeader
            title={COPY.formTitle(data.row.tax_year, FORM_LABEL[data.row.form])}
            context={data.row.client_name}
            state={s.label}
            {...(s.tone === null ? {} : { stateTone: s.tone })}
            checkpoints={PLANNED_VISIBLE || checkpointsOn}
            onCheckpoints={() => {
              openOverlay(ov.SHL16("tax_return", returnId));
            }}
            sync={data.row.sync}
            onSync={() => {
              openOverlay(ov.TAX09(returnId));
            }}
            assistant={PLANNED_VISIBLE}
          />
        );
      })()
    );

  const counts = new Map((data?.tabs ?? []).map((t) => [t.tab, t.count]));
  const TAB_COPY = {
    overview: "Overview",
    intake: "Intake",
    review: "Review",
    issues: "Issues",
    activity: "Activity",
  } as const;
  const option = (key: Tax02Tab, live_: boolean) => {
    const n = counts.get(key);
    return {
      label: TAB_COPY[key],
      ...(n == null || n === 0 ? {} : { count: n }),
      ...(key === "issues" ? { bad: true } : {}),
      ...(live_ ? {} : { disabled: true }),
    };
  };
  const tabs = (
    <Tabsbar
      label="Return"
      options={[
        option("overview", true),
        option("intake", true),
        ...(PLANNED_VISIBLE
          ? (["review", "issues", "activity"] as const).map((k) => option(k, false))
          : []),
      ]}
      active={TAB_COPY.intake}
      onChange={(label) => {
        const key = (Object.keys(TAB_COPY) as Tax02Tab[]).find((k) => TAB_COPY[k] === label);
        if (key !== undefined && key !== "intake") onTab?.(key);
      }}
    />
  );

  const empty = intake !== undefined && intake.binder_id === null && rows.length === 0;
  const done = intake?.requests_received ?? 0;
  const total = intake?.requests_total ?? 0;
  const allowed = new Set(intake?.allowed_actions ?? []);

  const canvasBody =
    intake === undefined ? null : empty ? (
      <EmptyState
        title={COPY.noRequests}
        icon="folder-open"
        action={
          // BND-02 is planned: Generate binder names it and waits for its build.
          <Tooltip content={COPY.generateHint}>
            <span>
              <Button variant="primary" disabled>
                {COPY.generateBinder}
              </Button>
            </span>
          </Tooltip>
        }
      >
        {COPY.noRequestsBody}
      </EmptyState>
    ) : (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex h-[44px] flex-none items-center gap-[8px] px-[12px]">
          <SearchField
            label={COPY.search}
            placeholder={COPY.search}
            value={query}
            onChange={setQuery}
            className="flex-1"
          />
          <Picker
            label={COPY.sort}
            options={[
              { value: "open", label: COPY.sortOpenFirst },
              { value: "category", label: COPY.sortCategory },
            ]}
            value={openFirst ? "open" : "category"}
            onChange={(v) => {
              setOpenFirst(v === "open");
            }}
          />
        </div>
        <Banner intake={intake} now={now} />
        <div className="mt-[10px] min-h-0 flex-1 overflow-y-auto hairline-t">
          <RequestList
            intake={intake}
            live={liveBy}
            now={now}
            category={category}
            query={query}
            openFirst={openFirst}
            selected={open?.id ?? null}
            onOpen={(row) => {
              setDocRow(row.id);
            }}
            resolving={resolve.isPending}
            onResolve={(row, decision) => {
              const dup = row.duplicate;
              if (dup == null || engagementId === null) return;
              resolve.mutate(
                {
                  path: {
                    engagement_id: engagementId,
                    item_id: row.id,
                    version_id: dup.version_id,
                  },
                  body: { decision },
                },
                {
                  onSuccess: () => {
                    toast.show({
                      kind: "success",
                      text:
                        decision === "keep_newer"
                          ? COPY.duplicateKept(dup.file_name)
                          : COPY.duplicateDiscarded(dup.file_name),
                    });
                    refresh();
                  },
                  onError: failed,
                },
              );
            }}
          />
        </div>
      </div>
    );

  const footer =
    intake === undefined || empty ? undefined : (
      <p className="text-dense text-ink-3">
        {COPY.footer(total, done, total - done, day(intake.binder?.published_at, now))}
      </p>
    );

  const categoryLabel = (key: string): string =>
    intake?.categories.find((c) => c.key === key)?.label ?? key;

  const dock =
    intake === undefined || empty
      ? undefined
      : open !== null && open.latest_version_id !== null
        ? {
            view: "Viewer" as const,
            views: ["Viewer"] as const,
            title: open.file_name ?? open.title,
            action: (
              <Button
                variant="ghost"
                size="xs"
                icon="x"
                aria-label={COPY.closeViewer}
                onClick={() => {
                  setDocRow(null);
                }}
              />
            ),
            children: (
              <div className="flex min-h-0 flex-1 flex-col">
                <div className="min-h-0 flex-1 overflow-y-auto">
                  <ViewerPane target={{ versionId: open.latest_version_id, engagementId }} />
                  <p className="px-[16px] py-[10px] text-meta text-ink-3">
                    {COPY.matchedTo(categoryLabel(open.category), open.title)}
                  </p>
                </div>
                {allowed.has("evidence.accept") && engagementId !== null && (
                  <div className="flex-none p-[12px] hairline-t">
                    <Button
                      variant="primary"
                      size="footer"
                      icon="check"
                      className="w-full"
                      disabled={accept.isPending}
                      onClick={() => {
                        const version = open.latest_version_id;
                        if (version === null) return;
                        accept.mutate(
                          { path: { engagement_id: engagementId, version_id: version }, body: {} },
                          {
                            onSuccess: () => {
                              toast.show({
                                kind: "success",
                                text: COPY.approved(open.file_name ?? open.title),
                              });
                              refresh();
                            },
                            onError: failed,
                          },
                        );
                      }}
                    >
                      {COPY.approve}
                    </Button>
                  </div>
                )}
              </div>
            ),
          }
        : {
            view: "Notes" as const,
            views: ["Notes"] as const,
            title: COPY.dock((intake.waiting ?? []).length),
            children: (
              <WaitingDock
                intake={intake}
                busy={triage.isPending}
                ignored={ignored}
                onFile={fileTo}
                onIgnore={ignore}
              />
            ),
          };

  return (
    <div data-screen="TAX-03" className="flex min-h-0 flex-1 flex-col">
      <RecordCockpit
        {...(toolbar === undefined ? {} : { toolbar })}
        frame={frame}
        {...(frame ? { height: 860 } : {})}
        header={subbar}
        tabs={tabs}
        rail={
          <Rail
            intake={intake}
            now={now}
            category={category}
            onCategory={setCategory}
            onQuestion={setQuestion}
            onAddOrganizer={() => {
              setDialog("organizer");
            }}
            onAsk={() => {
              setDialog("ask");
            }}
            onUnpublish={() => {
              setDialog("unpublish");
            }}
          />
        }
        canvas={{
          title: COPY.canvas,
          state,
          ...(intake === undefined ||
          empty ||
          !allowed.has("request_item.create") ||
          binderId === null
            ? {}
            : {
                actions: (
                  <Tooltip content={COPY.requestMoreHint}>
                    <span>
                      <Button
                        variant="secondary"
                        size="sm"
                        icon="file-plus"
                        opensDialog
                        onClick={() => {
                          openOverlay(ov.SHL14("new", binderId));
                        }}
                      >
                        {COPY.requestMore}
                      </Button>
                    </span>
                  </Tooltip>
                ),
              }),
          ...(footer === undefined ? {} : { footer }),
          children: canvasBody,
        }}
        {...(dock === undefined ? {} : { dock })}
      />
      {question !== null && (
        <QuestionsDrawer
          questionnaire={question}
          onClose={() => {
            setQuestion(null);
          }}
        />
      )}
      {dialog === "organizer" && binderId !== null && (
        <OrganizerDialog
          binderId={binderId}
          onClose={() => {
            setDialog(null);
          }}
        />
      )}
      {dialog === "ask" && data !== undefined && (
        <AskDialog
          workItemId={data.work_item_id}
          onClose={() => {
            setDialog(null);
          }}
        />
      )}
      <ConfirmDialog
        open={dialog === "unpublish"}
        onOpenChange={(o) => {
          if (!o) setDialog(null);
        }}
        title={COPY.unpublishTitle}
        confirmLabel={COPY.unpublishConfirm}
        onConfirm={() => {
          if (binderId === null) return;
          unpublish.mutate(
            { path: { binder_id: binderId }, body: { reason: COPY.unpublishReason } },
            {
              onSuccess: () => {
                toast.show({ kind: "success", text: COPY.unpublished });
                refresh();
              },
              onError: failed,
            },
          );
        }}
      >
        {COPY.unpublishBody}
      </ConfirmDialog>
    </div>
  );
}

/** The screen with its own tab state: the gallery's artboard and the tests' host. */
export function ReturnIntakePage(props: Omit<TAX03Props, "onTab">): JSX.Element {
  return <TAX03 {...props} />;
}
