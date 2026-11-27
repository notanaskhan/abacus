// F-08-T28 (DEC-6026): real paper at print geometry (F-08 §5 C1): US Letter 612 × 792 pt drawn
// at 0.82 (502 × 649) with 54 pt margins (44 at scale) on the #EFEEEB well. Document type only
// inside the page (Gelasio heads, Arimo 9.5 tabular body; fonts-doc.css in the editor chunk).
import type { JSX, ReactNode } from "react";
import { cn } from "../cn";

export const PAPER = { width: 612, height: 792, scale: 0.82, margin: 54 } as const;

export function PaperWell({ children }: { children: ReactNode }): JSX.Element {
  return (
    <div
      data-paper-well
      className="flex min-h-0 flex-1 flex-col items-center gap-[18px] overflow-auto bg-sunken p-[18px]"
    >
      {children}
    </div>
  );
}

export function Paper({
  page,
  children,
  watermark,
}: {
  page: number;
  children: ReactNode;
  watermark?: string;
}): JSX.Element {
  return (
    <article
      data-page={page}
      aria-label={`Page ${String(page)}`}
      className="relative h-[649px] w-[502px] flex-none bg-card p-[44px] font-doc text-[9.5px] text-doc-ink shadow-page"
    >
      {watermark !== undefined ? (
        <span
          aria-hidden
          data-watermark
          className="pointer-events-none absolute inset-0 flex -rotate-[30deg] items-center justify-center font-doc text-[72px] text-ink/[.06]"
        >
          {watermark}
        </span>
      ) : null}
      <div className={cn("relative h-full")}>{children}</div>
      <span className="absolute bottom-[18px] left-0 right-0 text-center text-[8.5px]">
        {page}
      </span>
    </article>
  );
}
