// PLT-01 Accrued tenant console (G-04-T14; handoff PLT-01 a to g) in fixture mode: Tenants with tiles,
// filters and search (a), the tenant drawer with entitlement edits (b), the provisioning wizard (c)
// to the created toast and tinted row (g), the support request sheet with no approve control (d),
// Library releases (e, fixture-only: its nav item is hidden in production until W-03) and Regions
// (f). The console sees tenant metadata only: no control opens firm content, and no firm client
// name appears anywhere.
import {
  Button,
  Drawer,
  FilterChip,
  Icon,
  Pill,
  SearchField,
  SheetModal,
  StatusTile,
  Tag,
  Toast,
  Toggle,
  Wizard,
  type WizardStep,
  cn,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import {
  AW_PROVISION,
  BH_DRAWER,
  CONSOLE_REGIONS,
  CONSOLE_TENANTS,
  type ConsoleTenant,
  KM_SUPPORT,
  LIBRARY_RELEASES,
} from "../kit-console-data";
import { COPY as C } from "./copy";
import { PLT01_SCENARIOS, type Plt01Scenario } from "./scenarios";

type Tab = "tenants" | "regions" | "library";

const HEALTH: Record<ConsoleTenant["health"], "green-tint" | "amber" | "neutral"> = {
  healthy: "green-tint",
  degraded: "amber",
  onboarding: "neutral",
};

function Toolbar({
  tab,
  onTab,
  production,
}: {
  tab: Tab;
  onTab: (t: Tab) => void;
  production: boolean;
}) {
  const items: { id: Tab | "support" | "status"; label: string }[] = [
    { id: "tenants", label: C.nav.tenants },
    { id: "regions", label: C.nav.regions },
    ...(production ? [] : [{ id: "library" as const, label: C.nav.library }]),
    { id: "support", label: C.nav.support },
    { id: "status", label: C.nav.status },
  ];
  return (
    <header className="flex h-[46px] items-center gap-[12px] bg-card px-[12px] hairline-b">
      <span className="flex h-[30px] items-center rounded-full bg-nested px-[10px] text-[13.5px] font-medium">
        {C.console}
      </span>
      <nav
        aria-label={C.navLabel}
        className="flex flex-1 justify-center gap-[4px]"
        data-plt01="nav"
      >
        {items.map((i) => (
          <button
            key={i.id}
            type="button"
            data-nav={i.id}
            aria-current={tab === i.id ? "page" : undefined}
            className={cn(
              "h-[32px] rounded-full px-[12px] text-[13.5px] text-ink-2",
              tab === i.id && "bg-nested font-medium text-ink",
            )}
            onClick={() => {
              if (i.id === "tenants" || i.id === "regions" || i.id === "library") onTab(i.id);
            }}
          >
            {i.label}
          </button>
        ))}
      </nav>
      <span className="text-[13px] text-ink-2">{C.supportQueue}</span>
      <span className="flex size-[30px] items-center justify-center rounded-full bg-nested text-[12px]">
        RA
      </span>
    </header>
  );
}

function Tenants({
  rows,
  created,
  onRow,
  onProvision,
  onSupport,
}: {
  rows: readonly ConsoleTenant[];
  created: boolean;
  onRow: (id: string) => void;
  onProvision: () => void;
  onSupport: (id: string) => void;
}): JSX.Element {
  const [q, setQ] = useState("");
  const shown = rows.filter((r) => r.firm.toLowerCase().includes(q.toLowerCase()));
  const count = (h: ConsoleTenant["health"]): number => rows.filter((r) => r.health === h).length;
  const counted = rows.filter((r) => r.seats !== "sandbox");
  const used = counted.reduce((s, r) => s + (r.seats === "sandbox" ? 0 : r.seats.used), 0);
  const of = counted.reduce((s, r) => s + (r.seats === "sandbox" ? 0 : r.seats.of), 0);
  return (
    <>
      <div className="flex h-[42px] items-center justify-between px-[12px]">
        <h1 className="text-[15px] font-medium">
          {C.tenants} <span className="font-normal text-ink-2">{C.env}</span>
        </h1>
        <span className="flex gap-[8px]">
          <FilterChip label={C.filters.region} options={[]} placeholder={C.filters.all} />
          <FilterChip label={C.filters.health} options={[]} placeholder={C.filters.all} />
        </span>
      </div>
      <div className="flex gap-[8px] px-[12px] py-[10px]" data-plt01="tiles">
        <StatusTile count={rows.length} label={C.tiles.tenants} variant="neutral" />
        <StatusTile count={count("healthy")} label={C.tiles.healthy} variant="green-tint" />
        <StatusTile count={count("degraded")} label={C.tiles.degraded} variant="amber" />
        <StatusTile count={count("onboarding")} label={C.tiles.onboarding} variant="state" />
        <div
          className="flex h-[72px] w-[200px] flex-col justify-center rounded-[10px] bg-card px-[12px] shadow-e1"
          data-plt01="seats"
        >
          <span className="text-[22px]">{C.seatsOf(used, of)}</span>
          <span className="text-[11.5px] text-ink-3">{C.tiles.seats}</span>
        </div>
      </div>
      <section aria-label={C.tenants} className="mx-[12px] rounded-[12px] bg-card shadow-e2">
        <header className="flex h-[46px] items-center justify-between px-[12px]">
          <span className="w-[220px]">
            <SearchField label={C.search} value={q} onChange={setQ} />
          </span>
          <h2 className="text-[14px] font-medium">{C.tenantsCount(rows.length)}</h2>
          <Button variant="primary" size="sm" onClick={onProvision}>
            {C.provision}
          </Button>
        </header>
        <table className="w-full border-collapse" data-plt01="tenants">
          <thead>
            <tr className="hairline-b">
              {C.columns.map((h) => (
                <th
                  key={h}
                  scope="col"
                  className="h-[30px] bg-nested px-[8px] text-left text-[12px] font-normal text-ink-2"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr
                key={r.id}
                data-tenant={r.id}
                className={cn(
                  "h-[44px] cursor-pointer hairline-b text-[12.5px]",
                  created && r.id === "tnt_aw15" && "bg-green-tint",
                )}
                onClick={() => {
                  onRow(r.id);
                }}
              >
                <td className="px-[8px]">
                  <span className="block text-[13px] font-medium">{r.firm}</span>
                  <span className="text-[11.5px] text-ink-3">{r.id}</span>
                </td>
                <td className="px-[8px]">{r.region}</td>
                <td className="px-[8px]">
                  {r.seats === "sandbox" ? (
                    <Pill variant="soon">{C.sandbox}</Pill>
                  ) : (
                    C.seatsOf(r.seats.used, r.seats.of)
                  )}
                </td>
                <td className="px-[8px]">
                  <span className="flex flex-wrap gap-[4px]">
                    {r.modules.map((m) => (
                      <Tag key={m}>{m}</Tag>
                    ))}
                  </span>
                </td>
                <td className="px-[8px]">
                  <Pill variant={HEALTH[r.health]}>
                    {C.health[r.health]}
                    {r.healthNote ? ` · ${r.healthNote}` : ""}
                  </Pill>
                </td>
                <td className="px-[8px]">{r.channel}</td>
                <td className="px-[8px]">
                  {r.support === null ? (
                    "—"
                  ) : r.supportPending === true ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSupport(r.id);
                      }}
                    >
                      <Pill variant="amber">{r.support}</Pill>
                    </button>
                  ) : (
                    <span className="text-ink-3">{r.support}</span>
                  )}
                </td>
                <td className="px-[8px]">{r.since}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <footer className="px-[12px] py-[8px] text-[12px] text-ink-3" data-plt01="footer">
          {C.footer}
        </footer>
      </section>
    </>
  );
}

function TenantDrawer({
  open,
  onOpenChange,
  held,
  onSupport,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  held: boolean;
  onSupport: () => void;
}) {
  const D = BH_DRAWER;
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Brightwater Hale LLP"
      width={480}
      {...(held ? { forceState: "open" as const } : {})}
      footer={
        <Button variant="secondary" onClick={onSupport}>
          {C.drawer.request}
        </Button>
      }
    >
      <div data-plt01="drawer" className="flex flex-col gap-[10px] p-[12px] text-[12.5px]">
        <section className="rounded-[10px] bg-card p-[12px] shadow-e1">
          <h3 className="text-[13px] font-medium">{C.drawer.entitlements}</h3>
          <dl className="grid grid-cols-[150px_1fr] gap-[6px]">
            <dt className="text-ink-2">{C.drawer.modules}</dt>
            <dd>
              {D.modules.map((m) => `${m} ✓`).join(" · ")}
              <span className="block text-[11.5px] text-ink-3">{D.modulesHelper}</span>
            </dd>
            <dt className="text-ink-2">{C.drawer.seats}</dt>
            <dd>{D.seats} ⇕</dd>
            <dt className="text-ink-2">{C.drawer.renewal}</dt>
            <dd>{D.renewal}</dd>
            <dt className="text-ink-2">{C.drawer.region}</dt>
            <dd>
              {D.region} <Icon name="lock" size={12} className="text-ink-3" />
              <span className="block text-[11.5px] text-ink-3">{D.regionHelper}</span>
            </dd>
            <dt className="text-ink-2">{C.drawer.channel}</dt>
            <dd>
              {D.channel} ⇕
              <span className="block text-[11.5px] text-ink-3">{D.channelHelper}</span>
            </dd>
            <dt className="text-ink-2">{C.drawer.policy}</dt>
            <dd>
              <Toggle label={C.drawer.policy} defaultChecked={D.policyPrincipal} />
              <span className="block text-[11.5px] text-ink-3">{D.policyHelper}</span>
            </dd>
            <dt className="text-ink-2">{C.drawer.teach}</dt>
            <dd>
              <Pill variant="soon">{C.comingSoon}</Pill>
            </dd>
          </dl>
        </section>
        <section className="rounded-[10px] bg-card p-[12px] shadow-e1">
          <h3 className="text-[13px] font-medium">{C.drawer.support}</h3>
          <p>{D.supportNote}</p>
          <p className="text-ink-2">
            {D.history} <Pill variant="green-tint">{C.closed}</Pill>
          </p>
        </section>
        <p className="text-[11.5px] text-ink-3" data-plt01="metadata-note">
          {C.drawer.note}
        </p>
      </div>
    </Drawer>
  );
}

