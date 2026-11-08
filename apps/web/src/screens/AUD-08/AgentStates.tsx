import type { CoverageOut, LinkTargetOut, LinkageOut } from "@abacus/api-client";
import { riskCoverageMutation } from "@abacus/api-client/query";
import { Button, Menu, PaneAction, Pill, cn } from "@abacus/ui";
import { useMutation } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

// AUD-08 c, e, f and g (A-04-T26; the handoff spec and its R2 revision):
//   c  the Linkage tab: risks × responses with 13 px dots (linked filled, suggested outlined);
//      R8 reads "Suggested" until a person links it, and "Link EBP-03…" opens the link picker;
//   e  "Revising after Internal Control…" with skeleton rows while the re-draft run is running;
//   f  a drafted value (C-31): ink-2 with the atom marker until a person adopts it, with the
//      Adopt · Edit · Discard footer (never auto-adopted);
//   g  "Identify risks with agent": code's coverage result in an O1 under the control row, with
//      "Open R8 →". With workpapers.drafting off every agent control is absent and the control
//      reads "Check coverage", showing the same code result without agent voice.

/** The link picker's targets for one risk: its suggested ones first, then every other response. */
export function linkTargets(linkage: LinkageOut, riskCode: string): LinkTargetOut[] {
  const suggested = new Set(
    linkage.cells
      .filter((c) => c.risk_code === riskCode && c.state === "suggested")
      .map((c) => c.target_ref),
  );
  return [...linkage.targets].sort(
    (a, b) => Number(suggested.has(b.ref)) - Number(suggested.has(a.ref)),
  );
}

export function LinkageMatrix({
  linkage,
  onLink,
}: {
  linkage: LinkageOut;
  /** A-04-T26: a person links the risk to a response; a suggested link is accepted into it. */
  onLink?: (riskCode: string, target: LinkTargetOut) => void;
}): JSX.Element {
  const state = new Map(linkage.cells.map((c) => [`${c.risk_code}|${c.target_ref}`, c.state]));
  const linkedAny = new Set(
    linkage.cells.filter((c) => c.state === "linked").map((c) => c.risk_code),
  );
  return (
    <div
      data-aud08="linkage"
      role="table"
      aria-label={COPY.linkage.title}
      className="mx-[12px] mb-[12px] overflow-auto rounded-pane bg-card shadow-e1"
    >
      <div
        role="row"
        className="flex h-[30px] items-center bg-nested px-[10px] text-[11.5px] font-medium text-ink-2"
      >
        <span role="columnheader" className="w-[64px]">
          {COPY.columns.code}
        </span>
        {linkage.targets.map((t) => (
          <span key={t.ref} role="columnheader" className="w-[96px] truncate" title={t.label}>
            {t.label}
          </span>
        ))}
        <span className="flex-1" />
      </div>
      {linkage.risk_codes.map((code) => (
        <div
          key={code}
          role="row"
          data-risk={code}
          className="flex h-[40px] items-center px-[10px] text-[13px]"
        >
          <span role="rowheader" className="w-[64px] tabular-nums">
            {code}
          </span>
          {linkage.targets.map((t) => {
            const s = state.get(`${code}|${t.ref}`);
            return (
              <span key={t.ref} role="cell" className="flex w-[96px] items-center">
                {s !== undefined && (
                  <span
                    data-dot={s}
                    aria-label={s === "linked" ? COPY.linkage.linked : COPY.linkage.suggested}
                    className={cn(
                      "inline-block size-[13px] rounded-full",
                      s === "linked" ? "bg-ink" : "border border-ink-3",
                    )}
                  />
                )}
              </span>
            );
          })}
          <span className="flex-1" />
          {!linkedAny.has(code) && (
            <span className="flex items-center gap-[6px]">
              <Pill variant="amber" size="micro">
                {COPY.linkage.suggested}
              </Pill>
              {onLink !== undefined && (
                <Menu
                  label={COPY.linkage.link}
                  align="end"
                  trigger={
                    <Button variant="secondary" size="sm">
                      {COPY.linkage.link}
                    </Button>
                  }
                  sections={[
                    linkTargets(linkage, code).map((t) => ({
                      label: t.label,
                      ...(linkage.cells.some(
                        (c) =>
                          c.risk_code === code &&
                          c.target_ref === t.ref &&
                          c.state === "suggested",
                      )
                        ? { hint: COPY.linkage.suggested }
                        : {}),
                      onSelect: () => {
                        onLink(code, t);
                      },
                    })),
                  ]}
                />
              )}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

export function RevisingHeader({ rows = 3 }: { rows?: number }): JSX.Element {
  return (
    <div data-aud08="revising" role="status" aria-live="polite" className="px-[12px] pb-[8px]">
      <div className="flex h-[30px] items-center gap-[8px] text-[12.5px] text-ink-2">
        <span
          aria-hidden
          className="size-[12px] animate-spin rounded-full border border-ink-3 border-t-transparent"
        />
        {COPY.revising}
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} data-skeleton className="my-[4px] h-[40px] rounded-[8px] bg-nested" />
      ))}
    </div>
  );
}

export function DraftedFooter({
  onAdopt,
  onEdit,
  onDiscard,
}: {
  onAdopt: () => void;
  onEdit: () => void;
  onDiscard: () => void;
}): JSX.Element {
  // C-31: a suggestion waits for a person; nothing here adopts by itself.
  return (
    <div data-aud08="drafted-footer" className="flex items-center gap-[8px] pt-[8px]">
      <button
        type="button"
        onClick={onAdopt}
        className="h-[26px] rounded-pill bg-ink px-[12px] text-[12px] font-medium text-paper"
      >
        {COPY.drafted.adopt}
      </button>
      <PaneAction kind="pill" label={COPY.drafted.edit} onClick={onEdit} />
      <PaneAction kind="pill" label={COPY.drafted.discard} onClick={onDiscard} />
    </div>
  );
}

export function DraftedMarker({ citations }: { citations: number }): JSX.Element {
  return (
    <span
      data-drafted
      title={COPY.drafted.tooltip(citations)}
      aria-label={COPY.drafted.tooltip(citations)}
      className="ml-[6px] inline-block size-[11px] rounded-full border border-ink-3"
    />
  );
}

export function IdentifyRisks({
  engagementId,
  drafting,
  onOpenRisk,
}: {
  engagementId: string;
  drafting: boolean;
  onOpenRisk: (code: string) => void;
}): JSX.Element {
  const [result, setResult] = useState<CoverageOut | null>(null);
  const coverage = useMutation({
    ...riskCoverageMutation(),
    onSuccess: (data) => {
      setResult(data);
    },
  });
  const label = drafting ? COPY.identify.button : COPY.identify.check;
  return (
    <span className="relative">
      <PaneAction
        kind="pill"
        label={label}
        onClick={() => {
          coverage.mutate({ path: { engagement_id: engagementId } });
        }}
      />
      {result !== null && (
        <div
          data-aud08="identify-result"
          role="dialog"
          aria-label={label}
          className="absolute right-0 top-[32px] z-10 w-[360px] rounded-[10px] bg-card p-[12px] text-[12.5px] shadow-e2"
        >
          <p>{drafting ? COPY.identify.agentLine(result) : COPY.identify.codeLine(result)}</p>
          {result.unaddressed_codes.map((code) => (
            <button
              key={code}
              type="button"
              className="mt-[8px] text-[13px] font-medium text-ink"
              onClick={() => {
                onOpenRisk(code);
              }}
            >
              {COPY.identify.open(code)}
            </button>
          ))}
        </div>
      )}
    </span>
  );
}
