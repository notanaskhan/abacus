import { type JSX, useEffect, useRef, useState } from "react";
import { AgentCard } from "../agent/agent-card";
import { CatalogGrid, CatalogSkeletonCard, CategoryList } from "../catalog/catalog-kit";
import { Button, IconButton } from "../components/button";
import { Picker, SearchField } from "../components/inputs";
import { EmptyLink, EmptyState } from "../components/states";
import { ConnectionTile, type ConnectionStatus } from "../connect/connection-tile";
import { ConfirmDialog } from "../overlays/confirm";
import { AboutCard } from "../record/record-kit";
import { CatalogLayout } from "../templates/catalog-layout";
import guards from "../../scope-guards.gen.json";
import { Artboard } from "./portal";
import { FIRM } from "./seed-figures";
import {
  AGENTS,
  AGENT_FILTERS,
  type AgentFilter,
  type AgentView,
  CONNECT_FILTERS,
  type CatalogIntegration,
  type ConnectFilter,
  INTEGRATIONS,
  VIEWER,
  agentCategories,
  agentCategory,
  connectCategories,
  connectCategory,
  disconnectText,
  scopeLine,
  visibleAgents,
  visibleIntegrations,
} from "./t5-data";

// T5 CatalogLayout (F-05-T59; T5 handoff, Wave 0 Foundations #t5) and its specimen TPL-05
// (Workbench › Agents › Library, #tpl05): the C-11 AgentCard and IconTile and the C-14
// ConnectionTile on one grammar, artboards T5a to T5f and TPL-05a to TPL-05e. Every board is live:
// switch Agents and Connect, Library and My Agents, pick a category (↑ ↓ Home End too), filter by
// status with All ⌄, search, Notify me on a coming-soon card, Enable an integration (Connecting…,
// then Connected as added by the viewer) and Disconnect one through its confirm. Details…, + and
// the Sessions tab open screens of their own (WB-05, WB-07, WB-11, T4) and are not drawn here.

const TOOLBAR = {
  nav: guards.nav.map((label) => ({ label })),
  firm: FIRM,
  firmShort: "Brightwater",
  firmTitle: "Brightwater Hale LLP",
  active: "Workbench",
} as const;

const TABS = [{ label: "Sessions", disabled: true }, "Agents", "Connect"];
const VIEWS = ["Library", "My Agents"];

const AGENTS_ABOUT =
  "Explore agents published by Accrued. Review their instructions, install an agent, and adapt it to your firm’s work.";
const CONNECT_ABOUT =
  "Bring your tax engine, client ledgers and everyday tools into Accrued. Firm connections are shared; personal connections act as you.";

const CONNECT_MS = 1600;

interface Board {
  id: string;
  badge: string;
  name: string;
  note: string;
  tab: "Agents" | "Connect";
  cat?: string;
  query?: string;
  loading?: boolean;
}

const T5_BOARDS: readonly Board[] = [
  {
    id: "t5a",
    badge: "T5a",
    name: "Agents · Library",
    note: "All 28 agents. Pick a category, or switch the sub-row to My Agents",
    tab: "Agents",
  },
  {
    id: "t5b",
    badge: "T5b",
    name: "Filtered by category",
    note: "Audit selected: 3 installed, 1 available and 1 coming soon",
    tab: "Agents",
    cat: "audit",
  },
  {
    id: "t5c",
    badge: "T5c",
    name: "Search, no results",
    note: "Nothing matches “Form 941”, so the well shows the empty state",
    tab: "Agents",
    query: "Form 941",
  },
  {
    id: "t5d",
    badge: "T5d",
    name: "Loading",
    note: "Skeleton cards hold the grid, each a tile and three bars",
    tab: "Agents",
    loading: true,
  },
  {
    id: "t5e",
    badge: "T5e",
    name: "Connect · Integrations",
    note: "Tiles 212 tall; the well pads 14 on every side",
    tab: "Connect",
  },
  {
    id: "t5f",
    badge: "T5f",
    name: "Connect · filtered",
    note: "Tax Software: 1 connected, 6 available and 1 coming soon",
    tab: "Connect",
    cat: "tax",
  },
];

