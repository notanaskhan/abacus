// TPL-24 "Accrued add-in — AP leadsheet.xlsx" (F-08-T19; TASK-8926; handoff TPL-24 a–g;
// DEC-5928): the T22 add-in pane (C-39 AddinChrome) in the drawn host frames, on the Granite Peak
// AP leadsheet seed (fixtures/seed/granite-peak-fy2026-ap-leadsheet.ts, footed by its test).
// Wed Sep 30, 2026, Cole Hart (CH), Brightwater Hale SSO:
//   a 2:15 PM Link (D14 =SUM(D12:D13) linked 2:12, the only link) · b Tickmarks (✓ 2 · ⊕ 1 · ∧ 0
//   · ◊ 3 · ¢ 0) · c 2:21 PM Sign-off (P CH signed, reviewer awaited; D13 linked 2:16) · d 2:40 PM
//   Changed after sign-off (exactly F12–F14; P stale) · e Offline (2 changes waiting; sign-off
//   off) · f Word host, Mon Oct 26 4:15 PM, Hannah Leclerc (Incoming changes (2)) · g Signed out.
// Host greys only, no host brand colours or Microsoft marks; every sign-off is a person's in
// SHL-12 (the pane only opens it). Gallery only.
import {
  AddinCard,
  AddinChrome,
  type AddinTab,
  Button,
  Icon,
  SearchField,
  Toggle,
  count,
  pct,
} from "@abacus/ui";
import { ExcelGrid, type HostCell, HostWindow, WordPage } from "@abacus/ui/specimens";
import type { JSX } from "react";
import { AP_LEADSHEET } from "../../../fixtures/seed/granite-peak-fy2026-ap-leadsheet";
import type { FixtureParams } from "../../fixture-mode";
import { C } from "./copy";

export const TPL24_STATES = ["a", "b", "c", "d", "e", "f", "g"] as const;
type State = (typeof TPL24_STATES)[number];

const COLUMNS = [64, 260, 110, 120, 64, 90, 110, 64, 134] as const;
const [TRADE, FREIGHT] = AP_LEADSHEET.rows;
const n = (v: number): string => count(v);
const prior = AP_LEADSHEET.rows.reduce((s, r) => s + r.prior, 0);
const current = AP_LEADSHEET.rows.reduce((s, r) => s + r.current, 0);
const marks = (glyphs: string): HostCell => ({ text: glyphs, muted: true });

/** The leadsheet's cells: every figure the seed's (the change and % are code's, ADR-050). */
function cells(): Record<string, HostCell> {
  const out: Record<string, HostCell> = {
    A1: { text: C.grid.company, bold: true },
    A2: { text: C.grid.title },
    A3: { text: C.grid.workItem, muted: true },
    A5: { text: C.grid.objective, bold: true },
    B5: { text: C.grid.objectiveText },
    A6: { text: C.grid.procedures, bold: true },
    B6: { text: C.grid.proceduresText },
    A7: { text: C.grid.materiality, bold: true },
    B7: { text: C.grid.materialityText },
    A9: { text: C.grid.leadsheet, bold: true },
    A16: { text: C.grid.tieOut, bold: true },
    B17: { text: C.grid.perTb },
    D17: { text: n(current), numeric: true },
    B18: { text: C.grid.perLeadsheet },
    D18: { text: n(current), numeric: true },
    B19: { text: C.grid.difference },
    D19: { text: "—", numeric: true, muted: true },
    A21: { text: C.grid.surl, bold: true },
    B22: { text: C.grid.payments },
    D22: { text: n(38_640_200), numeric: true },
    B23: { text: C.grid.tested },
    D23: { text: n(3_698_700), numeric: true },
    B24: { text: C.grid.excluded },
    D24: { text: n(68_400), numeric: true },
    F24: { text: "—", muted: true },
    B25: { text: C.grid.belowPm },
    A27: { text: C.grid.legend, muted: true },
  };
  C.grid.headers.forEach((h, i) => {
    out[`${"ABCDEFGHI".charAt(i)}11`] = { text: h, header: true };
  });
  const line = (row: number, r: (typeof AP_LEADSHEET.rows)[number], glyphs: string) => {
    const change = r.current - r.prior;
    Object.assign(out, {
      [`A${String(row)}`]: { text: r.account },
      [`B${String(row)}`]: { text: r.label },
      [`C${String(row)}`]: { text: n(r.prior), numeric: true },
      [`D${String(row)}`]: { text: n(r.current), numeric: true },
      [`E${String(row)}`]: marks(glyphs),
      [`F${String(row)}`]: { text: r.ref },
      [`G${String(row)}`]: { text: n(change), numeric: true },
      [`H${String(row)}`]: { text: pct(change / r.prior, { decimals: 1 }), numeric: true },
      [`I${String(row)}`]: { text: row === 12 ? C.grid.sourceAging : C.grid.sourceFreight },
    });
  };
  if (TRADE !== undefined) line(12, TRADE, "✓ ◊");
  if (FREIGHT !== undefined) line(13, FREIGHT, "✓ ◊");
  const total = current - prior;
  Object.assign(out, {
    A14: { text: "—", muted: true },
    B14: { text: C.grid.total, bold: true },
    C14: { text: n(prior), numeric: true, bold: true, rule: true },
    D14: { text: n(current), numeric: true, bold: true, rule: true },
    E14: { ...marks("⊕ ◊"), rule: true },
    F14: { text: "BS", rule: true },
    G14: { text: n(total), numeric: true, bold: true, rule: true },
    H14: { text: pct(total / prior, { decimals: 1 }), numeric: true, rule: true },
    I14: { text: "—", muted: true },
  });
  return out;
}

