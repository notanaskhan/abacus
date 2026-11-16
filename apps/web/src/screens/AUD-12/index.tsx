import { type JSX, useState } from "react";
import {
  CardWell,
  DeviationLog,
  ExpandTestingSheet,
  TestGrid,
  TestingFooter,
} from "../../domain/fieldwork";
import { JeBoard } from "../kit-a08";
import { NORTHWIND_GRID, NORTHWIND_HEADERS } from "../kit-a08-data";
import { AUD12_SCENARIOS, type Aud12Scenario, KIT_STATE_OF } from "./scenarios";

// AUD-12 Testing workspace (A-08-T27): the eight artboards on the A-08 kit in fixture mode. The
// JE artboards (a, d to g) are the kit's JE board with the Viewer dock beside it; b, c and h are
// the shared test grid. Value chips are the only clickable source links (the kit's
// `ValueChipLink`); Escape closes the expand sheet (the design system's sheet).

const HANNAH = { id: "hannah", name: "Hannah Leclerc" };

function GridBoard({ scenario }: { scenario: "b" | "c" | "h" }): JSX.Element {
  const [expand, setExpand] = useState(scenario === "h");
  const variant = scenario === "c" ? "controls" : "details";
  return (
    <div className="flex w-[536px] flex-col">
      <CardWell>
        <TestGrid
          variant={variant}
          title={
            variant === "details"
              ? "Contribution testing, Dec 12, 2025 payroll"
              : "Credit approval, revenue cycle"
          }
          grid={NORTHWIND_GRID}
          headers={NORTHWIND_HEADERS}
        />
        {variant === "controls" && <DeviationLog deviations={[]} udl="8.8%" tolerable="10%" />}
      </CardWell>
      <TestingFooter
        expandPrimary={variant === "details"}
        onExpand={() => {
          setExpand(true);
        }}
      />
      {scenario === "h" && (
        <ExpandTestingSheet
          open={expand}
          onOpenChange={setExpand}
          base={25}
          mode="participants"
          approvers={[HANNAH]}
          viewer={{ kind: "human", name: "Simone Baptiste" }}
          held
        />
      )}
    </div>
  );
}

export function TestingWorkspace({ st }: { st?: string | undefined }): JSX.Element {
  const scenario: Aud12Scenario = (AUD12_SCENARIOS as readonly string[]).includes(st ?? "")
    ? (st as Aud12Scenario)
    : "a";
  return (
    <div data-screen="AUD-12" data-scenario={scenario} className="bg-shell p-[12px]">
      {scenario === "b" || scenario === "c" || scenario === "h" ? (
        <GridBoard scenario={scenario} />
      ) : (
        <JeBoard state={KIT_STATE_OF[scenario]} />
      )}
    </div>
  );
}
