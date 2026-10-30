import {
  type CitationView,
  type DocBlock,
  DocBlocks,
  type DocSegment,
  DocumentOnWell,
  type DocumentVM,
  type KvSheetVM,
  type MatchId,
  RecordHeader,
  SegmentedGroup,
  amount,
} from "@abacus/ui";
import type { JSX } from "react";
import { useSession } from "../../../app-core/session";
import {
  BRIDGE,
  BRIDGE_LABELS,
  GENERAL_INFORMATION,
  MEMO_SECTIONS,
  RIDGELINE,
  RIDGELINE_ENG04,
} from "../../../fixtures/seed/tax";
import type { FixtureParams } from "../../fixture-mode";
import { specimenToolbar } from "../firm-toolbar";
import { COPY } from "./copy";

// TPL-10 Ridgeline preparer memo specimen (F-06-T16; TPL-10 handoff; F-06.md §3 F4): T10 with the
// seeded memo on DocBlocks. a awaiting the reviewer (the DRAFT watermark, "Adopted by Olivia
// Brandt", Approve memo… for Samuel Ito); b drafting (the agent's run, nothing to approve yet); c
// approved by Samuel Ito; d the ENG-04 engagement letter: template and clause blocks only, no agent
// prose (ADR P-25 off). Citation markers [1]–[5] light the KV row they cite. Every figure is seed
// data, formatted by code; the memo's figures foot (1,231,600; 1,256,200; 733,500) in the seed's
// tests. Registered for /components/screens/TPL-10?st=a|b|c|d.

export const TPL10_STATES = ["a", "b", "c", "d"] as const;
export type Tpl10State = (typeof TPL10_STATES)[number];

const m = (id: string): MatchId => `tpl10:${id}` as MatchId;
const SAMUEL = { kind: "human" as const, name: "Samuel Ito" };
// Which KV row each memo citation lights (the facts, the allocation, the engine return, the year
// and the extension the memo's figures rest on).
const CITED: Readonly<Record<number, string>> = {
  1: "partners",
  2: "allocation",
  3: "engineReturn",
  4: "taxYear",
  5: "extension",
};
const CITE_TITLES: Readonly<Record<number, string>> = {
  1: "Partnership agreement",
  2: "Pell Street transfer memo",
  3: "2025P:Ridgeline:V2",
  4: "Fixed asset register",
  5: "State apportionment workpaper",
};

function cite(n: number): CitationView {
  const key = CITED[n] ?? "partners";
  return {
    n,
    title: CITE_TITLES[n] ?? "",
    quote: GENERAL_INFORMATION.find((r) => r.key === key)?.value ?? "",
    loc: COPY.kv[key as keyof typeof COPY.kv],
    match: m(key),
  };
}

const SHEET: KvSheetVM = {
  crumb: COPY.sheetHeader,
  sections: [
    {
      title: COPY.paperTitle,
      rows: GENERAL_INFORMATION.map((r) => ({
        key: COPY.kv[r.key as keyof typeof COPY.kv],
        value: r.value,
        ...(r.link === true ? { linkId: r.key } : {}),
        ...(Object.values(CITED).includes(r.key) ? { match: m(r.key) } : {}),
      })),
    },
  ],
};

const fig = (v: string): DocSegment => ({ kind: "fact", text: amount(v, "whole").text });

function memoBlocks(): DocBlock[] {
  const blocks: DocBlock[] = [];
  for (const section of MEMO_SECTIONS) {
    blocks.push({ kind: "h", level: 4, text: section.heading, provenance: "agent" });
    if (section.table === "bridge") {
      const keys = Object.keys(BRIDGE) as (keyof typeof BRIDGE)[];
      blocks.push({
        kind: "table",
        provenance: "agent",
        head: ["", "2025"],
        rows: keys.map((k) => ({
          cells: [[{ kind: "text", text: BRIDGE_LABELS[k] }], [fig(BRIDGE[k])]],
          ...(k === "netRental" || k === "bookNetIncome" ? { total: true } : {}),
        })),
      });
    }
    for (const text of section.paragraphs) {
      blocks.push({
        kind: "p",
        provenance: "agent",
        segments: [
          { kind: "text", text },
          ...(section.cite === undefined
            ? []
            : [
                {
                  kind: "cite" as const,
                  n: section.cite,
                  citation: cite(section.cite),
                  verified: true,
                },
              ]),
        ],
      });
    }
    if (section.bullets !== undefined) {
      blocks.push({
        kind: "ul",
        provenance: "agent",
        items: section.bullets.map((b) => [{ kind: "text" as const, text: b }]),
      });
    }
  }
  return blocks;
}

