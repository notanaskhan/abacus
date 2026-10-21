import { type JSX, useEffect, useState } from "react";
import { Button } from "../components/button";
import { DoneCount } from "../components/pill";
import {
  KpiGrid,
  KpiTile,
  ProgressBar,
  RatioStat,
  StatusTile,
  StatusTileStrip,
  StepCounter,
  UploadRing,
} from "../components/progress";
import { practiceOpen } from "../components/progress-model";
import { count, prose } from "../format";
import { Held, Row, Sheet } from "./frame";

// The C-19 Progress kit's specimens (F-05-T19): every bar, pill, ring, step and tile of the
// bundle's boards, including the forced states. The counts are the handoff's own sample, kept in
// this file; the strips' totals are computed with `practiceOpen`, so the 79 open is the sum of the
// tiles and the two returns that have no tile, never a typed number. The live demos run when a
// person presses Replay: nothing ticks at rest (C-19: animate only on change).

function useTicker(total: number, stepMs: number): { value: number; replay: () => void } {
  const [value, setValue] = useState(total);
  const [run, setRun] = useState(0);
  useEffect(() => {
    if (run === 0) return;
    setValue(0);
    const timer = setInterval(() => {
      setValue((v) => {
        if (v >= total) {
          clearInterval(timer);
          return v;
        }
        return v + 1;
      });
    }, stepMs);
    return () => {
      clearInterval(timer);
    };
  }, [run, total, stepMs]);
  return {
    value,
    replay: () => {
      setRun((n) => n + 1);
    },
  };
}

export function ProgressBarSpecimen(): JSX.Element {
  const uploads = useTicker(18, 400);
  return (
    <Sheet title="ProgressBar" meta="3h · track chip · 400ms on change · indeterminate 1.4s">
      <Row name="Espresso" meaning="The default; never green">
        <div className="flex w-[520px] flex-col gap-[10px]">
          <ProgressBar done={0} total={12} />
          <ProgressBar done={6} total={12} />
          <ProgressBar done={12} total={12} />
          <ProgressBar done={9} total={13} right="Started 20 minutes ago" />
        </div>
      </Row>
      <Row name="Amber" meaning="Uploads and anything in progress">
        <div className="flex w-[520px] flex-col gap-[10px]">
          <ProgressBar done={0} total={18} tone="amber" noun="files uploaded" />
          <ProgressBar done={9} total={18} tone="amber" noun="files uploaded" />
          <ProgressBar done={18} total={18} tone="amber" noun="files uploaded" />
        </div>
      </Row>
      <Row name="Live" meaning="Press Replay; it moves only when the count changes">
        <div className="flex w-[520px] items-center gap-[12px]">
          <ProgressBar
            className="flex-1"
            done={uploads.value}
            total={18}
            tone="amber"
            noun="files uploaded"
            right="Started just now"
          />
          <Button variant="secondary" size="sm" onClick={uploads.replay}>
            Replay
          </Button>
        </div>
      </Row>
      <Row name="Indeterminate" meaning="Only while the total is unknown">
        <div className="flex w-[520px] flex-col gap-[10px]">
          <ProgressBar done={0} total={null} tone="amber" />
          <ProgressBar done={0} total={null} tone="amber" left="Counting files in the binder…" />
          <Held name="Still (reduced motion)">
            <div className="w-[520px]">
              <ProgressBar done={0} total={null} tone="amber" still />
            </div>
          </Held>
        </div>
      </Row>
      <Row name="DoneCount" meaning="Complete, partial, none (C-06)">
        <DoneCount done={5} total={5} />
        <DoneCount done={4} total={5} />
        <DoneCount done={0} total={1} />
      </Row>
    </Sheet>
  );
}

export function RatioStatSpecimen(): JSX.Element {
  return (
    <Sheet title="RatioStat" meta="Cells 12 14 · value 15 · caption 12 ink-3 · whole percent">
      <Row name="Rail stat row" meaning="progress(): 17% (4 / 24)">
        <RatioStat
          className="w-[520px]"
          items={[
            { done: 4, total: 24, caption: "Accounts Reconciled" },
            { done: 13, total: 20, caption: "Documents Received" },
            { done: 9, total: 13, caption: "Steps Complete" },
          ]}
        />
      </Row>
    </Sheet>
  );
}

export function UploadRingSpecimen(): JSX.Element {
  const ring = useTicker(20, 160);
  return (
    <Sheet title="UploadRing" meta="50 box · arc r22 stroke 2 · 400ms · done swaps in 180ms">
      <Row name="States" meaning="Waiting, 25, 45, 75 percent, uploaded">
        <div className="flex flex-wrap gap-[28px]">
          <UploadRing fraction={0} caption="Waiting" />
          <UploadRing fraction={0.25} caption="25%" />
          <UploadRing fraction={0.45} caption="Uploading" />
          <UploadRing fraction={0.75} caption="75%" />
          <UploadRing fraction={1} caption="Uploaded" />
        </div>
      </Row>
      <Row name="Live" meaning="Press Replay">
        <div className="flex items-center gap-[20px]">
          <UploadRing
            fraction={ring.value / 20}
            caption={ring.value >= 20 ? "Uploaded" : "Uploading"}
          />
          <Button variant="secondary" size="sm" onClick={ring.replay}>
            Replay
          </Button>
        </div>
      </Row>
      <Row name="Still" meaning="Reduced motion: the arc jumps">
        <UploadRing fraction={0.45} caption="Uploading" still />
      </Row>
    </Sheet>
  );
}

