import type { ConsentOut } from "@abacus/api-client";
import {
  consentSummaryOptions,
  exportConsentsMutation,
  listConsentsOptions,
  renewConsentsMutation,
  settingsOverviewOptions,
} from "@abacus/api-client/query";
import {
  Button,
  Checkbox,
  EmptyState,
  ErrorState,
  FilterChip,
  Icon,
  Pill,
  SearchField,
  SettingsLayout,
  Skeleton,
  StatusTile,
  Tooltip,
  count,
  date,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useMemo, useState } from "react";
import { todayIso, useNow } from "../../app-core/clock";
import { useOpenHref } from "../../app-core/open";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { hrefOf, to } from "../../routes/to";
import { GROUPS } from "../ADM-01/copy";
import { COPY, PURPOSES, PURPOSE_OPTIONS, SET_PURPOSE, STATUS_TILES, type TileCode } from "./copy";
import { EvidenceDrawer } from "./drawer";

// ADM-05 · Consent registry (§7216) (T-01-T13, part 1; docs/screens/ADM-05.md): the T1 index in
// the T12 frame, section "Consents". Every artboard is a data condition of one screen:
//
//   a  Grace Holloway at E0: tiles 212 · 2 · 1 · 1 · 1 · 1 = 218, the note card, 14 rows needs
//      attention first, the footer's facts
//   b  ?status=expiring: Rao (16 days) and Osterberg (22 days); "Consents · 2"
//   f  ?purpose=offshore_disclosure: "No consents match." / "Clear filters to see all 218."
//   g  rows 3 to 5 checked: the selection bar "3 selected · Renew 3…"
//
// Part 2 (T-01-T32): c, a row's Evidence opens the drawer (each signed document on its own paper);
// d and h, Renew n drafts one envelope per client through C19's renewal (each consent keeps its
// purpose and recipient) and says so in a toast, then opens SIG-02 on the first; e, a declined
// row's status explains why it is never asked again; Export CSV queues the audited export.
// A standard set's two consents share one row. A declined consent is never re-requested: no
// control on its row asks again (§7216, Rev. Proc. 2013-14).

export interface Adm05Search {
  status?: string;
  purpose?: string;
  client?: string;
  q?: string;
}
const KEYS = ["status", "purpose", "client", "q"] as const;
const TILE_CODES = new Set<string>(STATUS_TILES.map((t) => t.code));
const DAY = 86_400_000;

export function parseSearch(search: Record<string, unknown> | string): Adm05Search {
  const entries =
    typeof search === "string"
      ? [...new URLSearchParams(search.startsWith("?") ? search.slice(1) : search).entries()]
      : Object.entries(search);
  const out: Adm05Search = {};
  for (const [key, value] of entries) {
    if ((KEYS as readonly string[]).includes(key) && typeof value === "string" && value !== "") {
      out[key as (typeof KEYS)[number]] = value;
    }
  }
  return out;
}

/** One table row: a consent, or a standard set's two consents. */
interface Line {
  key: string;
  consents: ConsentOut[];
  first: ConsentOut;
}

function lines(items: readonly ConsentOut[]): Line[] {
  const out: Line[] = [];
  const bySet = new Map<string, Line>();
  for (const c of items) {
    const key = c.consent_set_id ?? c.id;
    const found = bySet.get(key);
    if (found !== undefined) {
      found.consents.push(c);
      continue;
    }
    const line = { key, consents: [c], first: c };
    bySet.set(key, line);
    out.push(line);
  }
  return out;
}

function purposeOf(line: Line): string {
  return line.consents.length > 1 ? SET_PURPOSE : PURPOSES[line.first.purpose];
}

/** The scope, with the outside recipient a set's consents name (a standard set's AI-disclosure
 * consent carries the provider; its use consent names only the firm). */
function scopeOf(line: Line): string {
  const label = line.first.scope.label ?? "";
  const recipient = line.consents.flatMap((c) => c.recipients).find((r) => r.kind !== "firm");
  if (recipient === undefined) return label;
  const where = recipient.country === null ? "" : ` (${recipient.country})`;
  return `${label} · ${recipient.name}${where}`;
}

