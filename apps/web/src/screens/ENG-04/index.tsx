import type {
  ComposerLetterOut,
  DiffOpOut,
  LetterConsentOut,
  LetterVariable,
  ParagraphBlock,
  SectionBlockOutput,
} from "@abacus/api-client";
import {
  type Actor,
  Button,
  ConfirmDialog,
  DEFAULT_TZ,
  Dialog,
  HumanAction,
  Icon,
  PaperCard,
  Pane,
  Pill,
  Segmented,
  SplitLayout,
  Tag,
  Toggle,
  date,
  status,
  time,
} from "@abacus/ui";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import { RevealStepUp } from "../../domain/audits";
import {
  useComposedLetter,
  useLetterCompare,
  useLetterWrites,
  withClause,
} from "../../domain/engagements";
import { COPY } from "./copy";

// ENG-04 · Engagement letter composer, part 1 (N-02-T34; docs/screens/ENG-04.md; N-02 §3.11): T10
// inside ENG-02's Letter & terms tab, on C7's composer read. The 470 structure pane: the Template
// band (template and clause-library links to KNW-03, the status, who approved, the redline count),
// the variables (facts and computed fees; one that does not apply reads "—" with its reason), the
// clause toggles (Draft only; a toggle saves a new version and the server answers the redline),
// the §7216 consents (each its own document, never a clause; a missing one links to CLI-05) and
// the signers in order. The paper on the well: the letterhead and the composed blocks, a switched
// off clause struck through, a non-standard clause on an amber rule with its tag, and a citation
// marker beside each value that lights its variable row. Frames built: a (partner approved), b
// (Draft, watermarked, "Request partner approval…") and c (Sent, read-only, "View envelope ›").
// Send is a person's click (INV-1) and opens the C7 draft in SIG-02. N-02-T35: the engagement
// partner approves in a dialog that lists the §7216 consents (each its own document; a needed one
// holds the approval), stepping up when the second factor is stale; an envelope that came back
// declined, expired or voided is withdrawn by a person, and Send drafts a new one.
//
// Part 2 (N-02-T37): d signed and locked (the signers and their days, the approver of record, the
// SSARS routing note, Edit disabled and Amend… (addendum)), e the audit variant (the sent date on
// the status, the AU-C 210 clauses, the §103(a)(3)(C) election), f the bundled consents (each
// consent its own document, in tabs beside the letter, with its template and signers), and Compare
// to standard: C11's word-level diff over the paper, insertions underlined, deletions struck.

type Target =
  { screen: "KNW-03" } | { screen: "CLI-05" } | { screen: "SIG-01"; envelopeId: string };

export interface LetterComposerProps {
  engagementId: string;
  engagementName: string;
  /** SIG-02's builder for the C7 draft Send created. */
  onOpenEnvelope?: (envelopeId: string) => void;
  onNavigate?: (target: Target) => void;
  /** d: Amend… (addendum) on a signed letter. */
  onAmend?: () => void;
  height?: number;
}

/** The variables the structure pane lists, in the handoff's order; a template's own declared
 * keys follow the computed fees. The paper's own values (the date, the addressee) stay on paper. */
const ORDER = [
  "client.signer",
  "firm.signer",
  "fee.summary",
  "billing.terms",
  "third_party_fee.summary",
] as const;
const AFTER = [
  "approver_of_record",
  "ske_designee",
  "ebp.limited_scope_election",
  "ai_use.disclosure",
] as const;
const ON_PAPER = new Set([
  "client.name",
  "letter.date",
  "letter.addressee",
  "acceptance.decided_on",
]);

/** Which pane row a value on the paper lights: the fee and billing amounts light their summary. */
export function rowOf(key: string): string {
  if (key.startsWith("fee.")) return "fee.summary";
  if (key.startsWith("billing.")) return "billing.terms";
  if (key.startsWith("third_party_fee.")) return "third_party_fee.summary";
  if (key === "section_754.due") return "section_754.decision_by";
  return key;
}

export function paneVariables(letter: ComposerLetterOut): LetterVariable[] {
  const byKey = new Map(letter.variables.map((v) => [v.key, v]));
  const head = ORDER.flatMap((k) => byKey.get(k) ?? []);
  const tail = AFTER.flatMap((k) => byKey.get(k) ?? []);
  const named = new Set<string>([...ORDER, ...AFTER]);
  const declared = letter.variables.filter(
    (v) =>
      !named.has(v.key) &&
      !ON_PAPER.has(v.key) &&
      v.source !== "computed" &&
      v.label != null &&
      rowOf(v.key) === v.key,
  );
  return [...head, ...declared, ...tail];
}

