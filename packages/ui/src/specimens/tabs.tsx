import { type JSX, useState } from "react";
import {
  Segmented,
  SegmentedGroup,
  SheetTabs,
  type TabForceState,
  UnderlineTabs,
  ViewToggle,
  type Opt,
} from "../components/tabs";
import { Held, Row, Sheet } from "./frame";

// The C-05 Tabs kit's specimens (F-05-T15): the handoff's gallery sets and states. Segmented in
// both sizes, with each held state; SegmentedGroup with its sub-track; UnderlineTabs; SheetTabs;
// ViewToggle closed, hovered and open. The sets are the kit's own (`tabs-types.ts` SETS), so the
// words and counts are the handoff's. Every tablist is live: click, or use the arrows, Home and End.

const RETURN: Opt[] = [
  "Overview",
  { label: "Intake", count: 7 },
  { label: "Review", count: 38 },
  { label: "Issues", count: 16, bad: true },
  "Activity",
];
const CLOSE: Opt[] = [
  "Overview",
  "Intake",
  "Accounts",
  { label: "Review", count: 9, bad: true },
  "Deliverables",
];
const WORKBENCH: Opt[] = ["Sessions", "Agents", "Connect"];
const SMALL: readonly (readonly [string, string])[] = [
  ["By partner", "By movement"],
  ["Detail", "Workpaper"],
  ["Internal Control", "Exceptions"],
  ["Library", "My Agents"],
];
const SETTINGS: Opt[] = ["Firm", "Members", "Roles", "Billing", "Integrations"];
const SHEETS: Opt[] = [
  { label: "Worksheets", icon: "panels-top-left" },
  { label: "Leadsheets", icon: "layers" },
  { label: "2-Year Comparison", icon: "chart-column" },
];
const PARTNERSHIP: Opt[] = [
  "Agent",
  { label: "Issues", count: 16, bad: true },
  "Workpaper",
  "Review",
];
const PARTNERSHIP_SUB = {
  Workpaper: {
    options: [
      "Summary",
      "Financials",
      "Fixed Assets",
      "M-1/M-3",
      "Schedule M-2",
      "Schedule K",
      "Capital Accounts",
    ],
  },
};

const HELD: readonly TabForceState[] = ["hover", "focus", "pressed"];

function LastChange({ value }: { value: string }): JSX.Element {
  return (
    <span className="text-meta text-ink-3" data-testid="last-change">
      {value === "" ? "Last change: none yet" : `Last change: ${value}`}
    </span>
  );
}

export function SegmentedSpecimen(): JSX.Element {
  const [last, setLast] = useState("");
  return (
    <div className="flex flex-col gap-3">
      <Sheet
        title="Segmented: primary sets"
        meta="Track nav-fill, padding 4, gap 2 · options 30, 14 · centre it in the tabsbar"
      >
        <Row name="Return" meaning="Count badges, one bad">
          <Segmented label="Return" options={RETURN} active="Overview" onChange={setLast} />
        </Row>
        <Row name="Close" meaning="A bad count on Review">
          <Segmented label="Close" options={CLOSE} active="Overview" onChange={setLast} />
        </Row>
        <Row name="Workbench" meaning="60 high tabsbar">
          <Segmented label="Workbench" options={WORKBENCH} active="Sessions" onChange={setLast} />
        </Row>
        <Row name="Live" meaning="Click, or use the arrows, Home and End">
          <LastChange value={last} />
        </Row>
      </Sheet>
      <Sheet title="Segmented: small, in a pane header" meta="Track padding 3 · options 28, 13.5">
        {SMALL.map((pair) => (
          <Row key={pair.join("|")} name={pair.join(" · ")}>
            <Segmented label={pair.join(" or ")} size="small" options={pair} active={pair[0]} />
          </Row>
        ))}
      </Sheet>
      <Sheet
        title="Segmented: held states"
        meta="Selected, hover, focus, pressed, disabled; count and bad count"
      >
        {(["default", "small"] as const).map((size) => (
          <Row key={size} name={size}>
            <Held name="selected">
              <Segmented
                label={`${size} selected`}
                size={size}
                options={["Overview", "Intake", "Accounts"]}
                active="Overview"
              />
            </Held>
            {HELD.map((state) => (
              <Held key={state} name={state}>
                <Segmented
                  label={`${size} ${state}`}
                  size={size}
                  options={["Overview", "Intake", "Accounts"]}
                  active="Overview"
                  forceState={state}
                />
              </Held>
            ))}
            <Held name="disabled">
              <Segmented
                label={`${size} disabled`}
                size={size}
                options={["Overview", "Intake", { label: "Deliverables", disabled: true }]}
                active="Overview"
              />
            </Held>
            <Held name="count and bad count">
              <Segmented
                label={`${size} counts`}
                size={size}
                options={[
                  "Overview",
                  { label: "Review", count: 9 },
                  { label: "Issues", count: 16, bad: true },
                ]}
                active="Overview"
              />
            </Held>
          </Row>
        ))}
      </Sheet>
    </div>
  );
}

