import { type JSX, useState } from "react";
import { Button } from "../components/button";
import { Pane } from "../layout/pane";
import { NestedSplit, SplitLayout } from "../layout/split-layout";
import { SPLIT_PRESETS, type SplitPresetName } from "../layout/split-presets";
import { Sheet } from "./frame";

// C-09 Split Layout (F-05-T29): presets as data (plan 04 §3.11 widths), resizable gutters, the two
// nested kinds, and the ≤1280 drawer. Pane titles are the kit's.

function Body({ text }: { text: string }): JSX.Element {
  return <div className="p-3 text-meta text-ink-3">{text}</div>;
}

function Preset({ name, titles }: { name: SplitPresetName; titles: string[] }): JSX.Element {
  const widths = SPLIT_PRESETS[name].panes.map((p) => String(p.width)).join(" | ");
  return (
    <Sheet title={name} meta={widths}>
      <SplitLayout preset={name} height={220}>
        {titles.map((t) => (
          <Pane key={t} title={t}>
            <Body text="Drag a gutter, or focus it and use ← →; Enter resets." />
          </Pane>
        ))}
      </SplitLayout>
    </Sheet>
  );
}

export function SplitPresetsSpecimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      <Preset
        name="audit"
        titles={["Overview", "Service Organizations", "Harborline SOC 1 Type 2.pdf"]}
      />
      <Preset
        name="taxReview"
        titles={["Review", "2025 Composite 1099 — Brokerage.pdf", "Worksheet"]}
      />
      <Preset name="workbench" titles={["Sessions", "Plan Review · Investments"]} />
      <Preset name="library" titles={["Library", "Bank reconciliation"]} />
    </div>
  );
}

export function NestedSplitSpecimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      <Sheet title="close-review · hair" meta="790 = 310 + 480 | 576">
        <SplitLayout preset="close-review" height={220}>
          <Pane title="Review">
            <NestedSplit kind="hair" columns={[310, "flex"]}>
              <Body text="Review queue" />
              <Body text="Amex Business Card ••2008" />
            </NestedSplit>
          </Pane>
          <Pane title="Register">
            <Body text="Register" />
          </Pane>
        </SplitLayout>
      </Sheet>
      <Sheet title="issues-individual · well" meta="546 (262 + flex) | 433 | 377">
        <SplitLayout preset="issues-individual" height={220} narrow={false}>
          <Pane title="Issues" well>
            <NestedSplit kind="well" columns={[262, "flex"]}>
              <Body text="Queue" />
              <Body text="Issue 6" />
            </NestedSplit>
          </Pane>
          <Pane title="2025 Composite 1099 — Brokerage.pdf">
            <Body text="Viewer" />
          </Pane>
          <Pane title="Sheets">
            <Body text="Sheets" />
          </Pane>
        </SplitLayout>
      </Sheet>
    </div>
  );
}

export function SplitNarrowSpecimen(): JSX.Element {
  const [open, setOpen] = useState(false);
  return (
    <Sheet title="taxReview at ≤ 1280" meta="the third column becomes a drawer">
      <div className="flex justify-end bg-shell px-3 pt-2">
        <Button
          variant="secondary"
          size="sm"
          aria-pressed={open}
          onClick={() => {
            setOpen(!open);
          }}
        >
          Worksheet
        </Button>
      </div>
      <SplitLayout
        preset="taxReview"
        height={220}
        narrow
        drawerOpen={open}
        onDrawerOpenChange={setOpen}
        drawerTitle="Worksheet"
      >
        <Pane title="Review">
          <Body text="Tree" />
        </Pane>
        <Pane title="2025 Composite 1099 — Brokerage.pdf">
          <Body text="Viewer" />
        </Pane>
        <Body text="The worksheet, in the drawer" />
      </SplitLayout>
    </Sheet>
  );
}
