import type { FirmTeamOut, StaffRowV2Out } from "@abacus/api-client";
import {
  annualIndependenceOptions,
  firmClientsOptions,
  firmMembersOptions,
  listWallsOptions,
  officesOptions,
  roleTemplatesOptions,
  settingsOverviewOptions,
  staffOptions,
  teamsOptions,
} from "@abacus/api-client/query";
import {
  Button,
  DEFAULT_TZ,
  Dialog,
  EmptyState,
  Icon,
  Segmented,
  isoDate,
  SettingsLayout,
  TallyStrip,
} from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { useCan } from "../../app-core/can";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import { GROUPS } from "../ADM-01/copy";
import { COPY } from "./copy";
import { InviteDrawer, PersonDrawer, detailOf } from "./drawers";
import { Independence } from "./independence";
import { type Adm02Patch, type Adm02Search, type Segment, parseSearch } from "./model";
import { AGENT_KEY, Templates } from "./templates";
import { FilterRow, PeopleTable, tallyItems } from "./users";

// ADM-02 · Users & roles (+ permission matrix) (G-01-T10; G-01 §3.3–3.6; docs/screens/ADM-02.md)
// on the T12 frame, People selected. The form pane holds a list, not a form: the header carries the
// segments (Users · Role templates · Invitations · Independence) and the people actions. Every
// artboard is a data condition of the same screen:
//
//   a  Grace Holloway at E0: 46 rows in six bands, the tallies, filters
//   b  Role templates, Partner highlighted: eight templates, the 16-row grid, the locked agent
//   c  ?ov=invite with every seat held: the amber banner, Send invite off
//   d  ?ov=person:<Lena Park>: her access, wall, assignments and last sign-ins
//   e  Mon Nov 2, 2026: the five seasonal rows "Deactivated Oct 31", 41 of 46
//   f  Mon Jan 5, 2026: Lena Park's invitation pending, "46 of 46 · 1 pending"
//   g  Margaret Okonkwo on Independence: each seat holder's status for the year (DF-07)
//
// What the viewer may do comes from the matrix (`useCan`) and each row's `allowed_actions`, never a
// role comparison (AC11.1). The people list stays on `firm.manage_users` (DEC-286), so a partner
// sees Role templates and Independence only. Names and emails never travel in the URL.

export { parseSearch, type Adm02Search } from "./model";

export interface ADM02Props {
  search: Adm02Search;
  onSearch: (next: Adm02Search) => void;
  /** Another settings section: its route id ("general", "offices", …). */
  onNavigate?: (section: string) => void;
  onBack?: () => void;
}

function StepUp({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.stepUpTitle}
      description={COPY.stepUpBody}
    >
      <div className="flex justify-end gap-2">
        <Button
          variant="secondary"
          onClick={() => {
            onOpenChange(false);
          }}
        >
          {COPY.cancel}
        </Button>
        <Button
          onClick={() => {
            signIn(currentRoute(), { forceLogin: true });
          }}
        >
          {COPY.signInAgain}
        </Button>
      </div>
    </Dialog>
  );
}

const PEOPLE_KEYS = new Set(["staff", "person", "listWalls"]);

