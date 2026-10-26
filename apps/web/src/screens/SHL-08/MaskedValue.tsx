// SHL-08c masked PII (P-03-T20; P-03 F4, AC4.4–AC4.6; C4 §3.5): the logged reveal on the source
// viewer. One explicit click on "Reveal (logged)" posts `POST …/pii-reveals {region_id}` through
// the generated SDK function, never React Query: the answer is in no query or mutation cache. The
// clear value lives only in this hook's state and is dropped on Hide, after `expires_in` (30 s),
// when the viewer moves to another version, and on unmount; it never reaches storage or the URL.
// While a value shows, the line under the toolbar reads "Revealed by Samuel Ito · 9:31 AM · logged
// to the audit trail" and the chip reads Hide. A stale MFA answers 403 `mfa_required` and opens the
// shell's step-up words (`RevealStepUp`, as `ConfirmItsYou`); any other refusal reveals nothing.

import { revealPii } from "@abacus/api-client";
import { DEFAULT_TZ, type RevealSlot, type RevealedValue, time } from "@abacus/ui";
import { type JSX, useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "../../app-core/session";
import { COPY } from "./copy";

/** The server's 403 that asks for a step-up (DEC-370: only this refusal carries a reason). */
export function needsMfa(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  const facts = (error as { facts?: { reason?: unknown } }).facts;
  return facts?.reason === "mfa_required";
}

export interface MaskedReveal {
  /** The E5 shell's reveal slot (undefined when the reader may not reveal: no chip at all). */
  slot: RevealSlot | undefined;
  /** "Revealed by … · logged to the audit trail" while a value shows. */
  line: string | null;
  /** The polite announcement: "Revealed for 30 seconds" / "Hidden again". */
  announce: string;
  stepUp: boolean;
  setStepUp: (open: boolean) => void;
}

export function useMaskedReveal(versionId: string, allowed: boolean): MaskedReveal {
  const session = useSession();
  const tz = session.tz ?? DEFAULT_TZ;
  const [revealed, setRevealed] = useState<Record<string, RevealedValue>>({});
  const [announce, setAnnounce] = useState("");
  const [stepUp, setStepUp] = useState(false);
  const timers = useRef<Map<string, number>>(new Map());

  const hide = useCallback((maskId: string, words: string = COPY.reveal.hidden): void => {
    const timer = timers.current.get(maskId);
    if (timer !== undefined) window.clearTimeout(timer);
    timers.current.delete(maskId);
    setRevealed((was) =>
      maskId in was
        ? Object.fromEntries(Object.entries(was).filter(([id]) => id !== maskId))
        : was,
    );
    setAnnounce(words);
  }, []);

  // Another version, or the viewer closes: every revealed value goes with it.
  useEffect(() => {
    const live = timers.current;
    return () => {
      for (const t of live.values()) window.clearTimeout(t);
      live.clear();
      setRevealed({});
    };
  }, [versionId]);

  const onReveal = (maskId: string): void => {
    void revealPii({
      path: { version_id: versionId },
      body: { region_id: maskId },
      throwOnError: true,
    }).then(
      ({ data }) => {
        setRevealed((was) => ({
          ...was,
          [maskId]: {
            value: data.value,
            note: COPY.reveal.line(data.revealed_by, time(data.revealed_at, { tz })),
          },
        }));
        setAnnounce(COPY.reveal.shown(data.expires_in));
        timers.current.set(
          maskId,
          window.setTimeout(() => {
            hide(maskId);
          }, data.expires_in * 1000),
        );
      },
      (error: unknown) => {
        if (needsMfa(error)) setStepUp(true);
      },
    );
  };

  const notes = Object.values(revealed);
  return {
    slot: allowed
      ? {
          allowed: true,
          onReveal,
          revealed,
          label: COPY.reveal.label,
          onHide: (id) => {
            hide(id);
          },
          hideLabel: COPY.reveal.hide,
        }
      : undefined,
    line: notes.length > 0 ? (notes[notes.length - 1]?.note ?? null) : null,
    announce,
    stepUp,
    setStepUp,
  };
}

/** The line under the toolbar and the polite live region (P-03 §5.6). */
export function RevealLine({
  line,
  announce,
}: {
  line: string | null;
  announce: string;
}): JSX.Element {
  return (
    <>
      {line !== null && (
        <p data-reveal-line="" className="flex-none px-[16px] pt-[6px] text-meta text-ink-3">
          {line}
        </p>
      )}
      <span aria-live="polite" className="sr-only">
        {announce}
      </span>
    </>
  );
}
