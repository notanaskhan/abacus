import type { EnvelopeListRow } from "@abacus/api-client";
import { envelopeSummaryOptions, listEnvelopesOptions } from "@abacus/api-client/query";
import {
  type Actor,
  Button,
  Checkbox,
  DEFAULT_TZ,
  Drawer,
  DrawerCard,
  type IndexColumn,
  type IndexTile,
  IconButton,
  IndexList,
  type ListEnvelope,
  Menu,
  Segmented,
  StatusPill,
  type ViewState,
  date,
  status,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import { COPY } from "./copy";
import { ImportSheet, RemindDialog, WetSignatureSheet } from "./flows";

// SIG-01 · Signatures hub and evidence drawer (N-02-T11; docs/screens/SIG-01.md; DEC-827). T1 over
// C7's `GET /v1/envelopes` (by tab) and `/summary`: the tabs carry their counts, the tiles filter
// the Out for signature table (Sent, Viewed, Partially signed, Due ≤ 7 days), each row draws its
// signer chips, due tone and work item, and a row opens the O2 drawer. The drawer reads the row:
// the envelope card, one card per signer (DF-11: a locked identity check reads "Needs a
// handwritten signature" with "Upload signed 8879…"), and the retention card. Nothing here sends,
// voids or signs on its own: "Review & send…", "Remind selected…" and "Void…" open their flows
// (SIG-02, the reminder preview, the reason dialog), each a person's act (INV-1).

export type Sig01Tab = "to_send" | "out" | "completed" | "expired";
type Tile = "sent" | "viewed" | "partially_signed" | "due";

const TAB_LABEL: Readonly<Record<Sig01Tab, string>> = {
  to_send: COPY.tabs.toSend,
  out: COPY.tabs.out,
  completed: COPY.tabs.completed,
  expired: COPY.tabs.expired,
};
const TABS: readonly Sig01Tab[] = ["to_send", "out", "completed", "expired"];

const TILES: readonly IndexTile[] = [
  { code: "sent", label: COPY.tiles.sent, variant: "amber" },
  { code: "viewed", label: COPY.tiles.viewed, variant: "amber" },
  { code: "partially_signed", label: COPY.tiles.partiallySigned, variant: "amber" },
  { code: "due", label: COPY.tiles.due, variant: "red-tint" },
];

function daysUntil(day: string, now: Date): number {
  const start = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  return Math.round((Date.parse(`${day}T00:00:00Z`) - start) / 86_400_000);
}

function statusLabel(row: EnvelopeListRow): { label: string; variant: string } {
  const word = status("envelope", row.status);
  const label = word.label
    .replace("{signed}", String(row.signed))
    .replace("{total}", String(row.total));
  return { label, variant: word.variant ?? "neutral" };
}

function Chips({ row }: { row: EnvelopeListRow }): JSX.Element {
  return (
    <span className="flex flex-wrap gap-[4px]">
      {(row.signer_chips ?? []).map((chip) => (
        <span
          key={chip.name}
          className={
            chip.signed
              ? "inline-flex h-[22px] items-center rounded-full bg-green-tint px-[8px] text-meta text-green-ink"
              : "inline-flex h-[22px] items-center rounded-full bg-card px-[8px] text-meta text-ink-2 shadow-e1"
          }
        >
          {chip.signed ? `✓ ${chip.name}` : `○ ${chip.name}`}
        </span>
      ))}
    </span>
  );
}

function SignerCard({ row, index }: { row: EnvelopeListRow; index: number }): JSX.Element {
  const [uploading, setUploading] = useState(false);
  const chip = (row.signer_chips ?? [])[index];
  if (chip === undefined) return <></>;
  // N-02-T27: the chip says which signer locked; older rows fall back to the envelope's flag.
  const locked = !chip.signed && (chip.locked ?? row.needs_handwritten);
  const signerId = chip.signer_id ?? null;
  return (
    <DrawerCard>
      <div className="flex items-center justify-between px-[12px] py-[10px] hairline-b">
        <span className="font-medium">{chip.name}</span>
        <StatusPill variant={chip.signed ? "green-tint" : locked ? "amber" : "neutral"} size="sm">
          {chip.signed
            ? status("envelope_signer", "signed").label
            : locked
              ? COPY.df11.needsHandwritten
              : status("envelope_signer", "pending").label}
        </StatusPill>
      </div>
      {locked && (
        <div className="flex justify-end px-[12px] py-[10px]">
          <Button
            variant="secondary"
            size="sm"
            opensDialog
            disabled={signerId === null}
            onClick={() => {
              setUploading(true);
            }}
          >
            {COPY.df11.upload}
          </Button>
        </div>
      )}
      {locked && signerId !== null && (
        <WetSignatureSheet
          open={uploading}
          row={row}
          signerId={signerId}
          signerName={chip.name}
          onClose={() => {
            setUploading(false);
          }}
        />
      )}
    </DrawerCard>
  );
}

const OPEN_STATUSES: ReadonlySet<string> = new Set(["sent", "viewed", "partially_signed"]);

function EvidenceDrawer({
  row,
  now,
  tz,
  onClose,
  onRemind,
}: {
  row: EnvelopeListRow | null;
  now: Date;
  tz: string;
  onClose: () => void;
  onRemind: (row: EnvelopeListRow) => void;
}): JSX.Element {
  return (
    <Drawer
      open={row !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={row === null ? COPY.drawer.evidence : `${row.number} · ${row.title}`}
      footer={
        <span className="flex gap-[8px]">
          {row !== null && OPEN_STATUSES.has(row.status) && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                onRemind(row);
              }}
            >
              {COPY.drawerRemind}
            </Button>
          )}
          <Button variant="secondary" size="sm">
            {COPY.drawer.download}
          </Button>
        </span>
      }
    >
      {row !== null && (
        <>
          <DrawerCard>
            <dl className="grid grid-cols-[110px_1fr] gap-x-[10px] gap-y-[6px] p-[12px] text-body">
              <dt className="text-ink-3">{COPY.drawer.workItem}</dt>
              <dd>{row.work_item_label}</dd>
              {row.sent_at !== null && (
                <>
                  <dt className="text-ink-3">{COPY.drawer.sent}</dt>
                  <dd>
                    {date(row.sent_at, { now, tz })}
                    {row.sent_by_name !== null && ` by ${row.sent_by_name}`}
                  </dd>
                </>
              )}
              {row.due_on !== null && (
                <>
                  <dt className="text-ink-3">{COPY.drawer.due}</dt>
                  <dd>{date(`${row.due_on}T12:00:00Z`, { now, tz, withYear: true })}</dd>
                </>
              )}
            </dl>
          </DrawerCard>
          {(row.signer_chips ?? []).map((chip, i) => (
            <SignerCard key={chip.name} row={row} index={i} />
          ))}
          <DrawerCard>
            <div className="px-[12px] py-[10px] font-medium hairline-b">
              {COPY.drawer.retention}
            </div>
            <p className="p-[12px] text-body text-ink-2">{COPY.drawer.retentionText}</p>
          </DrawerCard>
        </>
      )}
    </Drawer>
  );
}