const firstWord = (name: string): string => name.split(/[\s,]/)[0] ?? name;

function Band({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section aria-label={title} className="flex flex-col">
      <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-section hairline-t">
        {title}
      </h3>
      <ul className="flex flex-col">{children}</ul>
    </section>
  );
}

function Row({
  label,
  children,
  lit = false,
  helper,
}: {
  label: string;
  children?: ReactNode;
  lit?: boolean;
  helper?: string | undefined;
}): JSX.Element {
  return (
    <li
      data-lit={lit ? "true" : undefined}
      className={`flex min-h-[33px] flex-col justify-center px-[12px] py-[6px] hairline-t ${
        lit ? "bg-match-bg ring-1 ring-match-ink/40 ring-inset" : ""
      }`}
    >
      <span className="flex items-center gap-[10px]">
        <span className="flex-none text-body text-ink-2">{label}</span>
        <span className="ml-auto min-w-0 text-right text-body text-ink">{children}</span>
      </span>
      {helper !== undefined && <span className="text-meta text-ink-3">{helper}</span>}
    </li>
  );
}

function LinkValue({ text, onOpen }: { text: string; onOpen?: () => void }): JSX.Element {
  return (
    <Button variant="link" size="sm" className="text-ink" onClick={onOpen}>
      {text}
      <Icon name="arrow-right" size={12} className="ml-[4px] text-ink-3" />
    </Button>
  );
}

function StatusValue({
  letter,
  now,
  tz,
}: {
  letter: ComposerLetterOut;
  now: Date;
  tz: string;
}): JSX.Element {
  const word = status("letter", letter.status);
  const signers = letter.signers ?? [];
  const signed = signers.filter((s) => s.signed).length;
  if (letter.status === "signed") {
    return (
      <Pill variant={word.variant ?? "green"} data-locked="true">
        <Icon name="lock" size={12} className="mr-[4px]" />
        {word.label}
      </Pill>
    );
  }
  const label =
    letter.status !== "sent"
      ? word.label
      : letter.sent_at == null
        ? `${word.label} · ${COPY.signedCount(signed, signers.length)}`
        : COPY.sentOn(date(letter.sent_at, { now, tz }), signed, signers.length);
  return <Pill variant={word.variant ?? "neutral"}>{label}</Pill>;
}

/** d: who signed and countersigned, and when (from the signers' days). */
export function signedMeta(letter: ComposerLetterOut, now: Date, tz: string): string | undefined {
  if (letter.status !== "signed") return undefined;
  const signers = letter.signers ?? [];
  const client = signers.find((x) => x.role === "client" && x.signed_on != null);
  const firm = signers.find((x) => x.role === "firm" && x.signed_on != null);
  if (client?.signed_on == null || firm?.signed_on == null) return undefined;
  const on = (day: string): string => date(`${day}T12:00:00Z`, { now, tz, withYear: true });
  return COPY.signedMeta(client.name, on(client.signed_on), firm.name, on(firm.signed_on));
}

function ConsentRow({
  consent,
  client,
  now,
  tz,
  onOpen,
}: {
  consent: LetterConsentOut;
  client: string;
  now: Date;
  tz: string;
  onOpen: () => void;
}): JSX.Element {
  const party = consent.label.split(" · ").at(-1) ?? consent.label;
  if (consent.status === "on_file" && consent.signed_on != null && consent.expires_on != null) {
    const on = date(`${consent.signed_on}T12:00:00Z`, { now, tz, withYear: true });
    const until = date(`${consent.expires_on}T12:00:00Z`, { now, tz, withYear: true });
    return (
      <Row label={consent.label}>
        <Pill variant="green-tint">{COPY.consents.signed(on, until)}</Pill>
      </Row>
    );
  }
  return (
    <Row label={consent.label} helper={COPY.consents.notOnFile(client, firstWord(party))}>
      <Button variant="link" size="sm" onClick={onOpen}>
        <Pill variant="amber">{COPY.consents.needed}</Pill>
      </Button>
    </Row>
  );
}

/** C11's blocks: the composer sends the template's DocBlocks as JSON (engagements may not import
 * reporting's models), so the paper reads them as the client's C11 block types. */
type Block = SectionBlockOutput["blocks"][number];
type Runs = ParagraphBlock["runs"];

