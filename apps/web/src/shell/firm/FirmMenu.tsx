import type { MeOut, MembershipOut, RoleOut } from "@abacus/api-client";
import {
  confirmAnnualIndependenceMutation,
  meQueryKey,
  meOptions,
  myAnnualIndependenceOptions,
  myAnnualIndependenceQueryKey,
  setPreferencesMutation,
  signOutMutation,
} from "@abacus/api-client/query";
import {
  Button,
  Dialog,
  Drawer,
  Fieldset,
  ValueRow,
  FirmMark,
  Icon,
  type IconName,
  Menu,
  Pill,
  Wordmark,
  cn,
  toast,
  useFormat,
  useMotion,
  useOverlayLayer,
  useOverlayStack,
  zoneName,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type JSX,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import { type NavAccess, useSession } from "../../app-core/session";
import { FIRM_MENU, PROFILE } from "./copy";

// SHL-03 · the firm menu (P-01-T08): an O1 tray of white sections under the firm pill, since the
// toolbar has no avatar. Firm rows (one per staff membership; picking another switches firm),
// the person card, Your profile, the default office filter (its 200 menu PUTs the preference),
// Notification preferences, Keyboard shortcuts, the admin rows and Sign out, then the footer.
//
// The admin section is computed only from `/v1/me/capabilities.nav` (AC 2.1.2): a key that reads
// `none` hides its row, `read` adds "View only". Nothing here compares a role code. The person
// card's line is the firm-wide role labels, the job title and the home office, as /v1/me and the
// capabilities give them (DEC-142). Sign out calls `POST /v1/auth/sign-out` through the generated
// client, then hands over to the caller's local sign-out (the SPA's auth client is P-01-T11).

/** The admin rows in the order the frames draw them (a: settings, users, log; d: security,
 * developer, log). `path` is the legacy route that serves the row today, or null while its ADM
 * screen is planned (the row then only closes the menu). */
export const ADMIN_ROWS = [
  { key: "firm_settings", icon: "settings", path: "/admin/methodology" },
  { key: "users_roles", icon: "users-round", path: "/admin/people" },
  { key: "security_center", icon: "lock", path: null },
  { key: "developer_api", icon: "code", path: null },
  { key: "audit_log", icon: "scroll-text", path: "/admin/audit-log" },
] as const satisfies readonly { key: string; icon: IconName; path: string | null }[];

export type AdminKey = (typeof ADMIN_ROWS)[number]["key"];

export interface AdminRow {
  key: AdminKey;
  label: string;
  icon: IconName;
  path: string | null;
  viewOnly: boolean;
}

/** The admin section for a capabilities `nav` (AC 2.1.2): empty hides the section. Firm settings
 * at `read` carries "View only" (SHL-03c). */
export function adminRows(nav: Readonly<Record<string, NavAccess>>): AdminRow[] {
  return ADMIN_ROWS.flatMap((row) => {
    const access = nav[row.key] ?? "none";
    if (access === "none") return [];
    return [
      {
        key: row.key,
        label: FIRM_MENU.admin[row.key],
        icon: row.icon,
        path: row.path,
        // The canvas notes only the settings row: the audit log is read-only for everyone.
        viewOnly: row.key === "firm_settings" && access === "read",
      },
    ];
  });
}

/** The person card's second line: the firm-wide role labels, the job title and the home office.
 * A role label the job title already says ("Partner" in "Tax Partner") is not repeated (DEC-142). */
export function cardLine(
  roles: readonly RoleOut[],
  jobTitle: string | null | undefined,
  office: string | null | undefined,
): string {
  const title = jobTitle ?? "";
  const labels = roles.map((r) => r.label).filter((label) => !title.includes(label));
  return [...labels, title, office ?? ""].filter((part) => part !== "").join(" · ");
}

/** A firm row's second line: "US · Central Time · 46 seats", or the sandbox's own line. */
export function firmFacts(membership: MembershipOut): string {
  const firm = membership.firm;
  if (firm === null || firm === undefined) return "";
  if (firm.is_sandbox) return FIRM_MENU.sandboxLine;
  return [
    firm.region,
    zoneName(firm.time_zone),
    firm.seats_total === null ? "" : FIRM_MENU.seats(firm.seats_total),
  ]
    .filter((part) => part !== "")
    .join(" · ");
}

function officeName(me: MeOut | undefined, id: string | null | undefined): string | null {
  if (id === null || id === undefined) return null;
  return me?.offices?.find((o) => o.id === id)?.name ?? null;
}

export interface FirmMenuProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The firm the session is in (the API's `active_tenant_id`, or the one chosen). */
  activeTenantId: string | null;
  /** Go to a path (the router's navigate). */
  navigate: (path: string) => void;
  /** Keyboard shortcuts: the shortcut list (the interim Go… frame until SHL-02). */
  onShortcuts: () => void;
  /** Notification preferences: the SHL-04 drawer, whose settings menu holds them. */
  onNotificationPreferences: () => void;
  /** Picking another firm: the caller sets the tenant selector (`X-Abacus-Tenant`); the menu then
   * resets every query and shows the toast. */
  onSwitch: (membership: MembershipOut) => void;
  /** After `POST /v1/auth/sign-out` answers (or fails): the caller's local sign-out. */
  onSignedOut: () => void;
  /** An artboard: the tray is drawn in place, not as a layer, and the office menu may be held. */
  held?: { officeMenu?: boolean };
}

const ITEM_SELECTOR = '[role="menuitem"],[role="menuitemradio"]';

const ROW =
  "flex h-[36px] w-full items-center gap-[10px] px-[12px] text-left text-body text-ink outline-offset-[-2px] hover:bg-nav-fill focus-visible:bg-nav-fill data-[state=open]:bg-nav-fill";
const SECTION = "overflow-hidden rounded-menu-inner bg-card py-[4px] shadow-e1";

function Section({ children, label }: { children: ReactNode; label?: string }): JSX.Element {
  return (
    <div
      role="group"
      {...(label === undefined ? {} : { "aria-label": label })}
      className={SECTION}
    >
      {children}
    </div>
  );
}

function Keycap({ children }: { children: ReactNode }): JSX.Element {
  return (
    <kbd className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-value bg-nested px-[5px] font-sans text-micro text-ink-2">
      {children}
    </kbd>
  );
}

function RowIcon({ name }: { name: IconName }): JSX.Element {
  return <Icon name={name} size={14} className="text-ink-2" />;
}

/** The firm menu tray and the profile drawer it opens. */
export function FirmMenu({
  open,
  onOpenChange,
  activeTenantId,
  navigate,
  onShortcuts,
  onNotificationPreferences,
  onSwitch,
  onSignedOut,
  held,
}: FirmMenuProps): JSX.Element {
  const queryClient = useQueryClient();
  const animate = useMotion();
  const me = useQuery(meOptions()).data;
  const session = useSession();
  const [officeOpen, setOfficeOpen] = useState(false);
  const [profile, setProfile] = useState(false);
  const tray = useRef<HTMLDivElement>(null);
  const stack = useOverlayStack();
  const layer = useOverlayLayer({
    kind: "popover",
    modal: false,
    open: open && held === undefined,
    onOpenChange,
  });
  const setOffice = useMutation({
    ...setPreferencesMutation(),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: meQueryKey() }),
  });
  const signOut = useMutation(signOutMutation());

  // Escape closes the topmost layer (the office menu first), then the tray, and focus returns to
  // the firm pill; a press outside closes it. The pill's own press toggles it (the toolbar).
  useEffect(() => {
    if (!open || held !== undefined) return;
    const onKey = (event: KeyboardEvent): void => {
      if (event.key !== "Escape") return;
      layer.onEscape(event);
      layer.returnFocus({ preventDefault: () => undefined });
    };
    const onDown = (event: PointerEvent): void => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (tray.current?.contains(target) === true) return;
      if (stack.top()?.id !== layer.id) return;
      if (target.closest('button[aria-haspopup="menu"][data-pressed]') !== null) return;
      layer.requestClose("outside");
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [open, held, layer, stack]);

  // Focus lands on the first row once the rows are there (the firm row, after /v1/me answers).
  const ready = me !== undefined;
  useEffect(() => {
    if (!open || held !== undefined || !ready) return;
    tray.current?.querySelector<HTMLElement>(ITEM_SELECTOR)?.focus();
  }, [open, held, ready]);

  const close = (): void => {
    onOpenChange(false);
  };
  const go = (path: string | null): void => {
    close();
    if (path !== null) navigate(path);
  };
  // Roving focus across the tray's rows (↑ ↓ Home End); → opens the office menu.
  const onTrayKey = (event: ReactKeyboardEvent<HTMLDivElement>): void => {
    const items = [...(tray.current?.querySelectorAll<HTMLElement>(ITEM_SELECTOR) ?? [])];
    const at = items.indexOf(document.activeElement as HTMLElement);
    const move = (i: number): void => {
      event.preventDefault();
      items[(i + items.length) % items.length]?.focus();
    };
    if (event.key === "ArrowDown") move(at + 1);
    else if (event.key === "ArrowUp") move(at < 0 ? items.length - 1 : at - 1);
    else if (event.key === "Home") move(0);
    else if (event.key === "End") move(items.length - 1);
  };

  const staff = (me?.memberships ?? []).filter((m) => m.kind !== "client");
  const active = staff.find((m) => m.tenant_id === activeTenantId) ?? staff[0];
  const office = officeName(me, me?.default_office_id) ?? FIRM_MENU.allOffices;
  const homeOffice = officeName(me, session.officeId);
  const admin = adminRows(session.nav);
  const version = import.meta.env.VITE_APP_VERSION;
  const offices: { id: string | null; name: string }[] = [
    { id: null, name: FIRM_MENU.allOffices },
    ...(me?.offices ?? []),
  ];
  const officeMenuOpen = held?.officeMenu === true ? undefined : officeOpen;

  const body = (
    <div
      ref={tray}
      role="menu"
      aria-label={FIRM_MENU.label}
      data-overlay="firm-menu"
      onKeyDown={onTrayKey}
      style={held === undefined ? { zIndex: layer.panelZ } : undefined}
      className={cn(
        "top-[52px] left-[90px] flex w-[300px] flex-col gap-[6px] rounded-menu bg-nested p-[6px] shadow-menu",
        held === undefined ? "fixed" : "absolute z-10",
        animate && held === undefined && "motion-pop",
      )}
    >
      <Section label={FIRM_MENU.firmHeader}>
        <div className="-mt-[4px] flex h-[32px] items-center px-[12px] text-dense font-medium text-ink-3">
          {FIRM_MENU.firmHeader}
        </div>
        {staff.map((m) => {
          const on = m.tenant_id === active?.tenant_id;
          return (
            <button
              key={m.tenant_id}
              type="button"
              role="menuitemradio"
              aria-checked={on}
              tabIndex={-1}
              onClick={() => {
                close();
                if (on) return;
                // AC 2.1.4: the tenant selector, then every cached answer cleared and the active
                // ones (/v1/me first among them) fetched again in the new firm.
                onSwitch(m);
                void queryClient.resetQueries();
                toast.show({ kind: "success", text: FIRM_MENU.switched(m.firm_name) });
              }}
              className={cn(ROW, "h-[48px] border-t-[0.5px] border-hair")}
            >
              <FirmMark name={m.firm_name} size={20} />
              <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
                <span className="flex items-center gap-[6px]">
                  <span className="truncate text-section">{m.firm_name}</span>
                  {m.firm?.is_sandbox === true && (
                    <Pill variant="soon" size="micro">
                      {FIRM_MENU.sandboxPill}
                    </Pill>
                  )}
                </span>
                <span className="truncate text-meta text-ink-3">{firmFacts(m)}</span>
              </span>
              {on && <Icon name="check" size={14} className="text-green" />}
            </button>
          );
        })}
      </Section>

      <Section>
        <div className="flex items-center gap-[10px] p-[12px]">
          <span
            aria-hidden="true"
            className="flex size-[32px] flex-none items-center justify-center rounded-pill bg-chip text-cell font-medium text-ink-2"
          >
            {me?.initials ?? ""}
          </span>
          <span className="flex min-w-0 flex-col gap-[2px]">
            <span className="truncate text-section">{me?.display_name}</span>
            <span className="truncate text-cell text-ink-3">
              {cardLine(session.roles, me?.job_title, homeOffice)}
            </span>
            <span className="truncate text-meta text-ink-3">{me?.email}</span>
          </span>
        </div>
        <button
          type="button"
          role="menuitem"
          tabIndex={-1}
          aria-haspopup="dialog"
          onClick={() => {
            close();
            setProfile(true);
          }}
          className={ROW}
        >
          <RowIcon name="user-round" />
          <span className="flex-1">{FIRM_MENU.profile}</span>
        </button>
        <Menu
          label={FIRM_MENU.office}
          width={200}
          align="start"
          {...(officeMenuOpen === undefined
            ? { forceState: "open" as const }
            : { open: officeMenuOpen, onOpenChange: setOfficeOpen })}
          sections={[
            offices.map((o) => ({
              label: o.name,
              checked: o.id === (me?.default_office_id ?? null),
              onSelect: () => {
                setOffice.mutate({ body: { default_office_id: o.id } });
              },
            })),
          ]}
          trigger={
            <button
              type="button"
              role="menuitem"
              tabIndex={-1}
              aria-label={FIRM_MENU.office}
              onKeyDown={(event) => {
                if (event.key === "ArrowRight") {
                  event.preventDefault();
                  setOfficeOpen(true);
                }
              }}
              className={ROW}
            >
              <RowIcon name="map-pin" />
              <span className="flex-1">{FIRM_MENU.office}</span>
              <span data-value="office" className="inline-flex items-center gap-[4px] font-medium">
                {office}
                <Icon name="chevrons-up-down" size={12} className="text-ink-3" />
              </span>
            </button>
          }
        />
        <button
          type="button"
          role="menuitem"
          tabIndex={-1}
          onClick={() => {
            close();
            onNotificationPreferences();
          }}
          className={ROW}
        >
          <RowIcon name="bell" />
          <span className="flex-1">{FIRM_MENU.notificationPreferences}</span>
        </button>
        <button
          type="button"
          role="menuitem"
          tabIndex={-1}
          aria-haspopup="dialog"
          onClick={() => {
            close();
            onShortcuts();
          }}
          className={ROW}
        >
          <RowIcon name="keyboard" />
          <span className="flex-1">{FIRM_MENU.shortcuts}</span>
          <span aria-hidden="true" className="flex gap-[3px]">
            {FIRM_MENU.shortcutKeys.map((k) => (
              <Keycap key={k}>{k}</Keycap>
            ))}
          </span>
        </button>
      </Section>

      {admin.length > 0 && (
        <Section label="Admin">
          {admin.map((row) => (
            <button
              key={row.key}
              type="button"
              role="menuitem"
              tabIndex={-1}
              data-admin={row.key}
              onClick={() => {
                go(row.path);
              }}
              className={ROW}
            >
              <RowIcon name={row.icon} />
              <span className="flex-1">{row.label}</span>
              {row.viewOnly && <span className="text-meta text-ink-3">{FIRM_MENU.viewOnly}</span>}
            </button>
          ))}
        </Section>
      )}

      <Section>
        <button
          type="button"
          role="menuitem"
          tabIndex={-1}
          disabled={signOut.isPending}
          onClick={() => {
            signOut.mutate(
              {},
              {
                onSettled: () => {
                  close();
                  onSignedOut();
                },
              },
            );
          }}
          className={cn(ROW, "text-ink-2")}
        >
          <RowIcon name="log-out" />
          <span className="flex-1">{FIRM_MENU.signOut}</span>
        </button>
      </Section>

      <div className="flex items-center justify-between px-[8px] pt-[8px] pb-[2px]">
        {/* Decorative here: an img is not a child a menu may own (axe aria-required-children,
            found by the J01 and J16 journeys); the version line stays readable. */}
        <span aria-hidden="true">
          <Wordmark size={12} />
        </span>
        {version !== undefined && version !== "" && (
          <span className="text-meta text-ink-4">{FIRM_MENU.version(version)}</span>
        )}
      </div>
    </div>
  );

  return (
    <>
      {open && body}
      <ProfileDrawer
        open={profile}
        onOpenChange={setProfile}
        me={me}
        roles={session.roles}
        office={homeOffice}
        timeZone={active?.firm?.time_zone ?? session.tz}
      />
    </>
  );
}

