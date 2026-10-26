// SHL-08 EvidenceViewer (P-03-T14; P-03 F3, AC3.1–AC3.7): the L3 container on F-05's E5
// SourceViewer shell, shared by its two hosts, the O2 drawer (ViewerDrawer) and the T2 dock pane
// (ViewerPane).
//
// - Opened on a match, the region lights in the match purple and the well scrolls so it sits 30%
//   from the top; the linked-figure row for the same citation carries the same match, so the row
//   and the region light together (one store per viewer, MatchScope).
// - Opened from a cited record (its anchor), "Source n of m ‹ ›" steps the anchor's stack: each
//   step loads that source's version and lights its match. Two page edges peek under the page with
//   a match-mark band, and "Also cited: …" lists the other members.
// - Auto-highlight cited fields (R2, AC3.6): on by default, per viewer, kept in browser storage
//   (wrapped: a blocked store just means the default).
// - Download is only ever a ⋯ menu item, on the audited attachment route; no bar carries it, and
//   no raw file, pdf.js or SheetJS reaches the browser (AC3.7). Masks render as their tokens; the
//   viewer never unmasks anything itself. When the manifest gives the `text` view (DEC-369: an
//   offshore reader, until OCR) the body is the masked text instead of any page image.

import { type CitationV2Out, content } from "@abacus/api-client";
import { listCitationsOptions } from "@abacus/api-client/query";
import {
  type MatchId,
  type MenuItem,
  SourceViewer,
  contractMatchId,
  useMatchStore,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useEffect, useMemo, useState } from "react";
import { MaskedTextView } from "../../app-core/masked-text";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { COPY } from "./copy";
import { LinkedFigures } from "./LinkedFigures";
import { type ViewerData, useViewerData } from "./useViewerManifest";

export interface ViewerAnchor {
  type: string;
  id: string;
  ref: string;
}

export interface EvidenceViewerTarget {
  versionId: string;
  /** The match lit on open; none opens on page 1. */
  matchId?: string | null;
  /** The cited record the viewer opened from. */
  anchor?: ViewerAnchor | null;
  /** The card's figure name ("Form 1040 line 2a"). */
  figure?: string | null;
  /** The engagement the version belongs to: Download needs it (the audited attachment route). */
  engagementId?: string | null;
  /** A region hovered as the artboard opens (SHL-08h). */
  hovered?: string | null;
}

// ---- Auto-highlight preference ----------------------------------------------------------------

export const AUTO_HIGHLIGHT_KEY = "abacus.viewer.auto-highlight";

function readAutoHighlight(): boolean {
  try {
    return window.localStorage.getItem(AUTO_HIGHLIGHT_KEY) !== "off";
  } catch {
    return true;
  }
}

function writeAutoHighlight(on: boolean): void {
  try {
    window.localStorage.setItem(AUTO_HIGHLIGHT_KEY, on ? "on" : "off");
  } catch {
    // Storage blocked (a private window): the toggle still holds for this viewer.
  }
}

// ---- Download ----------------------------------------------------------------------------------

