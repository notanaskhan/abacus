// C-01-T57 (DEC-5305): the pre-window live-path seams for the close engine. Each seam is a
// registration on a live screen that renders nothing new while its flag is off, and with its flag
// on lazy-imports the closes component that lands in the Sep 1 window (`./close-seam-slots`), so the live
// files change once, by the Thu Aug 24, 2028 train, and no in-window C-01 PR edits them again.
//
// - `closes.portal_requests`: the portal `/documents?period=` close-intake branch (POR-11), its
//   nav entry, and the POR-04 question variant e slot.
// - `closes.engine`: the close sources of `?ov=viewer` (SHL-08), `?ov=signoff` (SHL-12) and
//   `?ov=approve` (SHL-10).
import { type JSX, type ReactNode, Suspense, lazy } from "react";
import { useFlag } from "./flags";

export const CLOSES_ENGINE = "closes.engine";
export const CLOSES_PORTAL_REQUESTS = "closes.portal_requests";

/** The record types each overlay shows for a close. Anything else is not a close source. */
export const CLOSE_SOURCES = {
  viewer: ["close_statement", "close_upload", "close_policy"],
  signoff: ["reconciliation"],
  approve: ["close_aje", "recategorization"],
} as const;

export type CloseOverlay = keyof typeof CLOSE_SOURCES;

export function isCloseSource(overlay: CloseOverlay, targetType: string | undefined): boolean {
  return (
    targetType !== undefined && (CLOSE_SOURCES[overlay] as readonly string[]).includes(targetType)
  );
}

/** A close period in the portal documents route's search: `?period=2026-08`. */
export function closePeriod(search: string): string | undefined {
  const value = new URLSearchParams(search).get("period");
  return value !== null && /^[0-9]{4}-(0[1-9]|1[0-2])$/.test(value) ? value : undefined;
}

const CloseSourceSlot = lazy(async () => ({
  default: (await import("./close-seam-slots")).CloseSourceSlot,
}));
const PortalCloseIntakeSlot = lazy(async () => ({
  default: (await import("./close-seam-slots")).PortalCloseIntakeSlot,
}));
const QuestionVariantSlot = lazy(async () => ({
  default: (await import("./close-seam-slots")).QuestionVariantSlot,
}));

/** A close source on SHL-08, SHL-12 or SHL-10: with `closes.engine` off the overlay renders as it
 * does today (`children`); on, the in-window closes component takes the source. */
export function CloseSourceSeam(props: {
  overlay: CloseOverlay;
  targetType: string | undefined;
  targetId: string;
  children: ReactNode;
}): JSX.Element {
  const on = useFlag(CLOSES_ENGINE) === true;
  if (!on || !isCloseSource(props.overlay, props.targetType)) return <>{props.children}</>;
  return (
    <Suspense fallback={props.children}>
      <CloseSourceSlot
        overlay={props.overlay}
        targetType={props.targetType ?? ""}
        targetId={props.targetId}
      >
        {props.children}
      </CloseSourceSlot>
    </Suspense>
  );
}

/** The portal documents route's close-intake branch (POR-11): flag off, or no close period, the
 * documents area renders unchanged. */
export function PortalCloseIntakeSeam(props: {
  search: string;
  children: ReactNode;
}): JSX.Element {
  const on = useFlag(CLOSES_PORTAL_REQUESTS) === true;
  const period = closePeriod(props.search);
  if (!on || period === undefined) return <>{props.children}</>;
  return (
    <Suspense fallback={props.children}>
      <PortalCloseIntakeSlot period={period}>{props.children}</PortalCloseIntakeSlot>
    </Suspense>
  );
}

/** POR-04's question variant e (a close transaction question): flag off, the request renders as
 * it does today. */
export function QuestionVariantSeam(props: {
  questionId: string | undefined;
  children: ReactNode;
}): JSX.Element {
  const on = useFlag(CLOSES_PORTAL_REQUESTS) === true;
  if (!on || props.questionId === undefined) return <>{props.children}</>;
  return (
    <Suspense fallback={props.children}>
      <QuestionVariantSlot questionId={props.questionId}>{props.children}</QuestionVariantSlot>
    </Suspense>
  );
}

/** The portal nav's close entry (POR-11, under Documents), only while `closes.portal_requests`
 * is on; its wording lands with POR-11 in-window. */
export function useCloseNavEntry(): { href: string } | undefined {
  const on = useFlag(CLOSES_PORTAL_REQUESTS) === true;
  return on ? { href: "/documents?period=" } : undefined;
}