function ProfileDrawer({
  open,
  onOpenChange,
  me,
  roles,
  office,
  timeZone,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  me: MeOut | undefined;
  roles: readonly RoleOut[];
  office: string | null;
  timeZone: string | null;
}): JSX.Element {
  const rows: [string, string][] = [
    [PROFILE.name, me?.display_name ?? ""],
    [PROFILE.initials, me?.initials ?? ""],
    [PROFILE.role, roles.map((r) => r.label).join(" · ")],
    [PROFILE.jobTitle, me?.job_title ?? ""],
    [PROFILE.office, office ?? ""],
    [PROFILE.email, me?.email ?? ""],
    [PROFILE.timeZone, timeZone === null ? "" : zoneName(timeZone)],
  ];
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={PROFILE.title}
      description={PROFILE.note}
    >
      <dl className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e1">
        {rows.map(([label, value]) => (
          <div
            key={label}
            className="flex min-h-[36px] items-center gap-[12px] border-b-[0.5px] border-hair px-[12px] last:border-b-0"
          >
            <dt className="w-[96px] flex-none text-body text-ink-3">{label}</dt>
            <dd className="min-w-0 flex-1 truncate text-body text-ink">{value}</dd>
          </div>
        ))}
      </dl>
      <AnnualIndependence enabled={open} />
    </Drawer>
  );
}

