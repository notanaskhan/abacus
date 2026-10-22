import {
  inboxPreviewPage,
  type PreviewOut,
  uploadPreviewPage,
  versionPreviewPage,
} from "@abacus/api-client";
import {
  inboxPreviewOptions,
  uploadPreviewOptions,
  versionPreviewOptions,
} from "@abacus/api-client/query";
import { Alert, Button, Skeleton, Table, Td, Th } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useEffect, useState } from "react";
import { isForbidden } from "../shell/mfa";

export type PreviewSource =
  | { kind: "upload"; engagementId: string; itemId: string; versionId: string }
  | { kind: "inbox"; engagementId: string; fileId: string }
  // TASK-334: a version by itself, for screens that don't know its request.
  | { kind: "version"; engagementId: string; versionId: string };

/** Where a value was printed (TASK-334): a page and a box as fractions of the page. */
export type Box = [number, number, number, number];
export type Highlight = { page: number; box: Box };

/** The first printed line on a page that contains the text (case and spacing ignored). */
export function findLine(
  lines: { text: string; box: Box }[] | undefined,
  text: string,
): Box | null {
  const want = text.toLowerCase().replace(/\s+/g, " ").trim();
  if (want === "" || lines === undefined) return null;
  const hit = lines.find((l) => l.text.toLowerCase().replace(/\s+/g, " ").includes(want));
  return hit?.box ?? null;
}

const REASONS: Record<string, string> = {
  encrypted: "This file is password-protected, so it can't be previewed.",
  damaged: "This file couldn't be opened for a preview.",
  too_large: "This image is too large to preview.",
  not_previewable: "Preview isn't available for this kind of file.",
  crashed: "This file couldn't be opened for a preview.",
  empty: "This file has no pages.",
};

/** "C9" (or "Sheet1!C9") as 0-based column and 1-based sheet row; null if it isn't a cell. */
export function parseCell(ref: string): { col: number; row: number } | null {
  const m = /^(?:.*!)?\$?([A-Z]{1,3})\$?(\d{1,7})$/.exec(ref.trim().toUpperCase());
  if (m === null) return null;
  let col = 0;
  for (const ch of m[1] ?? "") col = col * 26 + (ch.charCodeAt(0) - 64);
  return { col: col - 1, row: Number(m[2]) };
}

// A figure, aligned right as in a ledger (TASK-095); the text itself is never changed.
const NUMERIC = /^\(?-?[\d,]+(\.\d+)?\)?$/;

function usePreview(source: PreviewSource) {
  const pending = (data: PreviewOut | undefined): number | false =>
    data?.kind === "pending" ? 3000 : false;
  const upload = useQuery({
    ...uploadPreviewOptions({
      path: {
        engagement_id: source.engagementId,
        item_id: source.kind === "upload" ? source.itemId : "",
        version_id: source.kind === "upload" ? source.versionId : "",
      },
    }),
    enabled: source.kind === "upload",
    retry: false,
    refetchInterval: (query) => pending(query.state.data),
  });
  const inbox = useQuery({
    ...inboxPreviewOptions({
      path: {
        engagement_id: source.engagementId,
        file_id: source.kind === "inbox" ? source.fileId : "",
      },
    }),
    enabled: source.kind === "inbox",
    retry: false,
    refetchInterval: (query) => pending(query.state.data),
  });
  const version = useQuery({
    ...versionPreviewOptions({
      path: {
        engagement_id: source.engagementId,
        version_id: source.kind === "version" ? source.versionId : "",
      },
    }),
    enabled: source.kind === "version",
    retry: false,
    refetchInterval: (query) => pending(query.state.data),
  });
  return source.kind === "upload" ? upload : source.kind === "version" ? version : inbox;
}

export { usePreview };

