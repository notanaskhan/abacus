import type { ChangeLogEntryOut, KnowledgeItemOut, ReviewQueueItemOut } from "@abacus/api-client";
import {
  AboutCard,
  Button,
  CatalogCard,
  CatalogGrid,
  CatalogLayout,
  CatalogSkeletonCard,
  CategoryList,
  EmptyState,
  ErrorState,
  Icon,
  IconButton,
  Menu,
  Picker,
  Pill,
  SearchField,
  Tag,
  type ToolbarProps,
  cn,
  date,
  status as statusWord,
} from "@abacus/ui";
import { type JSX, type ReactNode, useState } from "react";
import { useCan } from "../../app-core/can";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import {
  CATEGORIES,
  type CatalogFilters,
  type KnowledgeCategory,
  TONE_FILL,
  categoryDef,
  usageWords,
  useChangeLog,
  useKnowledgeItems,
  useReviewQueue,
} from "../../domain/knowledge";
import { COPY } from "./copy";

// KNW-01 · Knowledge library (K-01-T04). T5 CatalogLayout: the tabsbar (Library · Review queue n ·
// Change log), the 358 side (search with the + menu, the AboutCard, the CategoryList in the
// addendum's order: a category without a provider has no count) beside the grid (status Picker,
// "Library", search; three columns of cards). Each artboard is its data (fixtures/scenarios/KNW-01):
//
//   a  Margaret Okonkwo at E0: All 48 (Published 46 · Draft 1 · Superseded 1)
//   b  Methodology: cards 1–4, card 4 struck with Superseded and "Kept for engagements archived
//      under it."
//   c  the Review queue: the 1040 Review Checklist v7 and the §754 memo
//   d  the Change log, newest last, each naming the person
//   e  Ana Cruz: no + menu, no drafts (the API leaves them out)
//   f  "materiality": cards 8 and 1, the match on --nested, never the source-tracing purple
//
// Every card target is planned before K-01-T06 and the provider epics: "Open" and "Review" are
// hidden in production and disabled with "Not built yet" in dev and fixture builds. The + menu is
// shown to whoever may manage or approve content (capabilities, never a role name) and carries
// built targets only: none yet, so in production it is absent.

export type KnowledgeTab = "library" | "review" | "changes";

export interface KNW01Initial {
  tab?: KnowledgeTab;
  category?: KnowledgeCategory | null;
  status?: CatalogFilters["status"];
  q?: string;
}

export interface KNW01Props {
  /** The firm toolbar when the screen draws its own frame (the gallery); routed, it renders bare
   * inside the app's shell. */
  toolbar?: ToolbarProps;
  height?: number;
  initial?: KNW01Initial;
}

const ALL = "all";
type Status = NonNullable<CatalogFilters["status"]>;
const STATUSES: readonly Status[] = ["published", "draft", "superseded"];

function TitleWithMatch({
  title,
  match,
  struck,
}: {
  title: string;
  match: KnowledgeItemOut["match"];
  struck: boolean;
}): JSX.Element {
  const parts: ReactNode[] = [];
  let at = 0;
  for (const { start, end } of [...match].sort((a, b) => a.start - b.start)) {
    if (start < at || end > title.length) continue;
    if (start > at) parts.push(title.slice(at, start));
    // The search hit: 500 ink on --nested, radius 4; never the purple reserved for tracing.
    parts.push(
      <mark
        key={start}
        data-search-hit=""
        className="rounded-[4px] bg-nested font-medium text-ink"
      >
        {title.slice(start, end)}
      </mark>,
    );
    at = end;
  }
  if (at < title.length) parts.push(title.slice(at));
  return (
    <p
      title={title}
      className={cn(
        "mt-[10px] truncate text-tab font-medium tracking-[-0.012em]",
        struck && "text-ink-3 line-through",
      )}
    >
      {parts}
    </p>
  );
}

function KnowledgeCard({ item, now }: { item: KnowledgeItemOut; now: Date }): JSX.Element {
  const def = categoryDef(item.category);
  const word = statusWord("knowledge_item", item.status);
  const draft = item.status === "draft";
  const meta = [
    !draft && item.effective_from !== null
      ? COPY.effective(date(item.effective_from, { now, withYear: true }))
      : null,
    item.owner_name,
    draft ? date(item.updated_at, { now, withYear: true }) : null,
  ].filter((m): m is string => m !== null);
  const usage = item.usage_kind == null ? null : usageWords(item.usage_kind, item.usage_count);
  return (
    <CatalogCard label={`${item.title}, ${word.label}`} height={210}>
      <div
        data-knowledge-card={item.status}
        className="flex items-start justify-between gap-[8px]"
      >
        <span
          aria-hidden="true"
          data-icon-tile={def.tone}
          className={cn(
            "flex size-[34px] flex-none items-center justify-center rounded-tile text-on-dark shadow-lift",
            TONE_FILL[def.tone],
          )}
        >
          <Icon name={def.icon} size={17} />
        </span>
        <span className="flex items-center gap-[6px]">
          {item.version_label !== null && <Tag>{item.version_label}</Tag>}
          <Pill variant={word.variant ?? "neutral"} size="outline">
            {word.label}
          </Pill>
        </span>
      </div>
      <TitleWithMatch
        title={item.title}
        match={item.match}
        struck={item.status === "superseded"}
      />
      {item.subtitle !== null && (
        <p className="mt-[4px] truncate text-cell text-ink-2">{item.subtitle}</p>
      )}
      {meta.length > 0 && (
        <p className="mt-[3px] truncate text-meta text-ink-3">{meta.join(" · ")}</p>
      )}
      {usage !== null && (
        <p className="mt-[6px] flex items-center gap-[6px] text-cell text-ink-2">
          <Icon name="link-2" size={12} className="text-ink-3" />
          {usage}
        </p>
      )}
      {PLANNED_VISIBLE && (
        <div className="mt-auto pt-[8px]">
          <Button variant="secondary" size="sm" disabled title={COPY.notBuilt}>
            {COPY.open}
          </Button>
        </div>
      )}
    </CatalogCard>
  );
}

