// SHL-05 Support panel (G-04-T19; handoff SHL-05 a-f and d'; G-04 §5.1 `?ov=support[:chat|help|
// status|article:<slug>]`): the O2 480 drawer the Support pill opens behind `support.panel_v2`
// (P-01's interim frame otherwise). Chat on the C-10 ChatThread kit (the firm user's own bubbles
// right, Accrued Support's line bubbles left with the sender row), the time-boxed session request
// card (Decline, Review in Settings; granted: Revoke; support never self-grants), help articles with
// search and the in-drawer article (d'), and system status in the canonical words. Escape closes
// and focus returns to the Support pill (the Drawer kit); the thread is the server's, so it
// persists across sign-ins.
import type { ConversationOut, SessionCardOut, StatusComponentOut } from "@abacus/api-client";
import {
  declineSupportSessionMutation,
  firmStatusOptions,
  helpArticleOptions,
  helpArticlesOptions,
  revokeSupportSessionMutation,
  supportConversationOptions,
  supportConversationQueryKey,
  supportSendMessageMutation,
} from "@abacus/api-client/query";
import {
  Button,
  ChatThread,
  type ChatThreadProps,
  Drawer,
  Icon,
  Pill,
  type PillVariant,
  SearchField,
  Segmented,
  Skeleton,
  StatusDisc,
  type ThreadItem,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY as C } from "./copy";

export type SupportTab = "chat" | "help" | "status";
const TABS: readonly SupportTab[] = ["chat", "help", "status"];
const TZ = "America/Chicago";

function clock(at: string): string {
  return new Date(at).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: TZ,
  });
}

function items(c: ConversationOut): ThreadItem[] {
  return c.messages.map((m, seq) => ({
    id: m.id,
    seq,
    kind: m.author_kind === "firm_user" ? "user_message" : "support_line",
    payload: {
      body: m.body,
      author: m.author_display_name,
      at: m.created_at,
      article: m.related_article_slug,
    },
    actor_kind: "human",
    actor_name: m.author_display_name,
  }));
}

function SupportLine({
  item,
  onArticle,
}: {
  item: ThreadItem;
  onArticle: (slug: string) => void;
}): JSX.Element {
  const article = typeof item.payload.article === "string" ? item.payload.article : null;
  return (
    <div className="flex max-w-[82%] flex-col gap-[4px]" data-row="support_line">
      <span className="flex items-center gap-[6px] text-[11.5px] text-ink-3">
        <span
          aria-hidden
          className="inline-flex size-[16px] items-center justify-center rounded-[4px] bg-ink text-[10px] text-card"
        >
          a
        </span>
        {C.staffSender(String(item.payload.author ?? ""))}
        <span>{clock(String(item.payload.at ?? ""))}</span>
      </span>
      <p className="rounded-[14px] bg-card px-[12px] py-[8px] text-[13px] leading-[1.45] text-ink hairline">
        {String(item.payload.body ?? "")}
      </p>
      {article === null ? null : <ArticleLink slug={article} onArticle={onArticle} />}
    </div>
  );
}

function ArticleLink({ slug, onArticle }: { slug: string; onArticle: (s: string) => void }) {
  const a = useQuery({ ...helpArticleOptions({ path: { slug } }), retry: false });
  if (a.data === undefined) return null;
  return (
    <div className="flex flex-col gap-[6px] rounded-[14px] bg-card px-[14px] py-[12px] hairline">
      <span className="text-[13px] font-medium text-ink">{C.relatedArticle}</span>
      <button
        type="button"
        className="flex items-center gap-[8px] text-left text-[13px] text-ink"
        onClick={() => {
          onArticle(slug);
        }}
      >
        <Icon name="file-text" size={14} className="text-ink-3" />
        <span className="flex-1">{a.data.title}</span>
        <span className="text-[11.5px] text-ink-3">{C.readMinutes(a.data.read_minutes)}</span>
        <Icon name="arrow-up-right" size={12} className="text-ink-3" />
      </button>
    </div>
  );
}

