// ADM-02c and d: the O2 480 drawers. The invite drawer (c) checks the seats the list's tallies
// report: with every seat assigned it says so and Send invite stays off (AC3.3); the server is the
// gate either way (`409 seats_full`). The person drawer (d) reads `GET /v1/firm/staff/{id}`: the
// template, attributes, walls, assignments and last three sign-ins (AC4.1). Its writes (role,
// offshore, deactivate) go through the generated client; a 403 opens the step-up, every other
// refusal is said in words (`COPY.errors`). Controls render from `allowed_actions`, never a role.

import type {
  FirmClientOut,
  FirmOfficeOut,
  FirmTeamOut,
  PersonOut,
  StaffInviteIn,
  StaffTalliesOut,
  WallOut,
} from "@abacus/api-client";
import {
  changeFirmRoleMutation,
  deactivatePersonMutation,
  inviteStaffMutation,
  personOptions,
  updatePersonMutation,
} from "@abacus/api-client/query";
import {
  Button,
  ConfirmDialog,
  Drawer,
  DrawerCard,
  Fieldset,
  Icon,
  Menu,
  RegistryStatus,
  SkeletonRows,
  ValueRow,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { ROLE_TEMPLATES } from "../../app-core/roleTemplates.gen";
import { type Adm02Template, COPY } from "./copy";
import { addedText, fullDayOf, initialsOf, signInText } from "./model";

interface When {
  now: Date;
  tz: string;
}

type Level = NonNullable<StaffInviteIn["level"]>;

/** The error's `detail`, when the server sent one. */
export function detailOf(error: unknown): string | undefined {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    return typeof detail === "string" ? detail : undefined;
  }
  return undefined;
}

/** Say a refusal: a stale second factor opens the step-up; anything else is a toast. */
export function refused(error: unknown, stepUp: () => void): void {
  const detail = detailOf(error);
  if (detail === "forbidden") {
    stepUp();
    return;
  }
  toast.show({
    kind: "error",
    text:
      (detail === undefined ? undefined : COPY.errors[detail]) ?? COPY.errors.unavailable ?? "",
  });
}

const TEMPLATE_KEYS = Object.keys(ROLE_TEMPLATES.templates) as Adm02Template[];
const TEMPLATE_OPTIONS = TEMPLATE_KEYS.map((key) => ({
  value: key,
  label: COPY.templates[key].label,
}));

function levelsOf(template: Adm02Template): readonly string[] {
  return ROLE_TEMPLATES.templates[template].levels;
}

// ---- c: Invite user ----------------------------------------------------------------------------

export interface InviteDrawerProps {
  open: boolean;
  onClose: () => void;
  tallies: StaffTalliesOut | undefined;
  offices: readonly FirmOfficeOut[];
  teams: readonly FirmTeamOut[];
  onSent: () => void;
  onStepUp: () => void;
}