export interface SIG01Props {
  initialTab?: Sig01Tab;
  /** The envelope number whose drawer is open (a: "E2"). */
  initialEnvelope?: string | null;
  /** The envelope numbers checked for a bulk reminder (f: E5, E8, E9). */
  initialChecked?: readonly string[];
  /** Import signed package open (r; `?ov=import`). */
  initialImport?: boolean;
}

export function SIG01({
  initialTab = "out",
  initialEnvelope = null,
  initialChecked = [],
  initialImport = false,
}: SIG01Props): JSX.Element {
  const now = useNow();
  const session = useSession();
  const tz = session.tz ?? DEFAULT_TZ;
  const viewer: Actor =
    session.user === null ? { kind: "system" } : { kind: "human", name: session.user.displayName };
  const [checked, setChecked] = useState<ReadonlySet<string>>(new Set(initialChecked));
  const [reminding, setReminding] = useState<readonly EnvelopeListRow[]>([]);
  const [importing, setImporting] = useState(initialImport);
  const [tab, setTab] = useState<Sig01Tab>(initialTab);
  const [tile, setTile] = useState<Tile | null>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<string | null>(initialEnvelope);
  const summary = useQuery(envelopeSummaryOptions());
  const list = useQuery(listEnvelopesOptions({ query: { tab, limit: 100 } }));

  const all = list.data?.items ?? [];
  const due = (r: EnvelopeListRow): boolean =>
    r.due_on !== null && daysUntil(r.due_on, now) <= 7 && daysUntil(r.due_on, now) >= 0;
  const counts: Record<string, number> = {
    sent: all.filter((r) => r.status === "sent").length,
    viewed: all.filter((r) => r.status === "viewed").length,
    partially_signed: all.filter((r) => r.status === "partially_signed").length,
    due: all.filter(due).length,
  };
  const q = query.trim().toLowerCase();
  const rows = all
    .filter((r) => tile === null || (tile === "due" ? due(r) : r.status === tile))
    .filter((r) => q === "" || `${r.number} ${r.title}`.toLowerCase().includes(q));

  const state: ViewState = list.isPending
    ? { kind: "loading" }
    : list.isError
      ? { kind: "error", retry: () => void list.refetch() }
      : all.length === 0
        ? { kind: "empty" }
        : { kind: "ready" };
  const envelope: ListEnvelope<EnvelopeListRow> = {
    items: rows,
    next_cursor: null,
    total: rows.length,
    counts,
  };

  const toggle = (number: string, on: boolean): void => {
    const next = new Set(checked);
    if (on) next.add(number);
    else next.delete(number);
    setChecked(next);
  };
  const picked = all.filter((r) => checked.has(r.number));
  const selectColumn: readonly IndexColumn<EnvelopeListRow>[] =
    tab === "out"
      ? [
          {
            key: "select",
            header: "",
            width: 32,
            cell: (r) => (
              // A check never opens the drawer.
              <span
                role="presentation"
                onClick={(e) => {
                  e.stopPropagation();
                }}
              >
                <Checkbox
                  label={COPY.selection.check(r.number)}
                  checked={checked.has(r.number)}
                  onChange={(on) => {
                    toggle(r.number, on);
                  }}
                />
              </span>
            ),
          },
        ]
      : [];
  const columns: readonly IndexColumn<EnvelopeListRow>[] = [
    ...selectColumn,
    {
      key: "envelope",
      header: COPY.columns.envelope,
      cell: (r) => (
        <span className="flex min-w-0 flex-col">
          <span className="truncate font-medium">{r.title}</span>
          <span className="text-meta text-ink-3">
            {r.drafted_by_name != null && r.sent_at === null
              ? COPY.drafted(r.number, r.drafted_by_name)
              : r.number}
          </span>
        </span>
      ),
    },
    { key: "signers", header: COPY.columns.signers, width: 230, cell: (r) => <Chips row={r} /> },
    {
      key: "sent",
      header: COPY.columns.sent,
      width: 70,
      cell: (r) => (r.sent_at === null ? "—" : date(r.sent_at, { now, tz })),
    },
    {
      key: "viewed",
      header: COPY.columns.viewed,
      width: 70,
      cell: (r) => (r.viewed_at == null ? "—" : date(r.viewed_at, { now, tz })),
    },
    {
      key: "due",
      header: COPY.columns.due,
      width: 110,
      align: "right",
      cell: (r) => {
        if (r.due_on === null) return COPY.datedAsOf;
        const n = daysUntil(r.due_on, now);
        const day = date(`${r.due_on}T12:00:00Z`, { now, tz });
        return n >= 0 && n <= 7 ? (
          <span className="font-medium text-red-ink">{`${day} · ${COPY.days(n)}`}</span>
        ) : (
          day
        );
      },
    },
    {
      key: "work",
      header: COPY.columns.workItem,
      width: 230,
      cell: (r) => <span className="truncate">{r.work_item_label}</span>,
    },
    {
      key: "status",
      header: COPY.columns.status,
      width: 130,
      cell: (r) => {
        const word = statusLabel(r);
        return (
          <span className="flex items-center gap-[6px]">
            <StatusPill variant={word.variant as never} size="state">
              {word.label}
            </StatusPill>
            {tab !== "to_send" && (
              <Menu
                label={COPY.menu.label}
                sections={[[{ label: COPY.menu.void, onSelect: () => undefined }]]}
                trigger={<IconButton icon="ellipsis" label={COPY.menu.label} variant="white" />}
              />
            )}
          </span>
        );
      },
    },
  ];

  const s = summary.data;
  const tabCount: Readonly<Record<Sig01Tab, number | undefined>> = {
    to_send: s?.to_send,
    out: s?.out,
    completed: undefined,
    expired: s?.expired,
  };

  return (
    <div data-screen="SIG-01" className="flex min-h-0 flex-1 flex-col">
      <IndexList<EnvelopeListRow>
        title={TAB_LABEL[tab]}
        noun={COPY.noun}
        state={state}
        envelope={envelope}
        columns={columns}
        rowKey={(r) => r.id}
        twoLine={() => true}
        selected={all.find((r) => r.number === open)?.id ?? null}
        onSelect={(r) => {
          setOpen(r.number);
        }}
        tabs={
          <Segmented
            label={COPY.tabs.label}
            options={TABS.map((t) => {
              const n = tabCount[t];
              return { label: TAB_LABEL[t], ...(n === undefined || n === 0 ? {} : { count: n }) };
            })}
            active={TAB_LABEL[tab]}
            onChange={(label) => {
              setTab(TABS.find((t) => TAB_LABEL[t] === label) ?? "out");
              setTile(null);
            }}
          />
        }
        {...(tab === "out"
          ? {
              tiles: TILES,
              tile,
              onTile: (code: string | null) => {
                setTile(code as Tile | null);
              },
              summary: COPY.summary,
            }
          : {})}
        query={query}
        onQuery={setQuery}
        searchPlaceholder={COPY.search}
        actions={
          <span className="flex gap-[8px]">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setImporting(true);
              }}
            >
              {COPY.importOpen}
            </Button>
            {tab === "out" && (
              <Button
                variant="secondary"
                size="sm"
                disabled={picked.length === 0}
                onClick={() => {
                  setReminding(picked);
                }}
              >
                {COPY.remind}
              </Button>
            )}
          </span>
        }
        {...(tab === "out" && picked.length > 0
          ? {
              footer: (
                <div
                  role="region"
                  aria-label={COPY.selection.selected(picked.length)}
                  className="flex items-center justify-between px-[12px] py-[8px] hairline-t"
                >
                  <span className="text-body">{COPY.selection.selected(picked.length)}</span>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => {
                      setReminding(picked);
                    }}
                  >
                    {COPY.selection.remind(picked.length)}
                  </Button>
                </div>
              ),
            }
          : {})}
        newLabel={COPY.newEnvelope}
        empty={{ title: COPY.empty.title, body: COPY.empty.body }}
      />
      <EvidenceDrawer
        row={all.find((r) => r.number === open) ?? null}
        now={now}
        tz={tz}
        onClose={() => {
          setOpen(null);
        }}
        onRemind={(row) => {
          setReminding([row]);
        }}
      />
      <RemindDialog
        rows={reminding}
        viewer={viewer}
        onClose={() => {
          setReminding([]);
        }}
      />
      <ImportSheet
        open={importing}
        onClose={() => {
          setImporting(false);
        }}
      />
    </div>
  );
}