function SessionCard({
  card,
  onDecline,
  onRevoke,
  onReview,
}: {
  card: SessionCardOut;
  onDecline: (id: string) => void;
  onRevoke: (id: string) => void;
  onReview: () => void;
}): JSX.Element {
  const active = card.status === "active";
  const statusPill: Record<SessionCardOut["status"], { v: PillVariant; w: string }> = {
    requested: { v: "amber", w: C.card.awaiting },
    active: {
      v: "green-tint",
      w: C.card.granted(
        card.decided_by_display_name ?? "",
        card.expires_at === null ? "" : clock(card.expires_at),
      ),
    },
    declined: { v: "muted", w: C.card.declined },
    revoked: { v: "muted", w: C.card.declined },
    ended: { v: "neutral", w: C.card.ended },
    expired: { v: "neutral", w: C.card.ended },
  };
  const rows: [string, string][] = [
    [C.card.requestedBy, C.card.requester],
    [C.card.scope, card.scope_label],
    [C.card.duration, C.card.hours(card.duration_minutes)],
  ];
  return (
    <section
      aria-label={C.card.scope}
      data-session-card={card.status}
      className={`flex flex-col rounded-[10px] px-[12px] py-[6px] hairline ${active ? "bg-green-tint" : "bg-card"}`}
    >
      {rows.map(([k, v]) => (
        <div key={k} className="flex h-[33px] items-center justify-between text-[12.5px]">
          <span className="text-ink-3">{k}</span>
          <span className="text-ink">{v}</span>
        </div>
      ))}
      <div className="flex h-[33px] items-center justify-between text-[12.5px]">
        <span className="text-ink-3">{C.card.status}</span>
        <Pill variant={statusPill[card.status].v} size="sm">
          {statusPill[card.status].w}
        </Pill>
      </div>
      {card.status === "requested" && card.can_decide ? (
        <div className="flex justify-end gap-[8px] py-[6px]">
          <Button variant="secondary" size="sm" onClick={() => onDecline(card.session_id)}>
            {C.card.decline}
          </Button>
          <Button size="sm" onClick={onReview}>
            {C.card.review}
          </Button>
        </div>
      ) : null}
      {active && card.can_decide ? (
        <div className="flex justify-end py-[6px]">
          <Button
            variant="ghost"
            size="sm"
            className="text-red"
            onClick={() => onRevoke(card.session_id)}
          >
            {C.card.revoke}
          </Button>
        </div>
      ) : null}
    </section>
  );
}

function Chat({ onArticle, onReview }: { onArticle: (s: string) => void; onReview: () => void }) {
  const client = useQueryClient();
  const q = useQuery({ ...supportConversationOptions(), retry: false });
  const refresh = {
    onSuccess: () => client.invalidateQueries({ queryKey: supportConversationQueryKey() }),
  };
  const send = useMutation({ ...supportSendMessageMutation(), ...refresh });
  const decline = useMutation({ ...declineSupportSessionMutation(), ...refresh });
  const revoke = useMutation({ ...revokeSupportSessionMutation(), ...refresh });
  if (q.data === undefined) return <Skeleton className="h-[520px] w-full" />;
  const c = q.data;
  const online = c.availability.online;
  const empty = c.messages.length === 0;
  return (
    <div
      className="flex h-full flex-col gap-[10px] bg-shell p-[14px]"
      data-chat={online ? "online" : "offline"}
    >
      <p className="flex gap-[6px] rounded-[10px] bg-nested px-[10px] py-[8px] text-[12px] text-ink-2">
        <Icon name="shield-check" size={14} />
        {C.notice}
      </p>
      {!online && c.availability.reply_email !== null ? (
        <p className="text-[12px] text-ink-2">{C.offlineNotice(c.availability.reply_email)}</p>
      ) : null}
      <ChatThread
        items={items(c)}
        still
        slots={
          {
            support_line: (item: ThreadItem) => <SupportLine item={item} onArticle={onArticle} />,
          } as unknown as NonNullable<ChatThreadProps["slots"]>
        }
        above={
          <div className="flex flex-col gap-[8px]">
            {c.session_cards.map((card) => (
              <SessionCard
                key={card.session_id}
                card={card}
                onReview={onReview}
                onDecline={(id) => {
                  decline.mutate({ path: { session_id: id } });
                }}
                onRevoke={(id) => {
                  revoke.mutate({ path: { session_id: id } });
                }}
              />
            ))}
          </div>
        }
        empty={
          empty ? (
            <div className="flex flex-col gap-[8px]">
              {(c.suggestions.length > 0 ? c.suggestions : C.empty.suggestions).map((s) => (
                <div
                  key={s}
                  className="rounded-[10px] bg-card px-[12px] py-[10px] text-[13px] text-ink hairline"
                >
                  {s}
                </div>
              ))}
            </div>
          ) : undefined
        }
        composerPlaceholder={online ? C.composer.online : C.composer.offline}
        onSend={(body) => {
          send.mutate({ body: { body }, headers: { "Idempotency-Key": crypto.randomUUID() } });
        }}
      />
    </div>
  );
}

