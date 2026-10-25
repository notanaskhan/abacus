// ADM-02a, e, f and the Invitations segment: the tally strip, the filter row and the people table
// (T1 density: th 30, rows 44, hairlines, no zebra) in bands. Every count is the server's: the
// bands' counts are the list's `counts`, the tallies its firm-wide `tallies`.

import type {
  FirmOfficeOut,
  FirmTeamOut,
  StaffListOut,
  StaffRowV2Out,
  StaffTalliesOut,
} from "@abacus/api-client";
import {
  EmptyState,
  FilterChip,
  Icon,
  RegistryStatus,
  SearchField,
  SkeletonRows,
  type TallyItem,
} from "@abacus/ui";
import type { JSX } from "react";
import { COPY } from "./copy";
import { type Adm02Patch, type Adm02Search, dayOf, initialsOf, lastActiveText } from "./model";

interface When {
  now: Date;
  tz: string;
}

/** The five tally cards (ADM-02a): SEATS · ROLES · SIGN-IN · WALLS · SEASONAL. */
export function tallyItems(
  t: StaffTalliesOut,
  rows: readonly StaffRowV2Out[],
  when: When,
): TallyItem[] {
  const total = t.seats_total ?? 0;
  const seats: TallyItem = {
    label: COPY.tally.seats,
    value: COPY.tally.seatsValue(t.seats_used, total, t.seats_pending),
    ...(total > 0 && t.seats_used >= total
      ? { pill: { text: COPY.tally.full, variant: "amber" as const } }
      : {}),
  };
  const items: TallyItem[] = [
    seats,
    {
      label: COPY.tally.roles,
      value: COPY.tally.rolesValue(t.partners, t.professionals, t.operations),
    },
    {
      label: COPY.tally.signIn,
      pill: {
        text: COPY.tally.signInValue(t.sso_mfa, t.signed_in_of),
        variant: "green",
        check: true,
      },
    },
  ];
  if (t.walls_active !== null && t.walls_active !== undefined) {
    items.push({ label: COPY.tally.walls, value: COPY.tally.wallsValue(t.walls_active) });
  }
  if (t.seasonal > 0 && t.seasonal_access_ends_on != null) {
    items.push({
      label: COPY.tally.seasonal,
      value: COPY.tally.seasonalValue(t.seasonal, dayOf(t.seasonal_access_ends_on, when)),
    });
  } else {
    // ADM-02e: the seasonal band ended together; the strip says so from the rows' own dates.
    const ended = rows.filter((r) => r.band === "seasonal" && r.deactivated_on != null);
    const on = ended[0]?.deactivated_on;
    if (on != null && ended.every((r) => r.deactivated_on === on)) {
      items.push({
        label: COPY.tally.seasonal,
        value: COPY.tally.seasonalEnded(ended.length, dayOf(on, when)),
      });
    }
  }
  return items;
}

export interface FilterRowProps {
  search: Adm02Search;
  onSearch: (patch: Adm02Patch) => void;
  offices: readonly FirmOfficeOut[];
  teams: readonly FirmTeamOut[];
  templates: readonly { value: string; label: string }[];
  /** "46 people" */
  count: number | undefined;
  /** The Invitations segment fixes the status. */
  statusFixed?: boolean;
}