async function download(engagementId: string, versionId: string): Promise<void> {
  const { data, response } = await content({
    path: { engagement_id: engagementId, version_id: versionId },
    parseAs: "blob",
    throwOnError: true,
  });
  const header = response.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(header)?.[1] ?? "evidence";
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

// ---- The container's state -------------------------------------------------------------------

export interface EvidenceViewerState {
  data: ViewerData;
  versionId: string;
  match: MatchId | null;
  /** The anchor's stack, when there is more than the one source. */
  stack: { items: readonly CitationV2Out[]; index: number; step: (to: number) => void } | null;
  autoHighlight: boolean;
  /** The ⋯ menu: Download and Open in Files, then the auto-highlight toggle. */
  menu: MenuItem[][];
  alsoCited: string | null;
}

/** "Also cited: Ridgeline statement p. 3 (…) · Ridgeline TB 4510 …" from the stack's other members. */
export function alsoCitedLine(items: readonly CitationV2Out[], index: number): string | null {
  const others = items.filter((_, i) => i !== index);
  if (others.length === 0) return null;
  return `${COPY.alsoCited}${others.map((c) => `${c.title} ${c.loc}`.trim()).join(" · ")}.`;
}

export function useEvidenceViewer(target: EvidenceViewerTarget): EvidenceViewerState {
  const anchor = target.anchor ?? null;
  const stackQuery = useQuery({
    ...listCitationsOptions({
      query: {
        anchor_type: anchor?.type ?? null,
        anchor_id: anchor?.id ?? null,
        anchor_ref: anchor?.ref ?? null,
      },
    }),
    enabled: anchor !== null,
  });
  const items = useMemo(
    () =>
      (stackQuery.data?.items ?? []).filter(
        (c) => c.source.evidence_version_id !== null && c.match_id !== null,
      ),
    [stackQuery.data],
  );
  const opened = items.findIndex((c) => c.match_id === target.matchId);
  const [picked, setPicked] = useState<number | null>(null);
  const index = picked ?? Math.max(0, opened);
  const current = items[index];
  const versionId = current?.source.evidence_version_id ?? target.versionId;
  const matchText = current?.match_id ?? target.matchId ?? null;
  const match = matchText === null ? null : contractMatchId({ match_id: matchText, rects: [] });
  const raw = useViewerData(versionId);
  // The opened region carries its linked-figure tag ("Form 1040 · line 2a 1,550"): the region's
  // label with the citation's verified value split off it, so the value reads in the match ink.
  const data = useMemo<ViewerData>(() => {
    const value = current?.value_text ?? null;
    if (value === null || matchText === null) return raw;
    return {
      ...raw,
      file: {
        ...raw.file,
        regions: raw.file.regions.map((r) => {
          const label = (r.label ?? "").trim();
          if (r.match !== matchText || !label.endsWith(value)) return r;
          const name = label.slice(0, label.length - value.length).trim();
          return name === "" ? r : { ...r, linkedFigure: { label: name, value } };
        }),
      },
    };
  }, [raw, current, matchText]);

  const store = useMatchStore();
  const regionsReady = data.file.regions.length > 0;
  const lit = match ?? (target.hovered == null ? null : (target.hovered as MatchId));
  useEffect(() => {
    if (lit === null || !regionsReady) return;
    store.light(lit, null);
  }, [lit, regionsReady, store]);

  const [autoHighlight, setAutoHighlight] = useState(readAutoHighlight);
  const engagementId = target.engagementId ?? null;
  // Download is always listed (AC-19: "Download · Open in Files"), enabled when the version's
  // engagement is known, since the audited content route is engagement-scoped.
  const files: MenuItem[] = [
    {
      label: COPY.menu.download,
      icon: "download",
      disabled: engagementId === null,
      onSelect: () => {
        if (engagementId !== null) void download(engagementId, versionId);
      },
    },
    ...(PLANNED_VISIBLE
      ? [
          {
            label: COPY.menu.openInFiles,
            hint: COPY.openInFilesHint,
            disabled: true,
            onSelect: () => undefined,
          },
        ]
      : []),
  ];
  const menu: MenuItem[][] = [
    files,
    [
      {
        label: COPY.menu.autoHighlight,
        checked: autoHighlight,
        onSelect: () => {
          const next = !autoHighlight;
          writeAutoHighlight(next);
          setAutoHighlight(next);
        },
      },
    ],
  ];

  return {
    data,
    versionId,
    match,
    stack:
      items.length > 1
        ? {
            items,
            index,
            step: (to) => {
              setPicked(Math.min(items.length - 1, Math.max(0, to)));
            },
          }
        : null,
    autoHighlight,
    menu,
    alsoCited: items.length > 1 ? alsoCitedLine(items, index) : null,
  };
}

// ---- The body ----------------------------------------------------------------------------------

/** The page width each host gives the shell: the 480 drawer and the 330 dock, less the well. */
export const PAGE_WIDTH = { drawer: 436, dock: 296 } as const;

export interface EvidenceViewerBodyProps {
  host: "drawer" | "dock";
  target: EvidenceViewerTarget;
  viewer: EvidenceViewerState;
}

export function EvidenceViewerBody({
  host,
  target,
  viewer,
}: EvidenceViewerBodyProps): JSX.Element {
  const { data, stack, match } = viewer;
  if (data.view === "text") {
    // DEC-369: no page images for this reader; the server's masked text instead.
    return <MaskedTextView text={data.text} width={PAGE_WIDTH[host]} />;
  }
  const anchor = target.anchor ?? null;
  const card =
    host === "drawer" && anchor !== null ? (
      <LinkedFigures
        hostRef={`${anchor.type}:${anchor.id}`}
        versionId={viewer.versionId}
        figure={target.figure ?? null}
        regions={data.file.regions}
        stack={
          stack === null
            ? null
            : { index: stack.index, total: stack.items.length, onStep: stack.step }
        }
      />
    ) : undefined;
  return (
    <SourceViewer
      key={viewer.versionId}
      file={data.file}
      variant={host === "dock" ? "evidence" : "full"}
      header={false}
      status={data.status === "processing" ? "ready" : data.status}
      loading={data.loading}
      skeletons={3}
      pageWidth={PAGE_WIDTH[host]}
      outlineCited={viewer.autoHighlight}
      scrollToLit
      {...(host === "dock"
        ? { menu: viewer.menu.flat().filter((i) => i.checked === undefined) }
        : {})}
      {...(stack !== null && match !== null
        ? { stack: { match, edges: stack.items.length > 2 ? 2 : 1 } as const }
        : {})}
      {...(card === undefined ? {} : { aboveWell: card })}
      {...(viewer.alsoCited === null || host === "dock"
        ? {}
        : {
            afterPages: (
              <p data-also-cited="" className="w-[436px] pb-[12px] text-para text-ink-3">
                {viewer.alsoCited}
              </p>
            ),
          })}
    />
  );
}
