// The evidence text view (P-03-T15; DEC-369, Ayush 2026-10-26): what a reader the server gives the
// `text` view (an offshore member, until OCR, P-11) sees instead of page images, in SHL-08 and the
// cockpit dock alike: each page's masked text, a muted line on a page with content no scan read,
// and a workbook's masked cells. Plain text only: no markup is ever made from it.

import type { ViewerTextOut } from "@abacus/api-client";
import type { JSX } from "react";

/** `unread` is P-03 AC4.8's line; the note, the empty line, loading and the withheld sheet line
 * are new copy, pending the design file (DEC-369). */
export const TEXT_VIEW = {
  note: "Page images aren't shown for your access. This is the document's text with personal data masked.",
  page: (n: number): string => `p. ${String(n)}`,
  unread: "Scanned page · personal data isn't detected automatically yet",
  empty: "No text on this page",
  loading: "Loading text…",
  sheetWithheld: "This sheet isn't shown for your access.",
} as const;

export interface MaskedTextViewProps {
  text: ViewerTextOut | undefined;
  width: number;
}

export function MaskedTextView({ text, width }: MaskedTextViewProps): JSX.Element {
  return (
    <section data-text-view="" className="flex flex-col gap-[12px] p-[12px]" style={{ width }}>
      <p className="text-meta text-ink-3">{TEXT_VIEW.note}</p>
      {text === undefined ? (
        <p className="text-meta text-ink-3">{TEXT_VIEW.loading}</p>
      ) : (
        <>
          {text.items.map((page) => (
            <article
              key={page.page}
              data-text-page={page.page}
              className="flex flex-col gap-[4px]"
            >
              <h3 className="text-meta text-ink-2">{TEXT_VIEW.page(page.page)}</h3>
              {page.unread ? (
                <p data-unread="" className="text-meta text-ink-3">
                  {TEXT_VIEW.unread}
                </p>
              ) : null}
              <p className="whitespace-pre-wrap text-body text-ink">
                {page.text === "" ? TEXT_VIEW.empty : page.text}
              </p>
            </article>
          ))}
          {text.sheets.map((sheet) => (
            <article
              key={sheet.name}
              data-text-sheet={sheet.name}
              className="flex flex-col gap-[4px]"
            >
              <h3 className="text-meta text-ink-2">{sheet.name}</h3>
              {sheet.withheld === true ? (
                <p data-withheld="" className="text-meta text-ink-3">
                  {TEXT_VIEW.sheetWithheld}
                </p>
              ) : null}
              {sheet.rows.map((row, i) => (
                <p key={String(i)} className="text-body text-ink">
                  {row.join(" · ")}
                </p>
              ))}
            </article>
          ))}
        </>
      )}
    </section>
  );
}