function ProvisionWizard({
  open,
  onOpenChange,
  held,
  onCreate,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  held: boolean;
  onCreate: () => void;
}) {
  const P = AW_PROVISION;
  const steps: WizardStep[] = C.wizard.steps.map((label, i) => ({
    id: label,
    label,
    state: i < 4 ? "done" : "current",
  }));
  return (
    <Wizard
      open={open}
      onOpenChange={onOpenChange}
      title={C.wizard.title}
      steps={steps}
      createLabel={C.wizard.create}
      onCreate={onCreate}
      {...(held ? { forceState: "open" as const } : {})}
    >
      <dl
        data-plt01="wizard"
        className="grid grid-cols-[160px_1fr] gap-[8px] p-[16px] text-[12.5px]"
      >
        <dt className="text-ink-2">{C.wizard.firm}</dt>
        <dd>{P.firm}</dd>
        <dt className="text-ink-2">{C.wizard.region}</dt>
        <dd>
          {P.region}{" "}
          {P.plannedRegions.map((r) => (
            <Pill key={r} variant="soon">{`${r} · ${C.planned}`}</Pill>
          ))}
        </dd>
        <dt className="text-ink-2">{C.wizard.modules}</dt>
        <dd>{P.modules.map((m) => `${m} ✓`).join(" · ")}</dd>
        <dt className="text-ink-2">{C.wizard.seats}</dt>
        <dd>{P.seats}</dd>
        <dt className="text-ink-2">{C.wizard.admins}</dt>
        <dd>{P.admins}</dd>
        <dt className="text-ink-2">{C.wizard.channel}</dt>
        <dd>{P.channel}</dd>
      </dl>
    </Wizard>
  );
}