function Help({
  onArticle,
  context,
}: {
  onArticle: (s: string) => void;
  context: string | null;
}): JSX.Element {
  const [q, setQ] = useState("");
  const list = useQuery({
    ...helpArticlesOptions({
      query: { ...(q === "" ? {} : { q }), ...(context === null ? {} : { context }) },
    }),
    retry: false,
  });
  return (
    <div className="flex flex-col gap-[8px] p-[12px]" data-help="list">
      <SearchField label={C.help.search} placeholder={C.help.search} value={q} onChange={setQ} />
      {list.data?.groups.map((g) => (
        <section key={g.key} aria-label={g.label}>
          <h3 className="flex h-[31px] items-center bg-nested px-[10px] text-[12px] text-ink-2">
            {g.label}
          </h3>
          <ul>
            {g.articles.map((a) => (
              <li key={a.slug}>
                <button
                  type="button"
                  className="flex h-[44px] w-full items-center gap-[8px] px-[10px] text-left"
                  onClick={() => {
                    onArticle(a.slug);
                  }}
                >
                  <span className="flex flex-1 flex-col">
                    <span className="text-[13px] text-ink">{a.title}</span>
                    {a.summary === "" ? null : (
                      <span className="truncate text-[11.5px] text-ink-3">{a.summary}</span>
                    )}
                  </span>
                  <Icon name="chevron-right" size={12} className="text-ink-3" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )) ?? <Skeleton className="h-[320px] w-full" />}
    </div>
  );
}

function Article({ slug, onBack }: { slug: string; onBack: () => void }): JSX.Element {
  const a = useQuery({ ...helpArticleOptions({ path: { slug } }), retry: false });
  return (
    <article className="flex flex-col gap-[10px] p-[14px]" data-help="article">
      <button
        type="button"
        className="flex items-center gap-[4px] text-[12.5px] text-ink-2"
        onClick={onBack}
      >
        <Icon name="chevron-left" size={12} />
        {C.help.back}
      </button>
      {a.data === undefined ? (
        <Skeleton className="h-[240px] w-full" />
      ) : (
        <>
          <h3 className="text-[14.5px] font-medium text-ink">{a.data.title}</h3>
          <span className="text-[11.5px] text-ink-3">{C.readMinutes(a.data.read_minutes)}</span>
          {a.data.blocks.map((b, i) =>
            b.kind === "heading" ? (
              <h4 key={i} className="text-[13px] font-medium text-ink">
                {b.text}
              </h4>
            ) : b.kind === "list" ? (
              <ul key={i} className="list-disc pl-[18px] text-[13px] text-ink-2">
                {(b.items ?? []).map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            ) : (
              <p
                key={i}
                className={`text-[13px] ${b.kind === "note" ? "rounded-[10px] bg-nested px-[10px] py-[8px] text-ink-2" : "text-ink-2"}`}
              >
                {b.text}
              </p>
            ),
          )}
        </>
      )}
    </article>
  );
}

const STATE_PILL: Record<StatusComponentOut["state"], PillVariant> = {
  operational: "green-tint",
  needs_attention: "amber",
  outage: "red-tint",
  maintenance: "neutral",
};
const STATE_DISC = {
  operational: "done",
  needs_attention: "warn",
  outage: "fail",
  maintenance: "wait",
} as const;

function SystemStatus(): JSX.Element {
  const s = useQuery({ ...firmStatusOptions(), retry: false });
  if (s.data === undefined) return <Skeleton className="m-[12px] h-[320px]" />;
  return (
    <div className="flex flex-col gap-[10px] p-[12px]" data-status="card">
      <section
        aria-label={C.status.card}
        className="flex flex-col rounded-[10px] bg-card px-[12px] hairline"
      >
        <h3 className="flex h-[38px] items-center text-[13px] font-medium text-ink">
          {C.status.card}
        </h3>
        {s.data.components.map((c) => (
          <div
            key={c.key}
            className="flex min-h-[38px] items-center gap-[8px] text-[13px] hairline-t"
          >
            <StatusDisc state={STATE_DISC[c.state]} size={15} />
            <span className="flex flex-1 flex-col">
              <span className="text-ink">{c.label}</span>
              {c.note === null ? null : <span className="text-[11.5px] text-ink-3">{c.note}</span>}
            </span>
            <Pill variant={STATE_PILL[c.state]} size="sm">
              {C.status.states[c.state]}
            </Pill>
          </div>
        ))}
      </section>
      <a
        href={s.data.history_url}
        target="_blank"
        rel="noreferrer"
        className="text-[12.5px] text-ink underline"
      >
        {C.status.history}
      </a>
      <span className="text-[11.5px] text-ink-3">{C.status.region(s.data.region_label)}</span>
    </div>
  );
}

function Chip(): JSX.Element | null {
  const q = useQuery({ ...supportConversationOptions(), retry: false });
  const a = q.data?.availability;
  if (a === undefined) return null;
  const next = a.next_open_at === null ? "" : `${clock(a.next_open_at)} CT`;
  return (
    <span className="flex h-[26px] items-center gap-[6px] rounded-full bg-card px-[10px] text-[12px] text-ink-2 hairline">
      <span
        aria-hidden
        className={`size-[8px] rounded-full ${a.online ? "bg-green" : "bg-ink-4"}`}
      />
      {a.online ? C.online(a.replies_in_minutes) : C.offline(next)}
    </span>
  );
}

export interface SupportPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The tab, or an article, on arrival (`?ov=support:help`, `support:article:<slug>`). */
  initialTab?: SupportTab;
  initialArticle?: string | null;
  /** "Review in Settings" → ADM-06's support-access block. */
  onReview?: () => void;
  /** The page the panel opened over ("Suggested for this page"). */
  context?: string | null;
}

export function SupportPanel({
  open,
  onOpenChange,
  initialTab = "chat",
  initialArticle = null,
  onReview = () => undefined,
  context = null,
}: SupportPanelProps): JSX.Element {
  const [tab, setTab] = useState<SupportTab>(initialArticle === null ? initialTab : "help");
  const [article, setArticle] = useState<string | null>(initialArticle);
  const showArticle = (slug: string) => {
    setTab("help");
    setArticle(slug);
  };
  return (
    <Drawer open={open} onOpenChange={onOpenChange} title={C.title} width={480}>
      <div className="flex h-full flex-col" data-screen-part="SHL-05">
        <div className="flex items-center justify-between pb-[8px]">
          <Segmented
            label={C.title}
            size="small"
            options={TABS.map((t) => C.tabs[t])}
            active={C.tabs[tab]}
            onChange={(label) => {
              const found = TABS.find((t) => C.tabs[t] === label);
              if (found !== undefined) {
                setTab(found);
                setArticle(null);
              }
            }}
          />
          <Chip />
        </div>
        {tab === "chat" ? <Chat onArticle={showArticle} onReview={onReview} /> : null}
        {tab === "help" && article === null ? (
          <Help onArticle={showArticle} context={context} />
        ) : null}
        {tab === "help" && article !== null ? (
          <Article
            slug={article}
            onBack={() => {
              setArticle(null);
            }}
          />
        ) : null}
        {tab === "status" ? <SystemStatus /> : null}
      </div>
    </Drawer>
  );
}

/** The artboard: the firm shell with the drawer open on the state's tab (the gallery's SHL-05). */
export function SHL05({
  tab = "chat",
  article = null,
}: {
  tab?: SupportTab;
  article?: string | null;
}): JSX.Element {
  return (
    <div className="relative h-[860px] w-[1440px]">
      <SupportPanel
        open
        onOpenChange={() => undefined}
        initialTab={tab}
        initialArticle={article}
      />
    </div>
  );
}
