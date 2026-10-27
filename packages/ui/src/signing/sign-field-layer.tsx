import { type JSX, type RefObject, useImperativeHandle, useRef } from "react";
import { cn } from "../cn";
import type { SignFieldVM, SigningPage } from "./types";

// SignFieldLayer (F-06-T04; F-06.md §3 Stories 1.2, §5.5): the sign fields over one server-rendered
// page (E5 pipeline: an image, never a document to parse; ADR-052). Fields are outlined 1.5px
// espresso, radius 6, never yellow. Only fields whose `signerId` is the viewer's are actionable;
// another signer's field is text ("Dev Kapoor · signed electronically Sep 9, 2026"), never a
// control, so one spouse can never sign for the other (INV-4). The dark "Sign here" tab sits on
// the viewer's next open field and moves focus to it.

/** The page's drawn width on the well (T16: 680 inside the 816 well). */
export const PAGE_WIDTH_PX = 680;

export interface SignFieldLayerHandle {
  /** Focus the viewer's next open field after `fromId` (or the first); false when none is left. */
  focusNext: (fromId?: string) => boolean;
}

export interface SignFieldLayerProps {
  page: SigningPage;
  documentName: string;
  fields: readonly SignFieldVM[];
  viewerId: string | null;
  /** The field the "Sign here" tab marks: the viewer's next open field on the envelope. */
  nextOpenId: string | null;
  onSignField?: (fieldId: string) => void;
  handle?: RefObject<SignFieldLayerHandle | null>;
}

export function openFieldsOf(
  fields: readonly SignFieldVM[],
  viewerId: string | null,
): SignFieldVM[] {
  return fields.filter((f) => f.signerId === viewerId && f.filled === undefined);
}

export function SignFieldLayer({
  page,
  documentName,
  fields,
  viewerId,
  nextOpenId,
  onSignField,
  handle,
}: SignFieldLayerProps): JSX.Element {
  const scale = PAGE_WIDTH_PX / page.width_pt;
  const refs = useRef(new Map<string, HTMLButtonElement>());
  const open = openFieldsOf(fields, viewerId);
  useImperativeHandle(
    handle,
    () => ({
      focusNext(fromId) {
        const at = fromId === undefined ? -1 : open.findIndex((f) => f.id === fromId);
        const next = open[at + 1] ?? open[0];
        if (next === undefined) return false;
        refs.current.get(next.id)?.focus();
        return true;
      },
    }),
    [open],
  );
  return (
    <div
      data-signing="page"
      className="relative flex-none bg-card shadow-page"
      style={{ width: PAGE_WIDTH_PX, height: Math.round(page.height_pt * scale) }}
    >
      <img src={page.src} alt={page.alt} className="absolute inset-0 size-full select-none" />
      {fields
        .filter((f) => f.page === page.n)
        .map((field) => {
          const box = {
            left: field.rect.x * scale,
            top: field.rect.y * scale,
            width: field.rect.w * scale,
            height: field.rect.h * scale,
          };
          const mine = field.signerId === viewerId;
          if (!mine || field.filled !== undefined) {
            return (
              <span
                key={field.id}
                data-field={field.id}
                data-field-state={field.filled === undefined ? "other" : "filled"}
                className="absolute flex items-center px-[6px] font-doc text-cell text-doc-typed"
                style={box}
              >
                {field.filled ?? ""}
              </span>
            );
          }
          const name = `Sign here: ${field.label}, ${documentName}, page ${String(page.n)}`;
          return (
            <span key={field.id} className="absolute" style={box}>
              {field.id === nextOpenId && (
                // The tab is a pointer affordance only: the field itself carries the name and
                // the keyboard stop, so the tab is hidden from assistive technology.
                <button
                  type="button"
                  tabIndex={-1}
                  aria-hidden="true"
                  data-sign-here-tab=""
                  onClick={() => refs.current.get(field.id)?.focus()}
                  className="absolute top-1/2 right-full mr-[4px] inline-flex h-[22px] -translate-y-1/2 items-center rounded-sheet bg-espresso px-[8px] text-meta font-medium whitespace-nowrap text-on-dark"
                >
                  Sign here
                </button>
              )}
              <button
                type="button"
                ref={(el) => {
                  if (el === null) refs.current.delete(field.id);
                  else refs.current.set(field.id, el);
                }}
                data-field={field.id}
                data-field-state="open"
                aria-label={name}
                onClick={() => onSignField?.(field.id)}
                className={cn(
                  "size-full rounded-sheet outline-[1.5px] outline-espresso outline-solid",
                  "hover:bg-tonal-hover focus-visible:outline-[2.5px]",
                )}
              />
            </span>
          );
        })}
    </div>
  );
}
