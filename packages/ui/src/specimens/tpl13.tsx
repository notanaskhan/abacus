// TPL-13 "Calendar specimen · firm deadlines, September 2026" (F-07-T12; handoff TPL-13; F-07 §F):
// seven artboards on the T13 CalendarLayout for Grace Holloway, Mon Sep 14, 2026 9:24 AM CT.
//   a  Month, the Ridgeline rule popover open      a2 Month, Sep 15 expanded (13 items)
//   b  Week Sep 13–19 (Sep 15 lists 13)            c  List Sep 10 → Oct 3 with the Rule column
//   d  Filtered · Denver (7 items)                 e  Postponed: Calloway Trust 1041 → Nov 2
//   f  Empty filter ("No deadlines match these filters." + Clear filters)
// Data in, intents out: risk tiers, rules and counts are the data's (tpl13-data.ts), never computed.
import { type JSX, useState } from "react";
import {
  CalendarLayout,
  type CalendarView,
  type DeadlineChip,
  ListView,
  RulePopover,
  WeekView,
  useRulePopover,
} from "../templates/calendar";
import { Artboard } from "./portal";
import {
  SEP15_EXPANDED,
  TPL13_CHIPS,
  TPL13_COPY,
  TPL13_DENVER,
  TPL13_DENVER_FILTERS,
  TPL13_EMPTY_FILTERS,
  TPL13_FILTERS,
  TPL13_HOLIDAYS,
  TPL13_LIST,
  TPL13_LIST_COPY,
  TPL13_MONTH,
  TPL13_POSTPONED,
  TPL13_TODAY,
} from "./tpl13-data";

export type Tpl13State = "a" | "a2" | "b" | "c" | "d" | "e" | "f";

interface Board {
  id: Tpl13State;
  name: string;
  note: string;
  view: CalendarView;
  chips: readonly DeadlineChip[];
  filtered?: "denver" | "empty";
  expanded?: boolean;
  pinned?: string;
}

export const TPL13_BOARDS: readonly Board[] = [
  {
    id: "a",
    name: "Month",
    note: "Ridgeline · Form 1065 hovered: the rule that produced Sep 15",
    view: "month",
    chips: TPL13_CHIPS,
    pinned: "ridgeline-1065",
  },
  {
    id: "a2",
    name: "Month · Sep 15 expanded",
    note: "+10 more opens all 13 items",
    view: "month",
    chips: TPL13_CHIPS,
    expanded: true,
  },
  {
    id: "b",
    name: "Week",
    note: "Sep 13–19; Sep 15 lists all 13",
    view: "week",
    chips: TPL13_CHIPS,
  },
  {
    id: "c",
    name: "List",
    note: "Sep 10 (overdue) to Oct 3, with the Rule column",
    view: "list",
    chips: TPL13_LIST,
  },
  {
    id: "d",
    name: "Filtered · Denver",
    note: "Seven items remain; +n more recomputes",
    view: "month",
    chips: TPL13_DENVER,
    filtered: "denver",
  },
  {
    id: "e",
    name: "Postponed item",
    note: "Calloway Trust 1041 postponed to Nov 2 (declared disaster area)",
    view: "month",
    chips: TPL13_POSTPONED,
  },
  {
    id: "f",
    name: "Empty filter",
    note: "No deadlines match these filters",
    view: "month",
    chips: [],
    filtered: "empty",
  },
];

function Tpl13({ board }: { board: Board }): JSX.Element {
  const [view, setView] = useState<CalendarView>(board.view);
  const [expanded, setExpanded] = useState(board.expanded === true);
  const popover = useRulePopover();
  const filters =
    board.filtered === "denver"
      ? TPL13_DENVER_FILTERS
      : board.filtered === "empty"
        ? TPL13_EMPTY_FILTERS
        : TPL13_FILTERS;
  const pinned =
    board.pinned === undefined ? undefined : board.chips.find((c) => c.id === board.pinned);
  const shown = popover.open?.chip ?? pinned;
  return (
    <Artboard
      id={`tpl-13${board.id}`}
      badge={`TPL-13${board.id === "a2" ? "a′" : board.id}`}
      name={board.name}
      note={board.note}
    >
      <div className="relative h-[800px] w-[1400px] bg-shell" data-tpl13={board.id}>
        <CalendarLayout
          view={view}
          month={TPL13_MONTH}
          today={TPL13_TODAY}
          chips={board.chips}
          holidays={TPL13_HOLIDAYS}
          filters={filters}
          copy={TPL13_COPY}
          {...(expanded ? { expanded: SEP15_EXPANDED } : {})}
          week={
            <WeekView
              start="2026-09-13"
              today={TPL13_TODAY}
              chips={board.chips}
              copy={TPL13_COPY}
              onHoverChip={popover.hover}
              onFocusChip={popover.focus}
              onLeaveChip={popover.leave}
            />
          }
          list={
            <ListView
              chips={board.chips}
              copy={TPL13_COPY}
              listCopy={TPL13_LIST_COPY}
              filtered={board.filtered !== undefined}
            />
          }
          onView={setView}
          onExpandDay={() => {
            setExpanded(true);
          }}
          onCloseDay={() => {
            setExpanded(false);
          }}
          onHoverChip={popover.hover}
          onFocusChip={popover.focus}
          onLeaveChip={popover.leave}
        />
        {shown === undefined ? null : (
          <div className="absolute top-[300px] left-[620px] z-20">
            <RulePopover chip={shown} copy={TPL13_COPY} listCopy={TPL13_LIST_COPY} />
          </div>
        )}
      </div>
    </Artboard>
  );
}

export function Tpl13Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {TPL13_BOARDS.map((b) => (
        <Tpl13 key={b.id} board={b} />
      ))}
    </div>
  );
}