interface PaperProps {
  letter: ComposerLetterOut;
  values: ReadonlyMap<string, string>;
  onLight: (key: string | null) => void;
  /** Compare to standard: each section's diff ops by block id (C11 compare). */
  diff?: ReadonlyMap<string, readonly DiffOpOut[]> | undefined;
}

function DiffView({ ops }: { ops: readonly DiffOpOut[] }): JSX.Element {
  return (
    <p data-diff className="mb-[8px] text-[12px] leading-[1.55]">
      {ops.map((o, i) =>
        o.op === "insert" ? (
          <ins key={i} data-op="insert" className="text-green-ink underline">
            {o.text}
          </ins>
        ) : o.op === "delete" ? (
          <del key={i} data-op="delete" className="text-ink-4 line-through">
            {o.text}
          </del>
        ) : (
          <span key={i}>{o.text}</span>
        ),
      )}
    </p>
  );
}

function RunsView({
  runs,
  values,
  onLight,
}: { runs: Runs } & Omit<PaperProps, "letter" | "diff">): JSX.Element {
  return (
    <>
      {runs.map((run, i) => {
        if (run.type === "text") return <span key={i}>{run.text}</span>;
        if (run.type === "var") {
          const value = values.get(run.key) ?? "";
          return (
            <span key={i} data-field={run.key}>
              {value}
              <button
                type="button"
                aria-label={COPY.paper.cite(run.key)}
                data-cite={rowOf(run.key)}
                className="ml-[3px] inline-flex h-[17px] items-center rounded-[4px] bg-chip px-[4px] align-middle text-micro text-ink-3"
                onMouseEnter={() => {
                  onLight(rowOf(run.key));
                }}
                onMouseLeave={() => {
                  onLight(null);
                }}
                onFocus={() => {
                  onLight(rowOf(run.key));
                }}
                onBlur={() => {
                  onLight(null);
                }}
              >
                <Icon name="link" size={12} />
              </button>
            </span>
          );
        }
        return null;
      })}
    </>
  );
}

function BlockView({
  block,
  states,
  ...rest
}: { block: Block; states: ReadonlyMap<string, string> } & Omit<
  PaperProps,
  "letter"
>): JSX.Element | null {
  switch (block.type) {
    case "paragraph":
      return (
        <p className="mb-[8px] text-[12px] leading-[1.55]">
          <RunsView runs={block.runs} {...rest} />
        </p>
      );
    case "heading":
      return <h3 className="mt-[6px] mb-[10px] text-[16px] font-medium">{block.text}</h3>;
    case "section": {
      const clause = block.blocks.find((b) => b.type === "clause");
      const off = clause?.type === "clause" && states.get(clause.clause_id) === "off";
      const flagged = clause?.type === "clause" && clause.non_standard;
      const ops = rest.diff?.get(block.id);
      return (
        <section
          data-section={block.id}
          data-struck={off ? "true" : undefined}
          className={`${flagged ? "border-l-2 border-amber pl-[10px]" : ""} ${
            off ? "text-ink-4 line-through" : ""
          }`}
        >
          <h4 className="mt-[10px] mb-[4px] flex items-center gap-[8px] text-[13.5px] font-medium">
            {block.title}
            {flagged && <Tag className="bg-amber-tint text-amber-ink">{COPY.nonStandard}</Tag>}
          </h4>
          {ops === undefined ? (
            block.blocks.map((b, i) => <BlockView key={i} block={b} states={states} {...rest} />)
          ) : (
            <DiffView ops={ops} />
          )}
        </section>
      );
    }
    case "clause":
      return (
        <>
          {block.blocks.map((b, i) => (
            <BlockView key={i} block={b} states={states} {...rest} />
          ))}
        </>
      );
    case "signature_block":
      return (
        <div className="mt-[18px] grid grid-cols-2 gap-[16px] text-[12px]">
          {block.signers.map((s, i) => (
            <div key={i} className="flex flex-col gap-[4px]">
              <span>{s.label}</span>
              <span className="mt-[18px] border-t border-ink pt-[2px]">
                <RunsView runs={s.name} {...rest} />
              </span>
            </div>
          ))}
        </div>
      );
    default:
      return null;
  }
}