export async function pageBlob(source: PreviewSource, page: number): Promise<Blob> {
  if (source.kind === "upload") {
    const { data } = await uploadPreviewPage({
      path: {
        engagement_id: source.engagementId,
        item_id: source.itemId,
        version_id: source.versionId,
        page_no: page,
      },
      parseAs: "blob",
      throwOnError: true,
    });
    return data;
  }
  if (source.kind === "version") {
    const { data } = await versionPreviewPage({
      path: { engagement_id: source.engagementId, version_id: source.versionId, page_no: page },
      parseAs: "blob",
      throwOnError: true,
    });
    return data;
  }
  const { data } = await inboxPreviewPage({
    path: { engagement_id: source.engagementId, file_id: source.fileId, page_no: page },
    parseAs: "blob",
    throwOnError: true,
  });
  return data;
}

export function PageImage({
  source,
  page,
  boxes = [],
}: {
  source: PreviewSource;
  page: number;
  boxes?: Box[];
}): JSX.Element {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let current: string | null = null;
    let live = true;
    setUrl(null);
    setFailed(false);
    pageBlob(source, page)
      .then((blob) => {
        if (!live) return;
        current = URL.createObjectURL(blob);
        setUrl(current);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
      if (current !== null) URL.revokeObjectURL(current);
    };
  }, [source, page]);
  if (failed) return <p className="text-body text-danger">This page couldn&apos;t be loaded.</p>;
  if (url === null) return <Skeleton className="h-96" />;
  return (
    <div className="relative">
      <img
        src={url}
        alt={`Page ${String(page)}`}
        className="block w-full rounded-[var(--radius-control)] border border-line bg-surface"
      />
      {boxes.map((b, i) => (
        <span
          key={i}
          data-highlight="true"
          aria-hidden="true"
          className="pointer-events-none absolute rounded-[3px] bg-match-bg/60 inset-shadow-[inset_0_0_0_1.5px_var(--color-match-line)]"
          style={{
            left: `${String(Math.max(b[0] * 100 - 0.6, 0))}%`,
            top: `${String(Math.max(b[1] * 100 - 0.4, 0))}%`,
            width: `${String((b[2] - b[0]) * 100 + 1.2)}%`,
            height: `${String((b[3] - b[1]) * 100 + 0.8)}%`,
          }}
        />
      ))}
    </div>
  );
}

/** SPEC-029 AC-12 (TASK-056): evidence in the browser, from server-made pages and extracted
 * values; the raw file is never rendered here. */