function Library({
  q,
  items,
  pending,
  failed,
  onRetry,
}: {
  q: string;
  items: readonly KnowledgeItemOut[];
  pending: boolean;
  failed: boolean;
  onRetry: () => void;
}): JSX.Element {
  const now = useNow();
  if (failed) return <ErrorState noun="knowledge" onRetry={onRetry} />;
  if (pending) {
    return (
      <CatalogGrid label={COPY.tabs.library} busy>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <CatalogSkeletonCard key={i} />
        ))}
      </CatalogGrid>
    );
  }
  if (items.length === 0 && q.trim() !== "") {
    return <EmptyState icon="search" title={COPY.noMatch(q.trim())} />;
  }
  return (
    <CatalogGrid label={COPY.tabs.library}>
      {items.map((item) => (
        <KnowledgeCard key={item.id} item={item} now={now} />
      ))}
    </CatalogGrid>
  );
}

function ReviewQueue({ rows }: { rows: readonly ReviewQueueItemOut[] }): JSX.Element {
  const now = useNow();
  if (rows.length === 0) return <EmptyState icon="check" title={COPY.queueEmpty} />;
  return (
    <ul aria-label={COPY.tabs.review} className="overflow-hidden rounded-pane bg-card shadow-e2">
      {rows.map((row) => {
        const word = statusWord("methodology_version", row.status);
        const by = [
          row.submitted_by_name,
          row.submitted_at === null ? null : COPY.submitted(date(row.submitted_at, { now })),
        ].filter((m): m is string => m !== null);
        return (
          <li
            key={row.object_id}
            data-review-row=""
            className="flex h-[52px] items-center gap-[12px] px-[14px] not-last:hairline-b"
          >
            <span className="min-w-0 flex-1 truncate text-body font-medium">
              {`${row.title} ${row.version_label}`}
            </span>
            <Pill variant={word.variant ?? "neutral"} size="state">
              {word.label}
            </Pill>
            <span className="w-[220px] truncate text-meta text-ink-3">{by.join(" · ")}</span>
            {PLANNED_VISIBLE && (
              <Button variant="primary" size="sm" disabled title={COPY.notBuilt}>
                {COPY.review}
              </Button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** One change-log line. The person who acted is named; an agent's act reads "<person> via Agent"
 * and the agent is never the approver (INV-5); a platform release names no person. */
export function changeSentence(entry: ChangeLogEntryOut, now: Date): string {
  const who =
    entry.actor.kind === "agent" && entry.actor.name !== null
      ? COPY.change.viaAgent(entry.actor.name)
      : entry.actor.name;
  const base =
    who === null
      ? COPY.change.available(entry.title)
      : entry.kind === "approved"
        ? COPY.change.approved(entry.title, who)
        : entry.kind === "published"
          ? COPY.change.published(entry.title, who)
          : entry.kind === "imported"
            ? COPY.change.imported(entry.title, who)
            : COPY.change.other(entry.title, who);
  const effective = entry.facts.effective_from;
  return typeof effective === "string"
    ? `${base} · ${COPY.change.effective(date(effective, { now, withYear: true }))}`
    : base;
}

function ChangeLog({ rows }: { rows: readonly ChangeLogEntryOut[] }): JSX.Element {
  const now = useNow();
  return (
    <ol aria-label={COPY.tabs.changes} className="overflow-hidden rounded-pane bg-card shadow-e2">
      {rows.map((entry) => (
        <li
          key={entry.id}
          data-change={entry.kind}
          className="flex min-h-[44px] items-center gap-[12px] px-[14px] not-last:hairline-b"
        >
          <span className="w-[96px] flex-none text-dense text-ink-3 tabular-nums">
            {date(entry.at, { now, withYear: true })}
          </span>
          <span className="min-w-0 flex-1 text-body">{changeSentence(entry, now)}</span>
        </li>
      ))}
    </ol>
  );
}

function tabOf(label: string): KnowledgeTab {
  return label === COPY.tabs.review
    ? "review"
    : label === COPY.tabs.changes
      ? "changes"
      : "library";
}

export function KNW01({ toolbar, height, initial = {} }: KNW01Props): JSX.Element {
  const [tab, setTab] = useState<KnowledgeTab>(initial.tab ?? "library");
  const [filters, setFilters] = useState<CatalogFilters>({
    category: initial.category ?? null,
    status: initial.status ?? null,
    q: initial.q ?? "",
  });
  const manages = useCan("methodology.manage");
  const approves = useCan("methodology.approve");
  const firm = useSession().tenant?.firm_name ?? "";
  const items = useKnowledgeItems(filters);
  const queue = useReviewQueue();
  const changes = useChangeLog(tab === "changes");
  const page = items.data;
  const facet = new Map((page?.facets?.category ?? []).map((f) => [f.value, f.n]));
  const allCount = [...facet.values()].reduce((a, b) => a + b, 0);
  const counts = page?.counts ?? {};
  const statusTotal = Object.values(counts).reduce((a, b) => a + b, 0);
  const tabLabel = COPY.tabs[tab];
  const queueTotal = queue.data?.total;
  const setQ = (q: string): void => {
    setFilters((f) => ({ ...f, q }));
  };
  // The + menu: for whoever may manage or approve content (capabilities); built targets only.
  const add =
    (manages || approves) && PLANNED_VISIBLE ? (
      <Menu
        label={COPY.add}
        trigger={<IconButton icon="plus" label={COPY.add} variant="dark" />}
        sections={[
          COPY.addMenu.map((label) => ({
            label,
            onSelect: () => undefined,
            disabled: true,
            hint: COPY.notBuilt,
          })),
        ]}
      />
    ) : null;
  const statusOptions = [
    { value: ALL, label: `${COPY.all} ${String(statusTotal)}` },
    ...STATUSES.map((s) => ({
      value: s,
      label: `${statusWord("knowledge_item", s).label} ${String(counts[s] ?? 0)}`,
    })),
  ];
  const body =
    tab === "library" ? (
      <Library
        q={filters.q}
        items={page?.items ?? []}
        pending={items.isPending}
        failed={items.isError}
        onRetry={() => void items.refetch()}
      />
    ) : tab === "review" ? (
      queue.isError ? (
        <ErrorState noun="the review queue" onRetry={() => void queue.refetch()} />
      ) : (
        <ReviewQueue rows={queue.data?.items ?? []} />
      )
    ) : changes.isError ? (
      <ErrorState noun="the change log" onRetry={() => void changes.refetch()} />
    ) : (
      <ChangeLog rows={changes.data?.items ?? []} />
    );
  return (
    <CatalogLayout
      {...(toolbar === undefined
        ? { bare: true, toolbar: { nav: [], active: "Knowledge", firm: "" } }
        : { toolbar: { ...toolbar, active: "Knowledge" }, embedded: true })}
      {...(height === undefined ? {} : { height })}
      tabs={{
        label: COPY.tabsLabel,
        options: [
          COPY.tabs.library,
          {
            label: COPY.tabs.review,
            ...(queueTotal === undefined || queueTotal === 0 ? {} : { count: queueTotal }),
          },
          COPY.tabs.changes,
        ],
        active: tabLabel,
        onChange: (label) => {
          setTab(tabOf(label));
        },
      }}
      side={{
        search: (
          <>
            <SearchField
              label={COPY.search}
              placeholder={COPY.search}
              value={filters.q}
              onChange={setQ}
              className="w-auto flex-1"
            />
            {add}
          </>
        ),
        about: (
          <AboutCard icon="notebook-text" title={COPY.about.title} body={COPY.about.body(firm)} />
        ),
        categories: (
          <CategoryList
            label={COPY.categories}
            selected={filters.category ?? ALL}
            onSelect={(key) => {
              setTab("library");
              setFilters((f) => ({
                ...f,
                category: key === ALL ? null : (key as KnowledgeCategory),
              }));
            }}
            categories={[
              { key: ALL, label: COPY.all, ...(page === undefined ? {} : { count: allCount }) },
              ...CATEGORIES.map((c) => {
                const n = facet.get(c.key);
                return { key: c.key, label: c.label, ...(n === undefined ? {} : { count: n }) };
              }),
            ]}
          />
        ),
      }}
      grid={{
        title: tabLabel,
        ...(tab === "library"
          ? {
              left: (
                <Picker
                  label={COPY.status}
                  variant="white"
                  options={statusOptions}
                  value={filters.status ?? ALL}
                  onChange={(value) => {
                    setFilters((f) => ({
                      ...f,
                      status: value === ALL ? null : (value as Status),
                    }));
                  }}
                />
              ),
              right: (
                <SearchField
                  label={COPY.gridSearch}
                  placeholder={COPY.gridSearch}
                  value={filters.q}
                  onChange={setQ}
                  className="w-[220px]"
                />
              ),
            }
          : {}),
        body,
      }}
    />
  );
}
