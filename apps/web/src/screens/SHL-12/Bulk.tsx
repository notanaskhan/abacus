import type { BulkSignOffOut, SignOffEligibilityOut } from "@abacus/api-client";
import {
  type Actor,
  Button,
  Checkbox,
  HumanAction,
  Pill,
  SheetModal,
  StatusDisc,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useSession } from "../../app-core/session";
import {
  type SignOffLevel,
  type SignOffTarget,
  useBulkEligibility,
  useBulkSignOffWrite,
  useGate,
} from "../../domain/review";
import { COPY } from "./copy";

// SHL-12 f · Bulk sign-off (P-04-T49; P-04 §3 F2, R-SO-7; the handoff's frame 6): reviewers sign
// several workpapers at one level in one request. Each picked workpaper's eligibility is read at
// that level; an ineligible one is excluded automatically, unchecked and disabled, with its
// reason in words ("Waiting on inputs" with a half disc, "1 open note", "You prepared this"). The
// CTA counts what will be signed ("Sign off 3 as Reviewer (L2)"). Signing is the person's
// HumanAction; the server decides each item on its own and the sheet shows each item's result.

export interface BulkSignOffSheetProps {
  targets: readonly SignOffTarget[];
  level: SignOffLevel;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The header's right ("Northwind · PY2025"). */
  meta?: string;
  /** The fieldset's right ("Planning 5 of 6 · SOC 1 waiting on inputs"), from the host. */
  context?: string;
  onSigned?: (result: BulkSignOffOut) => void;
}

interface Row {
  eligibility: SignOffEligibilityOut;
  /** Why it is excluded, in words; null when it can be signed. */
  reason: string | null;
  waiting: boolean;
  preparer: { initials: string; signed: boolean } | null;
}

const initialsOf = (name: string): string =>
  name
    .split(/\s+/)
    .map((w) => w.charAt(0))
    .join("")
    .slice(0, 2)
    .toUpperCase();

/** The row's reason in words from the server's checks: never inferred from colour or text. */
export function rowOf(eligibility: SignOffEligibilityOut): Row {
  const l1 = eligibility.ladder.find((l) => l.level === "L1_preparer");
  const preparer =
    l1?.latest !== null && l1?.latest !== undefined
      ? { initials: l1.latest.initials, signed: true }
      : l1?.expected_signer_name !== null && l1?.expected_signer_name !== undefined
        ? { initials: initialsOf(l1.expected_signer_name), signed: false }
        : null;
  const failing = eligibility.checks.find((c) => c.result === "fail");
  const waiting = eligibility.level !== "L1_preparer" && (l1?.latest ?? null) === null;
  let reason: string | null = null;
  if (failing?.code === "open_review_notes") {
    const n = failing.facts.count;
    reason = COPY.bulk.openNotes(typeof n === "number" ? n : 1);
  } else if (failing?.code === "segregation") reason = COPY.bulk.youPrepared;
  else if (failing?.code === "independence") reason = COPY.bulk.independence;
  else if (waiting) reason = COPY.bulk.waiting;
  else if (!eligibility.eligible) reason = COPY.bulk.notAllowed;
  return { eligibility, reason, waiting: waiting && failing === undefined, preparer };
}

const shortHash = (h: string): string => {
  const hex = h.replace(/^sha256:/, "");
  return `sha256:${hex.slice(0, 4)}…${hex.slice(-4)}`;
};

