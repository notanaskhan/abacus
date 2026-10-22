import { type JSX, useState } from "react";
import { Count } from "../components/pill";
import { StatusPill } from "../components/status";
import { type IndexColumn, IndexList, type ListEnvelope } from "../templates/index-list";
import type { ViewState } from "../components/view-state";

// T1 Index list (F-05-T28): the five artboards of the T1 handoff (TY2025 returns, Mon Sep 14,
// 2026). The envelope is fixed data a server would send; the template adds nothing up.

interface Return {
  id: string;
  client: string;
  form: string;
  status: string;
  variant: "tag" | "amber" | "red-tint" | "green-tint" | "neutral";
  team: string;
  issues: number;
  due: string;
}

const ROWS: Return[] = [
  {
    id: "feld",
    client: "Jonah & Claire Feld",
    form: "1040",
    status: "In review",
    variant: "amber",
    team: "KO / SI",
    issues: 0,
    due: "Oct 15",
  },
  {
    id: "cl",
    client: "Copperleaf Coffee Roasters, Inc.",
    form: "1120-S",
    status: "Issues",
    variant: "red-tint",
    team: "KO / SI",
    issues: 3,
    due: "Sep 15",
  },
  {
    id: "em",
    client: "Ellison & Ruth Marsh",
    form: "1040",
    status: "Issues",
    variant: "red-tint",
    team: "KO / SI",
    issues: 2,
    due: "Oct 15",
  },
  {
    id: "rp",
    client: "Ridgeline Property Partners, LP",
    form: "1065",
    status: "Prepared",
    variant: "tag",
    team: "PR / HL",
    issues: 0,
    due: "Sep 15",
  },
  {
    id: "ho",
    client: "Harborline Outfitters, LLC",
    form: "1065",
    status: "Ready",
    variant: "green-tint",
    team: "PR / HL",
    issues: 0,
    due: "Sep 15",
  },
];

const COLUMNS: IndexColumn<Return>[] = [
  { key: "client", header: "Client", cell: (r) => r.client },
  { key: "form", header: "Form", width: 90, cell: (r) => r.form },
  {
    key: "status",
    header: "Status",
    width: 170,
    cell: (r) => <StatusPill variant={r.variant}>{r.status}</StatusPill>,
  },
  { key: "team", header: "Preparer / Reviewer", width: 160, cell: (r) => r.team },
  {
    key: "issues",
    header: "Issues",
    width: 80,
    align: "right",
    cell: (r) => (r.issues > 0 ? <Count value={r.issues} tone="bad" /> : "—"),
  },
  { key: "due", header: "Due", width: 90, align: "right", cell: (r) => r.due },
];

const TILES = [
  { code: "prepared", label: "Prepared", variant: "state" as const },
  { code: "in_review", label: "In review", variant: "amber" as const },
  { code: "issues", label: "Issues", variant: "red-tint" as const },
  { code: "ready", label: "Ready", variant: "green-tint" as const },
];

const COUNTS = { prepared: 17, in_review: 15, issues: 11, ready: 7 };

const PREPARERS = [
  { value: "ko", label: "Kevin Osei" },
  { value: "pr", label: "Priya Raman" },
  { value: "hl", label: "Hannah Leclerc" },
];
const OFFICES = [
  { value: "den", label: "Denver" },
  { value: "bou", label: "Boulder" },
];

function T1({
  state,
  envelope,
  preparer = null,
  office = null,
  tile = null,
  query = "",
}: {
  state: ViewState;
  envelope?: ListEnvelope<Return>;
  preparer?: string | null;
  office?: string | null;
  tile?: string | null;
  query?: string;
}): JSX.Element {
  const [selected, setSelected] = useState<string | null>("feld");
  return (
    <div className="flex h-[420px] flex-col overflow-hidden rounded-pane">
      <IndexList<Return>
        title="Tax Returns"
        noun="returns"
        state={state}
        envelope={envelope}
        columns={COLUMNS}
        rowKey={(r) => r.id}
        selected={selected}
        onSelect={(r) => {
          setSelected(r.id);
        }}
        chips={[
          {
            key: "preparer",
            label: "Preparer",
            icon: "user",
            placeholder: "Anyone",
            options: PREPARERS,
            value: preparer,
          },
          {
            key: "office",
            label: "Office",
            icon: "building-2",
            placeholder: "All offices",
            options: OFFICES,
            value: office,
          },
        ]}
        tiles={TILES}
        tile={tile}
        summary="224 returns · 79 open · 145 filed or accepted"
        onClear={() => undefined}
        query={query}
        newLabel="New Return…"
        empty={{
          title: "No returns yet",
          body: "Returns appear here once a client is set up for TY2025.",
        }}
      />
    </div>
  );
}

export function IndexListSpecimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-4">
      <T1
        state={{ kind: "ready" }}
        envelope={{ items: ROWS, next_cursor: "c2", total: 79, counts: COUNTS }}
      />
      <T1
        state={{ kind: "ready" }}
        envelope={{
          items: ROWS.filter((r) => r.status === "Issues"),
          next_cursor: null,
          total: 11,
          counts: COUNTS,
        }}
        preparer="ko"
        tile="issues"
      />
      <T1
        state={{ kind: "empty", action: { label: "Set up a client", onSelect: () => undefined } }}
      />
      <T1
        state={{ kind: "filtered-empty", query: "Haverford", clear: () => undefined }}
        envelope={{ items: [], next_cursor: null, total: 0, counts: COUNTS }}
        office="den"
        query="Haverford"
      />
      <T1 state={{ kind: "loading" }} />
    </div>
  );
}
