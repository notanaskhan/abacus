// TXP-01 · Review › Summary, the preparer memo (T-05-T59; docs/screens/TXP-01.md; handoff TXP-01
// states A, A2, A3, B, C, D; T10 Document on well). The KV rail (the partnership's general
// information and each cited source), the memo's sections with CiteMarkers whose sources light in
// the rail (E1 match, 360 ms), SHL-07 on a marker, in-place edit of one section, Regenerate with a
// confirm, Adopt (L1) and Approve (L2) through SHL-12 (the host's), the Drafting skeleton, the
// Stale banner listing each moved figure with "Regenerate sections", and the opportunities as
// planned links (TAX-15, PRJ-01). Every figure is the server's; nothing here computes one.
import type {
  WorkbookGeneralInformationOut,
  WorkbookMemoCitationOut,
  WorkbookMemoOut,
  WorkbookOpportunityOut,
} from "@abacus/api-client";
import {
  Button,
  type CitationView,
  type DocBlock,
  DocBlocks,
  DocumentOnWell,
  type DocumentVM,
  type KvSheetVM,
  type MatchId,
  type ToolbarProps,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

const m = (id: string): MatchId => `txp01:${id}` as MatchId;
// Drawn bare inside the entity return's frame: the template's own shell is not drawn.
const BARE_TOOLBAR: ToolbarProps = { nav: [], firm: "" };
const SAMUEL = { kind: "human" as const };

type MemoCitation = WorkbookMemoCitationOut;

export function citeView(c: MemoCitation): CitationView {
  return { n: c.n, title: c.title, quote: c.quote, loc: c.loc, match: m(c.id) };
}

/** The rail: the partnership's facts, then each cited source (what a marker lights). */
export function railOf(
  general: WorkbookGeneralInformationOut | undefined,
  memo: WorkbookMemoOut | undefined,
): KvSheetVM {
  const g = general;
  const cited = new Map<string, MemoCitation>();
  for (const s of memo?.sections ?? []) for (const c of s.citations ?? []) cited.set(c.id, c);
  return {
    crumb: `${COPY.railHeader} › ${COPY.railGroup}`,
    sections: [
      {
        title: COPY.railGroup,
        rows: [
          { key: COPY.kv.entity, value: g?.entity_name ?? null },
          { key: COPY.kv.ein, value: g?.ein_last4 ? `••-•••${g.ein_last4}` : null },
          { key: COPY.kv.year, value: g ? `Calendar ${String(g.tax_year)}` : null },
          { key: COPY.kv.method, value: g?.accounting_method ?? null },
          { key: COPY.kv.preparer, value: g?.preparer_name ?? null },
          { key: COPY.kv.reviewer, value: g?.reviewer_name ?? null },
          { key: COPY.kv.signer, value: g?.signer_name ?? null },
        ],
      },
      ...(cited.size === 0
        ? []
        : [
            {
              title: COPY.sourcesGroup,
              rows: [...cited.values()]
                .sort((a, b) => a.n - b.n)
                .map((c) => ({ key: `[${String(c.n)}] ${c.title}`, value: c.quote, match: m(c.id) })),
            },
          ]),
    ],
  };
}

/** The memo as paper blocks: a heading per section, its body with its markers. */
export function memoBlocks(memo: WorkbookMemoOut): DocBlock[] {
  return memo.sections.flatMap((s): DocBlock[] => [
    { kind: "h", level: 4, text: s.title, provenance: s.human_owned ? "human" : "agent" },
    {
      kind: "p",
      provenance: s.human_owned ? "human" : "agent",
      segments: [
        { kind: "text", text: s.body },
        ...(s.citations ?? []).map((c) => ({
          kind: "cite" as const,
          n: c.n,
          citation: citeView(c),
          verified: true,
        })),
      ],
    },
  ]);
}

export interface TXP01Props {
  memo: WorkbookMemoOut | undefined;
  general: WorkbookGeneralInformationOut | undefined;
  opportunities?: readonly WorkbookOpportunityOut[];
  /** The adopter and approver names for the paper header (the ladder's). */
  adoptedBy?: string;
  approvedBy?: { name: string; when: string };
  onAdopt?: () => void;
  onApprove?: () => void;
  onRegenerate?: (affectedOnly: boolean) => void;
  onSaveSection?: (key: string, body: string) => void;
  onOpenLink?: (linkId: string) => void;
  /** The signed-in person (who would approve: INV-1). */
  viewerName?: string;
}

export function TXP01({
  memo,
  general,
  opportunities = [],
  adoptedBy,
  approvedBy,
  onAdopt,
  onApprove,
  onRegenerate,
  onSaveSection,
  onOpenLink,
  viewerName,
}: TXP01Props): JSX.Element {
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const actions = new Set(memo?.memo_actions ?? []);
  const drafting = memo === undefined || memo.status === "drafting";
  const approved = memo?.status === "approved";
  const document: DocumentVM = {
    status: drafting ? "drafting" : approved ? "approved" : "draft",
    variant: "paper",
    title: COPY.pane,
    watermark: !drafting && !approved,
    structure: { kind: "kv", sheets: [railOf(general, memo)] },
    ...(adoptedBy !== undefined && !approved ? { adoptedBy: COPY.adoptedBy(adoptedBy) } : {}),
    ...(approved && approvedBy !== undefined
      ? { approvedBy: { actor: { ...SAMUEL, name: approvedBy.name }, when: approvedBy.when } }
      : {}),
    actions: {
      ...(actions.has("tax_memo.approve") || actions.has("tax_memo.adopt")
        ? { approve: { actor: { kind: "human" as const, name: viewerName ?? "" }, object: "memo" } }
        : {}),
      edit: actions.has("tax_memo.edit"),
      regenerate: actions.has("tax_memo.draft"),
    },
  };
  return (
    <div data-screen="TXP-01" data-state={memo?.status ?? "drafting"} className="flex min-h-0 flex-1">
      <DocumentOnWell
        bare
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
        toolbar={BARE_TOOLBAR}
        record={null}
        onApprove={() => {
          if (actions.has("tax_memo.approve")) onApprove?.();
          else if (actions.has("tax_memo.adopt")) onAdopt?.();
        }}
        onEdit={() => {
          const first = memo?.sections.find((s) => !s.human_owned) ?? memo?.sections[0];
          if (first !== undefined) {
            setEditing(first.key);
            setDraft(first.body);
          }
        }}
        onRegenerate={() => {
          setConfirming(true);
        }}
        {...(onOpenLink === undefined ? {} : { onOpenLink })}
      >
        {memo !== undefined && memo.status === "stale" && (memo.stale_fields ?? []).length > 0 ? (
          <div
            role="status"
            data-stale-banner
            className="mb-[12px] flex min-h-[32px] items-center gap-[8px] rounded-[8px] bg-amber-tint px-[10px] text-[12px] text-amber-ink"
          >
            <span className="flex-1">{COPY.stale(memo.stale_fields ?? [])}</span>
            {actions.has("tax_memo.draft") ? (
              <Button variant="secondary" size="sm" onClick={() => onRegenerate?.(true)}>
                {COPY.regenerateSections}
              </Button>
            ) : null}
          </div>
        ) : null}
        {confirming ? (
          <div role="dialog" aria-label={COPY.confirmTitle} className="mb-[12px] rounded-[10px] bg-card p-[12px] shadow-e2">
            <p className="text-[13px] font-medium text-ink">{COPY.confirmTitle}</p>
            <p className="mt-[4px] text-[12px] text-ink-2">{COPY.confirmBody}</p>
            <div className="mt-[8px] flex justify-end gap-[6px]">
              <Button variant="ghost" size="sm" onClick={() => { setConfirming(false); }}>
                {COPY.cancel}
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  setConfirming(false);
                  onRegenerate?.(false);
                }}
              >
                {COPY.confirm}
              </Button>
            </div>
          </div>
        ) : null}
        {editing !== null ? (
          <div data-editing={editing} className="mb-[12px] flex flex-col gap-[6px]">
            <textarea
              aria-label={memo?.sections.find((s) => s.key === editing)?.title ?? editing}
              value={draft}
              onChange={(e) => { setDraft(e.target.value); }}
              className="min-h-[120px] rounded-[8px] bg-card p-[8px] text-[12.5px] shadow-e1"
            />
            <div className="flex justify-end gap-[6px]">
              <Button variant="ghost" size="sm" onClick={() => { setEditing(null); }}>
                {COPY.cancel}
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={draft.trim() === ""}
                onClick={() => {
                  onSaveSection?.(editing, draft.trim());
                  setEditing(null);
                }}
              >
                {COPY.save}
              </Button>
            </div>
          </div>
        ) : null}
        {drafting ? null : (
          <>
            <h3 className="mb-[6px] text-[16px] font-medium text-ink">
              {general
                ? COPY.memoTitle(general.entity_name, general.tax_year, general.form)
                : COPY.pane}
            </h3>
            <DocBlocks blocks={memoBlocks(memo)} variant="paper" />
            {opportunities.length > 0 ? (
              <section data-opportunities className="mt-[12px]">
                <h4 className="text-[13.5px] font-medium text-ink">{COPY.opportunities}</h4>
                <ul className="mt-[4px] flex flex-col gap-[6px]">
                  {opportunities.map((o) => (
                    <li key={o.key} className="flex items-center gap-[8px]">
                      <span aria-hidden className="h-[16px] w-[16px] rounded-full border border-hair" />
                      <span className="flex-1 text-[13px] font-medium text-ink">{o.title}</span>
                      <Button variant="ghost" size="sm" disabled title={COPY.planned}>
                        {COPY.raise}
                      </Button>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </>
        )}
      </DocumentOnWell>
    </div>
  );
}