const TPL05_BOARDS: readonly Board[] = [
  {
    id: "tpl-05a",
    badge: "TPL-05a",
    name: "Default",
    note: "All 28 agents. The third row runs under the pane edge, as in the demo",
    tab: "Agents",
  },
  {
    id: "tpl-05b",
    badge: "TPL-05b",
    name: "Filtered · Audit",
    note: "Five audit agents: three installed, one available and one coming soon",
    tab: "Agents",
    cat: "audit",
  },
  {
    id: "tpl-05c",
    badge: "TPL-05c",
    name: "Search, no results",
    note: "“payroll tax” matches nothing, so the well offers Clear search",
    tab: "Agents",
    query: "payroll tax",
  },
  {
    id: "tpl-05d",
    badge: "TPL-05d",
    name: "Loading",
    note: "Six skeleton cards, each a tile and three bars",
    tab: "Agents",
    loading: true,
  },
  {
    id: "tpl-05e",
    badge: "TPL-05e",
    name: "Connect · WB-10",
    note: "Nine of 53 connected. CCH Axcess Practice is card 2, added by Felix Andersen",
    tab: "Connect",
  },
];

/** The skeleton count: the expected results, clamped 3 to 6 (C-11 §1). */
const skeletons = (expected: number): number =>
  Math.max(3, Math.min(6, expected === 0 ? 3 : expected));

function SearchEmpty({ noun, q, onClear }: { noun: string; q: string; onClear: () => void }) {
  return (
    <EmptyState
      icon="search"
      title={`No ${noun} match ‘${q.trim()}’.`}
      className="min-h-[340px]"
      link={<EmptyLink onClick={onClear}>Clear search</EmptyLink>}
    />
  );
}

function useAgents({
  board,
  view,
  setView,
}: {
  board: Board;
  view: AgentView;
  setView: (v: AgentView) => void;
}): Pick<Parameters<typeof CatalogLayout>[0], "side" | "grid" | "subRow"> {
  const [cat, setCat] = useState(board.tab === "Agents" ? (board.cat ?? "all") : "all");
  const [status, setStatus] = useState<AgentFilter>("all");
  const [q, setQ] = useState(board.query ?? "");
  const [notify, setNotify] = useState<ReadonlySet<string>>(new Set());
  const shown = visibleAgents(AGENTS, { view, cat, status, q });
  const catLabel =
    cat === "all"
      ? "All Categories"
      : agentCategory(cat as Parameters<typeof agentCategory>[0]).label;

  let body: JSX.Element;
  if (board.loading === true) {
    body = (
      <CatalogGrid label="Agents" busy>
        {Array.from({ length: skeletons(shown.length) }, (_, i) => (
          <CatalogSkeletonCard key={i} />
        ))}
      </CatalogGrid>
    );
  } else if (shown.length > 0) {
    body = (
      <CatalogGrid label="Agents">
        {shown.map((a) => {
          const c = agentCategory(a.cat);
          return (
            <AgentCard
              key={a.id}
              name={a.name}
              description={a.text}
              category={c.label}
              tone={c.tone}
              status={a.status}
              notifying={notify.has(a.id)}
              onNotify={() => {
                setNotify((s) => {
                  const n = new Set(s);
                  if (n.has(a.id)) n.delete(a.id);
                  else n.add(a.id);
                  return n;
                });
              }}
            />
          );
        })}
      </CatalogGrid>
    );
  } else if (q.trim() !== "") {
    body = (
      <SearchEmpty
        noun="agents"
        q={q}
        onClear={() => {
          setQ("");
        }}
      />
    );
  } else if (view === "My Agents" && status === "all") {
    body = (
      <EmptyState
        icon="search"
        className="min-h-[340px]"
        title={cat === "all" ? "No agents installed yet" : `No installed agents in ${catLabel}`}
        action={
          <Button
            variant="secondary"
            size="md"
            onClick={() => {
              setView("Library");
            }}
          >
            Browse the library
          </Button>
        }
      >
        Install an agent from the library and it shows up here, ready to adapt to your work.
      </EmptyState>
    );
  } else {
    body = (
      <EmptyState
        icon="search"
        className="min-h-[340px]"
        title="No agents match"
        action={
          <Button
            variant="secondary"
            size="md"
            onClick={() => {
              setStatus("all");
              setQ("");
            }}
          >
            Clear filters
          </Button>
        }
      >
        {`Nothing in ${catLabel} has that status.`}
      </EmptyState>
    );
  }

  return {
    subRow: {
      label: "Agents",
      options: VIEWS,
      active: view,
      onChange: (l) => {
        setView(l as AgentView);
      },
    },
    side: {
      search: (
        <>
          <SearchField
            label="Search agents"
            placeholder="Search"
            value={q}
            onChange={setQ}
            className="min-w-0 flex-1"
          />
          <IconButton icon="plus" label="Create agent" variant="dark" />
        </>
      ),
      about: <AboutCard icon="notebook-text" title="Agents" body={AGENTS_ABOUT} />,
      categories: (
        <CategoryList
          categories={agentCategories(AGENTS, view)}
          selected={cat}
          onSelect={setCat}
        />
      ),
    },
    grid: {
      title: "Agents",
      left: (
        <Picker
          label="Status"
          variant="white"
          menuWidth={200}
          options={AGENT_FILTERS}
          value={status}
          onChange={(v) => {
            setStatus(v as AgentFilter);
          }}
        />
      ),
      well: "agents",
      body,
    },
  };
}