export function EvidencePreview({
  source,
  openAtPage,
  highlightCell,
  highlights,
  findText,
}: {
  source: PreviewSource;
  // SPEC-030 (TASK-059): an AI flag's quote opens the preview at its page.
  openAtPage?: number | undefined;
  // TASK-110: a citation's cell, highlighted in the source colours and scrolled into view.
  highlightCell?: string | undefined;
  // TASK-334: boxes on pages where values were printed, outlined on the page image.
  highlights?: Highlight[] | undefined;
  // TASK-334: a quote to find among the open page's printed lines and outline.
  findText?: string | undefined;
}): JSX.Element {
  const preview = usePreview(source);
  const [page, setPage] = useState(openAtPage ?? 1);
  useEffect(() => {
    if (openAtPage !== undefined) setPage(openAtPage);
  }, [openAtPage]);
  const [sheet, setSheet] = useState(0);
  const target = highlightCell !== undefined ? parseCell(highlightCell) : null;
  useEffect(() => {
    if (target === null) return;
    const id = window.setTimeout(() => {
      document
        .querySelector(`[data-cell="${String(target.row)}-${String(target.col)}"]`)
        ?.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
    }, 150);
    return () => {
      window.clearTimeout(id);
    };
  }, [target?.row, target?.col, preview.data]);

  const highlightKey = JSON.stringify([highlights, findText, page]);
  useEffect(() => {
    if (highlights === undefined && findText === undefined) return;
    const id = window.setTimeout(() => {
      document
        .querySelector('[data-highlight="true"]')
        ?.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 600);
    return () => {
      window.clearTimeout(id);
    };
  }, [highlightKey, preview.data]);

  if (preview.isPending) return <Skeleton className="h-64" />;
  if (preview.isError) {
    return isForbidden(preview.error) ? (
      <p className="text-body text-muted">You can&apos;t preview this file.</p>
    ) : (
      <Alert title="Couldn't load the preview">Try again, or download the file instead.</Alert>
    );
  }
  const data = preview.data;
  if (data.kind === "pending") {
    return <p className="text-body text-muted">Preparing the preview…</p>;
  }
  if (data.kind === "none") {
    return (
      <p className="text-body text-muted">
        {REASONS[data.reason ?? ""] ?? "Preview isn't available."} Download it instead.
      </p>
    );
  }
  if (data.kind === "table") {
    if (data.sheets.length === 0) {
      return <p className="text-body text-muted">This spreadsheet is empty.</p>;
    }
    const shown = data.sheets[Math.min(sheet, data.sheets.length - 1)];
    const rows = shown?.rows ?? [];
    return (
      <div className="flex flex-col gap-2">
        {data.sheets.length > 1 && (
          <div role="tablist" aria-label="Sheets" className="flex flex-wrap gap-1">
            {data.sheets.map((s, n) => (
              <Button
                key={`${s.name}-${String(n)}`}
                size="sm"
                role="tab"
                aria-selected={n === sheet}
                variant={n === sheet ? "primary" : "ghost"}
                onClick={() => {
                  setSheet(n);
                }}
              >
                {s.name || `Sheet ${String(n + 1)}`}
              </Button>
            ))}
          </div>
        )}
        <div className="max-h-[32rem] overflow-auto">
          {/* Cells are React text: a leading = + - @ is shown as typed, never evaluated. */}
          <Table aria-label="Spreadsheet preview">
            <thead className="sticky top-0 bg-surface">
              <tr>
                {(rows[0] ?? []).map((cell, n) => (
                  <Th
                    key={n}
                    data-cell={`1-${String(n)}`}
                    className={
                      target?.row === 1 && target.col === n
                        ? "bg-match-bg text-match-ink inset-shadow-[inset_0_0_0_1.5px_var(--color-match-line)]"
                        : undefined
                    }
                  >
                    {cell}
                  </Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(1).map((row, r) => (
                <tr key={r}>
                  {row.map((cell, n) => (
                    <Td
                      key={n}
                      data-cell={`${String(r + 2)}-${String(n)}`}
                      aria-current={target?.row === r + 2 && target.col === n ? "true" : undefined}
                      className={`${
                        NUMERIC.test(cell) ? "text-right tabular-nums" : "whitespace-pre-wrap"
                      } ${
                        target?.row === r + 2 && target.col === n
                          ? "bg-match-bg font-medium text-match-ink inset-shadow-[inset_0_0_0_1.5px_var(--color-match-line)]"
                          : ""
                      }`}
                    >
                      {cell}
                    </Td>
                  ))}
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
        {data.truncated && (
          <p className="text-meta text-muted">
            Showing the first rows only. Download for the rest.
          </p>
        )}
      </div>
    );
  }
  const count = Math.max(data.page_count, 1);
  const shownPage = Math.min(page, count);
  const pageLines = (data.page_lines ?? [])[shownPage - 1] as
    { text: string; box: Box }[] | undefined;
  const found = findText !== undefined ? findLine(pageLines, findText) : null;
  const boxes: Box[] = [
    ...(highlights ?? []).filter((h) => h.page === shownPage).map((h) => h.box),
    ...(found !== null ? [found] : []),
  ];
  return (
    <div className="flex flex-col gap-2">
      <PageImage source={source} page={shownPage} boxes={boxes} />
      {count > 1 && (
        <div className="flex items-center gap-2 text-body">
          <Button
            size="sm"
            variant="secondary"
            disabled={page <= 1}
            onClick={() => {
              setPage((p) => p - 1);
            }}
          >
            Previous page
          </Button>
          <span className="tabular-nums">
            Page {page} of {count}
          </span>
          <Button
            size="sm"
            variant="secondary"
            disabled={page >= count}
            onClick={() => {
              setPage((p) => p + 1);
            }}
          >
            Next page
          </Button>
        </div>
      )}
      {data.truncated && (
        <p className="text-meta text-muted">
          Showing the first pages only. Download for the rest.
        </p>
      )}
    </div>
  );
}