export function SegmentedGroupSpecimen(): JSX.Element {
  const [last, setLast] = useState("");
  return (
    <Sheet
      title="SegmentedGroup"
      meta="Two tracks 8 apart · the second follows the selected first item"
    >
      <Row name="Partnership" meaning="Workpaper has seven sections">
        <SegmentedGroup
          label="Partnership return"
          options={PARTNERSHIP}
          active="Workpaper"
          sub={PARTNERSHIP_SUB}
          onChange={(item, section) => {
            setLast(section === undefined ? item : `${item} › ${section}`);
          }}
        />
      </Row>
      <Row name="Small" meaning="In a pane header">
        <SegmentedGroup
          label="Partnership return, small"
          size="small"
          options={PARTNERSHIP}
          active="Workpaper"
          sub={PARTNERSHIP_SUB}
        />
      </Row>
      <Row name="Without a sub-track" meaning="Agent has none, so one track shows">
        <SegmentedGroup
          label="Partnership return, no sub-track"
          options={PARTNERSHIP}
          active="Agent"
          sub={PARTNERSHIP_SUB}
        />
      </Row>
      <Row name="Live" meaning="onChange(item, section)">
        <LastChange value={last} />
      </Row>
    </Sheet>
  );
}

export function UnderlineTabsSpecimen(): JSX.Element {
  return (
    <Sheet
      title="UnderlineTabs"
      meta="Settings only · 37 high · 2px espresso underline · never primary navigation"
    >
      <Row name="Settings">
        <div className="w-[480px] max-w-full">
          <UnderlineTabs label="Settings" options={SETTINGS} active="Firm" />
        </div>
      </Row>
      {HELD.map((state) => (
        <Row key={state} name={state}>
          <div className="w-[480px] max-w-full">
            <UnderlineTabs
              label={`Settings ${state}`}
              options={SETTINGS}
              active="Firm"
              forceState={state}
            />
          </div>
        </Row>
      ))}
      <Row name="disabled">
        <div className="w-[480px] max-w-full">
          <UnderlineTabs
            label="Settings disabled"
            options={["Firm", "Members", { label: "Billing", disabled: true }]}
            active="Firm"
          />
        </div>
      </Row>
    </Sheet>
  );
}

export function SheetTabsSpecimen(): JSX.Element {
  return (
    <Sheet title="SheetTabs" meta="Pane header · 30 high · nested with e1 when selected">
      <Row name="Sheets" meaning="Worksheets, Leadsheets, 2-Year Comparison">
        <SheetTabs label="Sheets" options={SHEETS} active="Worksheets" />
      </Row>
      {HELD.map((state) => (
        <Row key={state} name={state}>
          <SheetTabs
            label={`Sheets ${state}`}
            options={SHEETS}
            active="Worksheets"
            forceState={state}
          />
        </Row>
      ))}
      <Row name="disabled">
        <SheetTabs
          label="Sheets disabled"
          options={[
            SHEETS[0] ?? "Worksheets",
            { label: "Leadsheets", icon: "layers", disabled: true },
          ]}
          active="Worksheets"
        />
      </Row>
    </Sheet>
  );
}

export function ViewToggleSpecimen(): JSX.Element {
  const [view, setView] = useState("grid");
  return (
    <Sheet title="ViewToggle" meta="29 high · layout-grid and a chevron · 176px radio menu">
      <Row name="Closed" meaning="Click, or ↓ to open and focus the first item">
        <ViewToggle view={view} onView={setView} />
        <span className="text-meta text-ink-3">{`View: ${view}`}</span>
      </Row>
      <Row name="Hover">
        <ViewToggle view="grid" forceState="hover" />
      </Row>
      <Row name="Open" meaning="Held in place">
        <div className="flex min-h-[110px] items-start pl-[180px]">
          <ViewToggle view="grid" forceState="open" />
        </div>
      </Row>
      <Row name="List" meaning="The icon stays layout-grid; the name says the view">
        <ViewToggle view="list" />
      </Row>
    </Sheet>
  );
}