export function ADM02({ search, onSearch, onNavigate, onBack }: ADM02Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const when = { now, tz };
  const queryClient = useQueryClient();
  const [stepUp, setStepUp] = useState(false);
  const canManage = useCan("firm.manage_users");
  const canRead = useCan("firm.read_people");
  const canAnnual = useCan("independence.annual_read");
  const canWalls = useCan("wall.list");
  const canPick = useCan("wall.create");

  const overview = useQuery({ ...settingsOverviewOptions(), retry: false });
  // Every row, unfiltered: the segment counts and the firm-wide tallies.
  const everyone = useQuery({ ...staffOptions(), enabled: canManage, retry: false });
  const templates = useQuery({ ...roleTemplatesOptions(), enabled: canRead, retry: false });
  const year = Number(isoDate(now, tz).slice(0, 4));
  const annual = useQuery({
    ...annualIndependenceOptions({ query: { year } }),
    enabled: canAnnual,
    retry: false,
  });
  const offices = useQuery({ ...officesOptions(), retry: false });
  const teams = useQuery({ ...teamsOptions(), retry: false });
  const walls = useQuery({ ...listWallsOptions(), enabled: canWalls, retry: false });
  const clients = useQuery({ ...firmClientsOptions(), enabled: canPick, retry: false });
  const members = useQuery({
    ...firmMembersOptions(),
    enabled: canPick && canAnnual,
    retry: false,
  });

  // A segment shows when its read answers: Users and Invitations need the people list, Role
  // templates `firm.read_people`, Independence its year's read (501 until G-01-T13).
  const available: Segment[] = [
    ...(canManage && !everyone.isError ? (["users"] as const) : []),
    ...(canRead && !templates.isError ? (["templates"] as const) : []),
    ...(canManage && !everyone.isError ? (["invitations"] as const) : []),
    ...(canAnnual && !annual.isError ? (["independence"] as const) : []),
  ];
  const segment: Segment =
    search.segment !== undefined && available.includes(search.segment)
      ? search.segment
      : (available[0] ?? "users");

  const listQuery =
    segment === "invitations"
      ? { status: "invited" as const }
      : {
          ...(search.q === undefined ? {} : { q: search.q }),
          ...(search.role === undefined
            ? {}
            : { role_template: search.role as NonNullable<StaffRowV2Out["role_template"]> }),
          ...(search.office === undefined ? {} : { office_id: search.office }),
          ...(search.team === undefined ? {} : { team_id: search.team }),
          ...(search.status === undefined
            ? {}
            : { status: search.status as StaffRowV2Out["status"] }),
        };
  const list = useQuery({
    ...staffOptions({ query: listQuery }),
    enabled: canManage && (segment === "users" || segment === "invitations"),
    retry: false,
  });

  if (overview.isError) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <EmptyState title={COPY.notAllowed} />
      </div>
    );
  }

  const set = (patch: Adm02Patch): void => {
    const merged: Adm02Patch = { ...search, ...patch };
    onSearch(parseSearch(merged));
  };
  const officeNames = new Map((offices.data ?? []).map((o) => [o.id, o.name]));
  const teamById = new Map<string, FirmTeamOut>((teams.data ?? []).map((t) => [t.id, t]));
  const wallCounts = new Map<string, number>();
  for (const w of walls.data ?? []) {
    if (w.status === "active") wallCounts.set(w.user_id, (wallCounts.get(w.user_id) ?? 0) + 1);
  }
  const tallies = everyone.data?.tallies;
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      predicate: (q) => {
        const head = q.queryKey[0] as { _id?: string } | undefined;
        return head?._id !== undefined && PEOPLE_KEYS.has(head._id);
      },
    });
  };
  const personId = search.ov?.startsWith("person:") === true ? search.ov.slice(7) : null;
  const inviting = search.ov === "invite";
  const listForbidden = detailOf(list.error) === "forbidden";

  const counts: Record<Segment, number | undefined> = {
    users: everyone.data?.total,
    templates: templates.data?.templates.length,
    invitations: tallies?.seats_pending,
    independence: undefined,
  };
  const segments = (
    <Segmented
      label={COPY.segmentsLabel}
      size="small"
      options={available.map((s) => ({
        label: COPY.segments[s],
        ...(counts[s] === undefined ? {} : { count: counts[s] }),
      }))}
      active={COPY.segments[segment]}
      onChange={(label) => {
        const picked = available.find((s) => COPY.segments[s] === label);
        if (picked !== undefined) set({ segment: picked, ov: undefined });
      }}
    />
  );
  const actions = (
    <>
      {PLANNED_VISIBLE && canManage && (
        <Button
          variant="secondary"
          onClick={() => {
            onNavigate?.("plan-usage");
          }}
        >
          {COPY.addSeats}
        </Button>
      )}
      {canManage && (
        <Button
          onClick={() => {
            set({ ov: "invite" });
          }}
        >
          <Icon name="user-plus" size={14} />
          {COPY.invite}
        </Button>
      )}
    </>
  );

  const templateOptions = (templates.data?.templates ?? []).map((t) => ({
    value: t.key,
    label: COPY.templates[t.key].label,
  }));

  let body: JSX.Element;
  if (segment === "templates") {
    body = (
      <Templates
        data={templates.data}
        selected={search.template ?? null}
        onSelect={(key) => {
          set({ template: key === search.template && key !== AGENT_KEY ? undefined : key });
        }}
      />
    );
  } else if (segment === "independence") {
    body = <Independence data={annual.data} members={members.data ?? []} when={when} />;
  } else if (listForbidden) {
    body = (
      <EmptyState title={COPY.stepUpTitle} icon="lock">
        {COPY.stepUpBody}
      </EmptyState>
    );
  } else if (list.isError || everyone.isError) {
    body = <EmptyState title={COPY.error} tone="error" />;
  } else {
    const invitations = segment === "invitations";
    body = (
      <>
        {tallies !== undefined && (
          <div className="px-[16px] pt-[8px]">
            <TallyStrip
              label={COPY.tally.label}
              items={tallyItems(tallies, everyone.data?.items ?? [], when)}
              className="max-w-[1120px]"
            />
          </div>
        )}
        <FilterRow
          search={search}
          onSearch={set}
          offices={offices.data ?? []}
          teams={teams.data ?? []}
          templates={templateOptions.length > 0 ? templateOptions : []}
          count={list.data?.total}
          statusFixed={invitations}
        />
        <PeopleTable
          list={list.data}
          loading={list.isPending}
          offices={officeNames}
          teams={teamById}
          walls={wallCounts}
          when={when}
          onOpen={(row) => {
            if (row.user_id !== null) set({ ov: `person:${row.user_id}` });
          }}
          onClear={() => {
            set({
              q: undefined,
              role: undefined,
              office: undefined,
              team: undefined,
              status: undefined,
            });
          }}
          {...(invitations ? { empty: COPY.invitationsEmpty } : {})}
        />
      </>
    );
  }

  return (
    <SettingsLayout
      bare
      wide
      toolbar={{ nav: [], active: "", firm: "" }}
      title={COPY.title}
      context={overview.data?.firm_name ?? ""}
      backLabel={COPY.back}
      {...(onBack === undefined ? {} : { onBack })}
      navTitle={COPY.navTitle}
      groups={GROUPS.map((g) => ({
        ...g,
        sections: g.sections.filter(
          (s) => s.id === "general" || s.id === "people" || PLANNED_VISIBLE,
        ),
      })).filter((g) => g.sections.length > 0)}
      active="people"
      onSelect={(id) => {
        if (id !== "people") onNavigate?.(id);
      }}
      dirty={false}
      headerCenter={available.length > 0 ? segments : undefined}
      headerActions={actions}
      stepUp={<StepUp open={stepUp} onOpenChange={setStepUp} />}
      overlay={
        <>
          {inviting && (
            <InviteDrawer
              open
              onClose={() => {
                set({ ov: undefined });
              }}
              tallies={tallies}
              offices={offices.data ?? []}
              teams={teams.data ?? []}
              onSent={() => {
                set({ ov: undefined });
                refresh();
              }}
              onStepUp={() => {
                setStepUp(true);
              }}
            />
          )}
          {personId !== null && (
            <PersonDrawer
              key={personId}
              userId={personId}
              onClose={() => {
                set({ ov: undefined });
              }}
              offices={officeNames}
              teams={teamById}
              walls={walls.data ?? []}
              clients={clients.data ?? []}
              when={when}
              onChanged={refresh}
              onStepUp={() => {
                setStepUp(true);
              }}
            />
          )}
        </>
      }
    >
      {body}
    </SettingsLayout>
  );
}

/** ADM-02 holding its own search (the gallery, tests): `initial` is a `?…` string or a search. */
export function PeoplePage({
  initial = {},
  onNavigate,
}: {
  initial?: Adm02Search | string;
  onNavigate?: (section: string) => void;
}): JSX.Element {
  const [search, setSearch] = useState<Adm02Search>(() =>
    typeof initial === "string" ? parseSearch(initial) : initial,
  );
  return (
    <ADM02
      search={search}
      onSearch={setSearch}
      {...(onNavigate === undefined ? {} : { onNavigate })}
    />
  );
}