function signerLine(c: ConsentOut): string | null {
  const signers = c.signers ?? [];
  if (signers.length === 0) return null;
  const only = signers[0];
  if (signers.length === 1 && only !== undefined) {
    return only.title === null || only.title === undefined ? null : `${only.name}, ${only.title}`;
  }
  return signers.map((s) => s.name).join(", ");
}

/** Calendar days to the expiry date (the firm's today to the consent's last day), not instants:
 * Sep 14 to Sep 30 is 16 whatever the hour. */
function daysLeft(c: ConsentOut, now: Date): number | null {
  if (c.status !== "signed" || c.expires_at === null) return null;
  const today = todayIso(now.getTime());
  const left = Math.round(
    (Date.parse(`${c.expires_at.slice(0, 10)}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) /
      DAY,
  );
  return left >= 0 && left <= 30 ? left : null;
}

function Signed({ c, now }: { c: ConsentOut; now: Date }): JSX.Element {
  if (c.status === "requested") {
    return (
      <span className="tabular-nums">
        {(c.signers ?? []).map((s, i) => (
          <span key={s.name}>
            {i > 0 && " · "}
            {s.name.split(" ")[0]} {s.signed_at === null ? "○" : `✓ ${date(s.signed_at, { now })}`}
          </span>
        ))}
      </span>
    );
  }
  if (c.status === "declined" && c.declined_at !== null && c.declined_at !== undefined) {
    return <span>{COPY.declinedOn(date(c.declined_at, { now, withYear: true }))}</span>;
  }
  return <span>{date(c.signed_at, { now, withYear: true })}</span>;
}

function Status({ c, now }: { c: ConsentOut; now: Date }): JSX.Element {
  const left = daysLeft(c, now);
  if (c.status === "requested") {
    return (
      <span className="flex flex-col items-start gap-[2px]">
        <Pill variant="amber">{COPY.requested(c.signed_count, c.signer_count)}</Pill>
        <Tooltip content={COPY.envelopeTip}>
          <span className="text-meta text-ink-3">{COPY.envelopeDue}</span>
        </Tooltip>
      </span>
    );
  }
  if (c.status === "declined") {
    return (
      <span className="flex flex-col items-start gap-[2px]">
        <Tooltip content={COPY.declinedTip}>
          <span data-declined-tip>
            <Pill variant="neutral">Declined</Pill>
          </span>
        </Tooltip>
        <span className="text-meta text-ink-3">{COPY.declinedNote}</span>
      </span>
    );
  }
  if (c.status === "expired") return <Pill variant="red-tint">Expired</Pill>;
  if (c.status === "revoked") {
    return (
      <Pill variant="soon">
        {c.revoked_at === null || c.revoked_at === undefined
          ? "Revoked"
          : COPY.revokedOn(date(c.revoked_at, { now, withYear: true }))}
      </Pill>
    );
  }
  if (left !== null) return <Pill variant="amber">{COPY.expiring(left)}</Pill>;
  if (c.status === "superseded") return <Pill variant="muted">Superseded</Pill>;
  return (
    <Pill variant="green">
      {COPY.signedUntil(date(c.expires_at, { now, withYear: true }).replace(",", ""))}
    </Pill>
  );
}

export interface ADM05Props {
  search: Adm05Search;
  onSearch: (next: Adm05Search) => void;
  onNavigate?: (section: string) => void;
  /** "Settings": ADM-01, the settings home, unless a caller takes it. */
  onBack?: () => void;
  /** T-01-T32: SIG-02's builder for a drafted envelope (renewals). */
  onOpenEnvelope?: (envelopeId: string) => void;
}

export function ADM05({
  search,
  onSearch,
  onNavigate,
  onBack,
  onOpenEnvelope,
}: ADM05Props): JSX.Element {
  const now = useNow();
  const open = useOpenHref();
  const home = (): void => {
    open(hrefOf(to.ADM01()));
  };
  const overview = useQuery(settingsOverviewOptions());
  const summary = useQuery(consentSummaryOptions());
  const status =
    search.status !== undefined && TILE_CODES.has(search.status) ? search.status : undefined;
  const query = useMemo(
    () => ({
      ...(status === undefined ? {} : { status: status as ConsentOut["status"] }),
      ...(search.purpose === undefined
        ? {}
        : { purpose: search.purpose as ConsentOut["purpose"] }),
    }),
    [status, search.purpose],
  );
  const list = useQuery(listConsentsOptions({ query }));
  const [chosen, setChosen] = useState<ReadonlySet<string>>(new Set());
  const [drawer, setDrawer] = useState<{ id: string; client: string } | null>(null);
  const exporting = useMutation(exportConsentsMutation());
  const renewing = useMutation(renewConsentsMutation());
  const q = search.q?.toLowerCase();
  const rows = lines(list.data?.items ?? []).filter(
    (l) => q === undefined || l.first.client_name.toLowerCase().includes(q),
  );
  // d, h: one renewal envelope per client, each consent keeping its purpose and recipient.
  const renew = async (): Promise<void> => {
    const drafted: string[] = [];
    for (const l of rows.filter((r) => chosen.has(r.key))) {
      const out = await renewing.mutateAsync({
        body: { consent_ids: l.consents.map((c) => c.id) },
        headers: { "Idempotency-Key": globalThis.crypto.randomUUID() },
      });
      drafted.push(out.envelope_id);
    }
    toast.show(COPY.renewalsDrafted(drafted.length));
    setChosen(new Set());
    const first = drafted[0];
    if (first !== undefined) onOpenEnvelope?.(first);
  };
  const total = summary.data?.total ?? list.data?.total ?? 0;
  const filtered = status !== undefined || search.purpose !== undefined || q !== undefined;
  const set = (patch: Partial<Record<keyof Adm05Search, string | undefined>>): void => {
    const next = { ...search, ...patch };
    const clean: Adm05Search = {};
    for (const key of KEYS) {
      const value = next[key];
      if (value !== undefined && value !== "") clean[key] = value;
    }
    setChosen(new Set());
    onSearch(clean);
  };
  const tileCount = (code: TileCode): number => summary.data?.[code] ?? 0;
  const toggle = (key: string, on: boolean): void => {
    setChosen((prev) => {
      const next = new Set(prev);
      if (on) next.add(key);
      else next.delete(key);
      return next;
    });
  };

  return (
    <SettingsLayout
      bare
      wide
      toolbar={{ nav: [], active: "", firm: "" }}
      title={COPY.title}
      context={overview.data?.firm_name ?? ""}
      backLabel={COPY.back}
      onBack={onBack ?? home}
      navTitle={COPY.navTitle}
      groups={GROUPS.map((g) => ({
        ...g,
        sections: g.sections.filter(
          (s) =>
            [
              "general",
              "people",
              "offices",
              "security",
              "audit-log",
              "consents",
              "integrations",
            ].includes(s.id) || PLANNED_VISIBLE,
        ),
      })).filter((g) => g.sections.length > 0)}
      active="consents"
      onSelect={(id) => {
        if (id === "general") home();
        else if (id === "integrations") open(hrefOf(to.ADM08()));
        else if (id !== "consents") onNavigate?.(id);
      }}
      dirty={false}
    >
      <div className="flex flex-col gap-[8px] p-[12px]">
        <div className="flex flex-wrap items-center gap-[8px]">
          <FilterChip
            label={COPY.filters.purpose}
            icon="file-pen-line"
            options={PURPOSE_OPTIONS}
            value={search.purpose ?? null}
            placeholder={COPY.filters.all}
            clearLabel={COPY.filters.all}
            onChange={(value) => {
              set({ purpose: value ?? undefined });
            }}
          />
          <FilterChip
            label={COPY.filters.status}
            icon="circle"
            options={STATUS_TILES.map((t) => ({ value: t.code, label: t.label }))}
            value={status ?? null}
            placeholder={COPY.filters.all}
            clearLabel={COPY.filters.all}
            onChange={(value) => {
              set({ status: value ?? undefined });
            }}
          />
          <FilterChip
            label={COPY.filters.expires}
            icon="calendar"
            options={[]}
            value={null}
            placeholder={COPY.filters.anyTime}
          />
          <FilterChip
            label={COPY.filters.client}
            icon="users"
            options={[]}
            value={null}
            placeholder={COPY.filters.all}
          />
          <span className="ml-auto inline-flex items-center gap-[8px]">
            {PLANNED_VISIBLE && (
              <Tooltip content={COPY.templatesTip}>
                <span className="text-dense text-ink-2">{COPY.templates}</span>
              </Tooltip>
            )}
            <Button
              variant="secondary"
              disabled={exporting.isPending}
              onClick={() => {
                void exporting
                  .mutateAsync({ headers: { "Idempotency-Key": globalThis.crypto.randomUUID() } })
                  .then(() => {
                    toast.show(COPY.exportQueued);
                  });
              }}
            >
              {COPY.exportCsv}
            </Button>
          </span>
        </div>
        <div className="flex flex-wrap items-stretch gap-[8px]">
          <div role="group" aria-label={COPY.tilesLabel} className="flex flex-wrap gap-[8px]">
            {STATUS_TILES.map((t) => (
              <StatusTile
                key={t.code}
                count={tileCount(t.code)}
                label={t.label}
                variant={t.variant}
                pending={summary.isPending}
                selected={status === t.code}
                onSelect={() => {
                  set({ status: status === t.code ? undefined : t.code });
                }}
              />
            ))}
          </div>
          <p className="flex h-[72px] w-[352px] items-center rounded-pane bg-amber-tint px-[14px] text-dense text-amber-ink">
            {COPY.note}
          </p>
        </div>
        <section
          aria-label={COPY.section}
          className="flex min-h-0 flex-col overflow-hidden rounded-pane bg-card shadow-e2"
        >
          <div className="flex h-[46px] items-center gap-[10px] border-b-[0.5px] border-hair px-[12px]">
            <SearchField
              label={COPY.search}
              placeholder={COPY.search}
              clearLabel={COPY.clearSearch}
              className="w-[220px]"
              value={search.q ?? ""}
              onChange={(value) => {
                set({ q: value === "" ? undefined : value });
              }}
            />
            <h2 className="flex-1 text-center text-pane font-medium">
              {COPY.heading(count(String(filtered ? rows.length : total)))}
            </h2>
            <Tooltip content={COPY.requestTip}>
              <span>
                <Button disabled>
                  <Icon name="plus" size={14} />
                  {COPY.request}
                </Button>
              </span>
            </Tooltip>
          </div>
          {list.isPending && <Skeleton />}
          {list.isError && (
            <ErrorState
              title={COPY.error}
              retryLabel={COPY.retry}
              onRetry={() => {
                void list.refetch();
              }}
            />
          )}
          {list.data !== undefined && rows.length === 0 && (
            <div className="p-[24px]">
              <EmptyState title={COPY.emptyTitle}>
                {COPY.emptyBody(count(String(total)))}
              </EmptyState>
            </div>
          )}
          {rows.length > 0 && (
            <table className="w-full table-fixed text-body">
              <thead>
                <tr className="h-[30px] bg-band-hd text-meta font-medium text-ink-2">
                  <th className="w-[32px]">
                    <span className="sr-only">{COPY.columns.select}</span>
                  </th>
                  <th className="w-[230px] text-left">{COPY.columns.client}</th>
                  <th className="w-[190px] text-left">{COPY.columns.purpose}</th>
                  <th className="w-[230px] text-left">{COPY.columns.scope}</th>
                  <th className="w-[120px] text-left">{COPY.columns.signed}</th>
                  <th className="w-[110px] text-left">{COPY.columns.expires}</th>
                  <th className="w-[150px] text-left">{COPY.columns.status}</th>
                  <th className="w-[44px]">
                    <span className="sr-only">{COPY.columns.evidence}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((l) => {
                  const c = l.first;
                  const signer = signerLine(c);
                  return (
                    <tr
                      key={l.key}
                      data-row={c.client_name}
                      className="h-[44px] border-t-[0.5px] border-hair align-middle"
                    >
                      <td className="text-center">
                        <Checkbox
                          label={COPY.selectRow(c.client_name)}
                          checked={chosen.has(l.key)}
                          disabled={c.status === "declined"}
                          onChange={(on) => {
                            toggle(l.key, on);
                          }}
                        />
                      </td>
                      <td>
                        {/* The client name opens CLI-05's Consents section for that client. */}
                        <a
                          href={hrefOf(to.CLI05({ clientId: c.client_id, sub: "consents" }))}
                          className="block truncate font-medium hover:underline"
                        >
                          {c.client_name}
                        </a>
                        {signer !== null && (
                          <span className="block truncate text-meta text-ink-3">{signer}</span>
                        )}
                      </td>
                      <td className="truncate">{purposeOf(l)}</td>
                      <td className="truncate text-ink-2">{scopeOf(l)}</td>
                      <td>
                        <Signed c={c} now={now} />
                      </td>
                      <td className="tabular-nums">
                        {date(c.expires_at, { now, withYear: true })}
                      </td>
                      <td>
                        <Status c={c} now={now} />
                      </td>
                      <td className="text-center text-ink-2">
                        <button
                          type="button"
                          aria-label={COPY.evidence(c.client_name)}
                          className="inline-flex rounded-[4px] p-[4px] hover:bg-nested"
                          onClick={() => {
                            setDrawer({ id: c.id, client: c.client_name });
                          }}
                        >
                          <Icon name="file-check" size={14} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {rows.length > 0 && (
            <div className="flex h-[36px] items-center gap-[12px] border-t-[0.5px] border-hair px-[18px] text-dense text-ink-3">
              <span>{COPY.footerCount(count(String(rows.length)), count(String(total)))}</span>
              {!filtered && (
                <>
                  <span className="flex-1 text-center">{COPY.loadMore}</span>
                  <span className="truncate">{COPY.footerFacts}</span>
                </>
              )}
            </div>
          )}
        </section>
      </div>
      {drawer !== null && (
        <EvidenceDrawer
          consentId={drawer.id}
          client={drawer.client}
          now={now}
          onClose={() => {
            setDrawer(null);
          }}
        />
      )}
      {chosen.size > 0 && (
        <div
          role="region"
          aria-label={COPY.selected(chosen.size)}
          className="fixed bottom-[24px] left-1/2 flex h-[44px] -translate-x-1/2 items-center gap-[12px] rounded-full bg-espresso px-[16px] text-body text-on-dark"
        >
          <span>{COPY.selected(chosen.size)}</span>
          <span aria-hidden="true">·</span>
          <Tooltip content={COPY.renewTip}>
            <span>
              <Button
                size="sm"
                variant="secondary"
                opensDialog
                disabled={renewing.isPending}
                onClick={() => {
                  void renew();
                }}
              >
                {COPY.renew(chosen.size)}
              </Button>
            </span>
          </Tooltip>
          <button
            type="button"
            className="text-on-dark hover:underline"
            onClick={() => {
              setChosen(new Set());
            }}
          >
            {COPY.clear}
          </button>
        </div>
      )}
    </SettingsLayout>
  );
}

/** The routed page, or a test's: the search kept in state. */
export function ConsentRegistryPage({
  initial = "",
  onNavigate,
}: {
  initial?: string;
  onNavigate?: (section: string) => void;
}): JSX.Element {
  const [search, setSearch] = useState<Adm05Search>(() => parseSearch(initial));
  return (
    <ADM05
      search={search}
      onSearch={setSearch}
      {...(onNavigate === undefined ? {} : { onNavigate })}
    />
  );
}
