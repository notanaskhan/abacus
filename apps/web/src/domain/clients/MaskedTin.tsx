import type { ClientEntityBriefOut } from "@abacus/api-client";
import { Button, Dialog, Fieldset, ValueRow, toast } from "@abacus/ui";
import { type JSX, useEffect, useRef, useState } from "react";
import { REVEAL_REASONS, type RevealReason, maskTin, useRevealTin } from "./record";

// A masked taxpayer id with "Reveal (logged)" (P-07 §3.1 Story 1.3; docs/screens/CLI-02.md). The
// button is absent unless the record allows `tin.reveal`. It opens a reason dialog (Dialog 400 in
// the handoff's kits; the dialog itself is undesigned, P-07 R-9), then shows the plain value for
// the server's `remask_after_seconds`, says so through a polite live region, re-masks and returns
// focus to the button. The plain value lives only in this component's state; it is never logged,
// cached or put in a query (ADR-031).

export const TIN_COPY = {
  reveal: "Reveal (logged)",
  title: "Reveal taxpayer ID",
  description: "The reveal is logged with your reason.",
  reason: "Reason",
  confirm: "Reveal",
  revealed: (seconds: number) => `Taxpayer ID shown for ${String(seconds)} seconds.`,
  remasked: "Taxpayer ID masked again.",
  failed: "Couldn’t reveal the taxpayer ID.",
  reasons: {
    prepare_return: "Prepare the return",
    review_return: "Review the return",
    file_or_correct_filing: "File or correct a filing",
    respond_to_notice: "Respond to a notice",
    verify_identity: "Verify identity",
  } satisfies Record<RevealReason, string>,
} as const;

export interface MaskedTinProps {
  entity: ClientEntityBriefOut;
  /** The record allows `tin.reveal` for this person. */
  canReveal: boolean;
  /** Shown after the masked value ("(Claire)"). */
  suffix?: string;
}

export function MaskedTin({ entity, canReveal, suffix }: MaskedTinProps): JSX.Element | null {
  const masked = entity.tin == null ? null : maskTin(entity.tin);
  const reveal = useRevealTin();
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState<RevealReason>("prepare_return");
  const [plain, setPlain] = useState<string | null>(null);
  const [said, setSaid] = useState("");
  const button = useRef<HTMLButtonElement>(null);

  const shown = useRef(false);
  useEffect(() => {
    if (plain !== null) {
      shown.current = true;
      return;
    }
    if (!shown.current) return;
    shown.current = false;
    setSaid(TIN_COPY.remasked);
    button.current?.focus();
  }, [plain]);

  if (masked === null) return null;

  const run = async (): Promise<void> => {
    try {
      const out = await reveal.mutateAsync({
        path: { entity_id: entity.id },
        body: { reason },
      });
      const seconds = out.remask_after_seconds ?? 10;
      setAsking(false);
      setPlain(out.value);
      setSaid(TIN_COPY.revealed(seconds));
      window.setTimeout(() => {
        setPlain(null);
      }, seconds * 1000);
    } catch {
      toast.show({ kind: "error", text: TIN_COPY.failed });
    }
  };

  return (
    <span className="inline-flex min-w-0 items-center gap-[8px]">
      <span data-tin={plain === null ? "masked" : "revealed"} className="tabular-nums text-ink">
        {plain ?? masked}
        {suffix === undefined ? "" : ` ${suffix}`}
      </span>
      {canReveal && (
        <button
          ref={button}
          type="button"
          disabled={plain !== null}
          onClick={() => {
            setAsking(true);
          }}
          className="text-cell text-ink-3 hover:text-ink-2 disabled:text-ink-4"
        >
          {TIN_COPY.reveal}
        </button>
      )}
      <span role="status" aria-live="polite" className="sr-only">
        {said}
      </span>
      <Dialog
        open={asking}
        onOpenChange={setAsking}
        size="sm"
        title={TIN_COPY.title}
        description={TIN_COPY.description}
        action={
          <Button variant="primary" loading={reveal.isPending} onClick={() => void run()}>
            {TIN_COPY.confirm}
          </Button>
        }
      >
        <Fieldset flush>
          <ValueRow
            kind="select"
            label={TIN_COPY.reason}
            value={reason}
            options={REVEAL_REASONS.map((value) => ({ value, label: TIN_COPY.reasons[value] }))}
            onChange={(v) => {
              const found = REVEAL_REASONS.find((r) => r === v);
              if (found !== undefined) setReason(found);
            }}
          />
        </Fieldset>
      </Dialog>
    </span>
  );
}
