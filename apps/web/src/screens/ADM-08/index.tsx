import type { EngineSettingsOut, FormatCheckOut, MappingRowOut } from "@abacus/api-client";
import {
  engineSettingsOptions,
  putEngineSettingsMutation,
  putStatusMirrorMutation,
  testEngineMutation,
} from "@abacus/api-client/query";
import { Button, Drawer, Icon, Pill, Segmented, SettingsLayout, Toggle, toast } from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useEffect, useMemo, useState } from "react";
import { useOpenHref, useOpenOverlay } from "../../app-core/open";
import { hrefOf, ov, to } from "../../routes/to";
import { GROUPS } from "../ADM-01/copy";
import { COPY } from "./copy";

// ADM-08 · Integration settings (T-01-T40; docs/screens/ADM-08.md; handoff spec "ADM-08") at
// /settings/integrations on the T12 frame: the Segmented Tax engine, Ledgers and Mailboxes
// (Signatures & files hidden until DF-07); the CCH Axcess Tax file bridge (fieldset A: connection,
// return-id convention, client code rule, export and import rules with their locks, user and
// office mapping with the Edit mapping drawer g), the workflow status mirror (stored; the sync
// itself comes later), the Connected card of the connectors Accrued has built, Test connection
// (d passed, e failed with Needs reauth and Send reconnect request), the mapping conflict (f:
// Save stays disabled), Ledgers (b: posting only of human-approved batches, attest clients locked)
// and Mailboxes (c). Dirty-state Save and Discard. No control lets the agent export or post.

export type Adm08Segment = "tax-engine" | "ledgers" | "mailboxes";
const KEYS: Record<Adm08Segment, string> = {
  "tax-engine": "cch_axcess",
  ledgers: "ledgers",
  mailboxes: "mailboxes",
};
const LABELS: Record<Adm08Segment, string> = {
  "tax-engine": COPY.segments.tax,
  ledgers: COPY.segments.ledgers,
  mailboxes: COPY.segments.mailboxes,
};
/** The connectors Accrued has built (the row: "Connected card of built connectors only"). */
export const BUILT_CONNECTORS = [
  "CCH Axcess Tax",
  "QuickBooks Online",
  "NetSuite",
  "Sage Intacct",
  "Xero",
  "Microsoft 365",
] as const;

function cellOf(settings: EngineSettingsOut | undefined, key: string): string {
  return settings?.cells.find((c) => c.key === key)?.value ?? "";
}

function lockOf(settings: EngineSettingsOut | undefined, key: string): string | null {
  const found = settings?.cells.find((c) => c.key === key);
  return found?.locked === true ? found.lock_reason : null;
}

/** f: a workflow status that two Accrued statuses map to. */
export function mirrorConflict(rows: readonly MappingRowOut[]): boolean {
  const targets = rows
    .filter((r) => r.kind === "workflow_status" && r.direction === "one_way")
    .map((r) => r.target_value);
  return new Set(targets).size !== targets.length;
}

function Band({ title, right, icon }: { title: string; right?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex h-[40px] items-center gap-[10px] bg-band-hd px-[14px]">
      {icon}
      <h3 className="flex-1 text-[13.5px] font-medium">{title}</h3>
      {right}
    </div>
  );
}

function Value({
  label,
  children,
  help,
  lock,
}: {
  label: string;
  children: ReactNode;
  help?: string | null;
  lock?: string | null;
}): JSX.Element {
  return (
    <div className="flex flex-col gap-[2px] border-t border-hair px-[14px] py-[8px]">
      <div className="flex min-h-[18px] items-center gap-[12px]">
        <span className="w-[260px] shrink-0 text-[13px] text-ink-2">{label}</span>
        <span className="flex flex-1 items-center gap-[6px] text-[13px] font-medium">
          {children}
          {lock != null && (
            <span aria-label={lock} title={lock}>
              <Icon name="lock" size={12} />
            </span>
          )}
        </span>
      </div>
      {help != null && <p className="pl-[272px] text-[11.5px] text-ink-3">{help}</p>}
    </div>
  );
}

