// SHL-02 "Go…" (P-02-T10; docs/screens/SHL-02.md; C15 v1). The firm's palette over the O5 frame
// (`variant="go"`: 640 wide, 88 from the top, 40-high rows): groups in canonical order from
// `POST /v1/search`, each row's type, title with the matched words at 500, its context after "·"
// and the owner's C2 status word; with nothing typed, Recent and Create; `>` lists installed
// agents while `search.agent_mode` is on (literal text otherwise). ↑ ↓ move, ↵ opens, ⌘↵ / Ctrl+↵
// opens in a new tab and keeps the palette open, Escape closes and focus returns to Go….
// The server applies walls and `visible()`: there is never a note, glyph or count of what was left
// out (DEC-43). Planned targets are hidden in production builds (chapter 04 §2.1 rule 4).
import type { SearchItemOut, SearchResultsOut } from "@abacus/api-client";
import { CommandPalette, type PaletteGroup, type PaletteItem, registryWord } from "@abacus/ui";
import { type JSX, useMemo, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { type SearchGroup, useFirmSearch, useRecents, useRecordRecent } from "../../domain/search";
import { MANIFEST } from "../../routes/manifest";
import { COPY } from "./copy";

// The C2 object each result type's status code belongs to (docs/screens/SHL-02.md "Status").
const STATUS_OBJECT: Readonly<Record<string, string>> = {
  tax_return: "return",
  binder: "binder",
  document: "document",
  inbox_thread: "inbox_item",
  assurance: "audit_engagement",
  close: "close",
  workbench_session: "workbench_session",
  todo: "todo",
};
// Screens with no path open as an overlay over the current route.
const OVERLAY: Readonly<Record<string, (params: Record<string, string>) => string>> = {
  "SHL-17": (p) => `?ov=todos:${p.todoId ?? ""}`,
};

type Manifest = Record<string, { status: string; path: string | null }>;

/** Where a row opens, or null when its screen is planned and this is a production build. */
export function hrefOf(screen: string, params: Record<string, string>): string | null {
  const entry = (MANIFEST as unknown as Manifest)[screen];
  if (entry === undefined) return null;
  if (entry.status === "planned" && !PLANNED_VISIBLE) return null;
  const overlay = OVERLAY[screen];
  if (overlay !== undefined) return overlay(params);
  if (entry.path === null) return null;
  return entry.path.replace(/\$(\w+)/gu, (_m, name: string) =>
    encodeURIComponent(params[name] ?? ""),
  );
}

function statusWord(item: SearchItemOut): string | null {
  if (item.status == null) return null;
  const object = STATUS_OBJECT[item.object_type];
  if (object === undefined) return null;
  const word = registryWord(object as Parameters<typeof registryWord>[0], item.status.code).label;
  const context = item.status.context;
  return context == null
    ? word
    : `${word} · ${context.charAt(0).toUpperCase()}${context.slice(1)}`;
}

/** P-02-T10 rest (DEC-4631): the actions bound to the top Clients result, last in the canonical
 * order; none when no client matched, and each hidden while its target screen is planned in a
 * production build (the server still refuses anything the viewer may not do). */
export function contextActions(
  data: SearchResultsOut | undefined,
  onOpen: (href: string, newTab: boolean) => void,
): PaletteItem[] {
  const client = data?.groups.find((g) => g.group === "clients")?.items[0];
  if (client === undefined) return [];
  return COPY.contextActions
    .filter((a) => hrefOf(a.screen, {}) !== null)
    .map<PaletteItem>((a) => {
      const href = a.href(client.object_id);
      return {
        id: `action:${a.id}:${client.object_id}`,
        label: a.label(client.title),
        run: () => {
          onOpen(href, false);
        },
        runNewTab: () => {
          onOpen(href, true);
        },
      };
    });
}

export interface GoProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Open an href in this tab (the router) or, `newTab`, in a new one. */
  onOpen: (href: string, newTab: boolean) => void;
  /** The platform's footer words (macOS ⌘↵, others Ctrl+↵). */
  mac?: boolean;
}

export function Go({ open, onOpenChange, onOpen, mac = true }: GoProps): JSX.Element {
  const [query, setQuery] = useState("");
  const agentMode = useFlag("search.agent_mode") === true;
  const agents = agentMode && query.startsWith(">");
  const text = agents ? query.slice(1).trim() : query.trim();
  const types: SearchGroup[] | null = agents ? ["agents"] : null;
  const results = useFirmSearch(text, types, open);
  const recents = useRecents(open && query.trim() === "");
  const record = useRecordRecent();

  const row = (item: SearchItemOut): PaletteItem | null => {
    const href = hrefOf(item.target.screen_id, item.target.params);
    if (href === null) return null;
    const word = statusWord(item);
    return {
      id: `${item.object_type}:${item.object_id}`,
      label: item.title,
      context: item.context ?? null,
      ranges: item.match_ranges as [number, number][],
      ...(word === null ? {} : { status: <span className="text-meta text-ink-3">{word}</span> }),
      run: () => {
        record(item.object_type, item.object_id);
        onOpen(href, false);
      },
      runNewTab: () => {
        record(item.object_type, item.object_id);
        onOpen(href, true);
      },
    };
  };

  const groups = useMemo<PaletteGroup[]>(() => {
    if (query.trim() === "") {
      const recent = (recents.data?.items ?? [])
        .map(row)
        .filter((r): r is PaletteItem => r !== null);
      const create = COPY.create
        .filter((c) => hrefOf(c.screen, {}) !== null)
        .map<PaletteItem>((c) => ({
          id: `create:${c.id}`,
          label: c.label,
          run: () => {
            onOpen(c.href, false);
          },
        }));
      return [
        { label: COPY.groups.recent, items: recent },
        { label: COPY.groups.create, items: create },
      ];
    }
    const data: SearchResultsOut | undefined = results.data;
    const found = (data?.groups ?? []).map((g) => ({
      label: COPY.groups[g.group as keyof typeof COPY.groups],
      items: g.items.map(row).filter((r): r is PaletteItem => r !== null),
    }));
    const actions = contextActions(data, onOpen);
    return actions.length === 0
      ? found
      : [...found, { label: COPY.groups.actions, items: actions }];
    // `row` reads `record` and `onOpen`, both stable for the palette's life.
  }, [query, recents.data, results.data]);

  const suggestion = results.data?.suggestion;
  const empty = results.isError ? (
    <span data-shl02="error">{COPY.error}</span>
  ) : (
    <div data-shl02="empty" className="flex flex-col items-center gap-[6px]">
      <span>{COPY.empty(text)}</span>
      <span className="text-meta text-ink-3">{COPY.emptyHint}</span>
      {suggestion != null && (
        <button
          type="button"
          className="text-body text-ink underline"
          onClick={() => {
            const href = hrefOf(suggestion.target.screen_id, suggestion.target.params);
            if (href !== null) onOpen(href, false);
          }}
        >
          {COPY.suggestion(suggestion.title, suggestion.context ?? null)}
        </button>
      )}
    </div>
  );

  return (
    <CommandPalette
      variant="go"
      title={COPY.title}
      open={open}
      onOpenChange={(next) => {
        if (!next) setQuery("");
        onOpenChange(next);
      }}
      query={query}
      onQueryChange={setQuery}
      groups={groups}
      loading={results.isFetching}
      placeholder={COPY.placeholder}
      empty={empty}
      hints={mac ? COPY.hints.mac : COPY.hints.other}
      {...(results.data === undefined
        ? {}
        : { liveText: COPY.results(results.data.total_visible) })}
    />
  );
}
