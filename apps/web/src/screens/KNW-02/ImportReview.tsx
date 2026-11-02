import type {
  MethodologyImportOut,
  AbacusModulesMethodologyContractStepOut as StepOut,
} from "@abacus/api-client";
import {
  Button,
  Icon,
  Pill,
  type ViewerFile,
  type ViewerRegion,
  type MatchId,
  MATCH_ROW,
  cn,
  useMatch,
} from "@abacus/ui";
import type { JSX } from "react";
import { COPY } from "./copy";

// KNW-02 a, a2, b (K-01-T23; K-01 §3.2; the handoff's a, a2 and b): the import review on the T3
// triad. The viewer shows the uploaded file's pages as the server renders them (masked PNGs, never
// the file) with each parsed step's region; a step's row and its region share the server's
// `match_id`, so selecting step 4 lights page 14 and hovering the region lights the row (C-07,
// 360 ms). Flags are the server's (`parse_flag`): the ⚑ filter shows only them; Confirm and inline
// edit go through the flag-resolution route (a person's act). While the importer runs, the sheet
// shows its RunCard over the import's own progress (polling `…/versions/{id}/import`).

const PAGE_PT = { width: 612, height: 792 };

/** The page images and regions the parsed steps cite, for one file, in page order. */
export function importViewerFile(
  versionId: string,
  imp: MethodologyImportOut,
  steps: readonly StepOut[],
): ViewerFile {
  const file = imp.files.find((f) => f.role === "document_pdf") ?? imp.files[0];
  const regions: ViewerRegion[] = [];
  const pages = new Set<number>();
  for (const s of steps) {
    for (const src of s.sources ?? []) {
      if (file === undefined || src.file_id !== file.id) continue;
      for (let n = src.page_from; n <= src.page_to; n += 1) pages.add(n);
      if (src.bbox != null && src.bbox.length === 4) {
        const [x0 = 0, y0 = 0, x1 = 0, y1 = 0] = src.bbox;
        regions.push({
          match: src.match_id as MatchId, // the server's key (INV-2)
          page: src.page_from,
          rects: [[x0, y0, x1, y1]],
          label: s.text,
        });
      }
    }
  }
  return {
    name: file?.filename ?? "",
    pages: [...pages]
      .sort((a, b) => a - b)
      .map((n) => ({
        n,
        width_pt: PAGE_PT.width,
        height_pt: PAGE_PT.height,
        rotation: 0 as const,
        src:
          file === undefined
            ? ""
            : `/v1/methodology/versions/${versionId}/files/${file.id}/pages/${String(n)}`,
      })),
    regions,
  };
}

function ImportedRow({
  step,
  onConfirm,
}: {
  step: StepOut;
  onConfirm?: ((step: StepOut) => void) | undefined;
}): JSX.Element {
  const first = step.sources?.[0];
  // The server's key, which the page region carries too (INV-2: never built on the client).
  const match = (first?.match_id ?? `step-${step.id}`) as MatchId;
  const { bind, pin, lit } = useMatch(match, "row");
  const flagged = step.parse_flag != null && step.flag_resolution == null;
  const page = step.sources?.[0];
  return (
    <tr
      {...bind}
      data-step={step.number}
      data-flagged={flagged ? "true" : "false"}
      onClick={(e) => {
        pin(e.currentTarget);
      }}
      className={cn(
        "h-[42px] cursor-default align-top hairline-b",
        MATCH_ROW,
        lit && "font-medium",
      )}
    >
      <td className="w-[40px] px-[10px] py-[6px] text-ink-3">{step.number}</td>
      <td className="px-[6px] py-[6px]">
        <span className="line-clamp-2">{step.text}</span>
      </td>
      <td className="w-[90px] px-[6px] py-[6px] text-meta text-ink-3">
        {page === undefined
          ? COPY.sheet.workbook
          : page.page_to > page.page_from
            ? COPY.importReview.pages(page.page_from, page.page_to)
            : COPY.importReview.page(page.page_from)}
      </td>
      <td className="w-[90px] py-[6px]">
        {flagged ? (
          <span className="flex items-center gap-[4px]">
            <Pill variant="amber" size="sm">
              ⚑
            </Pill>
            {onConfirm !== undefined && (
              <Button
                variant="secondary"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onConfirm(step);
                }}
              >
                {COPY.importReview.confirm}
              </Button>
            )}
          </span>
        ) : (
          step.mandatory && <Icon name="lock" size={12} label={COPY.sheet.mandatory} />
        )}
      </td>
    </tr>
  );
}

export function ImportedStepRows({
  steps,
  flaggedOnly,
  onConfirm,
}: {
  steps: readonly StepOut[];
  flaggedOnly: boolean;
  onConfirm?: (step: StepOut) => void;
}): JSX.Element {
  const shown = flaggedOnly
    ? steps.filter((s) => s.parse_flag != null && s.flag_resolution == null)
    : steps;
  return (
    <table data-knw02="import-steps" className="w-full table-fixed text-body">
      <tbody>
        {shown.map((s) => (
          <ImportedRow key={s.id} step={s} onConfirm={onConfirm} />
        ))}
      </tbody>
    </table>
  );
}

/** b: the importer's progress, from the import's own counts (no client arithmetic beyond a ratio
 * for the bar's width). */
export function ParsingRunCard({ imp }: { imp: MethodologyImportOut }): JSX.Element {
  const total = imp.pages_total ?? 0;
  const width = total > 0 ? Math.round((imp.pages_done / total) * 100) : 0;
  return (
    <section data-knw02="run-card" className="m-[12px] rounded-pane bg-card p-[12px] shadow-e1">
      <p className="text-section font-medium">{COPY.importReview.reading(imp.files.length)}</p>
      <p className="mt-[2px] text-meta text-ink-3">
        {COPY.importReview.progress(imp.pages_done, total)}
      </p>
      <div className="mt-[8px] h-[3px] rounded-pill bg-nested">
        <div className="h-[3px] rounded-pill bg-ink" style={{ width: `${String(width)}%` }} />
      </div>
    </section>
  );
}
