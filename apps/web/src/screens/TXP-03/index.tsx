// TXP-03 · Review › Fixed Assets (T-06-T29; docs/screens/TXP-03.md; T-06 §3 F1): T6 inside the
// entity return's layout. The control bar (Register · By property · Dispositions, the title, the
// sign-off chips, Open in Excel and Sign off…), the tally strip and the register in the statement
// grammar with property group rows, the roof's Flag chip and the Larimer bonus Check chip. A row
// opens the O2 Asset detail drawer (a2): the invoice, the bonus date test, and the class and bonus
// pickers, whose choice is a ghost proposal until a reviewer approves it (C3). Every figure, total
// and tie is the server's (`GET …/fixed-assets`, E3 with engine_version and inputs_hash); the
// screen formats and adds nothing (ADR-050). Sign off… while a flag is open asks for a note.
import type { TaxDepthAssetRowOut, TaxDepthFixedAssetsOut } from "@abacus/api-client";
import {
  Button,
  DataGrid,
  Drawer,
  EmptyState,
  Picker,
  Pill,
  Segmented,
  SkeletonRows,
  type TableColumn,
  type TableRow,
  type TallyItem,
  TallyStrip,
  amount,
  date,
  monthYear,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

export type Txp03View = TaxDepthFixedAssetsOut["view"];
export interface AssetProposal {
  recovery_class?: TaxDepthAssetRowOut["recovery_class"];
  bonus_pct?: string;
}

const VIEW_LABEL: Record<Txp03View, string> = {
  register: COPY.register,
  by_property: COPY.byProperty,
  dispositions: COPY.dispositions,
};
const MONEY = { type: "num", format: "whole" } as const;
const PROPERTY_NAME: Record<string, string> = {
  "elm-street": "Elm Street, Chicago",
  larimer: "Larimer Lofts, Denver",
  bergen: "Bergen Street, Brooklyn",
};
const CUTOFF = "2025-01-19";
const NOW = Date.parse("2026-09-14T09:24:00-05:00");

const placed = (iso: string): string => monthYear(iso);
const day = (iso: string): string => date(iso, { now: NOW, withYear: true });
const pct = (v: string): string => (Number(v) === 0 ? "—" : `${v}%`);

function tie(label: string, state: string): TallyItem {
  if (state === "tie") return { label, tally: "tie" };
  if (state === "off") return { label, tally: "off", vars: { amount: "" } };
  return { label, pill: { text: COPY.check, variant: "amber" } };
}

export function tallyItems(fa: TaxDepthFixedAssetsOut | undefined): TallyItem[] {
  if (fa === undefined) {
    return Object.values(COPY.cards).map((label) => ({
      label,
      pill: { text: COPY.pending, variant: "neutral" as const },
    }));
  }
  const v = (label: string, value: string): TallyItem => ({
    label,
    value: amount(value, "whole").text,
  });
  return [
    tie(COPY.cards.ties, fa.ties_to_tb),
    tie(COPY.cards.book, fa.book_equals_tax),
    tie(COPY.cards.bonus, fa.bonus_eligibility),
    v(COPY.cards.cost, fa.depreciable_cost),
    v(COPY.cards.land, fa.land),
    v(COPY.cards.current, fa.current),
    v(COPY.cards.accumulated, fa.accumulated),
  ];
}

export const REGISTER_COLUMNS: TableColumn[] = [
  { key: "asset", header: COPY.columns.asset, type: "label", width: 260 },
  { key: "placed", header: COPY.columns.placed, type: "text", width: 120 },
  { key: "cost", header: COPY.columns.cost, ...MONEY, width: 110 },
  { key: "life", header: COPY.columns.life, type: "text", width: 170 },
  { key: "method", header: COPY.columns.method, type: "text", width: 70 },
  { key: "convention", header: COPY.columns.convention, type: "text", width: 56 },
  { key: "bonus", header: COPY.columns.bonus, type: "text", width: 64, align: "right" },
  { key: "prior", header: COPY.columns.prior, ...MONEY, width: 104 },
  { key: "current", header: COPY.columns.current, ...MONEY, width: 100 },
  { key: "accumulated", header: COPY.columns.accumulated, ...MONEY, width: 110 },
  { key: "check", header: COPY.columns.check, type: "chip", width: 96 },
];

/** Register rows under their Form 8825 property's group row (properties in first-seen order). */
export function registerRows(rows: readonly TaxDepthAssetRowOut[]): TableRow[] {
  const out: TableRow[] = [];
  const keys = [...new Set(rows.map((r) => r.property_key))];
  const ordered = keys.flatMap((k) => rows.filter((r) => r.property_key === k));
  let group: string | null = null;
  for (const r of ordered) {
    if (r.property_key !== group) {
      group = r.property_key;
      out.push({
        id: `group:${group}`,
        kind: "group",
        label: PROPERTY_NAME[group] ?? group,
        cells: {},
      });
    }
    const flagged = (r.flags ?? 0) > 0;
    out.push({
      id: r.asset_id,
      label: r.description,
      indent: 1,
      ...(flagged ? { tag: COPY.flag } : {}),
      cells: {
        placed: { value: placed(r.placed_in_service) },
        cost: { value: r.cost },
        life: { value: COPY.life[r.recovery_class] ?? r.recovery_class },
        method: { value: r.method },
        convention: { value: r.convention },
        bonus: { value: pct(r.bonus_pct) },
        prior: { value: r.prior },
        current: { value: r.current },
        accumulated: { value: r.accumulated },
        check:
          r.bonus_check === "check"
            ? { value: COPY.check }
            : r.bonus_check === "tie"
              ? { value: "tie" }
              : { value: null, text: "—" },
      },
    });
  }
  return out;
}

const PROPERTY_COLUMNS: TableColumn[] = [
  { key: "property", header: "", type: "label", width: 300 },
  { key: "land", header: COPY.columns.land, ...MONEY, width: 140 },
  { key: "depreciation", header: COPY.columns.depreciation, ...MONEY, width: 160 },
];

export function propertyRows(fa: TaxDepthFixedAssetsOut): TableRow[] {
  return [
    ...(fa.by_property ?? []).map((p) => ({
      id: p.property_key,
      label: p.name,
      cells: { land: { value: p.land }, depreciation: { value: p.depreciation } },
    })),
    {
      id: "total",
      kind: "total" as const,
      label: COPY.propertyTotal,
      cells: { land: { value: fa.land }, depreciation: { value: fa.current } },
    },
  ];
}

const CLASSES = ["5", "7", "15", "27.5", "39"] as const;
const BONUSES = ["0", "40", "100"] as const;

export function AssetDrawer({
  asset,
  onClose,
  onOpenInvoice,
  onPropose,
}: {
  asset: TaxDepthAssetRowOut;
  onClose: () => void;
  onOpenInvoice?: () => void;
  onPropose?: (change: AssetProposal) => void;
}): JSX.Element {
  const [life, setLife] = useState<string>(asset.recovery_class);
  const [bonus, setBonus] = useState<string>(String(Number(asset.bonus_pct)));
  const changed = life !== asset.recovery_class || bonus !== String(Number(asset.bonus_pct));
  const ghost = [
    ...(life !== asset.recovery_class ? [COPY.life[life] ?? life] : []),
    ...(bonus !== String(Number(asset.bonus_pct)) ? [`${bonus}% bonus`] : []),
  ].join(" · ");
  const bonusEligible = asset.placed_in_service >= CUTOFF;
  return (
    <Drawer
      open
      width={480}
      title={COPY.drawer.title(asset.description)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <div data-asset-drawer={asset.asset_id} className="flex flex-col gap-[12px] text-body">
        {onOpenInvoice === undefined ? null : (
          <Button variant="secondary" size="sm" icon="file-text" onClick={onOpenInvoice}>
            {COPY.drawer.invoice}
          </Button>
        )}
        <section aria-label={COPY.drawer.bonusTest} className="flex flex-col gap-[4px]">
          <h3 className="text-dense font-medium text-ink">{COPY.drawer.bonusTest}</h3>
          <p className="text-ink-2">{COPY.drawer.placed(day(asset.placed_in_service))}</p>
          {bonusEligible ? <p className="text-ink-2">{COPY.drawer.cutoff(day(CUTOFF))}</p> : null}
          <p data-bonus-test={asset.bonus_check} className="text-ink-2">
            {asset.bonus_check === "check" ? COPY.drawer.waiting : COPY.drawer.contract}
          </p>
        </section>
        <div className="flex flex-wrap items-center gap-[8px]">
          <Picker
            label={COPY.drawer.classLabel}
            value={life}
            onChange={setLife}
            options={CLASSES.map((c) => ({ value: c, label: COPY.life[c] ?? c }))}
          />
          <Picker
            label={COPY.drawer.bonusLabel}
            value={bonus}
            onChange={setBonus}
            options={BONUSES.map((b) => ({ value: b, label: `${b}%` }))}
          />
        </div>
        {changed ? (
          <div className="flex items-center gap-[8px]">
            <span
              data-ghost=""
              className="rounded-pill px-[8px] py-[2px] text-dense text-ink-3 inset-ring-[0.5px] inset-ring-hair"
            >
              {COPY.drawer.proposed(ghost)}
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                onPropose?.({
                  ...(life === asset.recovery_class
                    ? {}
                    : { recovery_class: life as TaxDepthAssetRowOut["recovery_class"] }),
                  ...(bonus === String(Number(asset.bonus_pct)) ? {} : { bonus_pct: bonus }),
                });
              }}
            >
              {COPY.drawer.propose}
            </Button>
          </div>
        ) : null}
      </div>
    </Drawer>
  );
}