export function InviteDrawer({
  open,
  onClose,
  tallies,
  offices,
  teams,
  onSent,
  onStepUp,
}: InviteDrawerProps): JSX.Element {
  const hq = offices.find((o) => o.is_hq) ?? offices[0];
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [template, setTemplate] = useState<Adm02Template>("tax_preparer");
  const [office, setOffice] = useState<string | null>(null);
  const [team, setTeam] = useState<string | null>(null);
  const [seasonal, setSeasonal] = useState(false);
  const [accessEnds, setAccessEnds] = useState("");
  const [offshore, setOffshore] = useState(false);
  const invite = useMutation(inviteStaffMutation());
  const total = tallies?.seats_total ?? null;
  const full = tallies !== undefined && total !== null && tallies.seats_used >= total;
  const canSeason = levelsOf(template).includes("seasonal");
  const isSeasonal = seasonal && canSeason;
  const officeId = office ?? hq?.id ?? null;
  const serviceTeams = teams.filter((t) => t.kind === "service_line");
  const ready =
    !full &&
    name.trim() !== "" &&
    email.trim() !== "" &&
    (!isSeasonal || /^\d{4}-\d{2}-\d{2}$/.test(accessEnds));
  const dirty = name !== "" || email !== "";

  async function send(): Promise<void> {
    const level = (isSeasonal ? "seasonal" : (levelsOf(template)[0] ?? "staff")) as Level;
    const body: StaffInviteIn = {
      email: email.trim(),
      display_name: name.trim(),
      role_template: template,
      level,
      office_id: officeId,
      team_ids: team === null ? [] : [team],
      access_ends_on: isSeasonal ? accessEnds : null,
      offshore,
    };
    try {
      await invite.mutateAsync({ body });
    } catch (error) {
      refused(error, onStepUp);
      return;
    }
    toast.show(COPY.inviteDrawer.sent);
    onSent();
  }

  return (
    <Drawer
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={COPY.inviteDrawer.title}
      width={480}
      bare
      dirty={dirty}
      footer={
        <div className="flex w-full justify-end gap-[8px]">
          <Button variant="secondary" onClick={onClose}>
            {COPY.inviteDrawer.cancel}
          </Button>
          <Button
            disabled={!ready || invite.isPending}
            onClick={() => {
              void send();
            }}
          >
            {COPY.inviteDrawer.send}
          </Button>
        </div>
      }
    >
      <DrawerCard>
        <Fieldset title={COPY.inviteDrawer.person} flush className="mb-0">
          <ValueRow
            kind="text"
            label={COPY.inviteDrawer.name}
            placeholder={COPY.inviteDrawer.namePlaceholder}
            value={name}
            onChange={setName}
          />
          <ValueRow
            kind="text"
            label={COPY.inviteDrawer.email}
            placeholder={COPY.inviteDrawer.emailPlaceholder}
            value={email}
            onChange={setEmail}
          />
        </Fieldset>
      </DrawerCard>
      <DrawerCard>
        <Fieldset title={COPY.inviteDrawer.access} flush className="mb-0">
          <ValueRow
            kind="select"
            label={COPY.inviteDrawer.role}
            value={template}
            options={TEMPLATE_OPTIONS}
            onChange={(next) => {
              setTemplate(next as Adm02Template);
            }}
          />
          <ValueRow
            kind="select"
            label={COPY.inviteDrawer.office}
            value={officeId ?? ""}
            options={offices.map((o) => ({ value: o.id, label: o.name }))}
            onChange={setOffice}
          />
          <ValueRow
            kind="select"
            label={COPY.inviteDrawer.team}
            value={team ?? ""}
            placeholder={COPY.none}
            options={serviceTeams.map((t) => ({ value: t.id, label: t.name }))}
            onChange={setTeam}
          />
          <ValueRow
            kind="toggle"
            label={COPY.inviteDrawer.seasonal}
            checked={isSeasonal}
            disabled={!canSeason}
            onChange={setSeasonal}
          />
          {isSeasonal && (
            <ValueRow
              kind="text"
              label={COPY.inviteDrawer.accessEnds}
              placeholder={COPY.inviteDrawer.accessEndsPlaceholder}
              value={accessEnds}
              onChange={setAccessEnds}
            />
          )}
          <ValueRow
            kind="toggle"
            label={COPY.inviteDrawer.offshore}
            help={COPY.inviteDrawer.offshoreHelp}
            checked={offshore}
            onChange={setOffshore}
          />
        </Fieldset>
      </DrawerCard>
      {full && (
        <div
          role="status"
          className="m-[10px] flex items-center gap-[8px] rounded-nested bg-amber-tint px-[14px] py-[12px] text-body text-amber-ink"
        >
          <Icon name="triangle-alert" size={14} />
          {COPY.inviteDrawer.seatsFull(total)}
        </div>
      )}
    </Drawer>
  );
}

// ---- d: a person -------------------------------------------------------------------------------

export interface PersonDrawerProps {
  userId: string;
  onClose: () => void;
  offices: ReadonlyMap<string, string>;
  teams: ReadonlyMap<string, FirmTeamOut>;
  walls: readonly WallOut[];
  clients: readonly FirmClientOut[];
  when: When;
  onChanged: () => void;
  onStepUp: () => void;
}

