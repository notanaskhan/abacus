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
  NO_TPL08_FILTERS,
  TPL08_CLIENTS,
  TPL08_DEFAULT,
  type Tpl08Attachment,
  type Tpl08Filters,
  type Tpl08Message,
  flat,
  tpl08Messages,
  visibleTpl08,
} from "./tpl08-data";
import { FORM_PAGE_PNG } from "./viewer-pages";

// TPL-08 (F-05-T58; TPL-08 handoff, Wave 0 Templates #tpl08): T8 for Kevin Osei, the Feld
// preparer, on the File Kit's `w0` inbox, TPL-08a to TPL-08e. The 392 rail of 52px rows beside
// the 974 reading pane; 23 attachments wait (19 on the rows above the fold and 4 below), the
// wrong-year 1095-C is flagged "2024 ≠ 2025" before anything reaches the binder, and the agent files
// nothing on its own: its note offers only Review. Every board is live: open threads, hover a
// waiting row for File…, File… or Move…, match a client, filter with the chips, toggle filed and
// ignored, and Reply.

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
  filed: boolean;
  selected: string;
  hovered: string | null;
  filters?: Partial<Tpl08Filters>;
}

// The canvas's TP8, word for word.
const BOARDS: readonly Board[] = [
  {
    id: "tpl-08a",
    badge: "TPL-08a",
    name: "Default",
    note: "The Feld thread open: two 1095-Cs wait, and one is a 2024 form",
    filed: false,
    selected: "feld",
    hovered: null,
  },
  {
    id: "tpl-08b",
    badge: "TPL-08b",
    name: "Row hover",
    note: "Hovering a waiting row shows File… at the right",
    filed: false,
    selected: "feld",
    hovered: "shah",
  },
  {
    id: "tpl-08c",
    badge: "TPL-08c",
    name: "Unmatched sender",
    note: "Sound Electric matches no client; the agent points to Copperleaf’s ledger",
    filed: false,
    selected: "sound",
    hovered: null,
  },
  {
    id: "tpl-08d",
    badge: "TPL-08d",
    name: "Filed",
    note: "After triage: the 2025 form is filed and the 2024 form ignored",
    filed: true,
    selected: "feld",
    hovered: null,
  },
  {
    id: "tpl-08e",
    badge: "TPL-08e",
    name: "Filter empty",
    note: "Ridgeline has no mail in the past 30 days",
    filed: false,
    selected: "feld",
    hovered: null,
    filters: { client: TPL08_CLIENTS[5] },
  },
];

const STATUS_OPTIONS = [
  { value: "new", label: "Not filed" },
  { value: "wait", label: "Waiting to be filed" },
  { value: "filed", label: "Filed" },
  { value: "ignored", label: "Ignored" },
] as const;
const RECEIVED_OPTIONS = [
  { value: "today", label: "Today" },
  { value: "7", label: "Past 7 Days" },
  { value: "30", label: "Past 30 Days" },
  { value: "all", label: "All time" },
] as const;
const CHANNEL_OPTIONS = [
  { value: "email", label: "Email" },
  { value: "portal", label: "Portal" },
] as const;

/** "2025 Binder › Health & Medical › Form 1095-C From Mercer Hill Health · 96%" → the path. */
const pathOf = (to: string): string => to.replace(/ · \d+%$/, "");