function letterBlocks(): DocBlock[] {
  const on = new Set(RIDGELINE_ENG04.sections.filter((s) => s.on).map((s) => s.id));
  const blocks: DocBlock[] = [
    {
      kind: "letterhead",
      firm: COPY.letterheadName,
      lines: [COPY.letterheadAddress],
    },
  ];
  for (const b of RIDGELINE_ENG04.blocks) {
    if (b.section !== "all" && !on.has(b.section)) continue;
    if (b.kind === "sign") {
      blocks.push({ kind: "signature", name: b.name, title: b.title, firm: COPY.letterheadName });
    } else if (b.kind === "h3" || b.kind === "h4") {
      blocks.push({
        kind: "h",
        level: b.kind === "h3" ? 3 : 4,
        text: b.text,
        provenance: "template",
      });
    } else if (b.kind === "li") {
      blocks.push({
        kind: "ul",
        provenance: "template",
        items: [[{ kind: "text", text: b.text }]],
      });
    } else {
      blocks.push({
        kind: "p",
        provenance: "template",
        segments: [{ kind: "text", text: b.text }],
      });
    }
  }
  return blocks;
}

export function tpl10Document(state: Tpl10State): DocumentVM {
  if (state === "d") {
    return {
      status: "draft",
      variant: "letter",
      title: RIDGELINE_ENG04.title,
      watermark: true,
      structure: {
        kind: "clauses",
        clauses: RIDGELINE_ENG04.sections.map((s) => ({
          id: s.id,
          label: s.label,
          on: s.on,
          reason: s.reason,
        })),
        variables: RIDGELINE_ENG04.variables.map((v) => ({
          id: v.key,
          label: v.key,
          value: v.value,
        })),
      },
      actions: { edit: true },
    };
  }
  return {
    status: state === "b" ? "drafting" : state === "c" ? "approved" : "draft",
    variant: "paper",
    title: COPY.paperTitle,
    watermark: state === "a",
    structure: { kind: "kv", sheets: [SHEET] },
    ...(state === "a" ? { adoptedBy: COPY.adoptedBy("Olivia Brandt") } : {}),
    ...(state === "c" ? { approvedBy: { actor: SAMUEL, when: "Sep 14, 9:40 AM" } } : {}),
    actions: { approve: { actor: SAMUEL, object: "memo" }, edit: true, regenerate: true },
  };
}

export function Tpl10Board({ state }: { state: Tpl10State }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const document = tpl10Document(state);
  return (
    <DocumentOnWell
      frame
      height={860}
      document={document}
      copy={{
        edit: COPY.edit,
        regenerate: COPY.regenerate,
        drafting: COPY.drafting,
        rendering: COPY.drafting,
        watermark: COPY.watermark,
        variables: COPY.variables,
        approved: COPY.approved,
      }}
      toolbar={specimenToolbar(firm, "Tax Returns")}
      record={
        <RecordHeader
          title="2025 Form 1065"
          context={RIDGELINE}
          state="In review · Partner"
          checkpoints
          sync="synced"
          syncDate="Sep 11"
          assistant
        />
      }
      tabs={
        <div
          data-shell="tabsbar"
          className="flex h-(--tabs-h) flex-none items-center justify-center px-[12px]"
        >
          <SegmentedGroup
            size="small"
            label="Partnership return"
            options={["Agent", "Issues", "Workpaper", "Review", "Deliverables"]}
            active="Deliverables"
          />
        </div>
      }
      onApprove={() => undefined}
      onEdit={() => undefined}
      onRegenerate={() => undefined}
      onOpenLink={() => undefined}
    >
      {document.status === "drafting" ? null : (
        <DocBlocks
          blocks={state === "d" ? letterBlocks() : memoBlocks()}
          variant={document.variant}
        />
      )}
    </DocumentOnWell>
  );
}

export function Tpl10Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: Tpl10State = TPL10_STATES.find((s) => s === params.st) ?? "a";
  return (
    <div data-artboard={state}>
      <Tpl10Board state={state} />
    </div>
  );
}