export function FilterRow({
  search,
  onSearch,
  offices,
  teams,
  templates,
  count,
  statusFixed = false,
}: FilterRowProps): JSX.Element {
  return (
    <div className="flex flex-wrap items-center gap-[8px] px-[16px] py-[8px]">
      <SearchField
        label={COPY.search}
        placeholder={COPY.search}
        clearLabel={COPY.clear}
        value={search.q ?? ""}
        onChange={(q) => {
          onSearch({ q: q === "" ? undefined : q });
        }}
        className="w-[220px]"
      />
      <FilterChip
        label={COPY.chips.role}
        icon="shield"
        options={templates}
        value={search.role ?? null}
        placeholder={COPY.chips.all}
        clearLabel={COPY.chips.all}
        onChange={(role) => {
          onSearch({ role: role ?? undefined });
        }}
      />
      <FilterChip
        label={COPY.chips.office}
        icon="map-pin"
        options={offices.map((o) => ({ value: o.id, label: o.name }))}
        value={search.office ?? null}
        placeholder={COPY.chips.allOffices}
        clearLabel={COPY.chips.allOffices}
        onChange={(office) => {
          onSearch({ office: office ?? undefined });
        }}
      />
      <FilterChip
        label={COPY.chips.team}
        icon="users-round"
        options={teams.map((t) => ({ value: t.id, label: t.name }))}
        value={search.team ?? null}
        placeholder={COPY.chips.all}
        clearLabel={COPY.chips.all}
        onChange={(team) => {
          onSearch({ team: team ?? undefined });
        }}
      />
      {!statusFixed && (
        <FilterChip
          label={COPY.chips.status}
          icon="circle"
          options={[
            { value: "active", label: COPY.statuses.active },
            { value: "invited", label: COPY.statuses.invited },
            { value: "deactivated", label: COPY.statuses.deactivated },
          ]}
          value={search.status ?? null}
          placeholder={COPY.chips.all}
          clearLabel={COPY.chips.all}
          onChange={(status) => {
            onSearch({ status: status ?? undefined });
          }}
        />
      )}
      <span className="flex-1" />
      {count !== undefined && <span className="text-body text-ink-3">{COPY.count(count)}</span>}
    </div>
  );
}

export interface PeopleTableProps {
  list: StaffListOut | undefined;
  loading: boolean;
  offices: ReadonlyMap<string, string>;
  teams: ReadonlyMap<string, FirmTeamOut>;
  /** Walls per user id, from the register; absent when it can't be read (never a count). */
  walls: ReadonlyMap<string, number>;
  when: When;
  onOpen: (row: StaffRowV2Out) => void;
  onClear: () => void;
  empty?: string;
}

const BAND_ORDER = ["partners", "managers", "seniors", "staff", "seasonal", "operations"] as const;

function TeamCell({
  row,
  teams,
  walls,
}: {
  row: StaffRowV2Out;
  teams: ReadonlyMap<string, FirmTeamOut>;
  walls: number;
}): JSX.Element {
  const own = (row.team_ids ?? []).map((id) => teams.get(id)).filter((t) => t !== undefined);
  const lines = own.filter((t) => t.kind === "service_line").map((t) => t.name);
  const groups = own.filter((t) => t.kind !== "service_line").map((t) => t.name);
  return (
    <span className="flex flex-wrap items-center gap-x-[6px] gap-y-[2px]">
      <span>{lines.join(" · ") || COPY.none}</span>
      {groups.length > 0 && (
        <span className="text-meta text-ink-3">{`· ${groups.join(" · ")}`}</span>
      )}
      {walls > 0 && (
        <span className="inline-flex h-[18px] items-center rounded-pill bg-nested px-[7px] text-micro text-ink-2 inset-shadow-hair">
          {COPY.wallTag(walls)}
        </span>
      )}
    </span>
  );
}

function StatusMark({ row, when }: { row: StaffRowV2Out; when: When }): JSX.Element | null {
  if (row.status === "invited" && row.invitation_expires_on != null) {
    return (
      <RegistryStatus
        object="invitation"
        code="invited"
        vars={{ date: dayOf(row.invitation_expires_on, when) }}
      />
    );
  }
  if (row.status === "deactivated" && row.deactivated_on != null) {
    return (
      <RegistryStatus
        object="invitation"
        code="deactivated"
        vars={{ date: dayOf(row.deactivated_on, when) }}
      />
    );
  }
  return null;
}

