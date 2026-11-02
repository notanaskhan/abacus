import { FlagOffState } from "@abacus/ui";
import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { appRoute, lazyScreen } from "../root";

// NOT-01 (N-04-T05; docs/screens/NOT-01.md): `/notices` behind `notices.workspace`; flag off
// renders C-20 and the nav keeps its 13 items (D4). The filters are the search params
// (`agency`, `type`, `assignee`, `respond_by`, `tile`, `q`), so a filtered view is a link.

// The search's words, kept here because routes never reach into a domain (the screen owns the
// filter type and reads these through its props).
const AGENCIES = ["irs", "state"] as const;
const TYPES = ["cp2000", "cp14", "cp501", "state"] as const;
const TILES = ["new", "analyzing", "response_drafted", "awaiting"] as const;
const one = <T extends string>(list: readonly T[], v: unknown): v is T =>
  typeof v === "string" && (list as readonly string[]).includes(v);
const isNoticeAgency = (v: unknown): v is (typeof AGENCIES)[number] => one(AGENCIES, v);
const isNoticeType = (v: unknown): v is (typeof TYPES)[number] => one(TYPES, v);
const isNoticeTile = (v: unknown): v is (typeof TILES)[number] => one(TILES, v);

interface NoticeFilters {
  agency: (typeof AGENCIES)[number] | null;
  type: (typeof TYPES)[number] | null;
  assignee: string | null;
  respondBy: 7 | 30 | null;
  tile: (typeof TILES)[number] | null;
  q: string;
}

const Index = lazyScreen(async () => (await import("../../screens/NOT-01")).NOT01);

interface NoticesSearch {
  agency?: string;
  type?: string;
  assignee?: string;
  respond_by?: number;
  tile?: string;
  q?: string;
}

function validateNoticesSearch(search: Record<string, unknown>): NoticesSearch {
  const text = (v: unknown): string | undefined =>
    typeof v === "string" && v !== "" ? v : undefined;
  const respondBy = Number(search.respond_by);
  const out: NoticesSearch = {};
  if (isNoticeAgency(search.agency)) out.agency = search.agency;
  if (isNoticeType(search.type)) out.type = search.type;
  const assignee = text(search.assignee);
  if (assignee !== undefined) out.assignee = assignee;
  if (respondBy === 7 || respondBy === 30) out.respond_by = respondBy;
  if (isNoticeTile(search.tile)) out.tile = search.tile;
  const q = text(search.q);
  if (q !== undefined) out.q = q;
  return out;
}

function filtersOf(s: NoticesSearch): NoticeFilters {
  return {
    agency: isNoticeAgency(s.agency) ? s.agency : null,
    type: isNoticeType(s.type) ? s.type : null,
    assignee: s.assignee ?? null,
    respondBy: s.respond_by === 7 || s.respond_by === 30 ? s.respond_by : null,
    tile: isNoticeTile(s.tile) ? s.tile : null,
    q: s.q ?? "",
  };
}

function searchOf(f: NoticeFilters): NoticesSearch {
  return {
    ...(f.agency === null ? {} : { agency: f.agency }),
    ...(f.type === null ? {} : { type: f.type }),
    ...(f.assignee === null ? {} : { assignee: f.assignee }),
    ...(f.respondBy === null ? {} : { respond_by: f.respondBy }),
    ...(f.tile === null ? {} : { tile: f.tile }),
    ...(f.q.trim() === "" ? {} : { q: f.q }),
  };
}

export const noticesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/notices",
  validateSearch: validateNoticesSearch,
  component: function NoticesPage(): JSX.Element {
    const search = noticesRoute.useSearch();
    const navigate = noticesRoute.useNavigate();
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate
          flag="notices.workspace"
          fallback={<FlagOffState flag="notices.workspace" label="Notices" />}
        >
          <Index
            filters={filtersOf(search)}
            onFilters={(next) => void navigate({ search: searchOf(next), replace: true })}
          />
        </FeatureGate>
      </div>
    );
  },
});

export const noticeRoutes = [noticesRoute] as const;
