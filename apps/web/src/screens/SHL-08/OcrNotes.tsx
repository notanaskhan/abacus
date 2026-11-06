import type { ViewerPageOut } from "@abacus/api-client";
import { extractedFieldsOptions, textRetryMutation } from "@abacus/api-client/query";
import { Button, Pill } from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { COPY } from "./copy";

// SHL-08's OCR additions (P-11-T31; P-11 F7, F8): how a page's text was read, the boxes code read
// with less confidence, and why OCR didn't run. Low confidence is said in words and an outline, not
// colour alone, and announced politely. A retry is a person's; the server refuses anything else.
// A TIN box's value never reaches here: `mask_token` only (P-11-T27).

type Refusal = NonNullable<NonNullable<ViewerPageOut["ocr"]>["refused_reason"]>;

export interface OcrNotesProps {
  versionId: string;
  pages: readonly ViewerPageOut[];
  /** The page in view (1-based). */
  page: number;
  /** Whether this viewer offers "Read text again". */
  canRetry?: boolean;
}

function sourceWord(page: ViewerPageOut): string | null {
  if (page.text_source === "ocr") {
    return page.ocr?.mean_confidence == null
      ? COPY.ocr.read
      : COPY.ocr.readConfidence(Math.round(page.ocr.mean_confidence * 100));
  }
  if (page.text_source === "text_layer") return COPY.ocr.textLayer;
  if (page.text_source === "none") return COPY.ocr.none;
  return null;
}

export function OcrNotes({
  versionId,
  pages,
  page,
  canRetry = false,
}: OcrNotesProps): JSX.Element | null {
  const current = pages.find((p) => p.n === page);
  const fields = useQuery({
    ...extractedFieldsOptions({ path: { version_id: versionId } }),
    enabled: current?.text_source === "ocr",
    retry: false,
  });
  const retry = useMutation({ ...textRetryMutation() });
  if (current === undefined) return null;
  const word = sourceWord(current);
  const refused: Refusal | null = current.ocr?.refused_reason ?? null;
  const low = (fields.data?.items ?? []).filter((f) => f.page === page && f.low_confidence);
  if (word === null && refused === null && low.length === 0) return null;
  return (
    <div
      data-ocr-notes
      className="flex flex-col gap-[4px] px-[12px] py-[6px] text-[11.5px] text-ink-3"
    >
      {word !== null && <p data-text-source={current.text_source}>{word}</p>}
      {refused !== null && (
        <p data-ocr-refused={refused} role="status">
          {COPY.ocr.refused[refused]}
          {canRetry && (
            <Button
              variant="link"
              size="xs"
              className="ml-[6px]"
              disabled={retry.isPending}
              onClick={() => {
                retry.mutate({ path: { version_id: versionId } });
              }}
            >
              {COPY.ocr.retry}
            </Button>
          )}
        </p>
      )}
      {low.length > 0 && (
        <ul aria-live="polite" aria-label={COPY.ocr.lowLabel(low.length)} data-low-confidence>
          {low.map((f) => (
            <li
              key={f.field_key}
              data-field={f.match_id}
              className="mt-[2px] flex items-center gap-[6px] rounded-[4px] border border-dashed border-ink-3 px-[6px] py-[2px]"
            >
              <span>{f.label}</span>
              <span>{f.mask_token ?? f.value_text}</span>
              <Pill size="micro" variant="amber">
                {COPY.ocr.low}
              </Pill>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
