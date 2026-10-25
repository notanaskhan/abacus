import type {
  ClientRecordOut,
  ContactDetailOut,
  ContactRowOut,
  RequestItemOut,
} from "@abacus/api-client";
import {
  Button,
  Checkbox,
  ConfirmDialog,
  DEFAULT_TZ,
  Drawer,
  DrawerCard,
  Fieldset,
  Icon,
  type IndexColumn,
  IndexList,
  Menu,
  type MenuItem,
  RegistryStatus,
  SheetModal,
  Tag,
  ValueRow,
  type ViewState,
  date,
  sameDay,
  time,
  toast,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import {
  grantsFor,
  isThirdParty,
  useClientRequestItems,
  useContact,
  useContactWrites,
  useContacts,
} from "../../domain/clients";
import { COPY } from "./copy";

// CLI-04 · Contacts & portal access (P-07-T33; docs/screens/CLI-04.md). T1 inside the client
// record (CLI-02 draws the subbar and the tabs and hosts this pane on its "Contacts & access"
// tab) over `GET /v1/clients/{id}/contacts`, with the O3 invite sheet, the O2 contact drawer and
// the 400 dialogs. Each artboard is its data and the overlay it opens on
// (fixtures/scenarios/CLI-04.ts):
//
//   a  Northwind's six contacts: "3 active · 1 invited · 2 not invited", footer 10 + 9 + 2 + 2 + 1
//   b  a with Harborline's "Invite…" sheet open (its two delegated requests ticked)
//   c  Harborline Invited "Sent Sep 14" after the send; toast "Invite sent to Harborline …"
//   d  Sam Ortiz Locked, "3 incorrect codes" (DF-24), row action "Unlock…"
//   e  Sam Ortiz's "Change scope…": "Change access — Sam Ortiz" with his 9 requests
//   f  Summit's "Revoke…" dialog: requests stay with Northwind
//   g  Copperleaf: owner and controller, "Non-attest client: no SKE designation required"
//
// Every write is a person's click (the agent never invites, sends or revokes; INV-1). "Portal
// preview" (POR-02, R-01) is planned: fixture builds draw it disabled with its hint.

/** The overlay an artboard opens on (the gallery passes it; the route never does). */
export type Cli04Open =
  | { sheet: string; mode: "invite" | "scope" }
  | { revoke: string }
  | { unlock: string }
  | { drawer: string };

export interface CLI04Props {
  clientId: string;
  record: ClientRecordOut | undefined;
  opens?: Cli04Open | undefined;
}

type Sheet = { contactId: string | null; mode: "invite" | "scope" } | null;

const ON_DAY = (day: string): string => `${day}T12:00:00Z`;

function notFound(error: unknown): boolean {
  const detail = (error as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" && detail.replace(" ", "_") === "not_found";
}

/** The contact's second line: the address or the organisation line its role carries. */
function subLine(row: ContactRowOut): string {
  const title = (row.roles ?? []).find((r) => r.title_text != null)?.title_text ?? null;
  return [row.email, title].filter((v) => v != null && v !== "").join(" · ");
}

function roleWords(row: ContactRowOut): string[] {
  const words = (row.roles ?? []).map((r) => COPY.roles[r.role]);
  return [...(isThirdParty(row) ? [COPY.row.thirdParty] : []), ...new Set(words)];
}

function scopeLine(row: ContactRowOut): string {
  const n = row.delegated_request_count ?? 0;
  if (isThirdParty(row)) return COPY.row.delegatedOnly(n);
  const names = [...new Set((row.roles ?? []).map((r) => r.scope_name))].filter((v) => v !== "");
  return [...names, ...(n > 0 ? [COPY.row.requests(n)] : [])].join(" · ") || COPY.none;
}

function can(row: ContactRowOut, action: string): boolean {
  return (row.allowed_actions ?? []).includes(action);
}

export function CLI04({ clientId, record, opens }: CLI04Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const list = useContacts(clientId);
  const writes = useContactWrites(clientId);
  const [query, setQuery] = useState("");
  const [sheet, setSheet] = useState<Sheet>(
    opens !== undefined && "sheet" in opens ? { contactId: opens.sheet, mode: opens.mode } : null,
  );
  const [revoking, setRevoking] = useState<string | null>(
    opens !== undefined && "revoke" in opens ? opens.revoke : null,
  );
  const [unlocking, setUnlocking] = useState<string | null>(
    opens !== undefined && "unlock" in opens ? opens.unlock : null,
  );
  const [drawer, setDrawer] = useState<string | null>(
    opens !== undefined && "drawer" in opens ? opens.drawer : null,
  );

  const page = list.data;
  const rows = page?.items ?? [];
  const find = (id: string | null): ContactRowOut | undefined => rows.find((r) => r.id === id);
  const q = query.trim().toLowerCase();
  const shown =
    q === ""
      ? rows
      : rows.filter((r) => [r.name, r.email ?? ""].some((v) => v.toLowerCase().includes(q)));

  let state: ViewState;
  if (list.isError) {
    state = notFound(list.error)
      ? { kind: "restricted", reason: "walled" }
      : { kind: "error", retry: () => void list.refetch() };
  } else if (page === undefined) state = { kind: "loading" };
  else if (rows.length === 0) state = { kind: "empty" };
  else if (shown.length === 0) {
    state = {
      kind: "filtered-empty",
      query,
      clear: () => {
        setQuery("");
      },
    };
  } else state = { kind: "ready" };

  const fail = (): void => {
    toast.show({ kind: "error", text: COPY.toast.failed });
  };
  const resend = async (row: ContactRowOut): Promise<void> => {
    if (row.invitation_id == null) return;
    try {
      await writes.resend(row.id, row.invitation_id);
      toast.show({ kind: "success", text: COPY.toast.sent(row.name) });
    } catch {
      fail();
    }
  };

  const menuFor = (row: ContactRowOut): MenuItem[][] => [
    [
      {
        label: COPY.row.menu.changeScope,
        opensDialog: true,
        disabled:
          !can(row, "client_access.grant") ||
          !["invited", "active", "locked"].includes(row.portal_status),
        onSelect: () => {
          setSheet({ contactId: row.id, mode: "scope" });
        },
      },
      {
        label: COPY.row.menu.unlock,
        opensDialog: true,
        disabled: !can(row, "contact.unlock") || row.portal_status !== "locked",
        onSelect: () => {
          setUnlocking(row.id);
        },
      },
    ],
    [
      {
        label: COPY.row.menu.revoke,
        opensDialog: true,
        danger: true,
        disabled: !can(row, "client_access.revoke") || row.invitation_id == null,
        onSelect: () => {
          setRevoking(row.id);
        },
      },
    ],
  ];

  const columns: IndexColumn<ContactRowOut>[] = [
    {
      key: "contact",
      header: COPY.columns.contact,
      cell: (r) => (
        <span className="flex min-w-0 flex-col">
          <button
            type="button"
            className="truncate text-left font-medium hover:underline"
            onClick={(e) => {
              e.stopPropagation();
              setDrawer(r.id);
            }}
          >
            {r.name}
          </button>
          <span className="truncate text-meta text-ink-3">{subLine(r)}</span>
        </span>
      ),
    },
    {
      key: "roles",
      header: COPY.columns.roles,
      width: 260,
      cell: (r) => (
        <span className="flex flex-wrap gap-[4px]">
          {roleWords(r).map((w) => (
            <Tag key={w}>{w}</Tag>
          ))}
        </span>
      ),
    },
    {
      key: "scope",
      header: COPY.columns.scope,
      width: 300,
      cell: (r) => (
        <span className="flex items-center gap-[4px] text-dense text-ink-2">
          {isThirdParty(r) && <Icon name="lock" size={12} />}
          <span className="truncate">{scopeLine(r)}</span>
        </span>
      ),
    },
    {
      key: "portal",
      header: COPY.columns.portal,
      width: 150,
      cell: (r) => (
        <span className="flex flex-col items-start gap-[2px]">
          <RegistryStatus object="invitation" code={r.portal_status} context="portal_pill" />
          {r.portal_status === "invited" && r.invited_on != null && (
            <span className="text-meta text-ink-3">
              {r.expires_on == null
                ? COPY.row.sent(date(ON_DAY(r.invited_on), { now, tz }))
                : COPY.row.invited(
                    date(ON_DAY(r.invited_on), { now, tz }),
                    date(ON_DAY(r.expires_on), { now, tz }),
                  )}
            </span>
          )}
          {r.portal_status === "locked" && (
            <span className="text-meta text-ink-3">{COPY.locked.sub(null)}</span>
          )}
        </span>
      ),
    },
    {
      key: "mfa",
      header: COPY.columns.mfa,
      width: 70,
      cell: (r) =>
        r.mfa_enrolled === true ? (
          <span>{COPY.row.mfaOn}</span>
        ) : (
          <span className="text-ink-4">{COPY.none}</span>
        ),
    },
    {
      key: "seen",
      header: COPY.columns.lastSeen,
      width: 110,
      align: "right",
      cell: (r) =>
        r.last_seen_at == null ? (
          <span className="text-ink-4">{COPY.none}</span>
        ) : (
          <span className="tabular-nums text-ink-2">
            {sameDay(r.last_seen_at, now, { tz })
              ? time(r.last_seen_at, { tz })
              : date(r.last_seen_at, { now, tz })}
          </span>
        ),
    },
    {
      key: "actions",
      header: "",
      width: 150,
      align: "right",
      cell: (r) => (
        <span className="flex items-center justify-end gap-[6px]">
          {r.portal_status === "not_invited" && (
            <Button
              variant="secondary"
              size="sm"
              opensDialog
              disabled={!can(r, "client_access.grant")}
              onClick={(e) => {
                e.stopPropagation();
                setSheet({ contactId: r.id, mode: "invite" });
              }}
            >
              {COPY.row.invite}
            </Button>
          )}
          {r.portal_status === "invited" && (
            <Button
              variant="secondary"
              size="sm"
              disabled={!can(r, "client_access.grant") || r.invitation_id == null}
              onClick={(e) => {
                e.stopPropagation();
                void resend(r);
              }}
            >
              {COPY.row.resend}
            </Button>
          )}
          {r.portal_status === "locked" && (
            <Button
              variant="secondary"
              size="sm"
              opensDialog
              disabled={!can(r, "contact.unlock")}
              onClick={(e) => {
                e.stopPropagation();
                setUnlocking(r.id);
              }}
            >
              {COPY.row.unlock}
            </Button>
          )}
          <Menu
            label={COPY.row.menuLabel(r.name)}
            align="end"
            sections={menuFor(r)}
            trigger={
              <button
                type="button"
                aria-label={COPY.row.menuLabel(r.name)}
                onClick={(e) => {
                  e.stopPropagation();
                }}
                className="flex size-[24px] items-center justify-center rounded-pill text-ink-3 hover:bg-nested"
              >
                <Icon name="ellipsis" size={14} />
              </button>
            }
          />
        </span>
      ),
    },
  ];

  const summary = page?.summary;
  const countText =
    summary === undefined
      ? undefined
      : COPY.header.counts(summary.active, summary.invited, summary.not_invited) +
        (summary.locked > 0 ? COPY.header.locked(summary.locked) : "");
  const delegated = page?.delegated;
  const footer =
    record?.is_attest_client === false ? (
      <p className="text-dense text-ink-3">{COPY.nonAttest}</p>
    ) : delegated !== undefined && delegated.total > 0 ? (
      <p data-footer="delegated" className="text-dense text-ink-3">
        {COPY.footer.delegated(delegated.parts, delegated.total, delegated.received)}
      </p>
    ) : undefined;
  const anyGrant = rows.some((r) => can(r, "client_access.grant"));
  const firstNotInvited = rows.find((r) => r.portal_status === "not_invited");

  const revokeRow = find(revoking);
  const unlockRow = find(unlocking);
  const drawerRow = find(drawer);

  return (
    <div data-screen="CLI-04" className="flex min-h-0 flex-1 flex-col">
      <IndexList<ContactRowOut>
        title={COPY.pane.title}
        noun={COPY.noun}
        state={state}
        envelope={
          page === undefined
            ? undefined
            : {
                items: shown,
                next_cursor: null,
                total: shown.length,
                counts: page.counts ?? {},
              }
        }
        columns={columns}
        rowKey={(r) => r.id}
        twoLine={() => true}
        query={query}
        searchPlaceholder={COPY.search.placeholder}
        onQuery={setQuery}
        {...(countText === undefined ? {} : { countText })}
        actions={
          <span className="flex items-center gap-[8px]">
            {PLANNED_VISIBLE && (
              <Button
                variant="secondary"
                size="sm"
                icon="eye"
                disabled
                title={COPY.header.previewHint}
              >
                {COPY.header.preview}
              </Button>
            )}
            <Button
              variant="primary"
              size="sm"
              icon="plus"
              opensDialog
              disabled={!anyGrant || firstNotInvited === undefined}
              onClick={() => {
                setSheet({ contactId: firstNotInvited?.id ?? null, mode: "invite" });
              }}
            >
              {COPY.header.invite}
            </Button>
          </span>
        }
        {...(footer === undefined ? {} : { footer })}
        empty={{ icon: "users", title: COPY.empty.title }}
      />
      {sheet !== null && (
        <AccessSheet
          key={`${sheet.contactId ?? ""}:${sheet.mode}`}
          clientId={clientId}
          record={record}
          rows={rows}
          contactId={sheet.contactId}
          mode={sheet.mode}
          onPick={(id) => {
            setSheet({ contactId: id, mode: "invite" });
          }}
          onClose={() => {
            setSheet(null);
          }}
        />
      )}
      <ConfirmDialog
        open={revokeRow !== undefined}
        onOpenChange={(open) => {
          if (!open) setRevoking(null);
        }}
        title={COPY.revoke.title(revokeRow?.name ?? "")}
        confirmLabel={COPY.revoke.confirm}
        cancelLabel={COPY.revoke.cancel}
        destructive
        onConfirm={() => {
          const row = revokeRow;
          if (row?.invitation_id == null) return;
          void writes
            .revoke(row.id, row.invitation_id)
            .then(() => {
              toast.show({ kind: "success", text: COPY.toast.revoked });
            })
            .catch(fail);
        }}
      >
        {COPY.revoke.body(record?.name ?? "")}
      </ConfirmDialog>
      <ConfirmDialog
        open={unlockRow !== undefined}
        onOpenChange={(open) => {
          if (!open) setUnlocking(null);
        }}
        title={COPY.unlock.title(unlockRow?.name ?? "")}
        confirmLabel={COPY.unlock.confirm}
        cancelLabel={COPY.unlock.cancel}
        destructive={false}
        onConfirm={() => {
          const row = unlockRow;
          if (row === undefined) return;
          void writes
            .unlock(row.id)
            .then(() => {
              toast.show({ kind: "success", text: COPY.toast.unlocked });
            })
            .catch(fail);
        }}
      >
        {COPY.unlock.body}
      </ConfirmDialog>
      {drawerRow !== undefined && (
        <ContactDrawer
          row={drawerRow}
          record={record}
          onClose={() => {
            setDrawer(null);
          }}
        />
      )}
    </div>
  );
}

/** The request items the contact's delegations name, with titles from C5's list. */
function useDelegated(
  record: ClientRecordOut | undefined,
  detail: ContactDetailOut | undefined,
): { items: RequestItemOut[]; ids: string[] } {
  const engagements = (record?.active_engagements ?? []).map((e) => e.id);
  const byId = useClientRequestItems(engagements, detail !== undefined);
  const ids = detail?.delegated_request_ids ?? [];
  return {
    ids,
    items: ids.map((id) => byId.get(id)).filter((i): i is RequestItemOut => i !== undefined),
  };
}

// ---- the O3 sheet (b, e) --------------------------------------------------------------------

function AccessSheet({
  clientId,
  record,
  rows,
  contactId,
  mode,
  onPick,
  onClose,
}: {
  clientId: string;
  record: ClientRecordOut | undefined;
  rows: readonly ContactRowOut[];
  contactId: string | null;
  mode: "invite" | "scope";
  onPick: (contactId: string) => void;
  onClose: () => void;
}): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const writes = useContactWrites(clientId);
  const row = rows.find((r) => r.id === contactId);
  const detail = useContact(contactId);
  const delegated = useDelegated(record, detail.data);
  const [unticked, setUnticked] = useState<ReadonlySet<string>>(new Set());
  const third = row !== undefined && isThirdParty(row);
  const ticked = delegated.ids.filter((id) => !unticked.has(id));
  const grants = row === undefined ? [] : grantsFor(row, clientId, ticked);
  const due = delegated.items
    .filter((i) => ticked.includes(i.id) && i.due_on != null)
    .map((i) => i.due_on ?? "")
    .sort()[0];
  const ready = row !== undefined && detail.data !== undefined && grants.length > 0;

  const submit = async (): Promise<void> => {
    if (row === undefined || detail.data === undefined) return;
    try {
      if (mode === "invite") {
        await writes.invite(row.id, grants);
        toast.show({ kind: "success", text: COPY.toast.sent(row.name) });
      } else {
        await writes.changeScope(row.id, detail.data.version, grants);
        toast.show({ kind: "success", text: COPY.toast.saved });
      }
      onClose();
    } catch {
      toast.show({ kind: "error", text: COPY.toast.failed });
    }
  };

  const notInvited = rows.filter((r) => r.portal_status === "not_invited");
  const roleLine = row === undefined ? COPY.none : roleWords(row).join(" · ") || COPY.none;
  return (
    <SheetModal
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={mode === "invite" ? COPY.sheet.title : COPY.sheet.titleChange(row?.name ?? "")}
      dirty={unticked.size > 0}
      action={
        <Button
          variant="primary"
          size="sm"
          disabled={!ready || writes.pending}
          onClick={() => void submit()}
        >
          {mode === "invite" ? COPY.sheet.send : COPY.sheet.save}
        </Button>
      }
    >
      <div className="flex flex-col gap-[12px] p-[12px]">
        <Fieldset title={COPY.sheet.who} flush>
          {mode === "invite" ? (
            <ValueRow
              kind="select"
              label={
                row?.party_kind === "person"
                  ? COPY.sheet.keys.contact
                  : COPY.sheet.keys.organization
              }
              value={row?.id ?? ""}
              options={notInvited.map((r) => ({ value: r.id, label: r.name }))}
              onChange={onPick}
            />
          ) : (
            <ValueRow kind="info" label={COPY.sheet.keys.contact}>
              {row?.name ?? COPY.none}
            </ValueRow>
          )}
          {row !== undefined && row.party_kind !== "person" && subLine(row) !== "" && (
            <ValueRow kind="info" label={COPY.sheet.keys.contact}>
              {(row.roles ?? []).find((r) => r.title_text != null)?.title_text ?? COPY.none}
            </ValueRow>
          )}
          <ValueRow kind="info" label={COPY.sheet.keys.email}>
            {row?.email ?? COPY.none}
          </ValueRow>
          <ValueRow kind="info" label={COPY.sheet.keys.role}>
            {roleLine}
          </ValueRow>
        </Fieldset>
        <Fieldset title={COPY.sheet.whatTheySee} flush>
          <ValueRow kind="info" label={COPY.sheet.keys.access}>
            {third ? (
              <span className="flex items-center gap-[4px]">
                {COPY.sheet.onlyDelegated}
                <Icon name="lock" size={12} />
              </span>
            ) : (
              COPY.sheet.fullClient(record?.name ?? COPY.none)
            )}
          </ValueRow>
          {third && delegated.ids.length === 0 && detail.data !== undefined && (
            <p className="px-[12px] py-[8px] text-dense text-ink-3">{COPY.sheet.noRequests}</p>
          )}
          {third &&
            delegated.ids.map((id) => {
              const item = delegated.items.find((i) => i.id === id);
              return (
                <div key={id} className="flex min-h-[34px] items-center px-[12px] hairline-t">
                  <Checkbox
                    label={item?.description ?? id}
                    showLabel
                    checked={!unticked.has(id)}
                    onChange={(on) => {
                      setUnticked((prev) => {
                        const next = new Set(prev);
                        if (on) next.delete(id);
                        else next.add(id);
                        return next;
                      });
                    }}
                  />
                </div>
              );
            })}
          {third && due !== undefined && (
            <ValueRow kind="info" label={COPY.sheet.keys.due}>
              {date(ON_DAY(due), { now, tz, withYear: true })}
            </ValueRow>
          )}
        </Fieldset>
        <Fieldset title={COPY.sheet.security} flush>
          <ValueRow kind="info" label={COPY.sheet.keys.signIn}>
            {COPY.sheet.signIn}
          </ValueRow>
          <ValueRow
            kind="toggle"
            label={COPY.sheet.keys.mfa}
            help={COPY.sheet.mfaLocked}
            checked
            disabled
          />
          <ValueRow kind="info" label={COPY.sheet.keys.expires}>
            {COPY.sheet.expires}
          </ValueRow>
        </Fieldset>
        {mode === "invite" && (
          <Fieldset title={COPY.sheet.emailPreview} flush>
            <p className="px-[12px] py-[10px] text-dense text-ink-3">{COPY.sheet.previewSource}</p>
          </Fieldset>
        )}
        {third && (
          <p className="px-[4px] text-meta text-ink-3">
            {COPY.sheet.note(row.name, ticked.length)}
          </p>
        )}
      </div>
    </SheetModal>
  );
}

// ---- the O2 drawer ----------------------------------------------------------------------------

function ContactDrawer({
  row,
  record,
  onClose,
}: {
  row: ContactRowOut;
  record: ClientRecordOut | undefined;
  onClose: () => void;
}): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const detail = useContact(row.id);
  const delegated = useDelegated(record, detail.data);
  const signIns = detail.data?.sign_ins ?? [];
  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={row.name}
      meta={<RegistryStatus object="invitation" code={row.portal_status} context="portal_pill" />}
      bare
    >
      <DrawerCard>
        <Fieldset title={COPY.drawer.roles} flush>
          {(row.roles ?? []).length === 0 ? (
            <p className="px-[12px] py-[8px] text-dense text-ink-3">{COPY.none}</p>
          ) : (
            (row.roles ?? []).map((r) => (
              <ValueRow key={`${r.role}:${r.scope_id}`} kind="info" label={COPY.roles[r.role]}>
                {r.scope_name}
              </ValueRow>
            ))
          )}
        </Fieldset>
      </DrawerCard>
      <DrawerCard>
        <Fieldset title={COPY.drawer.delegated} flush>
          {delegated.ids.length === 0 ? (
            <p className="px-[12px] py-[8px] text-dense text-ink-3">{COPY.drawer.noDelegated}</p>
          ) : (
            delegated.ids.map((id) => (
              <p key={id} className="px-[12px] py-[8px] text-dense hairline-t">
                {delegated.items.find((i) => i.id === id)?.description ?? COPY.none}
              </p>
            ))
          )}
        </Fieldset>
      </DrawerCard>
      <DrawerCard>
        <Fieldset title={COPY.drawer.signIns} flush>
          {signIns.length === 0 ? (
            <p className="px-[12px] py-[8px] text-dense text-ink-3">{COPY.drawer.noSignIns}</p>
          ) : (
            signIns.map((s) => (
              <ValueRow key={`${s.kind}:${s.at}`} kind="info" label={COPY.drawer.signIn[s.kind]}>
                {sameDay(s.at, now, { tz }) ? time(s.at, { tz }) : date(s.at, { now, tz })}
              </ValueRow>
            ))
          )}
        </Fieldset>
      </DrawerCard>
    </Drawer>
  );
}