export interface TXP03Props {
  fixedAssets: TaxDepthFixedAssetsOut | undefined;
  view: Txp03View;
  /** The asset whose drawer is open (a2). */
  assetId?: string | null;
  signOffOpen?: boolean;
  signedBy?: string | undefined;
  onView?: (view: Txp03View) => void;
  onAsset?: (assetId: string | null) => void;
  onOpenInvoice?: () => void;
  onPropose?: (assetId: string, change: AssetProposal) => void;
  onOpenExcel?: () => void;
  onOpenProject?: () => void;
  onSignOff?: (note: string | null) => void;
  onSignOffOpen?: (open: boolean) => void;
}

export function TXP03({
  fixedAssets: fa,
  view,
  assetId,
  signOffOpen = false,
  signedBy,
  onView,
  onAsset,
  onOpenInvoice,
  onPropose,
  onOpenExcel,
  onOpenProject,
  onSignOff,
  onSignOffOpen,
}: TXP03Props): JSX.Element {
  const [note, setNote] = useState("");
  const flags = (fa?.rows ?? []).filter((r) => (r.flags ?? 0) > 0).length;
  const open = fa?.rows.find((r) => r.asset_id === assetId);
  const signOff = () => {
    if (flags > 0) onSignOffOpen?.(true);
    else onSignOff?.(null);
  };
  return (
    <div data-screen="TXP-03" className="flex min-h-0 flex-1 flex-col">
      <div
        data-entity="control-bar"
        className="flex h-[44px] flex-none items-center gap-[8px] px-[12px]"
      >
        <Segmented
          size="small"
          label={COPY.views}
          options={[COPY.register, COPY.byProperty, COPY.dispositions]}
          active={VIEW_LABEL[view]}
          {...(onView === undefined
            ? {}
            : {
                onChange: (label: string) => {
                  const next = (Object.keys(VIEW_LABEL) as Txp03View[]).find(
                    (k) => VIEW_LABEL[k] === label,
                  );
                  if (next !== undefined) onView(next);
                },
              })}
        />
        <span className="flex-1 text-center text-[14.5px] font-medium text-ink">{COPY.title}</span>
        {signedBy !== undefined ? (
          <>
            <Pill variant="neutral">{COPY.signedChip(signedBy)}</Pill>
            <Pill variant="green">{COPY.reviewed(signedBy)}</Pill>
          </>
        ) : null}
        {onOpenProject === undefined ? null : (
          <Button variant="ghost" size="sm" onClick={onOpenProject}>
            {COPY.openProject}
          </Button>
        )}
        <Button variant="ghost" size="sm" icon="file-spreadsheet" onClick={onOpenExcel}>
          {COPY.openExcel}
        </Button>
        {signedBy === undefined ? (
          <Button variant="secondary" size="sm" onClick={signOff}>
            {COPY.signOff}
          </Button>
        ) : null}
      </div>
      <TallyStrip label={COPY.tally} items={tallyItems(fa)} className="px-[12px] pb-[10px]" />
      {signOffOpen ? (
        <div
          role="dialog"
          aria-label={COPY.signOff}
          className="mx-[12px] mb-[10px] rounded-[10px] border border-amber bg-amber-tint p-[12px]"
        >
          <p className="mb-[8px] text-body text-amber-ink">
            {COPY.signOffDialog.blocked(Math.max(1, flags))}
          </p>
          <label className="mb-[8px] flex flex-col gap-[4px] text-body text-ink">
            {COPY.signOffDialog.note}
            <textarea
              value={note}
              onChange={(e) => {
                setNote(e.target.value);
              }}
              rows={2}
              className="rounded-[6px] border border-hair bg-card p-[6px]"
            />
          </label>
          <div className="flex gap-[8px]">
            <Button
              variant="primary"
              size="sm"
              disabled={note.trim() === ""}
              onClick={() => onSignOff?.(note.trim())}
            >
              {COPY.signOffDialog.signWithNote}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => onSignOffOpen?.(false)}>
              {COPY.signOffDialog.cancel}
            </Button>
          </div>
        </div>
      ) : null}
      <div className="min-h-0 flex-1 overflow-auto px-[12px] pb-[12px]">
        {fa === undefined ? (
          <SkeletonRows type="table" immediate label={COPY.table} />
        ) : view === "dispositions" ? (
          <EmptyState title={COPY.emptyTitle} icon="archive">
            {COPY.emptyBody}
          </EmptyState>
        ) : view === "by_property" ? (
          <DataGrid
            label={COPY.byProperty}
            grammar="statement"
            columns={PROPERTY_COLUMNS}
            rows={propertyRows(fa)}
          />
        ) : (
          <>
            <DataGrid
              label={COPY.table}
              grammar="statement"
              columns={REGISTER_COLUMNS}
              rows={registerRows(fa.rows)}
              onOpen={(row) => {
                if (!row.id.startsWith("group:")) onAsset?.(row.id);
              }}
            />
            {flags > 0 ? (
              <p className="mt-[8px] text-[11.5px] text-ink-3">{`${COPY.flag} · ${COPY.flagged}`}</p>
            ) : null}
          </>
        )}
      </div>
      {open !== undefined ? (
        <AssetDrawer
          asset={open}
          onClose={() => onAsset?.(null)}
          {...(onOpenInvoice === undefined ? {} : { onOpenInvoice })}
          onPropose={(change) => onPropose?.(open.asset_id, change)}
        />
      ) : null}
    </div>
  );
}
