// HandoffProvenanceBanner (T-06-T45; TXP-13 revision item 1, TXP-02 DF-08 / DV-11; DEC-5937): the
// 36 strip under a return's control bar when its TB came from a hand-off. The words are the
// server's landing read (`GET /v1/tax-returns/{id}/handoff`): "From FY2026 audit · Final TB ·
// handed off Nov 9", then "Open audit TB →" (only when the reader may open the source; absent,
// never disabled) and "Hand-off details →". A superseded hand-off says so in amber. A return with
// no hand-off draws nothing.
import type { TbHandoffLandingOut } from "@abacus/api-client";
import { returnHandoffOptions } from "@abacus/api-client/query";
import { Icon, cn, date } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { useNow } from "../../app-core/clock";

export const HANDOFF_BANNER_COPY = {
  label: "Hand-off provenance",
  from: (source: string, tb: string, on: string) => `From ${source} · ${tb} · handed off ${on}`,
  finalTb: "Final TB",
  lockedClose: "locked close TB",
  openSource: {
    audit_release: "Open audit TB →",
    review_release: "Open review TB →",
    close_lock: "Open close →",
  } as Record<string, string>,
  details: "Hand-off details →",
  superseded: "The source TB changed after release; a newer hand-off replaces this one.",
};

/** The banner's sentence from the landing read; null when the return has no hand-off. */
export function handoffLine(landing: TbHandoffLandingOut, now: Date): string | null {
  if (landing.handoff_id == null || landing.handed_off_at == null) return null;
  const tb =
    landing.source_kind === "close_lock"
      ? HANDOFF_BANNER_COPY.lockedClose
      : HANDOFF_BANNER_COPY.finalTb;
  return HANDOFF_BANNER_COPY.from(
    landing.source_label ?? "",
    tb,
    date(landing.handed_off_at, { now }),
  );
}

export interface HandoffProvenanceBannerProps {
  returnId: string;
  /** "Open audit TB →": the source's TB (AUD-06's Final layer; a close's CLS screen). */
  onOpenSource?: (landing: TbHandoffLandingOut) => void;
  /** "Hand-off details →": AUD-38 over its source. */
  onDetails?: (landing: TbHandoffLandingOut) => void;
  className?: string;
}

export function HandoffProvenanceBanner({
  returnId,
  onOpenSource,
  onDetails,
  className,
}: HandoffProvenanceBannerProps): JSX.Element | null {
  const now = useNow();
  const read = useQuery({
    ...returnHandoffOptions({ path: { return_id: returnId } }),
    retry: false,
  });
  const landing = read.data;
  if (landing === undefined) return null;
  const line = handoffLine(landing, now);
  if (line === null) return null;
  const kind = landing.source_kind ?? "audit_release";
  return (
    <div
      role="note"
      aria-label={HANDOFF_BANNER_COPY.label}
      data-handoff-banner={landing.superseded ? "superseded" : "current"}
      className={cn(
        "flex h-[36px] flex-none items-center gap-[8px] bg-band-hd px-[12px] text-[12.5px] text-ink-2 hairline-b",
        className,
      )}
    >
      <Icon name="link-2" size={13} className="text-ink-3" />
      <span className="min-w-0 flex-1 truncate">{line}</span>
      {landing.superseded ? (
        <span data-handoff-banner="warning" className="text-amber-ink">
          {HANDOFF_BANNER_COPY.superseded}
        </span>
      ) : null}
      {landing.source_link_allowed && onOpenSource !== undefined ? (
        <button
          type="button"
          className="text-ink hover:underline"
          onClick={() => {
            onOpenSource(landing);
          }}
        >
          {HANDOFF_BANNER_COPY.openSource[kind] ?? HANDOFF_BANNER_COPY.openSource.audit_release}
        </button>
      ) : null}
      {landing.source_link_allowed && onDetails !== undefined ? (
        <button
          type="button"
          className="text-ink hover:underline"
          onClick={() => {
            onDetails(landing);
          }}
        >
          {HANDOFF_BANNER_COPY.details}
        </button>
      ) : null}
    </div>
  );
}