/** G-01 AC6.1: one's own annual independence confirmation for the firm's year; a decline needs
 * a note. The statement is the firm's published text, shown as written (version recorded). */
function AnnualIndependence({ enabled }: { enabled: boolean }): JSX.Element | null {
  const queryClient = useQueryClient();
  const f = useFormat();
  const mine = useQuery({ ...myAnnualIndependenceOptions(), enabled, retry: false });
  const [confirming, setConfirming] = useState(false);
  const [note, setNote] = useState("");
  const confirm = useMutation({
    ...confirmAnnualIndependenceMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: myAnnualIndependenceQueryKey() });
      setConfirming(false);
      setNote("");
    },
    onError: () => {
      toast.show({ kind: "error", text: PROFILE.annualFailed });
    },
  });
  const data = mine.data;
  if (data === undefined) return null;
  const statement = data.statement ?? null;
  const decided = data.decided_at ?? null;
  const decide = (decision: "confirmed" | "declined"): void => {
    if (statement === null) return;
    confirm.mutate({
      body: {
        decision,
        year: data.year,
        statement_version: statement.version,
        note: note.trim() === "" ? null : note.trim(),
      },
    });
  };
  return (
    <div className="mt-[10px] flex min-h-[44px] items-center gap-[12px] rounded-pane bg-card px-[12px] shadow-e1">
      <span className="min-w-0 flex-1 text-body text-ink">{PROFILE.annual(data.year)}</span>
      {data.status === "not_yet" || decided === null ? (
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            setConfirming(true);
          }}
        >
          {PROFILE.annualConfirmAction}
        </Button>
      ) : (
        <span className="text-meta text-ink-3">
          {data.status === "confirmed"
            ? PROFILE.annualConfirmed(f.date(decided))
            : PROFILE.annualDeclined(f.date(decided))}
        </span>
      )}
      <Dialog
        open={confirming}
        onOpenChange={(next) => {
          if (!next) {
            setConfirming(false);
            setNote("");
          }
        }}
        title={PROFILE.annualTitle(data.year)}
        dirty={note.trim() !== ""}
        action={
          <Button
            variant="primary"
            disabled={statement === null || confirm.isPending}
            onClick={() => {
              decide("confirmed");
            }}
          >
            {PROFILE.annualConfirm}
          </Button>
        }
      >
        {statement === null ? (
          <p className="text-para text-ink-2">{PROFILE.annualNoStatement}</p>
        ) : (
          <p className="whitespace-pre-line text-para text-ink">{statement.body}</p>
        )}
        <Fieldset flush>
          <ValueRow kind="paragraph" label={PROFILE.annualNote} value={note} onChange={setNote} />
        </Fieldset>
        <Button
          size="sm"
          variant="ghost"
          className="self-start"
          disabled={statement === null || note.trim() === "" || confirm.isPending}
          onClick={() => {
            decide("declined");
          }}
        >
          {PROFILE.annualDecline}
        </Button>
      </Dialog>
    </div>
  );
}
