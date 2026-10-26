// ADM-03's ethical walls (G-01-T14; G-01 §3.8, AC8.1–AC8.7, AC11.2; DEC-43, DEC-73): fieldset C,
// the new-wall sheet (b, c) and a wall's log drawer (g). A wall applies the moment it is saved;
// the named partner approves it themself with fresh MFA (INV-5), so the toast says an approval was
// requested and the row reads "Awaiting …". Walls answer 404 everywhere: nothing here counts what
// a wall hides. Approve and Lift come only from each row's `allowed_actions` (AC11.1).

import type {
  FirmClientOut,
  FirmMemberOut,
  StaffRowV2Out,
  WallIn,
  WallOut,
} from "@abacus/api-client";
import {
  approveWallMutation,
  createWallMutation,
  removeWallMutation,
  wallEventsOptions,
  wallPreviewOptions,
} from "@abacus/api-client/query";
import {
  Button,
  ConfirmDialog,
  Drawer,
  DrawerCard,
  EmptyState,
  Fieldset,
  FieldsetAdd,
  Icon,
  Menu,
  SettingsLock,
  SheetModal,
  Timeline,
  ValueRow,
  date,
  sameDay,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { COPY as PEOPLE } from "../ADM-02/copy";
import { COPY, type Reason } from "./copy";
import { type Names, initialsOf } from "./model";

export interface When {
  now: Date;
  tz: string;
}

export function detailOf(error: unknown): string | undefined {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = error.detail;
    return typeof detail === "string" ? detail : undefined;
  }
  return undefined;
}

const REASONS = Object.keys(COPY.reasons) as Reason[];

export function Initials({ name }: { name: string }): JSX.Element {
  return (
    <span
      aria-hidden="true"
      className="inline-flex size-[20px] flex-none items-center justify-center rounded-full bg-chip text-micro text-ink-2"
    >
      {initialsOf(name)}
    </span>
  );
}

function addedAt(at: string, when: When): string {
  return sameDay(at, when.now.toISOString(), { tz: when.tz })
    ? COPY.walls.today(time(at, { tz: when.tz }))
    : date(at, { now: when.now, tz: when.tz, withYear: true });
}

/** "Personal relationship (family member employed at Ashford)". */
function reasonText(wall: WallOut): string {
  const code = COPY.reasons[wall.reason_code];
  const text = wall.reason_text?.trim();
  if (text === undefined || text === "") return code;
  return `${code} (${text.charAt(0).toLowerCase()}${text.slice(1)})`;
}

// --- fieldset C ----------------------------------------------------------------------------------

export interface WallsProps {
  walls: readonly WallOut[] | undefined;
  /** `GET /v1/walls` answered 403: `wall.list` keeps fresh MFA (SPEC-002 Q2, R-5). */
  needsStepUp: boolean;
  /** No `wall.list` at all: the fieldset is not drawn. */
  canList: boolean;
  canCreate: boolean;
  readOnly: boolean;
  names: Names;
  clients: ReadonlyMap<string, string>;
  when: When;
  /** Rows tinted amber for 2 s (ADM-03f): just added. */
  tinted: ReadonlySet<string>;
  onAdd: () => void;
  onOpen: (wallId: string) => void;
  onStepUp: () => void;
  onChanged: () => void;
}

