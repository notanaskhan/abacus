// WB-03 d2: the O4 workbook preview (W-02-T08 registers `?ov=artifact:<artifactId>`; the full sheet
// with its tabs and grid is W-02-T21's). The sheet comes from the stored artifact
// (`GET /v1/run-artifacts/{id}/preview`), never recomputed in the browser (AC-R2, C11).
import { FullSheet } from "@abacus/ui";
import { type JSX, useState } from "react";
import { useArtifactPreview } from "../../domain/workbench";

export interface ArtifactPreviewProps {
  artifactId: string;
  onClose: () => void;
}

export function ArtifactPreview({ artifactId, onClose }: ArtifactPreviewProps): JSX.Element {
  const [sheet, setSheet] = useState<string | null>(null);
  const preview = useArtifactPreview(artifactId, sheet);
  const data = preview.data;
  return (
    <FullSheet
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={data?.file_name ?? ""}
    >
      {data === undefined ? null : (
        <div data-wb03="preview" className="flex min-h-0 flex-1 flex-col gap-[8px]">
          <div role="tablist" className="flex gap-[6px]">
            {data.sheets.map((name) => (
              <button
                key={name}
                type="button"
                role="tab"
                aria-selected={name === data.sheet}
                onClick={() => {
                  setSheet(name);
                }}
                className="h-[28px] rounded-[8px] px-[10px] text-body aria-selected:bg-sel-bg"
              >
                {name}
              </button>
            ))}
          </div>
          <table className="w-full text-body">
            <thead>
              <tr>
                {data.columns.map((c) => (
                  <th key={c} scope="col" className="text-left font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row, i) => (
                <tr key={`${data.sheet}-${String(i)}`}>
                  {row.map((cell, j) => (
                    <td
                      key={`${String(i)}-${String(j)}`}
                      className={cell.kind === "number" ? "text-right tabular-nums" : ""}
                      {...(cell.bold === true ? { "data-bold": true } : {})}
                    >
                      {cell.value}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {data.footnote == null ? null : <p className="text-meta text-ink-3">{data.footnote}</p>}
        </div>
      )}
    </FullSheet>
  );
}