export function BulkSignOffSheet({
  targets,
  level,
  open,
  onOpenChange,
  meta,
  context,
  onSigned,
}: BulkSignOffSheetProps): JSX.Element {
  const session = useSession();
  const reads = useBulkEligibility(targets, level);
  const loaded = reads.every((r) => r.data !== undefined);
  const rows = reads.flatMap((r) => (r.data === undefined ? [] : [rowOf(r.data)]));
  const [unchecked, setUnchecked] = useState<ReadonlySet<string>>(new Set());
  const [result, setResult] = useState<BulkSignOffOut | null>(null);
  const [key] = useState(() => crypto.randomUUID());
  const write = useBulkSignOffWrite();
  const actor: Actor =
    session.user === null ? { kind: "system" } : { kind: "human", name: session.user.displayName };
  const role = COPY.roles[level];
  const short = COPY.short[level];
  const chosen = rows.filter(
    (r) => r.reason === null && !unchecked.has(r.eligibility.target.target_id),
  );
  const gate = useGate({
    command: () =>
      write(
        chosen.map((r) => r.eligibility),
        key,
      ),
    doneText: (out: BulkSignOffOut) => COPY.bulk.toast(out.signed, short),
    failedText: COPY.toasts.failed,
    onDone: (out: BulkSignOffOut) => {
      setResult(out);
      onSigned?.(out);
    },
  });
  const outcome = (id: string) => result?.results.find((r) => r.target_id === id);
  const statement = rows[0]?.eligibility.statement.text;

  return (
    <SheetModal
      open={open}
      onOpenChange={onOpenChange}
      title={COPY.bulk.title(targets.length)}
      {...(meta === undefined
        ? {}
        : { meta: <span className="text-meta text-ink-3">{meta}</span> })}
    >
      {!loaded ? (
        <p className="p-[12px] text-meta text-ink-3">
          {reads.some((r) => r.isError) ? COPY.missing : COPY.loading}
        </p>
      ) : (
        <div className="flex flex-col gap-[12px] p-[12px]" data-signoff="bulk">
          <div className="flex h-[38px] items-center rounded-full bg-card px-[14px] text-body shadow-e1">
            {`${role} (${short})`}
          </div>
          <section
            aria-label={COPY.bulk.workpapers}
            className="overflow-hidden rounded-pane bg-card shadow-e1"
          >
            <header className="flex h-[44px] items-center justify-between border-b-[0.5px] border-hair px-[16px]">
              <h3 className="text-section font-medium">{COPY.bulk.workpapers}</h3>
              {context !== undefined && <span className="text-meta text-ink-3">{context}</span>}
            </header>
            <ul>
              {rows.map((r) => {
                const t = r.eligibility.target;
                const done = outcome(t.target_id);
                const excluded = r.reason !== null;
                return (
                  <li
                    key={t.target_id}
                    data-bulk-row={t.target_id}
                    {...(excluded ? { "data-excluded": "" } : {})}
                    className="flex min-h-[66px] items-center gap-[12px] border-b-[0.5px] border-hair px-[16px] last:border-b-0"
                  >
                    <Checkbox
                      label={`${t.label} v${String(t.version_no)}`}
                      checked={!excluded && !unchecked.has(t.target_id)}
                      disabled={excluded || result !== null}
                      onChange={(checked) => {
                        setUnchecked((prev) => {
                          const next = new Set(prev);
                          if (checked) next.delete(t.target_id);
                          else next.add(t.target_id);
                          return next;
                        });
                      }}
                    />
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className={excluded ? "text-body text-ink-3" : "text-body"}>
                        {t.label}{" "}
                        <span className="text-dense text-ink-3">{`v${String(t.version_no)}`}</span>
                      </span>
                      <span className="font-mono text-meta text-ink-3">
                        {shortHash(t.content_hash)}
                      </span>
                    </span>
                    {done !== undefined ? (
                      <span
                        data-bulk-result={done.ok ? "signed" : "excluded"}
                        className="text-dense"
                      >
                        {done.ok
                          ? COPY.bulk.signed
                          : (COPY.bulk.excluded[done.detail ?? ""] ??
                            COPY.bulk.excluded.sign_off_invalid)}
                      </span>
                    ) : (
                      excluded && (
                        <span className="flex items-center gap-[6px] text-dense text-ink-3">
                          {r.waiting && <StatusDisc state="half" />}
                          {r.reason}
                        </span>
                      )
                    )}
                    {r.preparer !== null &&
                      (r.preparer.signed ? (
                        <Pill variant="green" size="tally" check>
                          {r.preparer.initials}
                        </Pill>
                      ) : (
                        <Pill variant="neutral" size="tally">
                          {r.preparer.initials}
                        </Pill>
                      ))}
                  </li>
                );
              })}
            </ul>
          </section>
          <p className="px-[4px] text-meta text-ink-3">{COPY.bulk.excludedNote}</p>
          {statement !== undefined && (
            <p
              aria-label={COPY.statement}
              className="rounded-nested bg-card px-[14px] py-[12px] text-dense leading-[1.55] text-ink shadow-e1"
            >
              {statement}
            </p>
          )}
          <div
            data-signoff="footer"
            className="sticky bottom-0 -mx-[12px] -mb-[12px] flex items-center justify-between gap-[8px] bg-shell px-[12px] py-[12px]"
          >
            <Button
              variant="secondary"
              onClick={() => {
                onOpenChange(false);
              }}
            >
              {result === null ? COPY.cancel : COPY.bulk.done}
            </Button>
            {result === null && (
              <HumanAction
                verb="Sign off"
                label={COPY.bulk.cta(chosen.length, role, short)}
                actor={actor}
                disabled={chosen.length === 0 || gate.phase === "busy"}
                loading={gate.phase === "busy"}
                onClick={() => {
                  void gate.run();
                }}
              />
            )}
          </div>
        </div>
      )}
    </SheetModal>
  );
}
