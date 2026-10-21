import { Popover } from "@abacus/ui";
import { type JSX, type ReactNode, useEffect, useRef, useState } from "react";
import {
  type Box,
  findLine,
  pageBlob,
  parseCell,
  type PreviewSource,
  usePreview,
} from "./EvidencePreview";
import { SourceDrawer } from "./SourceDrawer";

// TASK-334: point from a value to where it was printed. Hovering (or focusing) a value shows a
// snippet of its source: the page around the outlined line, or the cell among its neighbours.
// Clicking opens the source viewer at that spot. Boxes come from the server's extraction;
// nothing here reads or interprets the document.

export type SourceRef = {
  versionId: string;
  itemId?: string | undefined;
  page?: number | undefined;
  box?: Box | undefined;
  cell?: string | undefined;
  findText?: string | undefined;
};

const SNIPPET_W = 340;
const SNIPPET_H = 130;
const SCALE = 2.2; // the page image is this many snippet widths wide

/** The page image cropped around a box, the box outlined (exported for tests). */
export function cropStyle(box: Box, aspect: number): { left: number; top: number; width: number } {
  const width = SNIPPET_W * SCALE;
  const height = width * aspect;
  const cx = ((box[0] + box[2]) / 2) * width;
  const cy = ((box[1] + box[3]) / 2) * height;
  const left = Math.min(0, Math.max(SNIPPET_W - width, SNIPPET_W / 2 - cx));
  const top = Math.min(0, Math.max(SNIPPET_H - height, SNIPPET_H / 2 - cy));
  return { left, top, width };
}

function PageSnippet({ source, page, box }: { source: PreviewSource; page: number; box: Box }) {
  const [url, setUrl] = useState<string | null>(null);
  const [aspect, setAspect] = useState(792 / 612);
  useEffect(() => {
    let current: string | null = null;
    let live = true;
    pageBlob(source, page)
      .then((blob) => {
        if (!live) return;
        current = URL.createObjectURL(blob);
        setUrl(current);
      })
      .catch(() => undefined);
    return () => {
      live = false;
      if (current !== null) URL.revokeObjectURL(current);
    };
  }, [source.kind, source.engagementId, page]);
  if (url === null) return <div className="h-[130px] animate-pulse rounded-nested bg-nested" />;
  const crop = cropStyle(box, aspect);
  return (
    <div
      className="relative overflow-hidden rounded-nested border border-line bg-surface"
      style={{ width: SNIPPET_W, height: SNIPPET_H }}
    >
      <div className="absolute" style={{ left: crop.left, top: crop.top, width: crop.width }}>
        <img
          src={url}
          alt={`Page ${String(page)}, around the value`}
          className="block w-full"
          onLoad={(e) => {
            const img = e.currentTarget;
            if (img.naturalWidth > 0) setAspect(img.naturalHeight / img.naturalWidth);
          }}
        />
        <span
          aria-hidden="true"
          className="absolute rounded-[3px] bg-match-bg/60 inset-shadow-[inset_0_0_0_1.5px_var(--color-match-line)]"
          style={{
            left: `${String(box[0] * 100 - 0.6)}%`,
            top: `${String(box[1] * 100 - 0.4)}%`,
            width: `${String((box[2] - box[0]) * 100 + 1.2)}%`,
            height: `${String((box[3] - box[1]) * 100 + 0.8)}%`,
          }}
        />
      </div>
    </div>
  );
}

function CellSnippet({ source, cell }: { source: PreviewSource; cell: string }) {
  const preview = usePreview(source);
  const target = parseCell(cell);
  const sheet = preview.data?.sheets[0];
  if (preview.isPending)
    return <div className="h-[80px] animate-pulse rounded-nested bg-nested" />;
  if (target === null || sheet === undefined) {
    return <p className="text-ink-3">{`Cell ${cell}`}</p>;
  }
  const rows = sheet.rows.slice(Math.max(target.row - 2, 0), target.row + 1);
  const first = Math.max(target.col - 2, 0);
  return (
    <table className="w-full border-collapse text-[12px]">
      <tbody>
        {rows.map((row, r) => {
          const rowNo = Math.max(target.row - 2, 0) + r + 1;
          return (
            <tr key={rowNo}>
              {row.slice(first, first + 5).map((value, c) => {
                const hit = rowNo === target.row && first + c === target.col;
                return (
                  <td
                    key={c}
                    className={`border-[0.5px] border-hair px-1.5 py-0.5 ${hit ? "bg-match-bg font-medium text-match-ink" : "text-ink-2"}`}
                  >
                    {value}
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Snippet({ engagementId, source: ref }: { engagementId: string; source: SourceRef }) {
  const source: PreviewSource =
    ref.itemId !== undefined
      ? { kind: "upload", engagementId, itemId: ref.itemId, versionId: ref.versionId }
      : { kind: "version", engagementId, versionId: ref.versionId };
  const preview = usePreview(source);
  if (ref.cell !== undefined) return <CellSnippet source={source} cell={ref.cell} />;
  const page = ref.page ?? 1;
  const lines = (preview.data?.page_lines ?? [])[page - 1] as
    { text: string; box: Box }[] | undefined;
  const box = ref.box ?? (ref.findText !== undefined ? findLine(lines, ref.findText) : null);
  if (box === null) {
    return <p className="text-ink-3">{`Page ${String(page)}. Click to open the document.`}</p>;
  }
  return <PageSnippet source={source} page={page} box={box} />;
}

/** A value that shows where it came from: a snippet on hover or focus, the viewer on click. */
export function SourceHover({
  engagementId,
  source,
  label,
  children,
  className,
}: {
  engagementId: string;
  source: SourceRef;
  label: string;
  children: ReactNode;
  className?: string;
}): JSX.Element {
  const [hover, setHover] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const timer = useRef<number | null>(null);
  const show = (): void => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      setHover(true);
    }, 250);
  };
  const hide = (): void => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    setHover(false);
  };
  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    },
    [],
  );
  const where =
    source.cell !== undefined
      ? `cell ${source.cell}`
      : source.page !== undefined
        ? `page ${String(source.page)}`
        : "the document";
  return (
    <>
      <Popover
        open={hover && !drawer}
        onOpenChange={(o) => {
          if (!o) setHover(false);
        }}
        align="start"
        width={SNIPPET_W + 28}
        label={`Where ${label} came from`}
        trigger={
          <button
            type="button"
            aria-label={`${label}: show where it came from (${where})`}
            onMouseEnter={show}
            onMouseLeave={hide}
            onFocus={show}
            onBlur={hide}
            onClick={() => {
              hide();
              setDrawer(true);
            }}
            className={`cursor-help rounded-[3px] text-left underline decoration-dotted decoration-ink-4 underline-offset-[3px] hover:bg-match-bg/40 ${className ?? ""}`}
          >
            {children}
          </button>
        }
      >
        <div className="flex flex-col gap-1.5">
          <p className="text-[11.5px] text-ink-3">{`From ${where} · click to open`}</p>
          <Snippet engagementId={engagementId} source={source} />
        </div>
      </Popover>
      {drawer && (
        <SourceDrawer
          engagementId={engagementId}
          itemId={source.itemId}
          versionId={source.versionId}
          cell={source.cell}
          page={source.page}
          highlights={
            source.box !== undefined && source.page !== undefined
              ? [{ page: source.page, box: source.box }]
              : undefined
          }
          findText={source.findText}
          title={`Where ${label} came from`}
          onClose={() => {
            setDrawer(false);
          }}
        />
      )}
    </>
  );
}