export function WallsFieldset(props: WallsProps): JSX.Element | null {
  const { names, clients, when } = props;
  const approve = useMutation(approveWallMutation());
  const lift = useMutation(removeWallMutation());
  const [lifting, setLifting] = useState<WallOut | null>(null);
  if (!props.canList) return null;
  const active = (props.walls ?? []).filter((w) => w.status === "active");
  const nameOf = (id: string | null | undefined): string => names.get(id ?? "") ?? "";
  const action = props.canCreate ? (
    <FieldsetAdd onClick={props.onAdd}>{COPY.adds.wall}</FieldsetAdd>
  ) : props.readOnly ? (
    <SettingsLock />
  ) : undefined;
  const fail = (error: unknown): void => {
    if (detailOf(error) === "forbidden") props.onStepUp();
    else toast.show(COPY.error);
  };

  return (
    <div id="walls">
      <Fieldset
        title={COPY.fieldsets.walls}
        flush
        className="mb-0"
        {...(action === undefined ? {} : { action })}
      >
        {props.needsStepUp ? (
          <div className="flex min-h-[40px] items-center justify-between gap-[10px] px-[12px] text-body">
            <span className="inline-flex items-center gap-[8px] text-ink-2">
              <Icon name="lock" size={12} className="text-ink-3" />
              {COPY.walls.stepUp}
            </span>
            <Button variant="secondary" size="sm" onClick={props.onStepUp}>
              {COPY.walls.stepUpAction}
            </Button>
          </div>
        ) : (
          <table aria-label={COPY.fieldsets.walls} className="w-full border-collapse text-body">
            <thead>
              <tr className="h-[30px] bg-band-hd text-th text-ink-2">
                {COPY.walls.columns.map((c) => (
                  <th key={c} scope="col" className="px-[12px] text-left font-medium">
                    {c}
                  </th>
                ))}
                <th scope="col" className="w-0 px-[12px]">
                  <span className="sr-only">{COPY.walls.approve}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {active.length === 0 && (
                <tr>
                  <td colSpan={6} className="h-[40px] px-[12px] text-ink-3">
                    {COPY.walls.empty}
                  </td>
                </tr>
              )}
              {active.map((w) => {
                const person = nameOf(w.user_id);
                const client = clients.get(w.client_id) ?? "";
                const approver = nameOf(w.approver_user_id);
                const actions = w.allowed_actions ?? [];
                return (
                  <tr
                    key={w.id}
                    data-wall={w.id}
                    data-tint={props.tinted.has(w.id) ? "on" : undefined}
                    className={`h-[40px] border-t-[0.5px] border-hair motion-safe:transition-colors motion-safe:duration-[600ms] ${
                      props.tinted.has(w.id) ? "bg-amber-tint" : ""
                    }`}
                  >
                    <td className="px-[12px]">
                      <button
                        type="button"
                        aria-label={COPY.walls.open(person, client)}
                        className="inline-flex items-center gap-[8px] text-left hover:underline"
                        onClick={() => {
                          props.onOpen(w.id);
                        }}
                      >
                        <Initials name={person} />
                        {person}
                      </button>
                    </td>
                    <td className="px-[12px]">{client}</td>
                    <td className="px-[12px] text-ink-2">{reasonText(w)}</td>
                    <td className="px-[12px] whitespace-nowrap text-ink-2">
                      {COPY.walls.added(
                        addedAt(w.created_at, when),
                        initialsOf(nameOf(w.created_by)),
                      )}
                    </td>
                    <td className="px-[12px] whitespace-nowrap">
                      {w.approved_at === null ? (
                        approver === "" ? (
                          <span className="text-ink-4">—</span>
                        ) : (
                          <span className="text-amber-ink">{COPY.walls.awaiting(approver)}</span>
                        )
                      ) : (
                        approver
                      )}
                    </td>
                    <td className="px-[12px] text-right whitespace-nowrap">
                      <span className="inline-flex gap-[6px]">
                        {actions.includes("wall.approve") && (
                          <Button
                            size="sm"
                            aria-label={COPY.walls.approveFor(person)}
                            disabled={approve.isPending}
                            onClick={() => {
                              approve.mutate(
                                { path: { wall_id: w.id } },
                                {
                                  onSuccess: () => {
                                    toast.show(COPY.walls.approved);
                                    props.onChanged();
                                  },
                                  onError: fail,
                                },
                              );
                            }}
                          >
                            {COPY.walls.approve}
                          </Button>
                        )}
                        {actions.includes("wall.remove") && (
                          <Button
                            size="sm"
                            variant="secondary"
                            aria-label={COPY.walls.liftFor(person)}
                            onClick={() => {
                              setLifting(w);
                            }}
                          >
                            {COPY.walls.lift}
                          </Button>
                        )}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        <p className="px-[12px] py-[8px] text-meta text-ink-3">{COPY.walls.helper}</p>
      </Fieldset>
      <ConfirmDialog
        open={lifting !== null}
        onOpenChange={(open) => {
          if (!open) setLifting(null);
        }}
        title={COPY.walls.liftFor(nameOf(lifting?.user_id))}
        confirmLabel={COPY.walls.lift}
        onConfirm={() => {
          if (lifting === null) return;
          lift.mutate(
            { path: { wall_id: lifting.id }, body: { reason: COPY.walls.liftReason } },
            {
              onSuccess: () => {
                toast.show(COPY.walls.lifted);
                props.onChanged();
              },
              onError: fail,
            },
          );
        }}
      >
        {COPY.walls.helper}
      </ConfirmDialog>
    </div>
  );
}

// --- the new-wall sheet (b, c) -------------------------------------------------------------------

interface PickOption {
  value: string;
  label: string;
  hint?: string;
}

function PickRow({
  label,
  value,
  options,
  onChange,
  avatar,
}: {
  label: string;
  value: string | undefined;
  options: readonly PickOption[];
  onChange: (value: string) => void;
  avatar?: boolean;
}): JSX.Element {
  const current = options.find((o) => o.value === value);
  return (
    <Menu
      label={label}
      align="end"
      width={320}
      sections={[
        options.map((o) => ({
          label: o.label,
          checked: o.value === value,
          onSelect: () => {
            onChange(o.value);
          },
        })),
      ]}
      trigger={
        <button
          type="button"
          aria-label={current === undefined ? label : `${label}: ${current.label}`}
          className="flex min-h-[44px] w-full items-center gap-[10px] px-[12px] py-[6px] text-left hover:bg-nav-fill"
        >
          {avatar === true && current !== undefined && <Initials name={current.label} />}
          <span className="flex min-w-0 flex-1 flex-col">
            <span className={current === undefined ? "text-ink-3" : "font-medium"}>
              {current?.label ?? COPY.sheet.choose}
            </span>
            {current?.hint !== undefined && (
              <span className="text-meta text-ink-3">{current.hint}</span>
            )}
          </span>
          <Icon name="chevrons-up-down" size={12} className="text-ink-3" />
        </button>
      }
    />
  );
}

export interface NewWallProps {
  initialUser?: string;
  initialClient?: string;
  members: readonly FirmMemberOut[];
  /** The people list when the viewer may read it: titles and levels for the person row, and the
   * partners the approver picker offers (otherwise every member; the server checks). */
  staff: readonly StaffRowV2Out[] | undefined;
  offices: ReadonlyMap<string, string>;
  clients: readonly FirmClientOut[];
  onClose: () => void;
  onAdded: (wall: WallOut) => void;
  onStepUp: () => void;
}

export function NewWallSheet(props: NewWallProps): JSX.Element {
  const [user, setUser] = useState<string | undefined>(props.initialUser);
  const [client, setClient] = useState<string | undefined>(props.initialClient);
  const [reason, setReason] = useState<Reason>("personal_relationship");
  const [text, setText] = useState("");
  const [approver, setApprover] = useState<string | undefined>(undefined);
  const create = useMutation(createWallMutation());
  const preview = useQuery({
    ...wallPreviewOptions({ query: { user_id: user ?? "", client_id: client ?? "" } }),
    enabled: user !== undefined && client !== undefined,
    retry: false,
  });
  const staffBy = new Map((props.staff ?? []).map((r) => [r.user_id ?? "", r]));
  const personHint = (id: string): string | undefined => {
    const row = staffBy.get(id);
    if (row === undefined) return undefined;
    const template = PEOPLE.templates[row.role_template].label;
    const office = props.offices.get(row.office_id ?? "") ?? "";
    return [template, row.level === "seasonal" ? "seasonal" : null, office || null]
      .filter((x): x is string => x !== null)
      .join(" · ");
  };
  const people = props.members.map((m) => {
    const hint = personHint(m.user_id);
    return { value: m.user_id, label: m.display_name, ...(hint === undefined ? {} : { hint }) };
  });
  const partners = (
    props.staff === undefined
      ? props.members
      : props.members.filter((m) => staffBy.get(m.user_id)?.level === "partner")
  )
    .filter((m) => m.user_id !== user)
    .map((m) => ({ value: m.user_id, label: m.display_name }));
  const blockers = preview.data?.blockers ?? [];
  const personName = props.members.find((m) => m.user_id === user)?.display_name ?? "";
  const clientName = props.clients.find((c) => c.client_id === client)?.name ?? "";
  const blocked: ReactNode =
    blockers[0] === "relationship_partner"
      ? COPY.sheet.conflict(personName)
      : blockers[0] === "wall_exists"
        ? COPY.sheet.exists(personName, clientName)
        : blockers[0] === "own_wall"
          ? COPY.sheet.own
          : null;
  const ready =
    user !== undefined &&
    client !== undefined &&
    preview.isSuccess &&
    blockers.length === 0 &&
    !create.isPending;

  const save = (): void => {
    if (user === undefined || client === undefined) return;
    const body: WallIn = {
      user_id: user,
      client_id: client,
      reason_code: reason,
      reason_text: text.trim() === "" ? null : text.trim(),
      approver_user_id: approver ?? null,
    };
    create.mutate(
      { body },
      {
        onSuccess: (wall) => {
          const partner = props.members.find((m) => m.user_id === approver)?.display_name;
          toast.show(
            partner === undefined ? COPY.sheet.toastNoApprover : COPY.sheet.toast(partner),
          );
          props.onAdded(wall);
        },
        onError: (error) => {
          if (detailOf(error) === "forbidden") props.onStepUp();
          else void preview.refetch();
        },
      },
    );
  };

  return (
    <SheetModal
      open
      onOpenChange={(open) => {
        if (!open) props.onClose();
      }}
      title={COPY.sheet.title}
      dirty={user !== undefined || client !== undefined || text !== ""}
      action={
        <Button disabled={!ready} onClick={save}>
          {COPY.sheet.save}
        </Button>
      }
    >
      <div className="flex flex-col gap-[10px] p-[12px]">
        <Fieldset title={COPY.sheet.person} flush className="mb-0">
          <PickRow
            label={COPY.sheet.person}
            value={user}
            options={people}
            onChange={setUser}
            avatar
          />
        </Fieldset>
        <Fieldset title={COPY.sheet.client} flush className="mb-0">
          <PickRow
            label={COPY.sheet.client}
            value={client}
            options={props.clients.map((c) => ({ value: c.client_id, label: c.name }))}
            onChange={setClient}
          />
          {blocked !== null && (
            <p role="alert" className="bg-red-tint px-[12px] py-[9px] text-body text-red-ink">
              {blocked}
            </p>
          )}
        </Fieldset>
        <Fieldset title={COPY.sheet.reason} flush className="mb-0">
          <ValueRow
            kind="select"
            label={COPY.sheet.reason}
            value={reason}
            options={REASONS.map((r) => ({ value: r, label: COPY.reasons[r] }))}
            onChange={(next) => {
              setReason(next as Reason);
            }}
          />
          <ValueRow
            kind="text"
            label={COPY.sheet.reasonText}
            value={text}
            placeholder={COPY.sheet.reasonPlaceholder}
            onChange={setText}
          />
        </Fieldset>
        <Fieldset title={COPY.sheet.effect} flush className="mb-0">
          <ul aria-label={COPY.sheet.effect}>
            {COPY.sheet.effects(preview.data?.assignments_ended ?? 0).map((line) => (
              <li
                key={line}
                className="flex min-h-[34px] items-center gap-[10px] border-t-[0.5px] border-hair px-[12px] text-body first:border-t-0"
              >
                <Icon name="check" size={14} className="text-green" />
                {line}
              </li>
            ))}
          </ul>
        </Fieldset>
        <Fieldset title={COPY.sheet.approval} flush className="mb-0">
          <ValueRow
            kind="select"
            label={COPY.sheet.requires}
            {...(approver === undefined ? {} : { value: approver })}
            placeholder={COPY.sheet.choose}
            options={partners}
            onChange={setApprover}
          />
        </Fieldset>
      </div>
    </SheetModal>
  );
}

// --- the wall log (g) ------------------------------------------------------------------------------

export function WallLogDrawer({
  wall,
  wallId,
  names,
  clients,
  when,
  onClose,
}: {
  wall: WallOut | undefined;
  wallId: string;
  names: Names;
  clients: ReadonlyMap<string, string>;
  when: When;
  onClose: () => void;
}): JSX.Element {
  const events = useQuery({ ...wallEventsOptions({ path: { wall_id: wallId } }), retry: false });
  const nameOf = (id: string | null | undefined): string => names.get(id ?? "") ?? "";
  const items = (events.data?.items ?? []).map((e, i) => {
    const words = COPY.log.events[e.event_type];
    const who = nameOf(e.actor_user_id) || COPY.log.someone;
    return {
      id: `${e.event_type}-${String(i)}`,
      date: addedAt(e.at, when),
      state: "done" as const,
      title: words === undefined ? e.event_type : words(who),
    };
  });
  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={COPY.log.title}
      bare
    >
      {wall === undefined ? (
        events.isError ? (
          <EmptyState title={COPY.error} tone="error" />
        ) : null
      ) : (
        <DrawerCard>
          <Fieldset title={COPY.log.wall} flush className="mb-0">
            <ValueRow kind="value" label={COPY.sheet.person}>
              <Initials name={nameOf(wall.user_id)} />
              {nameOf(wall.user_id)}
            </ValueRow>
            <ValueRow kind="value" label={COPY.sheet.client}>
              {clients.get(wall.client_id) ?? ""}
            </ValueRow>
            <ValueRow kind="value" label={COPY.sheet.reason}>
              {COPY.reasons[wall.reason_code]}
            </ValueRow>
            {wall.reason_text !== null && (
              <ValueRow kind="value" label={COPY.log.details}>
                {wall.reason_text}
              </ValueRow>
            )}
            <ValueRow kind="value" label={COPY.log.added}>
              {COPY.walls.added(addedAt(wall.created_at, when), nameOf(wall.created_by))}
            </ValueRow>
            <ValueRow kind="value" label={COPY.log.approvedBy}>
              {wall.approved_at === null
                ? COPY.walls.awaiting(nameOf(wall.approver_user_id))
                : nameOf(wall.approver_user_id)}
            </ValueRow>
          </Fieldset>
        </DrawerCard>
      )}
      <DrawerCard>
        <Fieldset title={COPY.log.log} flush className="mb-0">
          <Timeline events={items} label={COPY.log.label} />
        </Fieldset>
      </DrawerCard>
    </Drawer>
  );
}