function SupportSheet({
  open,
  onOpenChange,
  held,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  held: boolean;
}) {
  const S = KM_SUPPORT;
  return (
    <SheetModal
      open={open}
      onOpenChange={onOpenChange}
      title={C.support.title}
      {...(held ? { forceState: "open" as const, heldRole: "group" as const } : {})}
    >
      <dl
        data-plt01="support"
        className="grid grid-cols-[120px_1fr] gap-[8px] p-[16px] text-[12.5px]"
      >
        <dt className="text-ink-2">{C.support.firm}</dt>
        <dd>{S.firm}</dd>
        <dt className="text-ink-2">{C.support.requestedBy}</dt>
        <dd>{S.requestedBy}</dd>
        <dt className="text-ink-2">{C.support.reason}</dt>
        <dd>{S.reason}</dd>
        <dt className="text-ink-2">{C.support.scope}</dt>
        <dd>{S.scope} ⇕</dd>
        <dt className="text-ink-2">{C.support.duration}</dt>
        <dd>{S.duration} ⇕</dd>
        <dt className="text-ink-2">{C.support.status}</dt>
        <dd>
          <Pill variant="amber">{S.status}</Pill>
        </dd>
      </dl>
    </SheetModal>
  );
}

export function TenantConsole({
  st,
  production = false,
}: {
  st?: string | undefined;
  production?: boolean;
}): JSX.Element {
  const scenario: Plt01Scenario = (PLT01_SCENARIOS as readonly string[]).includes(st ?? "")
    ? (st as Plt01Scenario)
    : "a";
  const initialTab: Tab =
    scenario === "f" ? "regions" : scenario === "e" && !production ? "library" : "tenants";
  const [tab, setTab] = useState<Tab>(initialTab);
  const [drawer, setDrawer] = useState(scenario === "b");
  const [wizard, setWizard] = useState(scenario === "c");
  const [support, setSupport] = useState(scenario === "d");
  const [created, setCreated] = useState(scenario === "g");
  return (
    <div data-screen="PLT-01" data-scenario={scenario} className="flex flex-col bg-shell">
      <Toolbar tab={tab} onTab={setTab} production={production} />
      {tab === "tenants" && (
        <Tenants
          rows={CONSOLE_TENANTS}
          created={created}
          onRow={(id) => {
            if (id === "tnt_bh01") setDrawer(true);
          }}
          onProvision={() => {
            setWizard(true);
          }}
          onSupport={() => {
            setSupport(true);
          }}
        />
      )}
      {tab === "regions" && (
        <ul data-plt01="regions" className="m-[12px] rounded-[12px] bg-card shadow-e1">
          {CONSOLE_REGIONS.map((r) => (
            <li
              key={r.name}
              className="flex h-[44px] items-center justify-between px-[12px] hairline-b text-[13px]"
            >
              {r.name}
              <Pill variant={r.live ? "green-tint" : "soon"}>{r.live ? C.live : C.planned}</Pill>
            </li>
          ))}
        </ul>
      )}
      {tab === "library" && !production && (
        <section data-plt01="library" className="m-[12px] rounded-[12px] bg-card shadow-e1">
          <ul>
            {LIBRARY_RELEASES.map((r) => (
              <li
                key={r.version}
                className="flex h-[44px] items-center gap-[8px] px-[12px] hairline-b text-[13px]"
              >
                {[r.channel, r.version, r.agents, r.released, r.tenants]
                  .filter((x) => x !== "")
                  .join(" · ")}
              </li>
            ))}
          </ul>
          <footer className="flex items-center gap-[8px] p-[12px]">
            <Button variant="secondary">{C.promote}</Button>
            <span className="text-[12px] text-ink-3">{C.promoteNote}</span>
          </footer>
        </section>
      )}
      <TenantDrawer
        open={drawer}
        onOpenChange={setDrawer}
        held={scenario === "b"}
        onSupport={() => {
          setSupport(true);
        }}
      />
      <ProvisionWizard
        open={wizard}
        onOpenChange={setWizard}
        held={scenario === "c"}
        onCreate={() => {
          setWizard(false);
          setCreated(true);
        }}
      />
      <SupportSheet open={support} onOpenChange={setSupport} held={scenario === "d"} />
      {created && (
        <div data-plt01="toast">
          <Toast kind="success" text={AW_PROVISION.toast} still />
        </div>
      )}
    </div>
  );
}
