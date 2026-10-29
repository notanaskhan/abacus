import { type JSX, useId } from "react";
import { cn } from "../cn";
import { Icon } from "../icons";

// TPL-19 frames 5 and 6 (F-06-T11; DEC-45 v1 capture): the phone's upload action sheet, opened from
// a mobile request card's "Upload…" or the DropZone card, and the Review & assign sheet the camera
// hands to. Native inputs only: "Take a photo" is `<input type="file" accept="image/*"
// capture="environment">`, so the phone's own camera app takes the pages; there is no in-browser
// viewfinder in v1 (frames 3, 4 and 8 and the permission-off variant are R-03's, DEC-97).
// Stitching the pages into one PDF is server-side (R-03); this sheet shows what it is given.
// White-labelled: no product mark. Every target is at least 44 high.

/** Where the files came from: the camera or the file picker. */
export type CaptureSource = "camera" | "file";

export interface UploadActionSheetProps {
  /** The request the sheet uploads to, by title for the accessible name; null for the DropZone. */
  request: string | null;
  onFiles: (files: readonly File[], source: CaptureSource) => void;
  onClose: () => void;
  /** Accepted types for "Choose a file" (the binder's `accept`). */
  accept?: string;
}

const ROW =
  "flex h-[52px] w-full cursor-pointer items-center gap-[12px] px-[16px] text-section hairline-b last:shadow-none focus-within:bg-band-hd hover:bg-band-hd";