function Paper({
  letter,
  values,
  onLight,
  diff,
  blocks,
}: PaperProps & { blocks: readonly Block[] }): JSX.Element {
  const states = new Map(letter.clauses.map((c) => [c.key, c.state]));
  const head = letter.letterhead;
  return (
    <PaperCard {...(letter.status === "draft" ? { watermark: COPY.paper.watermark } : {})}>
      {head != null && (
        <div data-letterhead className="mb-[14px] flex flex-col pb-[8px] hairline-b">
          <span className="text-[13.5px] font-medium">{head.firm}</span>
          {(head.address ?? []).map((line) => (
            <span key={line} className="text-[11.5px] text-ink-3">
              {line}
            </span>
          ))}
        </div>
      )}
      {blocks.map((block, i) => (
        <BlockView
          key={i}
          block={block}
          states={states}
          values={values}
          onLight={onLight}
          diff={diff}
        />
      ))}
    </PaperCard>
  );
}

export function LetterComposer({
  engagementId,
  engagementName,
  onOpenEnvelope,
  onNavigate,
  onAmend,
  height,
}: LetterComposerProps): JSX.Element {
  const query = useComposedLetter(engagementId);
  const letter = query.data;
  const writes = useLetterWrites(letter);
  const [comparing, setComparing] = useState(false);
  const [tab, setTab] = useState<string>(COPY.paper.title);
  const compared = useLetterCompare(letter, comparing);
  const session = useSession();
  const now = useNow();
  const tz = session.tz ?? DEFAULT_TZ;
  const [lit, setLit] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  // N-02-T35: the partner's approval dialog, its step-up, and the withdrawal confirm.
  const [approving, setApproving] = useState(false);
  const [stepUp, setStepUp] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);

  if (letter === undefined) {
    return (
      <div
        data-screen="ENG-04"
        aria-busy={query.isPending ? true : undefined}
        className="p-[16px]"
      >
        {query.isError ? <p className="text-body text-ink-3">{COPY.failed}</p> : null}
      </div>
    );
  }

  const actor: Actor =
    session.user === null ? { kind: "system" } : { kind: "human", name: session.user.displayName };
  const can = (a: string): boolean => letter.allowed_actions.includes(a);
  const draft = letter.status === "draft";
  const editable = can("letter.draft") && (draft || editing);
  const values = new Map(
    letter.variables.flatMap((v) => (v.value == null ? [] : [[v.key, v.value]])),
  );
  const client = firstWord(letter.variables.find((v) => v.key === "client.name")?.value ?? "");
  const consents = letter.consents ?? [];
  const needed = consents.find((c) => c.status === "needed");
  const documents = letter.documents ?? [];
  const documentSigners = [
    ...new Set(documents.flatMap((d) => (d.signers ?? []).map((x) => x.name))),
  ];
  const shown = documents.find((d) => d.title === tab);
  const diff =
    comparing && compared.data !== undefined && shown === undefined
      ? new Map(compared.data.blocks.map((b) => [b.block_id, b.ops]))
      : undefined;
  const locked = letter.status === "signed";
  const approvedAt =
    letter.approved_at == null
      ? null
      : `${date(letter.approved_at, { now, tz })}, ${time(letter.approved_at, { tz })}`;

  const toggle = (key: string, on: boolean): void => {
    void writes.draft(withClause(letter, key, on));
  };

  const structure = (
    <div data-document="structure" className="flex flex-col">
      <div className="flex h-[32px] flex-none items-center bg-band-hd px-[12px] text-dense font-medium text-ink-2">
        {COPY.crumb(engagementName)}
      </div>
      <Band title={COPY.bands.template}>
        {letter.template_name != null && (
          <Row label={COPY.keys.template}>
            <LinkValue
              text={COPY.templateName(letter.template_name, letter.template_version_no ?? 1)}
              onOpen={() => onNavigate?.({ screen: "KNW-03" })}
            />
          </Row>
        )}
        {letter.clause_library != null && (
          <Row label={COPY.keys.library}>
            <LinkValue
              text={letter.clause_library}
              onOpen={() => onNavigate?.({ screen: "KNW-03" })}
            />
          </Row>
        )}
        <Row label={COPY.keys.status} helper={signedMeta(letter, now, tz)}>
          <StatusValue letter={letter} now={now} tz={tz} />
        </Row>
        {letter.approved_by_name != null && approvedAt !== null && (
          <Row label={COPY.keys.approved}>
            {COPY.approved(letter.approved_by_name, approvedAt)}
          </Row>
        )}
        <Row label={COPY.keys.redline}>
          <Pill variant="amber" data-redline={letter.redline_count ?? 0}>
            {COPY.redline(letter.redline_count ?? 0)}
          </Pill>
        </Row>
      </Band>
      <Band title={COPY.bands.variables}>
        {paneVariables(letter).map((v) => {
          const label = COPY.variables[v.key] ?? v.label ?? v.key;
          if (v.key === "ai_use.disclosure") {
            return (
              <Row key={v.key} label={label} helper={COPY.aiDefault}>
                <Toggle label={label} checked={v.value === "on"} disabled />
              </Row>
            );
          }
          const reason = v.reason == null ? undefined : COPY.reasons[v.reason];
          return (
            <Row
              key={v.key}
              label={label}
              lit={lit === v.key}
              helper={v.value == null ? reason : undefined}
            >
              {v.value ?? <span className="text-ink-4">—</span>}
            </Row>
          );
        })}
        {letter.routing_note != null && (
          <li data-routing-note className="px-[12px] py-[8px] text-meta text-ink-3 hairline-t">
            {letter.routing_note}
          </li>
        )}
      </Band>
      <Band title={COPY.bands.clauses}>
        {letter.clauses.map((c, i) => (
          <li
            key={c.key}
            className="flex min-h-[34px] items-center gap-[10px] px-[12px] hairline-t"
          >
            <Toggle
              label={c.title}
              checked={c.state !== "off"}
              disabled={!editable || c.state === "required" || writes.pending}
              onChange={(on) => {
                toggle(c.key, on);
              }}
            />
            <span className="text-body text-ink">{`${String(i + 1)} ${c.title}`}</span>
            {c.non_standard && (
              <Tag className="ml-auto bg-amber-tint text-amber-ink">{COPY.nonStandard}</Tag>
            )}
          </li>
        ))}
      </Band>
      <Band title={COPY.bands.consents}>
        {consents.map((c) => (
          <ConsentRow
            key={c.purpose}
            consent={c}
            client={client}
            now={now}
            tz={tz}
            onOpen={() => onNavigate?.({ screen: "CLI-05" })}
          />
        ))}
        {documents.length > 0 ? (
          <li data-bundled className="px-[12px] py-[8px] text-body text-ink hairline-t">
            {COPY.consents.bundled(documents.length, documentSigners)}
          </li>
        ) : (
          <Row
            label={COPY.consents.bundle}
            helper={
              needed === undefined
                ? COPY.consents.separate
                : `${COPY.consents.separate} ${COPY.consents.sentAlone(
                    firstWord(needed.label.split(" · ").at(-1) ?? ""),
                  )}`
            }
          >
            <Toggle label={COPY.consents.bundle} checked={false} disabled />
          </Row>
        )}
      </Band>
      <Band title={COPY.bands.signers}>
        {(letter.signers ?? []).map((s) => (
          <li
            key={s.order}
            className="flex min-h-[33px] items-center px-[12px] text-body hairline-t"
          >
            {s.role === "client"
              ? COPY.signer.client(s.order, s.name)
              : COPY.signer.firm(s.order, s.name)}
          </li>
        ))}
      </Band>
    </div>
  );

  const right = (
    <>
      {((letter.status === "partner_approved" && can("letter.draft")) || locked) && (
        <Button
          variant="secondary"
          size="sm"
          icon="pencil"
          disabled={locked}
          onClick={() => {
            setEditing(true);
          }}
        >
          {COPY.paper.edit}
        </Button>
      )}
      {locked && can("letter.amend") && (
        // The handoff's label ends "(addendum)", not "…": the dialog is named by aria-haspopup.
        <Button variant="secondary" size="sm" aria-haspopup="dialog" onClick={onAmend}>
          {COPY.paper.amend}
        </Button>
      )}
      <Button
        variant="ghost"
        size="sm"
        aria-pressed={comparing}
        disabled={letter.generated_document_id == null || shown !== undefined}
        onClick={() => {
          setComparing((on) => !on);
        }}
      >
        {COPY.paper.compare}
      </Button>
      {draft && can("letter.draft") && (
        <Button
          variant="primary"
          size="sm"
          opensDialog
          disabled={writes.pending}
          onClick={() => {
            void writes.requestApproval();
          }}
        >
          {COPY.paper.requestApproval}
        </Button>
      )}
      {draft && can("letter.approve") && (
        <HumanAction
          verb="Approve"
          actor={actor}
          label={COPY.approval.open}
          variant="primary"
          size="sm"
          disabled={writes.pending}
          onClick={() => {
            setApproving(true);
          }}
        />
      )}
      {can("letter.withdraw_envelope") && (
        <Button
          variant="secondary"
          size="sm"
          opensDialog
          disabled={writes.pending}
          onClick={() => {
            setWithdrawing(true);
          }}
        >
          {COPY.withdraw.open}
        </Button>
      )}
      {letter.status === "partner_approved" && can("letter.send") && (
        <HumanAction
          verb="Send"
          actor={actor}
          label={COPY.paper.send}
          variant="primary"
          size="sm"
          disabled={writes.pending}
          onClick={() => {
            void writes.send().then((out) => onOpenEnvelope?.(out.envelope_id));
          }}
        />
      )}
      {letter.status === "sent" && letter.envelope_id != null && (
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            if (letter.envelope_id != null) {
              onNavigate?.({ screen: "SIG-01", envelopeId: letter.envelope_id });
            }
          }}
        >
          {COPY.paper.viewEnvelope}
        </Button>
      )}
    </>
  );

  return (
    <div
      data-screen="ENG-04"
      data-status={letter.status}
      data-read-only={letter.status === "sent" || locked ? "true" : undefined}
      data-comparing={diff === undefined ? undefined : "true"}
      className="flex min-h-0 min-w-0 flex-1"
    >
      <Dialog
        open={approving}
        onOpenChange={setApproving}
        title={COPY.approval.title}
        description={COPY.approval.body}
        action={
          <HumanAction
            verb="Approve"
            actor={actor}
            label={COPY.approval.confirm}
            variant="primary"
            size="sm"
            disabled={writes.pending || consents.some((c) => c.status === "needed")}
            onClick={() => {
              writes.approve().then(
                () => {
                  setApproving(false);
                },
                (error: unknown) => {
                  // The approval asks a fresh second factor (`letter.approve`, mfa_recent).
                  if (
                    (error as { facts?: { reason?: unknown } } | null)?.facts?.reason ===
                    "mfa_required"
                  ) {
                    setStepUp(true);
                  }
                },
              );
            }}
          />
        }
      >
        <ul aria-label={COPY.approval.consents} className="flex flex-col gap-[6px]">
          {consents.map((c) => (
            <li key={c.label} className="flex items-center justify-between gap-[8px] text-dense">
              <span>{c.label}</span>
              {c.status === "on_file" ? (
                <Pill variant="green-tint">{COPY.approval.onFile}</Pill>
              ) : (
                <Pill variant="amber">{COPY.consents.needed}</Pill>
              )}
            </li>
          ))}
        </ul>
        <p className="mt-[10px] text-meta text-ink-3">{COPY.consents.separate}</p>
      </Dialog>
      <RevealStepUp open={stepUp} onOpenChange={setStepUp} />
      <ConfirmDialog
        open={withdrawing}
        onOpenChange={setWithdrawing}
        title={COPY.withdraw.title}
        confirmLabel={COPY.withdraw.confirm}
        destructive={false}
        onConfirm={() => {
          void writes.withdraw();
        }}
      >
        {COPY.withdraw.body(letter.envelope_status ?? "")}
      </ConfirmDialog>
      <SplitLayout
        preset="document"
        height={height ?? "viewport"}
        narrow={false}
        className="w-full bg-transparent p-0"
      >
        {[
          <Pane key="structure" width={470} header={false} scrollLabel={COPY.bands.template}>
            {structure}
          </Pane>,
          <Pane key="paper" title={COPY.paper.title} titleAlign="center" well right={right}>
            <div className="flex min-h-full flex-col gap-[10px] p-[14px]">
              {documents.length > 0 && (
                <div className="flex flex-col items-center gap-[4px]">
                  <Segmented
                    label={COPY.keys.documents}
                    size="small"
                    options={[COPY.paper.title, ...documents.map((d) => d.title)]}
                    active={shown === undefined ? COPY.paper.title : shown.title}
                    onChange={setTab}
                  />
                  {shown !== undefined && (
                    <span data-document-template className="text-meta text-ink-3">
                      {COPY.templateName(shown.template_name, shown.template_version_no)}
                    </span>
                  )}
                </div>
              )}
              <Paper
                letter={letter}
                values={values}
                onLight={setLit}
                diff={diff}
                blocks={(shown === undefined ? letter.paper : shown.paper) ?? []}
              />
            </div>
          </Pane>,
        ]}
      </SplitLayout>
    </div>
  );
}

export default LetterComposer;