export function StepCounterSpecimen(): JSX.Element {
  return (
    <Sheet title="StepCounter" meta="Rows 40 · disc 15 · counter 12 ink-3">
      <Row name="Run steps" meaning="One in progress; the rest wait">
        <StepCounter
          className="w-[520px]"
          steps={[
            { name: "Read the general ledger", done: 312, total: 312 },
            { name: "Match bank transactions", done: 156, total: 312 },
            { name: "Draft reconciling entries", done: 0, total: 18 },
            { name: "Wait for the reviewer", done: 0, total: 0 },
          ]}
        />
      </Row>
      <Row name="Early" meaning="10 of 312 · 3%">
        <StepCounter
          className="w-[520px]"
          steps={[
            { name: "Read the general ledger", done: 312, total: 312 },
            { name: "Match bank transactions", done: 10, total: 312 },
            { name: "Flag unmatched items for review", done: 0, total: 6 },
          ]}
        />
      </Row>
    </Sheet>
  );
}

export function KpiTileSpecimen(): JSX.Element {
  // The tiles rise 45ms apart on first mount. At rest they are drawn still, so the page is not
  // mid-animation when it is checked; Replay mounts them again and they rise.
  const [play, setPlay] = useState(0);
  const still = play === 0;
  return (
    <Sheet
      title="KPI tile"
      meta="Tile 12 14 · value 20/500 · spark 76 × 24 · rise 260ms, 45ms apart"
    >
      <Row name="Home tiles" meaning="Good is green ink, bad is red ink, flat is ink-3">
        <div className="flex flex-col items-start gap-[10px]">
          <KpiGrid key={play} className="w-[880px]">
            <KpiTile
              still={still}
              index={0}
              label="Returns filed this week"
              value={count(38)}
              delta={{ text: "12 more than last week", tone: "good" }}
              spark={[4, 6, 5, 9, 8, 12, 14]}
            />
            <KpiTile
              still={still}
              index={1}
              label="Unbilled WIP"
              value={`$${prose(412860, "whole")}`}
              delta={{ text: "6.1% since August 31", tone: "good-down" }}
              spark={[18, 17, 17, 15, 14, 13, 12]}
            />
            <KpiTile
              still={still}
              index={2}
              label="Open issues"
              value={count(47)}
              delta={{ text: "9 more since Monday", tone: "bad" }}
              spark={[30, 32, 35, 34, 39, 43, 47]}
            />
            <KpiTile
              still={still}
              index={3}
              label="Average days to file"
              value="11.4"
              delta={{ text: "Same as last season", tone: "flat" }}
            />
          </KpiGrid>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setPlay((n) => n + 1);
            }}
          >
            Replay
          </Button>
        </div>
      </Row>
      <Row name="bad-down" meaning="A fall that is bad">
        <KpiGrid className="w-[220px]">
          <KpiTile
            still
            label="Documents received"
            value={count(13)}
            delta={{ text: "4 fewer than Monday", tone: "bad-down" }}
            spark={[20, 19, 18, 16, 15, 14, 13]}
          />
        </KpiGrid>
      </Row>
    </Sheet>
  );
}

const PRACTICE_TILES = [
  { count: 17, label: "Prepared", variant: "neutral" },
  { count: 15, label: "In review", variant: "state" },
  { count: 11, label: "Issues", variant: "red-tint" },
  { count: 7, label: "Ready", variant: "green-tint" },
  { count: 8, label: "Gathering", variant: "state" },
  { count: 9, label: "Preparing", variant: "state" },
  { count: 10, label: "Awaiting signature", variant: "amber", mark: "dot" },
  { count: 145, label: "Filed · Accepted", variant: "green", mark: "check" },
] as const;

export function StatusTileSpecimen(): JSX.Element {
  // The tiles' open counts plus the two returns that have no tile: 79. Filed is the 145 done.
  const open = practiceOpen(
    PRACTICE_TILES.filter((t) => t.label !== "Filed · Accepted").map((t) => t.count),
    2,
  );
  const done = 145;
  const side = `${count(open)} open · ${count(done)} done · ${count(open + done)} TY2025 returns · 161 extended`;
  return (
    <Sheet title="StatusTile" meta="Practice 120 × 72 · Home 120 × 99 · count 22 · pill 21">
      <Row
        name="Practice strip"
        meaning="TAX-01: the 2 Not started returns are in the 79, with no tile"
      >
        <div className="w-[1200px]">
          <StatusTileStrip label="Tax returns by status" side={side}>
            {PRACTICE_TILES.map((t) => (
              <StatusTile
                key={t.label}
                count={t.count}
                label={t.label}
                variant={t.variant}
                {...("mark" in t ? { mark: t.mark } : {})}
              />
            ))}
          </StatusTileStrip>
        </div>
      </Row>
      <Row name="Home tiles" meaning="HOME-01: the first four, taller">
        <StatusTileStrip
          label="Tax returns by status"
          caption={`Tax returns · TY2025 · ${count(open)} open`}
        >
          {PRACTICE_TILES.slice(0, 4).map((t) => (
            <StatusTile
              key={t.label}
              size="home"
              count={t.count}
              label={t.label}
              variant={t.variant}
            />
          ))}
        </StatusTileStrip>
      </Row>
      <Row name="Pressed" meaning="A tile that filters">
        <StatusTile
          count={11}
          label="Issues"
          variant="red-tint"
          selected
          onSelect={() => undefined}
        />
        <StatusTile count={15} label="In review" variant="state" onSelect={() => undefined} />
      </Row>
    </Sheet>
  );
}
