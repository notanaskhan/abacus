import type { InboundMessageOut, InboxThreadRow } from "@abacus/api-client";
import {
  inboxSummaryOptions,
  getThreadOptions,
  listThreadsOptions,
} from "@abacus/api-client/query";
import {
  Button,
  DEFAULT_TZ,
  EmptyState,
  InboxList,
  type InboxMessage,
  type InboxState,
  InboxLayout,
  MessageView,
  ReadingHeader,
  SearchField,
  Skeleton,
  type ToolbarProps,
  date,
  time,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import { COPY } from "./copy";

// INB-01 · Inbox (N-01-T10; docs/screens/INB-01.md; DEC-830). T8 over C5's intake reads: the rail
// lists `GET /v1/inbox/threads` (polled every 10 s while visible, DEC-23), the header counts the
// summary ("23 waiting · 4 unmatched"), and the reading pane opens `GET /v1/inbox/threads/{id}`:
// each message in the inbox kit's MessageView, newest first, older ones recessed. Client words are
// plain text. Filing and matching are INB-02's and N-01-T18's (the header's File… opens them).

const STATE: Readonly<Record<InboxThreadRow["status"], InboxState>> = {
  new: "new",
  waiting: "wait",
  filed: "filed",
  ignored: "ignored",
  held: "wait",
  withdrawn: "ignored",
};

function rowOf(r: InboxThreadRow, now: Date, tz: string): InboxMessage {
  return {
    id: r.id,
    subject: r.subject_display,
    from: r.client_name === null ? r.sender_display : `${r.sender_display} · ${r.client_name}`,
    time: date(r.last_received_at, { now, tz }),
    state: STATE[r.status],
    preview: "",
  };
}

function Message({
  m,
  recessed,
  now,
  tz,
}: {
  m: InboundMessageOut;
  recessed: boolean;
  now: Date;
  tz: string;
}): JSX.Element {
  return (
    <MessageView
      subject={m.subject_display}
      date={`${date(m.received_at, { now, tz, withYear: true })}, ${time(m.received_at, { tz })}`}
      address={`From ${m.sender_display}`}
      body={m.body ?? ""}
      recessed={recessed}
      attachments={m.attachments.map((a) => ({
        name: a.file_name,
        meta: "PDF",
        src: "",
        state: STATE[a.status],
      }))}
    />
  );
}

export interface INB01Props {
  /** The gallery frame's toolbar; routed inside the firm shell (N-01-T23) there is none. */
  toolbar?: ToolbarProps;
  /** "File…" on a thread: INB-02 over it (`?ov=file&message=<id>`), its newest message. */
  onFile?: (messageId: string) => void;
  /** "Log received documents…" (DV-1): the sheet at `?ov=log-intake`. */
  onLogIntake?: () => void;
  /** The selected thread, kept in the route's `?thread=` when routed. */
  onSelect?: (threadId: string) => void;
  initialThread?: string | null;
  /** The Client filter (f: Ridgeline, which has no thread in the past 30 days). */
  initialClientId?: string | null;
  frame?: boolean;
}

export function INB01({
  toolbar,
  initialThread = null,
  initialClientId = null,
  frame = false,
  onFile,
  onLogIntake,
  onSelect,
}: INB01Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const [selected, setSelected] = useState<string | null>(initialThread);
  const [q, setQ] = useState("");
  const summary = useQuery(inboxSummaryOptions());
  const list = useQuery({
    ...listThreadsOptions({
      query: {
        ...(q === "" ? {} : { q }),
        ...(initialClientId === null ? {} : { client_id: initialClientId }),
        limit: 100,
      },
    }),
    refetchInterval: 10_000,
  });
  const detail = useQuery({
    ...getThreadOptions({ path: { thread_id: selected ?? "" } }),
    enabled: selected !== null,
  });

  const rows = list.data?.items ?? [];
  const rail = list.isPending ? (
    <div aria-busy="true" className="flex flex-col gap-[8px] p-[8px]">
      {Array.from({ length: 8 }, (_, i) => (
        <Skeleton key={i} className="h-[56px] w-full" />
      ))}
    </div>
  ) : (
    <InboxList
      messages={rows.map((r) => rowOf(r, now, tz))}
      selected={selected}
      onSelect={(m) => {
        setSelected(m.id);
        onSelect?.(m.id);
      }}
      empty={<EmptyState title={COPY.empty.title}>{COPY.empty.body}</EmptyState>}
    />
  );
  const open = detail.data;
  // INB-02 triages one message: the newest one holding a file still to decide.
  const newest = open?.messages.find((m) =>
    m.attachments.some((a) => a.status === "new" || a.status === "waiting" || a.status === "held"),
  );
  return (
    <div data-screen="INB-01" className="flex min-h-0 flex-1 flex-col">
      <InboxLayout
        {...(toolbar === undefined ? {} : { toolbar })}
        frame={frame}
        {...(frame ? { height: 860 } : {})}
        filters={
          <>
            <span className="text-body text-ink-2">
              {summary.data === undefined
                ? null
                : COPY.summary(summary.data.waiting, summary.data.unmatched)}
            </span>
            {onLogIntake !== undefined && (
              <Button variant="secondary" size="sm" className="ml-auto" onClick={onLogIntake}>
                {COPY.logIntake}
              </Button>
            )}
          </>
        }
        rail={{
          title: COPY.mailbox,
          search: (
            <SearchField
              label={COPY.search}
              placeholder="Search"
              value={q}
              onChange={setQ}
              className="flex-1"
            />
          ),
          body: rail,
        }}
        reading={{
          ...(open === undefined
            ? {}
            : {
                header: (
                  <ReadingHeader
                    client={open.thread.client_name}
                    clients={[]}
                    subject={open.thread.subject_display}
                    state={STATE[open.thread.status]}
                    {...(onFile === undefined || newest === undefined
                      ? {}
                      : {
                          fileTo: [COPY.fileAttachments],
                          onFile: () => {
                            onFile(newest.id);
                          },
                        })}
                    {...(open.work_item_label === null ? {} : { context: open.work_item_label })}
                  />
                ),
              }),
          body:
            open === undefined ? null : (
              <div data-reading="message" className="flex flex-col">
                {open.messages.map((m, i) => (
                  <Message key={m.id} m={m} recessed={i > 0} now={now} tz={tz} />
                ))}
              </div>
            ),
        }}
      />
    </div>
  );
}