function Tpl08({ board }: { board: Board }): JSX.Element {
  const [messages, setMessages] = useState<readonly Tpl08Message[]>(() =>
    tpl08Messages(board.filed),
  );
  const [filters, setFilters] = useState<Tpl08Filters>({ ...TPL08_DEFAULT, ...board.filters });
  const [sel, setSel] = useState<string | null>(board.selected);
  const [open, setOpen] = useState<readonly string[]>(["feld"]);
  const [clients, setClients] = useState<Readonly<Record<string, string>>>({});
  const [toast, setToast] = useState<string | null>(null);
  const set = (patch: Partial<Tpl08Filters>): void => {
    setFilters((f) => ({ ...f, ...patch }));
  };
  const stateOf = (m: Tpl08Message): InboxState => m.state;
  const shown = visibleTpl08(messages, filters, stateOf);
  const message = flat(shown).find((m) => m.id === sel) ?? null;

  /** Apply a person's triage to a message and its thread: states and attachment results. */
  const triage = (id: string, to: string | null): void => {
    // Once a person decides, the agent's note about what is waiting has nothing left to say.
    const apply = (full: Tpl08Message): Tpl08Message => {
      const m: Tpl08Message = { ...full };
      delete m.note;
      return applied(m);
    };
    const applied = (m: Tpl08Message): Tpl08Message => ({
      ...m,
      state: to === null ? "ignored" : "filed",
      attachments: m.attachments.map((a): Tpl08Attachment =>
        a.state === "wait" || a.state === "new"
          ? to === null
            ? { name: a.name, meta: a.meta, state: "ignored", result: { text: "Ignored" } }
            : {
                name: a.name,
                meta: a.meta,
                state: "filed",
                result: { text: "Filed to", link: pathOf(to) },
              }
          : a,
      ),
      ...(m.replies === undefined ? {} : { replies: m.replies.map((r) => apply(r)) }),
    });
    const walk = (m: Tpl08Message): Tpl08Message =>
      m.id === id
        ? apply(m)
        : m.replies === undefined
          ? m
          : { ...m, replies: m.replies.map(walk) };
    setMessages((ms) => ms.map(walk));
  };

  const filterBar = (
    <>
      <button
        type="button"
        onClick={() => {
          setFilters(NO_TPL08_FILTERS);
        }}
        className="inline-flex h-[29px] items-center gap-[6px] rounded-pill px-[10px] text-body text-ink-2 hover:bg-nav-fill"
      >
        <Icon name="arrow-left" size={14} />
        All Messages
      </button>
      <FilterChip
        label="Client"
        icon="circle-user-round"
        options={TPL08_CLIENTS.map((c) => ({ value: c, label: c }))}
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
        options={RECEIVED_OPTIONS}
        value={filters.received}
        clearLabel="Any time"
        onChange={(v) => {
          set({ received: v as Tpl08Filters["received"] });
        }}
      />
      <FilterChip
        label="Channel"
        icon="mail"
        options={CHANNEL_OPTIONS}
        value={filters.channel}
        placeholder="Email"
        clearLabel="Any channel"
        onChange={(v) => {
          set({ channel: v as Tpl08Filters["channel"] });
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

  const thumbs = (m: Tpl08Message) =>
    m.attachments.map((a) => ({
      name: a.name,
      meta: a.meta,
      src: FORM_PAGE_PNG,
      state: a.state,
      ...(a.tag === undefined ? {} : { tag: a.tag }),
      ...(a.result === undefined ? {} : { result: a.result }),
    }));
  const view = (m: Tpl08Message, recessed = false) => (
    <MessageView
      key={m.id}
      subject={m.subject}
      date={m.date}
      address={m.address}
      body={m.body}
      attachments={thumbs(m)}
      recessed={recessed}
      onDownloadAll={() => {
        setToast(
          `Downloading ${String(m.attachments.length)} attachment${m.attachments.length > 1 ? "s" : ""}`,
        );
      }}
    />
  );

  // A thread's roll-up opens the thread: the newest message, then the older ones recessed.
  const thread =
    message === null
      ? []
      : message.replies !== undefined && message.replies.length > 0 && message.body === ""
        ? message.replies
        : [message];

  const body =
    message === null ? (
      shown.length === 0 ? (
        <EmptyState
          title="No messages match these filters"
          link={
            <EmptyLink
              onClick={() => {
                setFilters(NO_TPL08_FILTERS);
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
          <AgentFilingNote text={message.note} onReview={() => undefined} />
        )}
        {thread.map((m, i) => view(m, i > 0))}
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
                aria-label="Mailbox: docs@brightwaterhale.com"
                className="inline-flex h-[28px] max-w-[120px] items-center gap-[4px] rounded-pill bg-nav-fill px-[10px] text-body text-ink-2"
              >
                <Icon name="at-sign" size={14} className="flex-none" />
                <span className="min-w-0 truncate">docs@brightwaterhale.com</span>
                <Icon name="chevron-down" size={12} className="flex-none" />
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
                hovered={board.hovered}
                onToggle={(id) => {
                  setOpen((o) => (o.includes(id) ? o.filter((x) => x !== id) : [...o, id]));
                }}
                onSelect={(m) => {
                  setSel(m.id);
                }}
                onFile={(m) => {
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
                      clients={TPL08_CLIENTS}
                      {...(message.context === undefined ? {} : { context: message.context })}
                      onMatch={(c) => {
                        setClients((x) => ({ ...x, [message.id]: c }));
                        setToast(`Matched to ${c}`);
                      }}
                      subject={message.subject}
                      state={message.state}
                      fileTo={message.suggest}
                      onFile={(to) => {
                        triage(message.id, to);
                        setToast(`Filed to ${pathOf(to)}`);
                      }}
                      onIgnore={() => {
                        triage(message.id, null);
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
export function Tpl08Board({ id }: { id: string }): JSX.Element | null {
  const board = BOARDS.find((b) => b.id === id);
  return board === undefined ? null : <Tpl08 board={board} />;
}

export function Tpl08Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {BOARDS.map((b) => (
        <Tpl08 key={b.id} board={b} />
      ))}
    </div>
  );
}
