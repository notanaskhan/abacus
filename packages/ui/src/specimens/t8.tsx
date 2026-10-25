import { type JSX, useState } from "react";
import { IconButton } from "../components/button";
import { FilterChip, SearchField } from "../components/inputs";
import { EmptyLink, EmptyState } from "../components/states";
import { Toast } from "../components/toast";
import { Icon } from "../icons";
import {
  AgentFilingNote,
  type InboxState,
  InboxList,
  MessageView,
  ReadingHeader,
} from "../inbox/inbox-kit";
import { InboxLayout } from "../templates/inbox-layout";
import guards from "../../scope-guards.gen.json";
import { Artboard } from "./portal";
import { FIRM } from "./seed-figures";
import {
  CHANNEL_OPTIONS,
  NO_FILTERS,
  RECEIVED_OPTIONS,
  STATUS_OPTIONS,
  T8_CLIENTS,
  T8_MESSAGES,
  type T8Filters,
  type T8Message,
  thumbSrc,
  visibleMessages,
} from "./t8-data";

// T8 InboxLayout (F-05-T56; T8 handoff, Wave 0 Foundations #t8): the firm inbox on the C-15/C-18
// File kit, states T8a to T8e. Every board is live: pick messages, open the Copperleaf thread,
// change filters (a chip turns amber once set), match a sender, File… or Move… a message, ignore
// it, show ignored and filed rows, and Reply.

const TOOLBAR = {
  nav: guards.nav.map((label) => ({ label })),
  firm: FIRM,
  firmShort: "Brightwater",
  firmTitle: "Brightwater Hale LLP",
  active: "Inbox",
} as const;

interface Board {
  id: string;
  badge: string;
  name: string;
  note: string;
  selected: string | null;
  filters?: Partial<T8Filters>;
}

const BOARDS: readonly Board[] = [
  {
    id: "t8a",
    badge: "T8a",
    name: "Waiting",
    note: "Claire Feld’s corrected 1099 waits to be filed; the agent suggests where",
    selected: "brk",
  },
  {
    id: "t8b",
    badge: "T8b",
    name: "Filed",
    note: "The Harborline statement is filed, so its thumbnail carries the green check",
    selected: "harbor",
  },
  {
    id: "t8c",
    badge: "T8c",
    name: "Ignored",
    note: "Show ignored is on; the newsletter row reads in ink-3",
    selected: "news",
    filters: { showIgnored: true },
  },
  {
    id: "t8d",
    badge: "T8d",
    name: "Unmatched sender",
    note: "Paycrest isn’t a client, so the chip reads Match client…",
    selected: "pay",
  },
  {
    id: "t8e",
    badge: "T8e",
    name: "Empty filter",
    note: "Ridgeline with Waiting to be filed matches nothing",
    selected: null,
    filters: { client: T8_CLIENTS[3], status: "wait" },
  },
];

const all = (ms: readonly T8Message[]): readonly T8Message[] =>
  ms.flatMap((m) => [m, ...(m.replies ?? [])]);

