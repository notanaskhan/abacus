import type { EngagementSummaryOut } from "@abacus/api-client";
import {
  listEngagementsOptions,
  searchFindingsOptions,
  searchRequestItemsOptions,
} from "@abacus/api-client/query";
import { CommandPalette, type PaletteGroup, type PaletteItem } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { type JSX, useEffect, useMemo, useState } from "react";

// SPEC-302 (TASK-303): ⌘K jumps across the firm. Engagements filter on the client; request items
// and findings come from the server, walls applied. Recent engagements stay in this browser only.

const RECENT_KEY = "abacus.palette.recent";

const TABS: [string, string][] = [
  ["Overview", ""],
  ["Requests", "/requests"],
  ["Review", "/review"],
  ["Planning", "/planning"],
  ["Fieldwork", "/fieldwork"],
  ["Findings", "/findings"],
  ["People", "/people"],
  ["Activity", "/activity"],
  ["Setup", "/setup"],
];

function readRecent(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    const parsed: unknown = raw === null ? [] : JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function remember(id: string): void {
  try {
    localStorage.setItem(
      RECENT_KEY,
      JSON.stringify([id, ...readRecent().filter((x) => x !== id)].slice(0, 5)),
    );
  } catch {
    // private windows: recent is a convenience
  }
}

/** Matches when every word of the query appears in the text, ignoring case. */
export function matches(text: string, query: string): boolean {
  const hay = text.toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((w) => hay.includes(w));
}

function useDebounced(value: string, ms: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(value);
    }, ms);
    return () => {
      clearTimeout(t);
    };
  }, [value, ms]);
  return debounced;
}

export function Palette({
  isAdmin,
  onNotifications,
}: {
  isAdmin: boolean;
  onNotifications: () => void;
}): JSX.Element {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const path = useRouterState({ select: (r) => r.location.pathname });
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, []);
  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);
  const q = query.trim();
  const debounced = useDebounced(q, 200);
  const remote = open && debounced.length >= 2;
  const engagements = useQuery({ ...listEngagementsOptions(), enabled: open });
  const items = useQuery({
    ...searchRequestItemsOptions({ query: { q: debounced } }),
    enabled: remote,
  });
  const findings = useQuery({
    ...searchFindingsOptions({ query: { q: debounced } }),
    enabled: remote,
  });
  const byId = useMemo(
    () => new Map((engagements.data ?? []).map((e) => [e.id, e])),
    [engagements.data],
  );
  const label = (e: EngagementSummaryOut | undefined): string =>
    e === undefined ? "" : `${e.client_name} · ${e.name}`;
  const go = (to: string): void => {
    void navigate({ to });
  };
  const engagementItem = (e: EngagementSummaryOut): PaletteItem => ({
    id: `e-${e.id}`,
    label: e.client_name,
    hint: `${e.name} · ${e.fiscal_period_end.slice(0, 4)}`,
    run: () => {
      remember(e.id);
      go(`/engagements/${e.id}`);
    },
  });
  const current = /^\/engagements\/([^/]+)/.exec(path)?.[1];
  const here = current === undefined ? undefined : byId.get(current);

  const pages: PaletteItem[] = [
    {
      id: "p-home",
      label: "Engagements",
      run: () => {
        go("/");
      },
    },
    {
      id: "p-clients",
      label: "Clients",
      run: () => {
        go("/clients");
      },
    },
    {
      id: "p-knowledge",
      label: "Knowledge",
      run: () => {
        go("/knowledge");
      },
    },
    ...(isAdmin
      ? [
          {
            id: "p-admin",
            label: "Firm settings",
            run: () => {
              go("/admin/methodology");
            },
          },
        ]
      : []),
    { id: "a-notifications", label: "Open notifications", run: onNotifications },
  ];
  const tabs: PaletteItem[] =
    current === undefined
      ? []
      : TABS.map(([name, suffix]) => ({
          id: `t-${name}`,
          label: name,
          hint: label(here),
          run: () => {
            go(`/engagements/${current}${suffix}`);
          },
        }));

  let groups: PaletteGroup[];
  if (q === "") {
    const recent = readRecent()
      .map((id) => byId.get(id))
      .filter((e): e is EngagementSummaryOut => e !== undefined);
    groups = [
      { label: "Recent", items: recent.map(engagementItem) },
      { label: "This engagement", items: tabs },
      { label: "Go to", items: pages },
    ];
  } else {
    const seen = new Set<string>();
    const clients: PaletteItem[] = [];
    for (const e of engagements.data ?? []) {
      if (seen.has(e.client_id) || !matches(e.client_name, q)) continue;
      seen.add(e.client_id);
      clients.push({
        id: `c-${e.client_id}`,
        label: e.client_name,
        hint: "Client",
        run: () => {
          go(`/clients/${e.client_id}`);
        },
      });
    }
    clients.splice(4);
    const found = (engagements.data ?? [])
      .filter((e) => matches(`${e.client_name} ${e.client_entity_name} ${e.name}`, q))
      .slice(0, 6);
    groups = [
      { label: "Clients", items: clients },
      { label: "Engagements", items: found.map(engagementItem) },
      {
        label: "Request items",
        items: (remote ? (items.data ?? []) : []).map((i) => ({
          id: `i-${i.id}`,
          label: i.description,
          hint: label(byId.get(i.engagement_id)) || i.audit_area,
          run: () => {
            go(`/engagements/${i.engagement_id}/items/${i.id}`);
          },
        })),
      },
      {
        label: "Findings",
        items: (remote ? (findings.data ?? []) : []).map((f) => ({
          id: `f-${f.id}`,
          label: f.title,
          hint: label(byId.get(f.engagement_id)),
          run: () => {
            go(`/engagements/${f.engagement_id}/findings`);
          },
        })),
      },
      { label: "This engagement", items: tabs.filter((t) => matches(t.label, q)) },
      { label: "Go to", items: pages.filter((p) => matches(p.label, q)) },
    ];
  }
  const loading = remote && (items.isFetching || findings.isFetching);
  return (
    <>
      <button
        type="button"
        aria-label="Search (⌘K)"
        onClick={() => {
          setOpen(true);
        }}
        className="flex h-[30px] w-[220px] items-center gap-2 rounded-[7px] bg-nav-fill px-2.5 text-[13px] text-ink-3 hover:text-ink-2"
      >
        <span className="flex-1 text-left">Search</span>
        <kbd className="rounded-[4px] bg-card px-1.5 font-mono text-[11px] shadow-e1">⌘K</kbd>
      </button>
      <CommandPalette
        open={open}
        onOpenChange={setOpen}
        query={query}
        onQueryChange={setQuery}
        groups={groups}
        loading={loading}
        placeholder="Search clients, requests and findings, or jump to a page"
        empty={
          q.length === 1 ? "Keep typing…" : loading ? "Searching…" : `Nothing matches “${q}”.`
        }
      />
    </>
  );
}