function Card({ title, children }: { title: string; children: JSX.Element[] | JSX.Element }) {
  return (
    <DrawerCard>
      <Fieldset title={title} flush className="mb-0">
        {children}
      </Fieldset>
    </DrawerCard>
  );
}

function Line({ children }: { children: string }): JSX.Element {
  return <div className="flex min-h-[34px] items-center px-[12px] text-body">{children}</div>;
}

export function PersonDrawer({
  userId,
  onClose,
  offices,
  teams,
  walls,
  clients,
  when,
  onChanged,
  onStepUp,
}: PersonDrawerProps): JSX.Element {
  const person = useQuery({ ...personOptions({ path: { user_id: userId } }), retry: false });
  const role = useMutation(changeFirmRoleMutation());
  const deactivate = useMutation(deactivatePersonMutation());
  const update = useMutation(updatePersonMutation());
  const [pending, setPending] = useState<Adm02Template | null>(null);
  const [ending, setEnding] = useState(false);
  const data: PersonOut | undefined = person.data;
  const row = data?.row;
  const name = row?.display_name ?? "";
  const manage = row?.allowed_actions?.includes("firm.manage_users") === true;

  async function changeRole(template: Adm02Template): Promise<void> {
    if (row === undefined) return;
    const levels = levelsOf(template);
    const level = (levels.includes(row.level) ? row.level : (levels[0] ?? row.level)) as Level;
    try {
      await role.mutateAsync({
        path: { user_id: userId },
        body: { role_template: template, level },
      });
    } catch (error) {
      refused(error, onStepUp);
      return;
    }
    toast.show(COPY.confirmRole.done);
    onChanged();
    void person.refetch();
  }

  async function end(): Promise<void> {
    try {
      await deactivate.mutateAsync({ path: { user_id: userId }, body: { reason: "manual" } });
    } catch (error) {
      refused(error, onStepUp);
      return;
    }
    toast.show(COPY.confirmDeactivate.done);
    onChanged();
    void person.refetch();
  }

  async function setOffshore(on: boolean): Promise<void> {
    if (data === undefined) return;
    try {
      await update.mutateAsync({
        path: { user_id: userId },
        body: { version: data.version, offshore: on },
      });
    } catch (error) {
      refused(error, onStepUp);
      return;
    }
    onChanged();
    void person.refetch();
  }

  const clientName = new Map(clients.map((c) => [c.client_id, c.name]));
  const own = walls.filter((w) => (data?.wall_ids ?? []).includes(w.id));
  const team = (row?.team_ids ?? [])
    .map((id) => teams.get(id)?.name)
    .filter((t) => t !== undefined)
    .join(" · ");
  const template = row === undefined ? "" : COPY.templates[row.role_template].label;

  return (
    <>
      <Drawer
        open
        onOpenChange={(next) => {
          if (!next) onClose();
        }}
        title={name}
        width={480}
        bare
        meta={
          <span
            aria-hidden="true"
            className="inline-flex size-[20px] items-center justify-center rounded-full bg-chip text-micro text-ink-2"
          >
            {initialsOf(name)}
          </span>
        }
        {...(manage && row.status !== "deactivated"
          ? {
              footer: (
                <div className="flex w-full items-center justify-between gap-[8px]">
                  <Menu
                    label={COPY.personDrawer.changeRole}
                    align="start"
                    trigger={
                      <button
                        type="button"
                        className="inline-flex h-[32px] items-center rounded-pill bg-card px-[14px] text-btn text-ink shadow-e1 hover:bg-nav-fill"
                      >
                        {COPY.personDrawer.changeRole}
                      </button>
                    }
                    sections={[
                      TEMPLATE_KEYS.map((key) => ({
                        label: COPY.templates[key].label,
                        checked: row.role_template === key,
                        onSelect: () => {
                          if (row.role_template !== key) setPending(key);
                        },
                      })),
                    ]}
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setEnding(true);
                    }}
                    className="inline-flex h-[32px] items-center rounded-pill bg-card px-[14px] text-btn text-red-ink shadow-e1 hover:bg-nav-fill"
                  >
                    {COPY.personDrawer.deactivate}
                  </button>
                </div>
              ),
            }
          : {})}
      >
        {data === undefined || row === undefined ? (
          <SkeletonRows type="list" />
        ) : (
          <>
            <Card title={COPY.personDrawer.access}>
              <ValueRow kind="value" label={COPY.personDrawer.role}>
                {row.level === "seasonal" ? COPY.personDrawer.seasonal(template) : template}
              </ValueRow>
              <ValueRow kind="value" label={COPY.personDrawer.office}>
                {row.office_id == null ? COPY.none : (offices.get(row.office_id) ?? COPY.none)}
              </ValueRow>
              <ValueRow kind="value" label={COPY.personDrawer.team}>
                {team === "" ? COPY.none : team}
              </ValueRow>
              <ValueRow kind="value" label={COPY.personDrawer.email}>
                {row.email}
              </ValueRow>
              {row.access_ends_on != null ? (
                <ValueRow kind="value" label={COPY.personDrawer.accessEnds}>
                  {fullDayOf(row.access_ends_on, when)}
                </ValueRow>
              ) : (
                <></>
              )}
              <ValueRow
                kind="toggle"
                label={COPY.personDrawer.offshore}
                checked={row.offshore === true}
                disabled={!manage || update.isPending}
                onChange={(on) => {
                  void setOffshore(on);
                }}
              />
              <ValueRow kind="value" label={COPY.personDrawer.status}>
                {row.status === "active" ? (
                  COPY.statusWords.active
                ) : (
                  <RegistryStatus object="membership" code={row.status} />
                )}
              </ValueRow>
            </Card>
            {own.length > 0 ? (
              <Card title={COPY.personDrawer.walls}>
                {own.map((w) => (
                  <Line key={w.id}>
                    {COPY.personDrawer.wallLine(
                      clientName.get(w.client_id) ?? COPY.none,
                      addedText(w.created_at, when),
                    )}
                  </Line>
                ))}
              </Card>
            ) : (
              <></>
            )}
            <Card title={COPY.personDrawer.assignments}>
              <Line>
                {(data.assignment_count ?? 0) === 0
                  ? COPY.personDrawer.noAssignments
                  : COPY.personDrawer.assignmentCount(data.assignment_count ?? 0)}
              </Line>
            </Card>
            <Card title={COPY.personDrawer.signIns}>
              {(data.recent_sign_ins ?? []).length === 0 ? (
                <Line>{COPY.personDrawer.noSignIns}</Line>
              ) : (
                (data.recent_sign_ins ?? []).map((s) => (
                  <Line key={s.at}>
                    {COPY.personDrawer.signIn(signInText(s.at, when), s.method, s.mfa, s.ip)}
                  </Line>
                ))
              )}
            </Card>
          </>
        )}
      </Drawer>
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(next) => {
          if (!next) setPending(null);
        }}
        title={COPY.confirmRole.title(name, pending === null ? "" : COPY.templates[pending].label)}
        confirmLabel={COPY.confirmRole.confirm}
        cancelLabel={COPY.confirmRole.cancel}
        destructive={false}
        onConfirm={() => {
          const next = pending;
          setPending(null);
          if (next !== null) void changeRole(next);
        }}
      >
        {COPY.confirmRole.body}
      </ConfirmDialog>
      <ConfirmDialog
        open={ending}
        onOpenChange={setEnding}
        title={COPY.confirmDeactivate.title(name)}
        confirmLabel={COPY.confirmDeactivate.confirm}
        cancelLabel={COPY.confirmDeactivate.cancel}
        onConfirm={() => {
          setEnding(false);
          void end();
        }}
      >
        {COPY.confirmDeactivate.body}
      </ConfirmDialog>
    </>
  );
}