function Switch({
  label,
  on,
  locked,
  onChange,
}: {
  label: string;
  on: boolean;
  locked: boolean;
  onChange: (on: boolean) => void;
}): JSX.Element {
  return <Toggle label={label} checked={on} disabled={locked} onChange={onChange} />;
}

function Sub({ title }: { title: string }): JSX.Element {
  return (
    <h4 className="border-t border-hair bg-nested px-[14px] py-[6px] text-[12px] font-medium text-ink-2">
      {title}
    </h4>
  );
}

function TestRow({ result }: { result: FormatCheckOut }): JSX.Element {
  return result.ok ? (
    <p role="status" className="border-t border-hair px-[14px] py-[8px] text-[12.5px] text-green">
      {COPY.testPassed(result.returns_read ?? 0)}
    </p>
  ) : (
    <p role="alert" className="border-t border-hair px-[14px] py-[8px] text-[12.5px] text-red">
      {COPY.testFailed(result.problems.join(" · "))}
    </p>
  );
}

function TaxEngine({
  settings,
  cells,
  setCell,
  onEditMapping,
  conflict,
}: {
  settings: EngineSettingsOut;
  cells: Record<string, string>;
  setCell: (key: string, value: string) => void;
  onEditMapping: () => void;
  conflict: boolean;
}): JSX.Element {
  const users = settings.mappings.filter((m) => m.kind === "user");
  const offices = settings.mappings.filter((m) => m.kind === "office");
  const mirror = settings.mappings.filter((m) => m.kind === "workflow_status");
  const unmapped = users.filter((u) => u.target_value === "").length;
  const value = (key: string): string => cells[key] ?? cellOf(settings, key);
  const openOverlay = useOpenOverlay();
  const toggle = (key: string, label: string): JSX.Element => (
    <Value label={label} lock={lockOf(settings, key)}>
      <Switch
        label={label}
        on={value(key) === "on"}
        locked={lockOf(settings, key) !== null}
        onChange={(on) => {
          setCell(key, on ? "on" : "off");
        }}
      />
    </Value>
  );
  return (
    <div className="flex flex-col gap-[12px]">
      <section aria-label={COPY.engine.title} className="rounded-[12px] bg-card shadow-e1">
        <Band
          title={COPY.engine.title}
          icon={
            <span className="flex size-[24px] items-center justify-center rounded-[8px] bg-green text-on-ink">
              <Icon name="table" size={14} />
            </span>
          }
          right={<Pill variant="green">{COPY.engine.connected}</Pill>}
        />
        <Value label={COPY.engine.rows.connection}>{value("connection")}</Value>
        <Value label={COPY.engine.rows.last_sync}>
          {/* ADM-08 → TAX-09: the return of the last sync, its engine sync over the page. */}
          {settings.last_sync_return_id == null ? (
            value("last_sync")
          ) : (
            <button
              type="button"
              className="text-left hover:underline"
              onClick={() => {
                openOverlay(ov.TAX09(settings.last_sync_return_id ?? ""));
              }}
            >
              {value("last_sync")} ›
            </button>
          )}
        </Value>
        <Value label={COPY.engine.rows.return_id_template} help={COPY.engine.returnIdHelp}>
          {value("return_id_template")}
        </Value>
        <Value label={COPY.engine.rows.client_code_rule} help={COPY.engine.clientCodeHelp}>
          {value("client_code_rule")}
        </Value>
        {toggle("new_version_on_import", COPY.engine.rows.new_version_on_import)}
        <Sub title={COPY.engine.rulesTitle} />
        <Value
          label={COPY.engine.rules.export_after_final_approval}
          help={lockOf(settings, "export_after_final_approval")}
          lock={lockOf(settings, "export_after_final_approval")}
        >
          <Switch
            label={COPY.engine.rules.export_after_final_approval}
            on={value("export_after_final_approval") === "on"}
            locked
            onChange={() => undefined}
          />
        </Value>
        <Value label={COPY.engine.rules.who_may_export}>{value("who_may_export")}</Value>
        {toggle("import_requires_approval", COPY.engine.rules.import_requires_approval)}
        {toggle("read_diagnostics", COPY.engine.rules.read_diagnostics)}
        <Value label={COPY.engine.rules.efile_status_every}>{value("efile_status_every")}</Value>
        <Sub title={COPY.engine.usersTitle} />
        <div className="flex items-center gap-[12px] border-t border-hair px-[14px] py-[8px] text-[13px]">
          <span className="flex-1">
            {COPY.engine.usersMapped(users.length - unmapped, users.length)}
          </span>
          <span className="text-ink-3">{COPY.engine.unmapped(unmapped)}</span>
          <button type="button" className="text-[12.5px] underline" onClick={onEditMapping}>
            {COPY.engine.editMapping}
          </button>
        </div>
        <Sub title={COPY.engine.officesTitle} />
        {offices.map((o) => (
          <Value key={o.source_key} label={o.source_key}>
            {o.target_value}
          </Value>
        ))}
      </section>
      <section aria-label={COPY.mirror.title} className="rounded-[12px] bg-card shadow-e1">
        <Band
          title={COPY.mirror.title}
          right={
            <Switch
              label={COPY.mirror.on}
              on={value("status_mirror") === "on"}
              locked={false}
              onChange={(on) => {
                setCell("status_mirror", on ? "on" : "off");
              }}
            />
          }
        />
        <p className="px-[14px] py-[6px] text-[12px] text-ink-3">{COPY.mirror.help}</p>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="h-[30px] text-left text-[11.5px] text-ink-3">
              {COPY.mirror.columns.map((c) => (
                <th key={c} className="px-[14px] font-normal">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {mirror.map((m) => (
              <tr key={m.source_key} className="h-[34px] border-t border-hair">
                <td className="px-[14px]">{m.source_key}</td>
                <td className="px-[14px] text-ink-3">{m.direction === "two_way" ? "↔" : "→"}</td>
                <td className="px-[14px]">{m.target_value}</td>
                <td className="px-[14px] text-ink-3">
                  {m.direction === "two_way" ? COPY.mirror.twoWay : COPY.mirror.oneWay}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {conflict && (
          <p role="alert" className="border-t border-hair px-[14px] py-[8px] text-[12px] text-red">
            {COPY.mirror.conflict}
          </p>
        )}
        <p className="border-t border-hair px-[14px] py-[8px] text-[12px] text-ink-3">
          {COPY.mirror.footer}
        </p>
      </section>
    </div>
  );
}

function Ledgers({
  settings,
  failed,
}: {
  settings: EngineSettingsOut;
  failed: boolean;
}): JSX.Element {
  const ledgers = useMemo(() => {
    const by = new Map<string, string[]>();
    for (const m of settings.mappings) {
      by.set(m.source_key, [...(by.get(m.source_key) ?? []), m.target_value]);
    }
    return [...by.entries()];
  }, [settings]);
  const reauth = failed || cellOf(settings, "sage_intacct_state") === "needs_reauth";
  return (
    <section aria-label={COPY.ledgers.title} className="rounded-[12px] bg-card shadow-e1">
      <Band title={COPY.ledgers.title} />
      {(
        [
          "post_only_approved",
          "attest_clients",
          "journal_memo",
          "journal_prefix",
          "post_as",
        ] as const
      ).map((key) => (
        <Value
          key={key}
          label={COPY.ledgers.rows[key]}
          lock={lockOf(settings, key)}
          help={key === "attest_clients" ? lockOf(settings, key) : null}
        >
          {key === "post_only_approved" ? (
            <Switch label={COPY.ledgers.rows[key]} on locked onChange={() => undefined} />
          ) : (
            cellOf(settings, key)
          )}
        </Value>
      ))}
      {ledgers.map(([ledger, clients]) => (
        <div key={ledger}>
          <Sub title={`${ledger} · ${String(clients.length)}`} />
          <ul>
            {clients.map((c) => (
              <li
                key={c}
                className="flex items-center gap-[8px] border-t border-hair px-[14px] py-[6px] text-[12.5px]"
              >
                <span className="flex-1">{c}</span>
                {ledger === "Sage Intacct" && reauth && (
                  <Pill variant="amber">{COPY.ledgers.needsReauth}</Pill>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
      {reauth && (
        <div className="flex flex-col gap-[8px] border-t border-hair px-[14px] py-[10px]">
          <p className="text-[12px] text-red">{COPY.ledgers.failedHelp}</p>
          <Button variant="secondary" size="sm" className="self-start">
            {COPY.ledgers.reconnect}
          </Button>
        </div>
      )}
      <p className="border-t border-hair px-[14px] py-[8px] text-[11.5px] text-ink-3">
        {COPY.ledgers.help}
      </p>
    </section>
  );
}

function Mailboxes({ settings }: { settings: EngineSettingsOut }): JSX.Element {
  const open = useOpenHref();
  return (
    <section aria-label={COPY.segments.mailboxes} className="rounded-[12px] bg-card shadow-e1">
      <Band title={cellOf(settings, "mailbox")} />
      {Object.entries(COPY.mailboxes.rows)
        .filter(([key]) => key !== "mailbox")
        .map(([key, label]) => {
          const value = cellOf(settings, key);
          return (
            <Value key={key} label={label}>
              {value === "on" || value === "off" ? (
                <Switch
                  label={label}
                  on={value === "on"}
                  locked={false}
                  onChange={() => undefined}
                />
              ) : key === "unmatched_senders" ? (
                // ADM-08 → INB-01: the Inbox, where unmatched senders wait (T-01-T51).
                <button
                  type="button"
                  className="text-left hover:underline"
                  onClick={() => {
                    open(hrefOf(to.INB01()));
                  }}
                >
                  {`${value} ›`}
                </button>
              ) : (
                `${value} ›`
              )}
            </Value>
          );
        })}
    </section>
  );
}

export interface Adm08Props {
  segment?: Adm08Segment;
  /** g: the Edit mapping drawer open (`?ov=integration-mapping:users`). */
  mappingOpen?: boolean;
  onSegment?: (segment: Adm08Segment) => void;
  onMapping?: (open: boolean) => void;
  onNavigate?: (section: string) => void;
  onBack?: () => void;
  /** d and e: run Test connection on open (the artboards show its result). */
  testOnOpen?: boolean;
}

export function ADM08({
  segment = "tax-engine",
  mappingOpen = false,
  onSegment,
  onMapping,
  onNavigate,
  onBack,
  testOnOpen = false,
}: Adm08Props): JSX.Element {
  const [active, setActive] = useState<Adm08Segment>(segment);
  const openHref = useOpenHref();
  const [drawer, setDrawer] = useState(mappingOpen);
  const key = KEYS[active];
  const settings = useQuery(engineSettingsOptions({ path: { key } }));
  const [cells, setCells] = useState<Record<string, string>>({});
  const [result, setResult] = useState<FormatCheckOut | null>(null);
  const test = useMutation({
    ...testEngineMutation(),
    onSuccess: (found) => {
      setResult(found);
      if (found.ok) toast.show(COPY.testPassedToast);
    },
  });
  const save = useMutation({
    ...putEngineSettingsMutation(),
    onSuccess: () => {
      setCells({});
      toast.show(COPY.saved);
    },
  });
  const mirrorSave = useMutation({ ...putStatusMirrorMutation() });
  useEffect(() => {
    setActive(segment);
  }, [segment]);
  useEffect(() => {
    setCells({});
    setResult(null);
  }, [key]);
  useEffect(() => {
    if (testOnOpen && settings.data !== undefined && result === null && !test.isPending) {
      test.mutate({ path: { key } });
    }
  }, [testOnOpen, settings.data, result, test, key]);
  const data = settings.data;
  const conflict = data !== undefined && mirrorConflict(data.mappings);
  const dirty = Object.keys(cells).length > 0;
  const canConfigure = data?.allowed_actions.includes("integration.configure") ?? false;
  return (
    <SettingsLayout
      bare
      wide
      toolbar={{ nav: [], active: "", firm: "" }}
      title={COPY.title}
      context=""
      backLabel={COPY.back}
      onBack={onBack ?? (() => undefined)}
      navTitle={COPY.navTitle}
      groups={GROUPS}
      active="integrations"
      onSelect={(id) => {
        // Built settings screens open through the manifest's builders (T-01-T51).
        if (id === "general") openHref(hrefOf(to.ADM01()));
        else if (id === "consents") openHref(hrefOf(to.ADM05()));
        else if (id !== "integrations") onNavigate?.(id);
      }}
      dirty={dirty}
      invalid={conflict}
      readOnly={data !== undefined && !canConfigure}
      labels={{ save: COPY.save, discard: COPY.discard }}
      onDiscard={() => {
        setCells({});
      }}
      onSave={() => {
        if (data === undefined || conflict) return;
        save.mutate({ path: { key }, body: { cells, seen_version: data.version } });
        if (active === "tax-engine") {
          const rows = Object.fromEntries(
            data.mappings
              .filter((m) => m.kind === "workflow_status")
              .map((m) => [m.source_key, m.target_value]),
          );
          mirrorSave.mutate({ path: { key }, body: { rows, seen_version: data.version } });
        }
      }}
    >
      <div className="flex flex-col" data-screen="ADM-08">
        <header className="flex h-[46px] items-center gap-[8px] px-[12px]">
          <h2 className="text-[14.5px] font-medium">{COPY.title}</h2>
          <div className="flex flex-1 justify-center">
            <Segmented
              size="small"
              label={COPY.title}
              options={Object.values(LABELS)}
              active={LABELS[active]}
              onChange={(label) => {
                const next = (Object.keys(LABELS) as Adm08Segment[]).find(
                  (s) => LABELS[s] === label,
                );
                if (next !== undefined) {
                  setActive(next);
                  onSegment?.(next);
                }
              }}
            />
          </div>
          <Button
            variant="secondary"
            size="sm"
            disabled={data === undefined || test.isPending}
            onClick={() => {
              test.mutate({ path: { key } });
            }}
          >
            {COPY.test}
          </Button>
        </header>
        <div className="grid grid-cols-[860fr_230fr] gap-[12px] bg-shell p-[12px]">
          <div className="flex flex-col gap-[12px]">
            {result !== null && (
              <div className="rounded-[12px] bg-card shadow-e1">
                <TestRow result={result} />
              </div>
            )}
            {data === undefined ? (
              <div aria-busy className="h-[200px]" />
            ) : active === "tax-engine" ? (
              <TaxEngine
                settings={data}
                cells={cells}
                setCell={(k, v) => {
                  setCells((c) => ({ ...c, [k]: v }));
                }}
                onEditMapping={() => {
                  setDrawer(true);
                  onMapping?.(true);
                }}
                conflict={conflict}
              />
            ) : active === "ledgers" ? (
              <Ledgers settings={data} failed={result !== null && !result.ok} />
            ) : (
              <Mailboxes settings={data} />
            )}
          </div>
          <aside
            aria-label={COPY.connected.band(BUILT_CONNECTORS.length)}
            className="self-start rounded-[12px] bg-card shadow-e1"
          >
            <Band title={COPY.connected.band(BUILT_CONNECTORS.length)} />
            <ul>
              {BUILT_CONNECTORS.map((name) => (
                <li
                  key={name}
                  className="flex h-[30px] items-center gap-[8px] border-t border-hair px-[14px] text-[12.5px]"
                >
                  <Icon name="check" size={12} />
                  {name}
                </li>
              ))}
            </ul>
            <p className="border-t border-hair px-[14px] py-[8px] text-[12px]">
              {COPY.connected.footer}
            </p>
          </aside>
        </div>
      </div>
      <Drawer
        open={drawer}
        onOpenChange={(open) => {
          setDrawer(open);
          onMapping?.(open);
        }}
        title={COPY.drawer.title}
        width={420}
      >
        <ul aria-label={COPY.engine.usersTitle}>
          {(data?.mappings ?? [])
            .filter((m) => m.kind === "user")
            .map((m) => (
              <li
                key={m.source_key}
                className="flex h-[36px] items-center gap-[10px] border-t border-hair px-[14px] text-[13px]"
              >
                <span
                  aria-hidden
                  className="flex size-[24px] items-center justify-center rounded-full bg-nested text-[11px] font-medium"
                >
                  {m.source_key
                    .split(" ")
                    .map((p) => p[0] ?? "")
                    .join("")
                    .slice(0, 2)}
                </span>
                <span className="flex-1">{m.source_key}</span>
                <span className="text-[12px] text-ink-3">
                  {COPY.drawer.staffId} {m.target_value}
                </span>
              </li>
            ))}
        </ul>
      </Drawer>
    </SettingsLayout>
  );
}
