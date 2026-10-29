// FIL-01 Files browser and document drawer: one fixture scenario per artboard (N-01-T16;
// docs/screens/FIL-01.md States). Clock E0 Mon Sep 14, 2026, 9:24 AM CT unless stated; the
// handlers answer the four Files routes in the read model's shapes (N-01-T19):
//
//   a  olivia-brandt   Ridgeline TY2025 Form 1065 › Source documents, the mortgage statements open
//   b  olivia-brandt   8:47 AM: the Elm Street roof invoice still classifying (Processing)
//   c  dina-sato       Iyer TY2025 Form 1040: the March 1099-DIV superseded and struck
//   d  felix-andersen  Collins TY2023 Form 1040 on legal hold; security admin, metadata only
//   e  hannah-leclerc  Meridian FY2025 FS audit archive sealed (fixture-only until A-07)
//   f  olivia-brandt   a with the borrower TIN revealed (the logged reveal)
//   g  olivia-brandt   Signed authorizations: empty
//   h  olivia-brandt   9:26 AM: after a preparer sign-off, P "OB" (fixture-only: writes slice)
//   i  olivia-brandt   version 1 locked (fixture-only: writes slice)
//   j  olivia-brandt   client access "Can view" (fixture-only: writes slice)

import type { DrawerOut, FileRow, FileTreeOut } from "@abacus/api-client";
import { defineScenarios, json, type Scenario } from "../../app-core/fixture-mode";
import { seedScenario } from "../scenario";
import { DEMO_INSTANT } from "../seed/clock";
import {
  COLLINS_ROWS,
  COLLINS_SOURCE,
  COLLINS_TREE,
  IYER_ROWS,
  IYER_SOURCE,
  IYER_TREE,
  MERIDIAN_ARCHIVE,
  MERIDIAN_ROWS,
  MERIDIAN_TREE,
  MORTGAGE,
  MORTGAGE_ACCESS_LOG,
  RIDGELINE_SOURCE_ROWS,
  RIDGELINE_TREE,
  ROOF,
  SIGNED_AUTHORIZATIONS,
  SOURCE_DOCS,
  collinsDrawer,
  mortgageDrawer,
  roofDrawer,
} from "../seed/files";

export type Fil01State = "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i" | "j";
export const FIL01_STATES: readonly Fil01State[] = [
  "a",
  "b",
  "c",
  "d",
  "e",
  "f",
  "g",
  "h",
  "i",
  "j",
];

/** What each artboard opens on: the folder (`?node=`) and the document (`?doc=`). */
export const OPENS: Readonly<Record<Fil01State, { node: string; doc: string | null }>> = {
  a: { node: SOURCE_DOCS, doc: MORTGAGE },
  b: { node: SOURCE_DOCS, doc: ROOF },
  c: { node: IYER_SOURCE, doc: null },
  d: { node: COLLINS_SOURCE, doc: COLLINS_ROWS[0]?.evidence_item_id ?? null },
  e: { node: MERIDIAN_ARCHIVE, doc: null },
  f: { node: SOURCE_DOCS, doc: MORTGAGE },
  g: { node: SIGNED_AUTHORIZATIONS, doc: null },
  h: { node: SOURCE_DOCS, doc: MORTGAGE },
  i: { node: SOURCE_DOCS, doc: MORTGAGE },
  j: { node: SOURCE_DOCS, doc: MORTGAGE },
};

/** FIL-01f: the fictional EIN the logged reveal returns (handoff frame F). */
export const REVEALED_TIN = "00-0000287";

const E0 = seedScenario();

function folderPage(rows: readonly FileRow[]): unknown {
  const real = rows.length;
  const virtual = rows.reduce((n, r) => n + r.virtual_children.length, 0);
  return { items: rows, next_cursor: null, total: rows.length, documents: real, virtual };
}

function files(
  state: Fil01State,
  persona: string,
  tree: FileTreeOut,
  folders: Readonly<Record<string, readonly FileRow[]>>,
  drawer: (id: string) => DrawerOut | null,
  clock: string = DEMO_INSTANT,
): Scenario {
  return {
    state,
    persona,
    clock,
    handlers: {
      ...E0.handlers,
      "GET /v1/files/tree": () => json(tree),
      "GET /v1/files/folders/{folder_ref}/items": ({ params }) =>
        json(folderPage(folders[params.folder_ref ?? ""] ?? [])),
      "GET /v1/evidence-items/{item_id}/drawer": ({ params }) => {
        const found = drawer(params.item_id ?? "");
        return found === null ? json({ detail: "not found" }, 404) : json(found);
      },
      "GET /v1/evidence-items/{item_id}/access-log": () =>
        json({ items: MORTGAGE_ACCESS_LOG, next_cursor: null, total: MORTGAGE_ACCESS_LOG.length }),
    },
  };
}

const RIDGELINE_FOLDERS = { [SOURCE_DOCS]: RIDGELINE_SOURCE_ROWS, [SIGNED_AUTHORIZATIONS]: [] };

function ridgelineDrawer(over: Partial<DrawerOut> = {}): (id: string) => DrawerOut | null {
  return (id) => (id === MORTGAGE ? mortgageDrawer(over) : id === ROOF ? roofDrawer() : null);
}

export const scenarios = defineScenarios({
  a: files("a", "olivia-brandt", RIDGELINE_TREE, RIDGELINE_FOLDERS, ridgelineDrawer()),
  b: files(
    "b",
    "olivia-brandt",
    RIDGELINE_TREE,
    RIDGELINE_FOLDERS,
    ridgelineDrawer(),
    "2026-09-14T08:47:00-05:00",
  ),
  c: files("c", "dina-sato", IYER_TREE, { [IYER_SOURCE]: IYER_ROWS }, () => null),
  d: files("d", "felix-andersen", COLLINS_TREE, { [COLLINS_SOURCE]: COLLINS_ROWS }, () =>
    collinsDrawer(),
  ),
  e: files(
    "e",
    "hannah-leclerc",
    MERIDIAN_TREE,
    { [MERIDIAN_ARCHIVE]: MERIDIAN_ROWS },
    () => null,
  ),
  f: files("f", "olivia-brandt", RIDGELINE_TREE, RIDGELINE_FOLDERS, ridgelineDrawer()),
  g: files("g", "olivia-brandt", RIDGELINE_TREE, RIDGELINE_FOLDERS, ridgelineDrawer()),
  h: files(
    "h",
    "olivia-brandt",
    RIDGELINE_TREE,
    RIDGELINE_FOLDERS,
    ridgelineDrawer({
      sign_off_slots: [
        { level: "preparer", initials: "OB", signed_at: "2026-09-14T14:26:00Z" },
        { level: "reviewer", initials: null, signed_at: null },
      ],
    }),
    "2026-09-14T09:26:00-05:00",
  ),
  i: files(
    "i",
    "olivia-brandt",
    {
      nodes: RIDGELINE_TREE.nodes.map((n, i) => (i === 0 ? { ...n, locked: true } : n)),
    },
    RIDGELINE_FOLDERS,
    ridgelineDrawer(),
  ),
  j: files(
    "j",
    "olivia-brandt",
    RIDGELINE_TREE,
    RIDGELINE_FOLDERS,
    ridgelineDrawer({ client_access: "view" }),
  ),
});
