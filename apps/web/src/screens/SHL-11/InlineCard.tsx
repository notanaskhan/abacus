import type { DecisionCardOut } from "@abacus/api-client";
import { Button, Icon, Pill, cn } from "@abacus/ui";
import { type JSX, useId } from "react";
import { useOpenOverlay } from "../../app-core/open";
import { useDecisionCard } from "../../domain/review";
import { ov } from "../../routes/to";
import { COPY } from "./copy";

// SHL-11 e · the inline decision card (P-04-T52; the handoff's SHL-11 spec frame 5, SHL-11e): the
// 330 px card in the agent dock (SHL-13 state 4, TPL-02c) and its chat variant in the Workbench
// thread (P-09), over the same C3 read as the sheet. The question with its "?" chip, the options as
// compact read-only rows with the agent's recommendation as a tag (never a choice made), and one
// primary "Open decision" that opens the O3 sheet on the same card (`?ov=decision:<cardId>`). No
// one decides here: the reserved person decides in the sheet (INV-1, ADR-005).

export type DecisionInlineVariant = "dock" | "chat";

export interface DecisionInlineCardProps {
  cardId: string;
  /** `dock`: 330 wide in the agent dock. `chat`: the message column's width, in a P-09 thread. */
  variant?: DecisionInlineVariant;
  /** Opens the sheet; by default `?ov=decision:<cardId>` over the current route. */
  onOpen?: (cardId: string) => void;
  className?: string;
}

export function DecisionInlineCard({
  cardId,
  variant = "dock",
  onOpen,
  className,
}: DecisionInlineCardProps): JSX.Element {
  const query = useDecisionCard(cardId);
  const openOverlay = useOpenOverlay();
  const open = (): void => {
    if (onOpen === undefined) openOverlay(ov.SHL11(cardId));
    else onOpen(cardId);
  };
  return (
    <section
      data-decision-inline={variant}
      data-card={cardId}
      aria-busy={query.data === undefined && !query.isError ? true : undefined}
      className={cn(
        "flex flex-col overflow-hidden rounded-pane bg-card shadow-ask",
        variant === "dock" ? "w-[330px]" : "w-full max-w-[520px]",
        className,
      )}
    >
      {query.data === undefined ? (
        <p className="px-[14px] py-[12px] text-meta text-ink-3">
          {query.isError ? COPY.missing : COPY.loading}
        </p>
      ) : (
        <Body card={query.data} onOpen={open} />
      )}
    </section>
  );
}

function Body({ card, onOpen }: { card: DecisionCardOut; onOpen: () => void }): JSX.Element {
  const ids = useId();
  const decided = card.decision;
  const chosen = card.options.find((o) => o.key === decided?.option_key);
  return (
    <>
      <header
        id={`${ids}-q`}
        className="flex items-start gap-[10px] px-[14px] pt-[12px] pb-[10px] hairline-b"
      >
        <span
          aria-hidden
          className="mt-[1px] flex size-[19px] flex-none items-center justify-center rounded-full bg-nested text-meta font-medium text-ink-2 inset-shadow-hair"
        >
          {COPY.question}
        </span>
        <h3 className="flex-1 text-body font-medium">{card.question}</h3>
        {decided !== null && (
          <Pill variant="green" size="sm">
            {COPY.decided}
          </Pill>
        )}
      </header>
      <ul aria-labelledby={`${ids}-q`} className="flex flex-col hairline-b">
        {card.options.map((o) => {
          const picked = chosen?.key === o.key;
          return (
            <li
              key={o.key}
              data-option={o.key}
              {...(picked ? { "data-decided": "" } : {})}
              className="flex min-h-[42px] items-center gap-[10px] px-[14px]"
            >
              <span
                aria-hidden
                className={cn(
                  "flex size-[17px] flex-none items-center justify-center rounded-full",
                  picked ? "bg-green text-on-dark" : "bg-card inset-ring-rule",
                )}
              >
                {picked && <Icon name="check" size={12} />}
              </span>
              <span className={cn("flex-1 text-body", picked && "font-medium")}>
                {o.label}
                {picked && <span className="sr-only">{` · ${COPY.decided}`}</span>}
              </span>
              {o.recommended && decided === null && (
                <span className="flex flex-none items-center gap-[4px] rounded-full bg-nested px-[7px] py-[1px] text-meta text-ink-2">
                  <Icon name="sparkles" size={12} />
                  {COPY.inline.recommended}
                  <span className="sr-only">{COPY.inline.recommendedBy}</span>
                </span>
              )}
            </li>
          );
        })}
      </ul>
      <footer className="flex justify-end px-[12px] py-[10px]">
        <Button variant="primary" onClick={onOpen} aria-haspopup="dialog">
          {COPY.inline.open}
        </Button>
      </footer>
    </>
  );
}
