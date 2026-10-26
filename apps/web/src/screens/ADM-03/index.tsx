import type {
  FirmOfficeIn,
  FirmOfficeOut,
  FirmTeamOut,
  ServiceLinePolicyOut,
  WallOut,
} from "@abacus/api-client";
import {
  firmClientsOptions,
  firmMembersOptions,
  listWallsOptions,
  offshoreOptions,
  officesOptions,
  serviceLinesOptions,
  setServiceLineMutation,
  settingsOverviewOptions,
  staffOptions,
  teamsOptions,
  updateOfficeMutation,
} from "@abacus/api-client/query";
import {
  Button,
  Count,
  DEFAULT_TZ,
  Dialog,
  EmptyState,
  Fieldset,
  FieldsetAdd,
  Icon,
  Menu,
  SettingsLayout,
  SettingsLock,
  ValueRow,
  date,
  toast,
  useReducedMotion,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useEffect, useRef, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { useCan } from "../../app-core/can";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import { GROUPS } from "../ADM-01/copy";
import { COPY, type Line } from "./copy";
import {
  type Adm03Patch,
  type Adm03Search,
  type Names,
  anchorOf,
  initialsOf,
  namesOf,
  overlayOf,
  parseSearch,
  poolText,
} from "./model";
import { NewWallSheet, WallLogDrawer, WallsFieldset, detailOf } from "./walls";

// ADM-03 · Offices, teams, walls & offshore (G-01-T14; G-01 §3.7–3.11; docs/screens/ADM-03.md) on
// the T12 frame, Offices & teams selected. Every artboard is a data condition of one screen:
//
//   a  Grace Holloway at E0, Chicago expanded: Save disabled
//   b  ?ov=wall:new with Lena Park ✕ Ashford: reason, effects from the preview, the approver
//   c  the sheet with Neil Ashcroft ✕ Ashford: the preview's `relationship_partner`, Save off
//   d  Remy Vidal in the offshore group: the amber banner, the two locked toggles
//   e  Daniel Reyes (partner): A, B, service lines and D locked under the banner; walls keep
//      "+ Wall" and each row's Approve or Lift where its `allowed_actions` say (AC11.2)
//   f  #walls at 9:20 AM: the wall just added tinted for 2 s (none under reduced motion)
//   g  ?ov=wall:<id>: the wall's log from `GET /v1/walls/{id}/events`
//   h  Tax narrowed to "Engagement team only": the amber confirm row, Save enabled
//
// Offices and service lines save together (Save: `PATCH /v1/firm/offices/{id}` and
// `PUT /v1/firm/service-lines/{line}`, each with the version read; a stale second factor opens the
// step-up). What the viewer may do comes from the matrix (`useCan`) and each wall's
// `allowed_actions`, never a role comparison (AC11.1). No count anywhere is derived from walls.

export { parseSearch, type Adm03Search } from "./model";

export interface ADM03Props {
  search: Adm03Search;
  onSearch: (next: Adm03Search) => void;
  /** "walls" or "offshore": scrolled into view on open (`#walls`, `#offshore`). */
  anchor?: string;
  /** Another settings section: its route id ("general", "people", …). */
  onNavigate?: (section: string) => void;
  /** ADM-02 filtered to an office or a team ("22 seats", a team's chips). */
  onOpenPeople?: (filter: { office?: string; team?: string }) => void;
  onBack?: () => void;
}

type OfficeEdit = Partial<Pick<FirmOfficeIn, "time_zone" | "lead_user_id" | "code">>;
const TINT_MS = 2000;
// A wall added within this long before the screen opened is "just added" (ADM-03f).
const JUST_ADDED_MS = 60_000;

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

/** Up to six 20px initials chips, overlapping, then "+n" (ADM-03 B). */
function Chips({ ids, names, label }: { ids: readonly string[]; names: Names; label: string }) {
  const shown = ids.slice(0, 6);
  return (
    <span role="img" aria-label={label} className="inline-flex items-center">
      {shown.map((id) => (
        <span
          key={id}
          aria-hidden="true"
          className="-ml-[6px] inline-flex size-[20px] items-center justify-center rounded-full bg-chip text-micro text-ink-2 ring-[1.5px] ring-card first:ml-0"
        >
          {initialsOf(names.get(id) ?? "")}
        </span>
      ))}
      {ids.length > shown.length && (
        <span
          aria-hidden="true"
          className="-ml-[6px] inline-flex h-[20px] items-center rounded-pill bg-chip px-[6px] text-micro text-ink-2 ring-[1.5px] ring-card"
        >
          {COPY.more(ids.length - shown.length)}
        </span>
      )}
    </span>
  );
}

function OfficeRows({
  office,
  edit,
  readOnly,
  expanded,
  names,
  members,
  pool,
  onToggle,
  onEdit,
  onSeats,
}: {
  office: FirmOfficeOut;
  edit: OfficeEdit;
  readOnly: boolean;
  expanded: boolean;
  names: Names;
  members: readonly { value: string; label: string }[];
  pool: string | undefined;
  onToggle: () => void;
  onEdit: (edit: OfficeEdit) => void;
  onSeats: () => void;
}): JSX.Element {
  const returns = office.facts?.returns;
  const value = <K extends keyof OfficeEdit>(key: K): OfficeEdit[K] | FirmOfficeOut[K] =>
    key in edit ? edit[key] : office[key];
  const address = [
    office.address_line1,
    office.address_line2,
    office.city,
    [office.region_code, office.postal_code]
      .filter((x) => x !== null && x !== undefined)
      .join(" "),
  ]
    .filter((x) => typeof x === "string" && x !== "")
    .join(", ");
  const lead = value("lead_user_id") ?? undefined;
  return (
    <>
      <div className="flex min-h-[34px] items-center gap-[8px] bg-nested pr-[12px] pl-[8px] text-body">
        <button
          type="button"
          aria-expanded={expanded}
          aria-label={COPY.officeToggle(office.name)}
          className="inline-flex min-w-0 flex-1 items-center gap-[6px] text-left font-medium"
          onClick={onToggle}
        >
          <Icon
            name={expanded ? "chevron-down" : "chevron-right"}
            size={12}
            className="text-ink-3"
          />
          {COPY.officeName(office.name, office.is_hq)}
        </button>
        <span className="text-meta">
          <button
            type="button"
            aria-label={COPY.openSeats(office.name)}
            className="text-ink hover:underline"
            onClick={onSeats}
          >
            {COPY.officeSeats(office.seats)}
          </button>
          {returns !== undefined && (
            <span className="text-ink-3"> {COPY.officeReturns(returns, office.is_hq)}</span>
          )}
        </span>
      </div>
      {expanded && (
        <div className="divide-y-[0.5px] divide-hair motion-safe:animate-[ac-reveal_340ms_ease-out]">
          <ValueRow kind="value" label={COPY.rows.address} indented readOnly={readOnly}>
            {address}
          </ValueRow>
          <ValueRow
            kind="select"
            label={COPY.rows.timeZone}
            indented
            readOnly={readOnly}
            value={value("time_zone") ?? ""}
            options={COPY.timeZones}
            onChange={(next) => {
              onEdit({ time_zone: next });
            }}
          />
          <ValueRow
            kind="select"
            label={COPY.rows.lead}
            indented
            readOnly={readOnly}
            {...(lead === undefined ? {} : { value: lead })}
            options={
              members.some((m) => m.value === lead) || lead === undefined
                ? members
                : [...members, { value: lead, label: names.get(lead) ?? "" }]
            }
            onChange={(next) => {
              onEdit({ lead_user_id: next });
            }}
          />
          <ValueRow
            kind="text"
            label={COPY.rows.code}
            indented
            readOnly={readOnly}
            help={COPY.codeHelp}
            value={value("code") ?? ""}
            onChange={(text) => {
              onEdit({ code: text.toUpperCase() });
            }}
          />
          {pool !== undefined && (
            <ValueRow kind="value" label={COPY.rows.pool} indented readOnly={readOnly}>
              {pool}
            </ValueRow>
          )}
        </div>
      )}
    </>
  );
}

function TeamRow({
  team,
  names,
  help,
  onOpen,
}: {
  team: FirmTeamOut;
  names: Names;
  help?: string;
  onOpen: () => void;
}): JSX.Element {
  const name = COPY.teamNames[team.name] ?? team.name;
  return (
    <div className="px-[12px] py-[7px] text-body">
      <div className="grid grid-cols-[minmax(0,320px)_1fr_auto] items-center gap-[10px]">
        <span>{name}</span>
        <button
          type="button"
          className="inline-flex justify-self-start"
          onClick={onOpen}
          aria-label={COPY.members(name)}
        >
          <Chips ids={team.member_ids} names={names} label={COPY.members(name)} />
        </button>
        <Count value={team.member_ids.length} />
      </div>
      {help !== undefined && <p className="pt-[4px] text-meta text-ink-3">{help}</p>}
    </div>
  );
}

function LinesFieldset({
  lines,
  edits,
  readOnly,
  names,
  onEdit,
}: {
  lines: readonly ServiceLinePolicyOut[];
  edits: Partial<Record<Line, ServiceLinePolicyOut["content_visible_to"]>>;
  readOnly: boolean;
  names: Names;
  onEdit: (line: Line, to: ServiceLinePolicyOut["content_visible_to"]) => void;
}): JSX.Element {
  const narrowed = lines.filter(
    (l) =>
      l.content_visible_to === "service_line" && edits[l.service_line] === "engagement_team_only",
  );
  return (
    <Fieldset
      title={COPY.fieldsets.lines}
      flush
      className="mb-0"
      {...(readOnly
        ? { action: <SettingsLock /> }
        : PLANNED_VISIBLE
          ? { action: <FieldsetAdd disabled>{COPY.adds.line}</FieldsetAdd> }
          : {})}
    >
      <table aria-label={COPY.fieldsets.lines} className="w-full border-collapse text-body">
        <thead>
          <tr className="h-[30px] bg-band-hd text-th text-ink-2">
            {COPY.lines.columns.map((c) => (
              <th key={c} scope="col" className="px-[12px] text-left font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lines.map((l) => {
            const audit = l.service_line === "audit";
            const to = edits[l.service_line] ?? l.content_visible_to;
            const label =
              COPY.lines.visibility.find((v) => v.value === to)?.label ??
              COPY.lines.visibility[0].label;
            return (
              <tr
                key={l.service_line}
                data-line={l.service_line}
                className="h-[40px] border-t-[0.5px] border-hair"
              >
                <th scope="row" className="px-[12px] text-left font-normal">
                  {COPY.lines.names[l.service_line]}
                </th>
                <td className="px-[12px]">{names.get(l.lead_user_id ?? "") ?? ""}</td>
                <td className="px-[12px]">
                  {audit || readOnly ? (
                    <span className="inline-flex items-center gap-[5px] font-medium">
                      {label}
                      {audit && (
                        <Icon
                          name="lock"
                          size={12}
                          label={COPY.lines.locked}
                          className="text-ink-4"
                        />
                      )}
                    </span>
                  ) : (
                    <Menu
                      label={`${COPY.lines.columns[2]}: ${COPY.lines.names[l.service_line]}`}
                      align="start"
                      sections={[
                        COPY.lines.visibility.map((v) => ({
                          label: v.label,
                          checked: v.value === to,
                          onSelect: () => {
                            onEdit(l.service_line, v.value);
                          },
                        })),
                      ]}
                      trigger={
                        <button
                          type="button"
                          aria-label={`${COPY.lines.names[l.service_line]}: ${label}`}
                          className="inline-flex min-h-[26px] items-center gap-[5px] rounded-sheet pr-[2px] font-medium hover:bg-nav-fill"
                        >
                          {label}
                          <Icon name="chevrons-up-down" size={12} className="text-ink-3" />
                        </button>
                      }
                    />
                  )}
                </td>
                <td className="px-[12px] text-ink-2">
                  {audit
                    ? COPY.lines.auditCrossLine
                    : (COPY.lines.crossLine[l.cross_line_access] ?? "")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {narrowed.map((l) => (
        <p
          key={l.service_line}
          role="status"
          className="bg-amber-tint px-[12px] py-[9px] text-body text-amber-ink"
        >
          {COPY.lines.narrowed[l.service_line]}
        </p>
      ))}
      <p className="bg-nested px-[12px] py-[9px] text-body">{COPY.lines.example}</p>
      <p className="px-[12px] py-[8px] text-meta text-ink-3">{COPY.lines.helper}</p>
    </Fieldset>
  );
}

export function ADM03({
  search,
  onSearch,
  anchor,
  onNavigate,
  onOpenPeople,
  onBack,
}: ADM03Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const when = { now, tz };
  const reduced = useReducedMotion();
  const queryClient = useQueryClient();
  const [stepUp, setStepUp] = useState(false);
  const [offices, setOffices] = useState<Record<string, OfficeEdit>>({});
  const [lineEdits, setLineEdits] = useState<
    Partial<Record<Line, ServiceLinePolicyOut["content_visible_to"]>>
  >({});
  const [tinted, setTinted] = useState<ReadonlySet<string>>(new Set());
  const opened = useRef(now.getTime());
  const canManage = useCan("org_structure.manage");
  const canLines = useCan("service_line_policy.manage");
  const canWalls = useCan("wall.list");
  const canWall = useCan("wall.create");
  const canPeople = useCan("firm.manage_users");

  const overview = useQuery({ ...settingsOverviewOptions(), retry: false });
  const officeList = useQuery({ ...officesOptions(), retry: false });
  const teams = useQuery({ ...teamsOptions(), retry: false });
  const lines = useQuery({ ...serviceLinesOptions(), retry: false });
  const offshore = useQuery({ ...offshoreOptions(), retry: false });
  const walls = useQuery({ ...listWallsOptions(), enabled: canWalls, retry: false });
  const members = useQuery({ ...firmMembersOptions(), enabled: canWall, retry: false });
  const clients = useQuery({ ...firmClientsOptions(), retry: false });
  const staff = useQuery({ ...staffOptions(), enabled: canPeople, retry: false });
  const saveOffice = useMutation(updateOfficeMutation());
  const saveLine = useMutation(setServiceLineMutation());

  // The names the rows show: the people list where the viewer may read it, else the members.
  const names: Names = namesOf([
    ...(members.data ?? []),
    ...(staff.data?.items ?? []).flatMap((r) =>
      r.user_id === null ? [] : [{ user_id: r.user_id, display_name: r.display_name }],
    ),
  ]);
  const clientNames = new Map((clients.data ?? []).map((c) => [c.client_id, c.name]));
  const officeNames = new Map((officeList.data ?? []).map((o) => [o.id, o.name]));

  // ADM-03f: a wall just added is tinted for two seconds (still under reduced motion, no fade).
  useEffect(() => {
    const fresh = (walls.data ?? []).filter(
      (w) => Math.abs(opened.current - Date.parse(w.created_at)) <= JUST_ADDED_MS,
    );
    if (fresh.length === 0) return undefined;
    setTinted(new Set(fresh.map((w) => w.id)));
    const timer = window.setTimeout(() => {
      setTinted(new Set());
    }, TINT_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [walls.data]);

  // `#walls`, `#offshore`: the fieldset scrolled into view once its data is there.
  const scrolled = useRef(false);
  useEffect(() => {
    if (anchor === undefined || scrolled.current) return;
    const target = document.getElementById(anchor);
    if (target === null) return;
    scrolled.current = true;
    // jsdom draws no layout and has no scrollIntoView.
    (target as Partial<HTMLElement>).scrollIntoView?.({
      block: "start",
      behavior: reduced ? "auto" : "smooth",
    });
  });

  if (overview.isError) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <EmptyState title={COPY.notAllowed} />
      </div>
    );
  }

  const set = (patch: Adm03Patch): void => {
    onSearch(parseSearch({ ...search, ...patch }));
  };
  const overlay = overlayOf(search.ov);
  const readOnly = !canManage;
  const dirty =
    Object.values(offices).some((e) => Object.keys(e).length > 0) ||
    Object.keys(lineEdits).length > 0;
  const invalid = Object.entries(offices).some(
    ([, e]) => e.code !== undefined && !/^[A-Z]{2,6}$/.test(e.code),
  );
  const refreshWalls = (): void => {
    void queryClient.invalidateQueries({ queryKey: listWallsOptions().queryKey });
  };

  async function onSave(): Promise<void> {
    try {
      for (const [id, edit] of Object.entries(offices)) {
        const office = officeList.data?.find((o) => o.id === id);
        if (office === undefined || Object.keys(edit).length === 0) continue;
        const body: FirmOfficeIn = {
          name: office.name,
          code: office.code,
          is_hq: office.is_hq,
          time_zone: office.time_zone,
          address_line1: office.address_line1 ?? null,
          address_line2: office.address_line2 ?? null,
          city: office.city ?? null,
          region_code: office.region_code ?? null,
          postal_code: office.postal_code ?? null,
          lead_user_id: office.lead_user_id ?? null,
          default_reviewer_pool_team_id: office.default_reviewer_pool_team_id ?? null,
          version: office.version ?? null,
          ...edit,
        };
        await saveOffice.mutateAsync({ path: { office_id: id }, body });
      }
      for (const [line, to] of Object.entries(lineEdits)) {
        const policy = lines.data?.find((l) => l.service_line === line);
        if (policy === undefined) continue;
        await saveLine.mutateAsync({
          path: { line: policy.service_line },
          body: {
            version: policy.version,
            enabled: policy.enabled,
            lead_user_id: policy.lead_user_id ?? null,
            content_visible_to: to,
            cross_line_access: policy.cross_line_access,
          },
        });
      }
    } catch (error) {
      const detail = detailOf(error);
      if (detail === "forbidden") setStepUp(true);
      else toast.show(detail === "stale_version" ? COPY.stale : COPY.error);
      return;
    }
    setOffices({});
    setLineEdits({});
    await queryClient.invalidateQueries({ queryKey: officesOptions().queryKey });
    await queryClient.invalidateQueries({ queryKey: serviceLinesOptions().queryKey });
    toast.show(COPY.saved);
  }

  const lock = readOnly ? { action: <SettingsLock /> } : {};
  const officeRows = officeList.data ?? [];
  const returns = officeRows.every((o) => o.facts?.returns !== undefined)
    ? officeRows.reduce((sum, o) => sum + (o.facts?.returns ?? 0), 0)
    : undefined;
  const teamRows = teams.data ?? [];
  const teamsById = new Map(teamRows.map((t) => [t.id, t]));
  const serviceTeams = teamRows.filter((t) => t.kind === "service_line");
  const groups = teamRows.filter(
    (t) => t.kind === "eqr_pool" || t.kind === "monitoring_reviewers" || t.kind === "custom",
  );
  const seasonalEnds = staff.data?.tallies.seasonal_access_ends_on ?? null;
  const memberOptions = (members.data ?? []).map((m) => ({
    value: m.user_id,
    label: m.display_name,
  }));
  const offshoreMembers = offshore.data?.member_ids ?? [];
  const wallFor = (id: string): WallOut | undefined => walls.data?.find((w) => w.id === id);

  return (
    <SettingsLayout
      bare
      toolbar={{ nav: [], active: "", firm: "" }}
      title={COPY.title}
      context={overview.data?.firm_name ?? ""}
      backLabel={COPY.back}
      {...(onBack === undefined ? {} : { onBack })}
      navTitle={COPY.navTitle}
      groups={GROUPS.map((g) => ({
        ...g,
        sections: g.sections.filter(
          (s) => s.id === "general" || s.id === "people" || s.id === "offices" || PLANNED_VISIBLE,
        ),
      })).filter((g) => g.sections.length > 0)}
      active="offices"
      onSelect={(id) => {
        if (id !== "offices") onNavigate?.(id);
      }}
      dirty={dirty}
      invalid={invalid}
      readOnly={readOnly && !canLines}
      readOnlyText={COPY.readOnly}
      labels={{ unsaved: COPY.unsaved }}
      onDiscard={() => {
        setOffices({});
        setLineEdits({});
      }}
      onSave={() => {
        void onSave();
      }}
      stepUp={<StepUp open={stepUp} onOpenChange={setStepUp} />}
      overlay={
        <>
          {overlay.kind === "new" && (
            <NewWallSheet
              key={search.ov}
              {...(overlay.userId === undefined ? {} : { initialUser: overlay.userId })}
              {...(overlay.clientId === undefined ? {} : { initialClient: overlay.clientId })}
              members={members.data ?? []}
              staff={staff.data?.items}
              offices={officeNames}
              clients={clients.data ?? []}
              onClose={() => {
                set({ ov: undefined });
              }}
              onAdded={(wall) => {
                set({ ov: undefined });
                setTinted(new Set([wall.id]));
                window.setTimeout(() => {
                  setTinted(new Set());
                }, TINT_MS);
                refreshWalls();
              }}
              onStepUp={() => {
                setStepUp(true);
              }}
            />
          )}
          {overlay.kind === "log" && (
            <WallLogDrawer
              key={overlay.wallId}
              wallId={overlay.wallId}
              wall={wallFor(overlay.wallId)}
              names={names}
              clients={clientNames}
              when={when}
              onClose={() => {
                set({ ov: undefined });
              }}
            />
          )}
        </>
      }
    >
      <div className="flex flex-col gap-[12px]">
        {officeRows.length > 0 && (
          <Fieldset
            title={COPY.fieldsets.offices}
            flush
            className="mb-0"
            {...(readOnly
              ? lock
              : PLANNED_VISIBLE
                ? { action: <FieldsetAdd disabled>{COPY.adds.office}</FieldsetAdd> }
                : {})}
          >
            {officeRows.map((o) => {
              const pool = teamsById.get(o.default_reviewer_pool_team_id ?? "");
              return (
                <OfficeRows
                  key={o.id}
                  office={o}
                  edit={offices[o.id] ?? {}}
                  readOnly={readOnly}
                  expanded={search.expand === o.code}
                  names={names}
                  members={memberOptions}
                  pool={pool === undefined ? undefined : poolText(pool, names)}
                  onToggle={() => {
                    set({ expand: search.expand === o.code ? undefined : o.code });
                  }}
                  onEdit={(edit) => {
                    setOffices((all) => ({ ...all, [o.id]: { ...(all[o.id] ?? {}), ...edit } }));
                  }}
                  onSeats={() => {
                    onOpenPeople?.({ office: o.id });
                  }}
                />
              );
            })}
            <div
              data-settings="total"
              className="flex h-[30px] items-center justify-between bg-sel-bg px-[12px] text-body font-medium"
            >
              <span>{COPY.allOffices}</span>
              <span>
                {COPY.allOfficesValue(
                  officeRows.reduce((sum, o) => sum + o.seats, 0),
                  returns,
                )}
              </span>
            </div>
          </Fieldset>
        )}

        {teamRows.length > 0 && (
          <Fieldset
            title={COPY.fieldsets.teams}
            flush
            className="mb-0"
            {...(readOnly
              ? lock
              : PLANNED_VISIBLE
                ? { action: <FieldsetAdd disabled>{COPY.adds.group}</FieldsetAdd> }
                : {})}
          >
            {serviceTeams.map((t) => (
              <TeamRow
                key={t.id}
                team={t}
                names={names}
                onOpen={() => {
                  onOpenPeople?.({ team: t.id });
                }}
              />
            ))}
            <p data-settings="sum" className="px-[12px] py-[8px] text-right text-meta text-ink-3">
              {COPY.teamsSum(serviceTeams.map((t) => t.member_ids.length))}
            </p>
            <div className="flex min-h-[34px] items-center bg-nested px-[12px] text-body font-medium">
              {COPY.groups}
            </div>
            {groups.map((t) => (
              <div key={t.id}>
                <TeamRow
                  team={t}
                  names={names}
                  {...(COPY.groupHelp[t.kind] === undefined
                    ? {}
                    : { help: COPY.groupHelp[t.kind] })}
                  onOpen={() => {
                    onOpenPeople?.({ team: t.id });
                  }}
                />
                {t.name === "Seasonal" && seasonalEnds !== null && (
                  <ValueRow kind="value" label={COPY.accessEnds} indented readOnly={readOnly}>
                    {date(seasonalEnds, { now, tz, withYear: true })}
                  </ValueRow>
                )}
              </div>
            ))}
          </Fieldset>
        )}

        {lines.data !== undefined && (
          <LinesFieldset
            lines={lines.data}
            edits={lineEdits}
            readOnly={!canLines}
            names={names}
            onEdit={(line, to) => {
              setLineEdits((all) => {
                const original = lines.data.find(
                  (l) => l.service_line === line,
                )?.content_visible_to;
                return Object.fromEntries(
                  Object.entries({ ...all, [line]: to }).filter(
                    ([key, value]) => key !== line || value !== original,
                  ),
                );
              });
            }}
          />
        )}

        <WallsFieldset
          walls={walls.data}
          needsStepUp={detailOf(walls.error) === "forbidden"}
          canList={canWalls}
          canCreate={canWall}
          readOnly={readOnly}
          names={names}
          clients={clientNames}
          when={when}
          tinted={tinted}
          onAdd={() => {
            set({ ov: "wall:new" });
          }}
          onOpen={(wallId) => {
            set({ ov: `wall:${wallId}` });
          }}
          onStepUp={() => {
            setStepUp(true);
          }}
          onChanged={refreshWalls}
        />

        {offshore.data !== undefined && (
          <div id="offshore">
            <Fieldset title={COPY.fieldsets.offshore} flush className="mb-0" {...lock}>
              {offshoreMembers.length > 0 && (
                <p
                  role="status"
                  className="bg-amber-tint px-[12px] py-[9px] text-body text-amber-ink"
                >
                  {COPY.offshore.banner(
                    offshoreMembers
                      .map((id) => names.get(id) ?? "")
                      .filter((x) => x !== "")
                      .join(", "),
                  )}
                </p>
              )}
              <ValueRow
                kind="value"
                label={COPY.offshore.group}
                readOnly={readOnly}
                help={COPY.offshore.groupHelp}
              >
                {COPY.offshore.members(offshoreMembers.length)}
              </ValueRow>
              <ValueRow kind="value" label={COPY.offshore.consented} readOnly={readOnly}>
                {String(offshore.data.consented_client_count)}
                {PLANNED_VISIBLE && <span className="text-ink-3">{COPY.offshore.registry}</span>}
              </ValueRow>
              <ValueRow
                kind="toggle"
                label={COPY.offshore.block}
                help={COPY.offshore.blockHelp}
                checked
                disabled
                lock
              />
              <ValueRow kind="toggle" label={COPY.offshore.mask} checked disabled lock />
            </Fieldset>
          </div>
        )}
        {(officeList.isError || teams.isError || lines.isError) && (
          <EmptyState title={COPY.error} tone="error" />
        )}
      </div>
    </SettingsLayout>
  );
}

/** ADM-03 holding its own search (the gallery, tests): `initial` is a `?…#anchor` string. */
export function OfficesPage({
  initial = "",
  onNavigate,
  onOpenPeople,
}: {
  initial?: string;
  onNavigate?: (section: string) => void;
  onOpenPeople?: (filter: { office?: string; team?: string }) => void;
}): JSX.Element {
  const [search, setSearch] = useState<Adm03Search>(() => parseSearch(initial));
  const anchor = anchorOf(initial);
  return (
    <ADM03
      search={search}
      onSearch={setSearch}
      {...(anchor === undefined ? {} : { anchor })}
      {...(onNavigate === undefined ? {} : { onNavigate })}
      {...(onOpenPeople === undefined ? {} : { onOpenPeople })}
    />
  );
}