function T8({ board }: { board: Board }): JSX.Element {
  const [filters, setFilters] = useState<T8Filters>({ ...NO_FILTERS, ...board.filters });
  const [sel, setSel] = useState<string | null>(board.selected);
  const [states, setStates] = useState<Readonly<Record<string, InboxState>>>({});
  const [dest, setDest] = useState<Readonly<Record<string, string>>>({});
  const [clients, setClients] = useState<Readonly<Record<string, string>>>({});
  const [open, setOpen] = useState<readonly string[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const set = (patch: Partial<T8Filters>): void => {
    setFilters((f) => ({ ...f, ...patch }));
  };
  const stateOf = (m: T8Message): InboxState => states[m.id] ?? m.state;
  const shown = visibleMessages(T8_MESSAGES, filters, stateOf).map((m) => ({
    ...m,
    state: stateOf(m),
    ...(dest[m.id] === undefined ? {} : { filedTo: dest[m.id] }),
    ...(m.replies === undefined
      ? {}
      : { replies: m.replies.map((r) => ({ ...r, state: stateOf(r) })) }),
  }));
  const message = all(shown).find((m) => m.id === sel) ?? null;
  const filtered =
    filters.client !== null ||
    filters.status !== null ||
    filters.received !== "30" ||
    filters.channel !== "both";

  const filterBar = (
    <>
      <button
        type="button"
        onClick={() => {
          setFilters(NO_FILTERS);
        }}
        className="inline-flex h-[29px] items-center gap-[6px] rounded-pill px-[10px] text-body text-ink-2 hover:bg-nav-fill"
      >
        <Icon name="arrow-left" size={14} />
        All Messages
      </button>
      <FilterChip
        label="Client"
        icon="circle-user-round"
        options={T8_CLIENTS.map((c) => ({ value: c, label: c }))}
        value={filters.client}
        clearLabel="Any client"
        menuWidth={260}
        onChange={(v) => {
          set({ client: v });
        }}
      />
      <FilterChip
        label="Status"
        icon="circle-check"
        options={STATUS_OPTIONS}
        value={filters.status}
        clearLabel="Any status"
        onChange={(v) => {
          set({ status: v as InboxState | null });
        }}
      />
      <FilterChip
        label="Received"
        icon="calendar"
        options={RECEIVED_OPTIONS.filter((o) => o.value !== "30")}
        value={filters.received === "30" ? null : filters.received}
        placeholder="Past 30 Days"
        clearLabel="Past 30 Days"
        onChange={(v) => {
          set({ received: (v ?? "30") as T8Filters["received"] });
        }}
      />
      <FilterChip
        label="Channel"
        icon="mail"
        options={CHANNEL_OPTIONS.filter((o) => o.value !== "both")}
        value={filters.channel === "both" ? null : filters.channel}
        placeholder="Email · Portal"
        clearLabel="Email · Portal"
        onChange={(v) => {
          set({ channel: (v ?? "both") as T8Filters["channel"] });
        }}
      />
    </>
  );

  const toggle = (
    on: boolean,
    label: string,
    icon: "circle-x" | "circle-check",
    flip: () => void,
  ) => (
    <IconButton
      icon={icon}
      label={label}
      variant="white"
      aria-pressed={on}
      onClick={flip}
      className={on && icon === "circle-check" ? "text-green" : "text-ink-3"}
    />
  );

  const body =
    message === null ? (
      shown.length === 0 && filtered ? (
        <EmptyState
          title="No messages match these filters"
          link={
            <EmptyLink
              onClick={() => {
                setFilters(NO_FILTERS);
              }}
            >
              Clear filters →
            </EmptyLink>
          }
        >
          Widen the date range or clear a filter to see more of the inbox.
        </EmptyState>
      ) : null
    ) : (
      <div data-reading="message" className="flex flex-col">
        {message.note !== undefined && (
          <AgentFilingNote
            text={message.note.text}
            {...(message.note.review ? { onReview: () => undefined } : {})}
          />
        )}
        <MessageView
          subject={message.subject}
          date={message.date}
          address={message.address}
          body={message.body}
          {...(message.signature === undefined ? {} : { signature: message.signature })}
          attachments={message.attachments.map((a) => ({
            name: a.name,
            meta: a.meta,
            src: thumbSrc(a),
            ...(a.state === undefined ? {} : { state: a.state }),
          }))}
          onDownloadAll={() => {
            setToast(
              `Downloading ${String(message.attachments.length)} attachment${message.attachments.length > 1 ? "s" : ""}`,
            );
          }}
        />
      </div>
    );

  return (
    <Artboard id={board.id} badge={board.badge} name={board.name} note={board.note}>
      <div className="relative">
        <InboxLayout
          embedded
          height={860}
          toolbar={TOOLBAR}
          filters={filterBar}
          rail={{
            left: (
              <button
                type="button"
                aria-label="Mailbox: All mailboxes"
                className="inline-flex h-[28px] items-center gap-[4px] rounded-pill bg-nav-fill px-[10px] text-ink-2"
              >
                <Icon name="at-sign" size={14} />
                <Icon name="chevron-down" size={12} />
              </button>
            ),
            right: (
              <>
                {toggle(filters.showIgnored, "Show ignored", "circle-x", () => {
                  set({ showIgnored: !filters.showIgnored });
                })}
                {toggle(filters.showFiled, "Show filed", "circle-check", () => {
                  set({ showFiled: !filters.showFiled });
                })}
              </>
            ),
            search: (
              <>
                <SearchField
                  label="Search messages"
                  placeholder="Search"
                  value={filters.q}
                  onChange={(q) => {
                    set({ q });
                  }}
                  className="flex-1"
                />
                <IconButton icon="list-filter" label="Sort and filter" variant="white" />
              </>
            ),
            body: (
              <InboxList
                messages={shown}
                selected={sel}
                open={open}
                onToggle={(id) => {
                  setOpen((o) => (o.includes(id) ? o.filter((x) => x !== id) : [...o, id]));
                }}
                onSelect={(m) => {
                  setSel(m.id);
                }}
              />
            ),
          }}
          reading={{
            ...(message === null
              ? {}
              : {
                  header: (
                    <ReadingHeader
                      client={clients[message.id] ?? message.client}
                      clients={T8_CLIENTS}
                      onMatch={(c) => {
                        setClients((x) => ({ ...x, [message.id]: c }));
                        setToast(`Matched to ${c}`);
                      }}
                      subject={message.subject}
                      state={message.state}
                      fileTo={message.suggest}
                      onFile={(to) => {
                        setStates((s) => ({ ...s, [message.id]: "filed" }));
                        setDest((d) => ({ ...d, [message.id]: to }));
                        setToast(`Filed to ${to}`);
                      }}
                      onIgnore={() => {
                        setStates((s) => ({ ...s, [message.id]: "ignored" }));
                        setToast("Ignored · nothing was filed");
                      }}
                    />
                  ),
                }),
            body,
          }}
        />
        {toast !== null && (
          <div className="pointer-events-none absolute bottom-[24px] left-1/2 -translate-x-1/2">
            <Toast kind="success" text={toast} still />
          </div>
        )}
      </div>
    </Artboard>
  );
}

/** One artboard on its own (the tests render a single board). */
export function T8Board({ id }: { id: string }): JSX.Element | null {
  const board = BOARDS.find((b) => b.id === id);
  return board === undefined ? null : <T8 board={board} />;
}

export function T8Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {BOARDS.map((b) => (
        <T8 key={b.id} board={b} />
      ))}
    </div>
  );
}