export function PeopleTable({
  list,
  loading,
  offices,
  teams,
  walls,
  when,
  onOpen,
  onClear,
  empty = COPY.empty,
}: PeopleTableProps): JSX.Element {
  if (loading || list === undefined) {
    return <SkeletonRows type="table" />;
  }
  if (list.items.length === 0) {
    return (
      <EmptyState
        title={empty}
        {...(empty === COPY.empty
          ? {
              action: (
                <button
                  type="button"
                  onClick={onClear}
                  className="text-body font-medium text-ink hover:underline"
                >
                  {COPY.clearFilters}
                </button>
              ),
            }
          : {})}
      />
    );
  }
  const counts = list.counts ?? {};
  return (
    <table aria-label={COPY.table} className="w-full border-collapse text-left text-body">
      <thead className="sticky top-0 z-[1]">
        <tr>
          {[
            [COPY.columns.name, "w-[270px] pl-[16px]"],
            [COPY.columns.role, "w-[190px]"],
            [COPY.columns.office, "w-[100px]"],
            [COPY.columns.team, ""],
            [COPY.columns.signIn, "w-[130px]"],
            [COPY.columns.lastActive, "w-[120px]"],
          ].map(([label, width]) => (
            <th
              key={label}
              scope="col"
              className={`h-[30px] bg-band-hd px-[8px] text-th font-normal whitespace-nowrap text-ink-2 hairline-b ${width ?? ""}`}
            >
              {label}
            </th>
          ))}
          <th scope="col" className="h-[30px] w-[36px] bg-band-hd hairline-b">
            <span className="sr-only">{COPY.columns.more}</span>
          </th>
        </tr>
      </thead>
      {BAND_ORDER.map((band) => {
        const rows = list.items.filter((r) => r.band === band);
        if (rows.length === 0) return null;
        return (
          <tbody key={band} data-band={band}>
            <tr>
              <th
                scope="colgroup"
                colSpan={7}
                className="h-[24px] bg-band-hd px-[16px] text-left hairline-b"
              >
                <span className="flex items-center justify-between text-group-row text-ink-3 uppercase">
                  <span>{COPY.bands[band]}</span>
                  <span className="font-normal tabular-nums">{String(counts[band] ?? 0)}</span>
                </span>
              </th>
            </tr>
            {rows.map((row) => {
              const key = row.user_id ?? row.invitation_id ?? row.email;
              const active = row.status === "active";
              return (
                <tr
                  key={key}
                  data-person={row.display_name}
                  className="cursor-pointer hover:bg-nav-fill"
                  onClick={() => {
                    onOpen(row);
                  }}
                >
                  <td className="h-[44px] py-[5px] pr-[8px] pl-[16px] hairline-b">
                    <span className="flex items-center gap-[8px]">
                      <span
                        aria-hidden="true"
                        className="inline-flex size-[20px] flex-none items-center justify-center rounded-full bg-chip text-micro text-ink-2"
                      >
                        {initialsOf(row.display_name)}
                      </span>
                      <span className="flex min-w-0 flex-col">
                        <span className="flex items-center gap-[6px]">
                          <button
                            type="button"
                            aria-label={COPY.openPerson(row.display_name)}
                            onClick={(e) => {
                              e.stopPropagation();
                              onOpen(row);
                            }}
                            className="truncate text-left font-medium text-ink hover:underline"
                          >
                            {row.display_name}
                          </button>
                          <StatusMark row={row} when={when} />
                        </span>
                        <span className="truncate text-meta text-ink-3">{row.email}</span>
                      </span>
                    </span>
                  </td>
                  <td className="px-[8px] py-[5px] hairline-b">
                    <span className="flex flex-col">
                      <span>{COPY.templates[row.role_template].label}</span>
                      {row.title != null && row.title !== "" && (
                        <span className="text-meta text-ink-3">{row.title}</span>
                      )}
                    </span>
                  </td>
                  <td className="px-[8px] py-[5px] hairline-b">
                    {row.office_id == null ? COPY.none : (offices.get(row.office_id) ?? COPY.none)}
                  </td>
                  <td className="px-[8px] py-[5px] hairline-b">
                    <TeamCell
                      row={row}
                      teams={teams}
                      walls={row.user_id === null ? 0 : (walls.get(row.user_id) ?? 0)}
                    />
                  </td>
                  <td className="px-[8px] py-[5px] hairline-b">
                    {active ? (
                      <span
                        aria-label={COPY.ssoChecked}
                        className="inline-flex items-center gap-[4px] text-dense text-green-ink"
                      >
                        {COPY.sso}
                        <Icon name="check" size={12} />
                      </span>
                    ) : (
                      <span className="text-ink-4">{COPY.none}</span>
                    )}
                  </td>
                  <td className="px-[8px] py-[5px] text-dense text-ink-2 hairline-b">
                    {active ? lastActiveText(row.last_sign_in_at, when) : COPY.none}
                  </td>
                  <td className="px-[4px] py-[5px] text-center hairline-b">
                    <Icon name="ellipsis" size={14} className="text-ink-3" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        );
      })}
    </table>
  );
}
