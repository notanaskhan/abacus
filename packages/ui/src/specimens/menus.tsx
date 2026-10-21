import type { JSX } from "react";
import { Button } from "../components/button";
import { Menu, type MenuItem, Tooltip } from "../components/popover";
import { Held, Row, Sheet } from "./frame";

// Menu and Tooltip specimens (C-00 menu primitive, the Go… tooltip; F-05-T15). The open ones are
// held in place (`forceState="open"`) and sit in reserved space; the closed ones are live: ↓ on a
// trigger opens its menu and focuses the first item, Escape closes it and returns focus, and a
// tooltip opens on keyboard focus at once and after 450ms of hover.

const ACTIONS: MenuItem[][] = [
  [
    { label: "Open", onSelect: () => undefined },
    { label: "Copy link", onSelect: () => undefined, hint: "To this request" },
    { label: "Archive", onSelect: () => undefined, disabled: true },
  ],
  [{ label: "Void…", onSelect: () => undefined, danger: true, opensDialog: true }],
];

const VIEWS: MenuItem[][] = [
  [
    { label: "Grid", icon: "layout-grid", checked: true, onSelect: () => undefined },
    { label: "List", icon: "list", checked: false, onSelect: () => undefined },
  ],
];

export function MenuSpecimen(): JSX.Element {
  return (
    <Sheet
      title="Menu"
      meta="Nested tray radius 15, white sections radius 11 · rows 34 high, radius 8"
    >
      <Row name="Closed" meaning="Click, or ↓ then ↑ ↓ Home End; Escape closes">
        <Menu
          label="Row actions"
          trigger={<Button variant="secondary">Row actions</Button>}
          sections={ACTIONS}
        />
        <Menu
          label="Views"
          width={176}
          trigger={<Button variant="secondary">Views</Button>}
          sections={VIEWS}
        />
      </Row>
      <Row
        name="Open"
        meaning="Held in place: hint, disabled, destructive, and a checked radio group"
      >
        <div className="flex min-h-[210px] flex-wrap items-start gap-[260px]">
          <Held name="actions">
            <Menu
              label="Row actions, open"
              forceState="open"
              align="start"
              trigger={<Button variant="secondary">Row actions</Button>}
              sections={ACTIONS}
            />
          </Held>
          <Held name="radio, 176px">
            <Menu
              label="Views, open"
              forceState="open"
              align="start"
              width={176}
              trigger={<Button variant="secondary">Views</Button>}
              sections={VIEWS}
            />
          </Held>
        </div>
      </Row>
    </Sheet>
  );
}

export function TooltipSpecimen(): JSX.Element {
  return (
    <Sheet
      title="Tooltip"
      meta="White, radius 10 · 12.5 ink with an 11.5 ink-3 line · 450ms hover, at once on focus"
    >
      <Row name="Live" meaning="Hover for 450ms, or Tab to the control">
        <Tooltip content="Prepared by Sam Staff on Oct 20">
          <Button variant="ghost">Prepared</Button>
        </Tooltip>
        <Tooltip content="Go to anything" detail="Also: Open board">
          <Button variant="secondary">Two lines</Button>
        </Tooltip>
      </Row>
      <Row name="Open" meaning="Held in place, below its trigger">
        <div className="flex min-h-[90px] flex-wrap items-start gap-[240px] pl-[120px]">
          <Held name="one line">
            <Tooltip content="Prepared by Sam Staff on Oct 20" forceState="open">
              <Button variant="ghost">Prepared</Button>
            </Tooltip>
          </Held>
          <Held name="two lines">
            <Tooltip content="Go to anything" detail="Also: Open board" forceState="open">
              <Button variant="secondary">Two lines</Button>
            </Tooltip>
          </Held>
        </div>
      </Row>
    </Sheet>
  );
}