function useConnect(board: Board) {
  const [cat, setCat] = useState(board.tab === "Connect" ? (board.cat ?? "all") : "all");
  const [status, setStatus] = useState<ConnectFilter>("all");
  const [q, setQ] = useState(board.tab === "Connect" ? (board.query ?? "") : "");
  const [over, setOver] = useState<Readonly<Record<string, ConnectionStatus>>>({});
  const [addedBy, setAddedBy] = useState<Readonly<Record<string, string>>>({});
  const [notify, setNotify] = useState<ReadonlySet<string>>(new Set());
  const [confirm, setConfirm] = useState<CatalogIntegration | null>(null);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
    },
    [],
  );
  const statusOf = (it: CatalogIntegration): ConnectionStatus => over[it.id] ?? it.status;
  const shown = visibleIntegrations(INTEGRATIONS, statusOf, { cat, status, q });
  const catLabel =
    cat === "all"
      ? "any category"
      : connectCategory(cat as Parameters<typeof connectCategory>[0]).label;

  const enable = (it: CatalogIntegration): void => {
    setOver((o) => ({ ...o, [it.id]: "connecting" }));
    timers.current.push(
      setTimeout(() => {
        setOver((o) => ({ ...o, [it.id]: "connected" }));
        setAddedBy((b) => ({ ...b, [it.id]: VIEWER }));
      }, CONNECT_MS),
    );
  };

  const body =
    board.loading === true ? (
      <CatalogGrid label="Integrations" busy>
        {Array.from({ length: skeletons(shown.length) }, (_, i) => (
          <CatalogSkeletonCard key={i} height={212} />
        ))}
      </CatalogGrid>
    ) : shown.length > 0 ? (
      <CatalogGrid label="Integrations">
        {shown.map((it) => {
          const st = statusOf(it);
          const by = addedBy[it.id];
          return (
            <ConnectionTile
              key={it.id}
              name={it.name}
              description={it.text}
              categories={it.cats.map((k) => connectCategory(k).label)}
              tone={connectCategory(it.cats[0]).tone}
              status={st}
              scope={scopeLine(it, st, by)}
              notifying={notify.has(it.id)}
              onEnable={() => {
                enable(it);
              }}
              onDisconnect={() => {
                setConfirm(it);
              }}
              onNotify={() => {
                setNotify((s) => {
                  const n = new Set(s);
                  if (n.has(it.id)) n.delete(it.id);
                  else n.add(it.id);
                  return n;
                });
              }}
            />
          );
        })}
      </CatalogGrid>
    ) : (
      <EmptyState
        icon="search"
        className="min-h-[340px]"
        title="No integrations match"
        action={
          <Button
            variant="secondary"
            size="md"
            onClick={() => {
              setStatus("all");
              setQ("");
            }}
          >
            Clear filters
          </Button>
        }
      >
        {q.trim() === ""
          ? `Nothing in ${catLabel} has that status.`
          : `Nothing in ${catLabel} matches “${q.trim()}”.`}
      </EmptyState>
    );

  const layout: Pick<Parameters<typeof CatalogLayout>[0], "side" | "grid" | "overlay"> = {
    side: {
      about: <AboutCard icon="plug" title="Integrations" body={CONNECT_ABOUT} />,
      categories: (
        <CategoryList
          categories={connectCategories(INTEGRATIONS)}
          selected={cat}
          onSelect={setCat}
        />
      ),
    },
    grid: {
      title: "Integrations",
      left: (
        <Picker
          label="Status"
          variant="white"
          menuWidth={200}
          options={CONNECT_FILTERS}
          value={status}
          onChange={(v) => {
            setStatus(v as ConnectFilter);
          }}
        />
      ),
      right: (
        <SearchField
          label="Search integrations"
          placeholder="Search"
          value={q}
          onChange={setQ}
          className="w-[300px]"
        />
      ),
      well: "connect",
      body,
    },
    overlay: (
      <ConfirmDialog
        open={confirm !== null}
        onOpenChange={(open) => {
          if (!open) setConfirm(null);
        }}
        title={confirm === null ? "" : `Disconnect ${confirm.name}?`}
        confirmLabel="Disconnect"
        onConfirm={() => {
          if (confirm === null) return;
          setOver((o) => ({ ...o, [confirm.id]: "available" }));
        }}
      >
        {confirm === null ? "" : disconnectText(confirm)}
      </ConfirmDialog>
    ),
  };
  return layout;
}