/** The bottom action sheet over the phone: Take a photo · Choose a file. */
export function UploadActionSheet({
  request,
  onFiles,
  onClose,
  accept,
}: UploadActionSheetProps): JSX.Element {
  const id = useId();
  const pick =
    (source: CaptureSource) =>
    (event: { currentTarget: HTMLInputElement }): void => {
      const files = [...(event.currentTarget.files ?? [])];
      event.currentTarget.value = "";
      if (files.length > 0) onFiles(files, source);
    };
  return (
    <div data-capture="action-sheet" className="absolute inset-0 z-(--z-menu) flex flex-col justify-end">
      <div aria-hidden="true" className="flex-1 bg-espresso/30" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={request === null ? "Upload" : `Upload… ${request}`}
        className="rounded-t-[20px] bg-card pt-[8px] pb-[20px] shadow-sheet"
      >
        <label htmlFor={`${id}-camera`} className={ROW}>
          <Icon name="camera" size={18} className="text-ink-2" />
          Take a photo
          <input
            id={`${id}-camera`}
            data-capture-input="camera"
            type="file"
            accept="image/*"
            capture="environment"
            multiple
            className="sr-only"
            onChange={pick("camera")}
          />
        </label>
        <label htmlFor={`${id}-file`} className={ROW}>
          <Icon name="file-up" size={18} className="text-ink-2" />
          Choose a file
          <input
            id={`${id}-file`}
            data-capture-input="file"
            type="file"
            multiple
            {...(accept === undefined ? {} : { accept })}
            className="sr-only"
            onChange={pick("file")}
          />
        </label>
        <button
          type="button"
          onClick={onClose}
          className="mt-[6px] flex h-[48px] w-full items-center justify-center text-section text-ink-2"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export interface CapturedPage {
  /** 1-based. */
  n: number;
  /** An object URL of the photo; without one the preview draws a blank page. */
  src?: string;
}

export interface RequestChoice {
  id: string;
  title: string;
}

export interface ReviewAssignSheetProps {
  pages: readonly CapturedPage[];
  /** The stitched file as the server names it ("Claire_Feld_2025_1095-C_MercerHill.pdf"). */
  fileName: string;
  /** Formatted by the caller ("3.1 MB"). */
  size: string;
  /** The photos it was combined from. */
  sources: readonly string[];
  /** The open requests the file can go to; "Something else" is always last. */
  requests: readonly RequestChoice[];
  /** The chosen request's id; null is "Something else". */
  selected: string | null;
  onSelect: (id: string | null) => void;
  onRetake: (page: number) => void;
  onAddPage: () => void;
  onUpload: () => void;
  busy?: boolean;
}

const SOMETHING_ELSE = "";

/** Frame 5: the white sheet over the camera with the pages, the file, the request and Upload. */
export function ReviewAssignSheet({
  pages,
  fileName,
  size,
  sources,
  requests,
  selected,
  onSelect,
  onRetake,
  onAddPage,
  onUpload,
  busy = false,
}: ReviewAssignSheetProps): JSX.Element {
  const id = useId();
  const last = pages.at(-1)?.n ?? 1;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Review & assign"
      data-capture="review-sheet"
      className="absolute inset-x-0 bottom-0 z-(--z-menu) flex flex-col gap-[14px] rounded-t-[20px] bg-card px-[16px] pt-[18px] pb-[20px] shadow-sheet"
    >
      <div className="flex justify-center gap-[12px]">
        {pages.map((p) => (
          <figure key={p.n} className="flex flex-col items-center gap-[6px]">
            <span
              data-page={p.n}
              className="block h-[194px] w-[150px] overflow-hidden bg-card shadow-page"
            >
              {p.src !== undefined && (
                <img src={p.src} alt={`Page ${String(p.n)}`} className="size-full object-cover" />
              )}
            </span>
            <figcaption className="text-meta text-ink-3">{p.n}</figcaption>
          </figure>
        ))}
      </div>
      <div className="flex flex-col gap-[3px]">
        <span className="text-body font-medium [overflow-wrap:anywhere]">
          {`${fileName} · ${String(pages.length)} ${pages.length === 1 ? "page" : "pages"} · ${size}`}
        </span>
        <span className="text-meta text-ink-3 [overflow-wrap:anywhere]">
          {`Combined from ${sources.join(" and ")}`}
        </span>
      </div>
      <div className="flex items-center gap-[16px]">
        <button
          type="button"
          onClick={() => {
            onRetake(last);
          }}
          className="inline-flex h-[44px] items-center text-body font-medium text-espresso"
        >
          {`Retake page ${String(last)}`}
        </button>
        <button
          type="button"
          onClick={onAddPage}
          className="inline-flex h-[44px] items-center text-body font-medium text-espresso"
        >
          Add a page
        </button>
      </div>
      <label
        htmlFor={`${id}-request`}
        className="relative flex min-h-[52px] items-center gap-[10px] rounded-nested bg-nested px-[14px]"
      >
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-meta text-ink-3">Add to request</span>
          <span className="truncate text-body">
            {requests.find((r) => r.id === selected)?.title ?? "Something else"}
          </span>
        </span>
        <Icon name="chevrons-up-down" size={14} className="text-ink-3" />
        <select
          id={`${id}-request`}
          aria-label="Add to request"
          value={selected ?? SOMETHING_ELSE}
          onChange={(event) => {
            onSelect(event.currentTarget.value === SOMETHING_ELSE ? null : event.currentTarget.value);
          }}
          className="absolute inset-0 cursor-pointer opacity-0"
        >
          {requests.map((r) => (
            <option key={r.id} value={r.id}>
              {r.title}
            </option>
          ))}
          <option value={SOMETHING_ELSE}>Something else</option>
        </select>
      </label>
      <button
        type="button"
        onClick={onUpload}
        disabled={busy}
        aria-busy={busy}
        className={cn(
          "flex h-[48px] w-full items-center justify-center rounded-pill bg-espresso text-section font-medium text-on-dark shadow-cta",
          busy && "opacity-60",
        )}
      >
        Upload
      </button>
    </div>
  );
}

/** Frames 3, 4 and 8 and the permission-off variant: R-03's (DEC-97), drawn as a placeholder. */
export function DeferredFrame(): JSX.Element {
  return (
    <div
      data-capture="deferred"
      className="flex h-[844px] w-[390px] flex-none flex-col items-center justify-center rounded-phone bg-nested text-center shadow-e1"
    >
      <span className="text-section font-medium text-ink-2">Deferred (DEC-97)</span>
    </div>
  );
}