function PaneBody({ state }: { state: State }): JSX.Element {
  const linkD13 = state !== "a" && state !== "b";
  switch (state) {
    case "b":
    case "e":
      return (
        <>
          {state === "e" ? (
            <p className="text-[11px] text-ink-3" data-queued="">
              {C.offline.queued(2)}
            </p>
          ) : null}
          <AddinCard title={C.tickmarks.title} meta={C.tickmarks.meta}>
            <ul data-tickmarks="">
              {AP_LEADSHEET.tickmarks.map((t, i) => (
                <li key={t.mark} className="flex h-[32px] items-center gap-[8px]">
                  <span className="flex size-[22px] items-center justify-center rounded-full bg-nested text-[11px] text-ink-2">
                    {t.mark}
                  </span>
                  <span className="flex-1 text-[12.5px]">{C.tickmarks.labels[i]}</span>
                  <span className="text-[11.5px] tabular-nums text-ink-3" data-usage={t.mark}>
                    {t.count}
                  </span>
                </li>
              ))}
            </ul>
            <Button variant="primary">{C.tickmarks.apply}</Button>
            <Toggle checked onChange={() => undefined} label={C.tickmarks.legend} size="small" />
          </AddinCard>
        </>
      );
    case "c":
      return (
        <AddinCard title={C.signOff.title}>
          <div className="flex h-[40px] items-center gap-[8px]" data-slot="preparer">
            <span className="w-[64px] text-[12px] text-ink-2">{C.signOff.preparer}</span>
            <span className="flex size-[24px] items-center justify-center rounded-full bg-green text-[10px] text-on-dark">
              CH
            </span>
            <span className="text-[12px]">{C.signOff.signedBy}</span>
          </div>
          <div className="flex h-[40px] items-center gap-[8px]" data-slot="reviewer">
            <span className="w-[64px] text-[12px] text-ink-2">{C.signOff.reviewer}</span>
            <span className="flex size-[24px] items-center justify-center rounded-full text-[10px] text-ink-3 ring-1 ring-ink-4">
              R
            </span>
            <span className="text-[12px] text-ink-2">{C.signOff.awaiting}</span>
          </div>
          <p className="text-[11.5px] text-ink-3">{C.signOff.board}</p>
          <p className="text-[11.5px] text-ink-3">{C.signOff.note}</p>
        </AddinCard>
      );
    case "d":
      return (
        <AddinCard title={C.changes.title(3)} meta={C.changes.signedBy}>
          <p className="flex items-center gap-[6px] text-[12.5px] font-medium text-amber-ink">
            <Icon name="triangle-alert" size={13} />
            {C.changes.title(3)}
          </p>
          <ul data-changes="">
            {(["F12", "F13", "F14"] as const).map((cell) => (
              <li key={cell} className="flex h-[30px] items-center gap-[8px]">
                <span className="font-mono text-[12px]">{cell}</span>
                <span className="flex-1 text-[11px] text-ink-3">{C.changes.edited}</span>
                <Button variant="ghost" size="sm">
                  {C.changes.show}
                </Button>
              </li>
            ))}
          </ul>
          <div className="flex gap-[8px]">
            <Button variant="secondary">{C.changes.review}</Button>
            <Button variant="primary">{C.changes.again}</Button>
          </div>
        </AddinCard>
      );
    case "f":
      return (
        <AddinCard title={C.word.incoming(AP_LEADSHEET.wordIncoming.length)}>
          <ul data-incoming="">
            {AP_LEADSHEET.wordIncoming.map((w) => (
              <li
                key={w.label}
                className="flex flex-wrap items-center gap-[6px] py-[4px] text-[12px]"
              >
                <span className="w-full">{w.label}</span>
                <s className="text-ink-3">{w.old}</s>
                <Icon name="arrow-right" size={12} className="text-ink-4" />
                <span className="font-medium">{w.new}</span>
              </li>
            ))}
          </ul>
          <Button variant="primary">{C.word.update}</Button>
          <Button variant="ghost" size="sm">
            {C.word.history}
          </Button>
        </AddinCard>
      );
    case "g":
      return (
        <div className="flex flex-1 items-center justify-center">
          <AddinCard title={C.signedOut.title}>
            <p className="text-[12.5px] text-ink-2">{C.signedOut.body}</p>
            <Button variant="primary">{C.signedOut.sso(C.firm)}</Button>
          </AddinCard>
        </div>
      );
    default: {
      const link = AP_LEADSHEET.links[0];
      return (
        <>
          <AddinCard title={C.link.cell("D14")} meta={n(current)}>
            <p className="flex items-center gap-[6px] text-[12px] text-ink-2">
              <Icon name="link-2" size={12} />
              {C.link.evidence(link?.evidence ?? "", link?.page ?? 1)}
            </p>
            <p className="text-[11px] text-ink-3">{C.link.linkedBy}</p>
            <div className="flex gap-[6px]">
              <Button variant="ghost" size="sm">
                {C.link.viewer}
              </Button>
              <Button variant="ghost" size="sm">
                {C.link.unlink}
              </Button>
            </div>
          </AddinCard>
          <AddinCard title={C.link.selectTitle}>
            <SearchField label={C.link.search} value="" onChange={() => undefined} />
            <ul>
              {C.link.files.map((f) => (
                <li key={f.name} className="flex h-[36px] items-center gap-[8px]">
                  <Icon name="file-text" size={14} className="text-ink-3" />
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate text-[12.5px]">{f.name}</span>
                    <span className="text-[11px] text-ink-3">{f.meta}</span>
                  </span>
                </li>
              ))}
            </ul>
            <Button variant="primary" disabled>
              {C.link.selectTitle}
            </Button>
            <p className="text-[11px] text-ink-3">{C.link.helper}</p>
          </AddinCard>
          <AddinCard title={C.link.workbook(linkD13 ? 2 : 1)}>
            <p className="text-[12px] text-ink-2">
              <span className="font-mono text-[12px] text-ink">D14</span>
              {` · ${link?.evidence ?? ""} · p.${String(link?.page ?? 1)}`}
            </p>
          </AddinCard>
        </>
      );
    }
  }
}