function T5({ board }: { board: Board }): JSX.Element {
  const [tab, setTab] = useState<"Agents" | "Connect">(board.tab);
  const [view, setView] = useState<AgentView>("Library");
  const agents = useAgents({ board, view, setView });
  const connect = useConnect(board);
  const tabs = {
    options: TABS,
    active: tab,
    onChange: (l: string) => {
      if (l === "Agents" || l === "Connect") setTab(l);
    },
  };
  return (
    <Artboard id={board.id} badge={board.badge} name={board.name} note={board.note}>
      {tab === "Agents" ? (
        <CatalogLayout embedded height={860} toolbar={TOOLBAR} tabs={tabs} {...agents} />
      ) : (
        <CatalogLayout embedded height={860} toolbar={TOOLBAR} tabs={tabs} {...connect} />
      )}
    </Artboard>
  );
}

/** One artboard on its own (the tests render a single board). */
export function T5Board({ id }: { id: string }): JSX.Element | null {
  const board = [...T5_BOARDS, ...TPL05_BOARDS].find((b) => b.id === id);
  return board === undefined ? null : <T5 board={board} />;
}

export function T5Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {T5_BOARDS.map((b) => (
        <T5 key={b.id} board={b} />
      ))}
    </div>
  );
}

export function Tpl05Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {TPL05_BOARDS.map((b) => (
        <T5 key={b.id} board={b} />
      ))}
    </div>
  );
}