const TAB: Record<State, AddinTab | undefined> = {
  a: "Link",
  b: "Tickmarks",
  c: "Sign-off",
  d: "Changes",
  e: "Tickmarks",
  f: "Changes",
  g: undefined,
};

function pane(state: State): JSX.Element {
  const word = state === "f";
  return (
    <AddinChrome
      context={word ? C.contextWord : C.contextExcel}
      {...(state === "g" ? {} : { initials: word ? "HL" : "CH" })}
      tab={TAB[state]}
      changes={state === "d" ? 3 : state === "f" ? AP_LEADSHEET.wordIncoming.length : 0}
      offline={state === "e"}
      syncedAt={
        word ? "4:15 PM" : state === "c" ? "2:21 PM" : state === "d" ? "2:40 PM" : "2:14 PM"
      }
    >
      <PaneBody state={state} />
    </AddinChrome>
  );
}

export function Tpl24Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: State = TPL24_STATES.find((s) => s === params.st) ?? "a";
  if (state === "f") {
    return (
      <div data-artboard={state}>
        <HostWindow host="word" file={C.word.file} tabs={C.word.tabs} pane={pane(state)}>
          <WordPage title={C.word.page}>
            <h2 className="text-center text-[13px] font-medium">{C.word.page}</h2>
            {C.word.lines.map((l) => (
              <p
                key={l.label}
                data-line={l.label}
                className={
                  l.changed
                    ? "flex justify-between bg-amber-tint text-[11px]"
                    : "flex justify-between text-[11px]"
                }
              >
                <span>{l.label}</span>
                <span className="tabular-nums">{l.value}</span>
              </p>
            ))}
          </WordPage>
        </HostWindow>
      </div>
    );
  }
  return (
    <div data-artboard={state}>
      <HostWindow
        host="excel"
        file={AP_LEADSHEET.workbook}
        tabs={C.excel.tabs}
        formula={{ cell: "D14", text: "=SUM(D12:D13)" }}
        sheets={C.excel.sheets}
        pane={pane(state)}
      >
        <ExcelGrid
          columns={COLUMNS}
          rows={27}
          cells={cells()}
          selected="D14"
          linked={state === "a" || state === "b" ? ["D14"] : ["D13", "D14"]}
          commented={["D24"]}
          changed={state === "d" ? ["F12", "F13", "F14"] : []}
        />
      </HostWindow>
    </div>
  );
}
