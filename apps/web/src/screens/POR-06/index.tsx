import type {
  PortalEnvelopeRow,
  PortalEnvelopeView,
  PortalSignerOut,
  SignerDeclineIn,
} from "@abacus/api-client";
import {
  Button,
  Checkbox,
  DEFAULT_TZ,
  EmptyState,
  type EnvelopeVM,
  Pane,
  PortalBrandProvider,
  PortalLayout,
  RegistryStatus,
  SigningCeremony,
  type SignerChipVM,
  type SignerVM,
  type SigningOutcomeCopy,
  type SigningStepVM,
  date,
  longDate,
  time,
  toast,
  usePortalBrand,
} from "@abacus/ui";
import { type JSX, useCallback, useEffect, useState } from "react";
import { useNow } from "../../app-core/clock";
import { brandOf, useBranding, usePortalToolbar } from "../../domain/portal";
import {
  toEnvelopeVM,
  useEnvelopeActions,
  usePageUrls,
  usePortalEnvelope,
  usePortalEnvelopes,
  useSigningReturn,
} from "../../domain/signing";
import { COPY } from "./copy";

// POR-06 · Sign, part 1 (N-02-T26; docs/screens/POR-06.md; handoff POR-06; DF-11, DF-12): the
// portal's Sign area on the T16 SigningCeremony kit (locked by F-06-T13), over C7's portal routes.
//
//   /sign                         the signer's envelopes: to sign, then signed
//   /sign/$envelopeId             a  review: "Continue to sign" waits until the last page was seen
//                                 b  the ERSD consent, then the provider's one-time view (iframe or
//                                    redirect) in the well: identity and signature are the provider's
//                                 g  declined: the envelope reads Declined, "Withdraw decline"
//   /sign/$envelopeId/return      the provider sent the signer back: "Checking your signature"
//                                 until the server says signed (polling is truth), then c, the
//                                 completion card with the evidence C7 carries
//
// The return's parameters are hints: nothing here renders Completed from them (ADR-041 pattern).
// A person who is not a signer gets one restricted state (every read 404, no oracle). 390 is the
// kit's phone layout with the step control as its sticky footer. The firm's name comes from the
// branding; the product's never shows (DEC-01).
//
// Part 2 (N-02-T29; DEC-1388) reads C7's additive fields: the signers in order (the signers card,
// a joint return's chips), the viewer's identity method (an e-file authorization verifies by
// identity questions in the provider's view: d, with the authorizing card), and the server's date
// gate (`signing_opens_on`: f keeps "Continue to sign" off and says why). h is DF-11: the kit's
// card replaces the page and offers nothing to retry.

/** C7's decline codes for the four reasons, in order (POR-06 contract). */
const DECLINE_CODES: Readonly<Record<string, SignerDeclineIn["reason"]>> = {
  [COPY.decline.reasons[0]]: "have_questions",
  [COPY.decline.reasons[1]]: "something_wrong",
  [COPY.decline.reasons[2]]: "someone_else_should_sign",
  [COPY.decline.reasons[3]]: "other",
};

function outcomeCopy(firm: string, document: string): SigningOutcomeCopy {
  return {
    verifyFailedTitle: COPY.verifyFailedTitle,
    verifyFailedBody: COPY.verifyFailedBody(firm),
    pendingTitle: COPY.pendingTitle,
    pendingBody: COPY.pendingBody,
    providerTitle: COPY.providerTitle(document),
    providerContinue: COPY.providerContinue,
    providerUnavailable: COPY.providerUnavailable,
    decline: {
      title: COPY.decline.title,
      reasons: COPY.decline.reasons,
      reasonsLabel: COPY.decline.reasonsLabel,
      noteLabel: COPY.decline.note,
      confirm: COPY.decline.confirm,
      trigger: COPY.decline.trigger,
    },
    stepNames: COPY.stepNames,
  };
}

/** Where the signer is, from the server's view and the review the screen has seen. */
export type Phase = "review" | "consent" | "ready" | "provider" | "signed" | "declined" | "failed";

export function phaseOf(view: PortalEnvelopeView, consenting: boolean): Phase {
  if (view.row.my_status === "signed") return "signed";
  // DF-11: remote signing closed for this signer; the paper form follows and nothing reopens it.
  if (view.row.my_status === "verification_failed" || view.paper_form_follows) return "failed";
  if (view.row.my_status === "declined" || view.outcome === "declined") return "declined";
  if (view.signing_session != null) return "provider";
  if (!view.esign_consent_needed) return "ready";
  return consenting ? "consent" : "review";
}

/** What else shapes the steps: identity questions in the provider's view (the 8879 family), and
 * the day signing opens (a dated letter, from the server). */
export interface StepFacts {
  kba?: boolean;
  opensOn?: string;
}

/** Verify identity · Review · Sign · Done for a phase (POR-06 steps pane). With identity questions
 * the provider verifies and signs in one view: Verify is current there, and done once signed. */
export function stepsOf(
  phase: Phase,
  seen: number,
  pages: number,
  facts: StepFacts = {},
): SigningStepVM[] {
  const reviewing = phase === "review";
  const signing = phase === "consent" || phase === "ready" || phase === "provider";
  const kba = facts.kba === true;
  const signed = phase === "signed";
  return [
    kba
      ? {
          key: "verify",
          state: signed ? "done" : phase === "provider" ? "current" : "todo",
          sub: COPY.stepSubs.kba,
        }
      : { key: "verify", state: "done", sub: COPY.stepSubs.verify },
    {
      key: "review",
      state: reviewing ? "current" : "done",
      sub: reviewing
        ? COPY.stepSubs.reviewing(Math.max(seen, 1), pages)
        : COPY.stepSubs.reviewed(pages),
    },
    {
      key: "sign",
      state: signed ? "done" : signing && !(kba && phase === "provider") ? "current" : "todo",
      sub: facts.opensOn === undefined ? "" : COPY.stepSubs.opens(facts.opensOn),
    },
    { key: "done", state: phase === "signed" ? "done" : "todo", sub: "" },
  ];
}

export interface POR06Props {
  /** `/sign/$envelopeId`; without it, the Sign list. */
  envelopeId?: string;
  /** `/sign/$envelopeId/return?session=`: the provider's one-time view the signer came back from. */
  session?: string;
  mobile?: boolean;
  /** Presentation only (the gallery): the 1400 window or the 390 phone. */
  frame?: boolean;
  onNavigate?: (area: string) => void;
  onOpenEnvelope?: (envelopeId: string) => void;
  onBack?: () => void;
}

function onDay(day: string): string {
  return `${day}T12:00:00Z`;
}

function isMissing(error: unknown): boolean {
  return typeof error === "object" && error !== null && "detail" in error;
}

/** A signer's line on the signers card, in client words from the server's status and role. */
function signerDetail(s: PortalSignerOut, firm: string, now: Date): string {
  if (s.status === "signed" && s.signed_at !== null) {
    const at = { now, tz: DEFAULT_TZ };
    return COPY.signer.signed(`${date(s.signed_at, at)}, ${time(s.signed_at, at)}`);
  }
  if (s.status === "declined") return COPY.signer.declined;
  if (s.status === "verification_failed") return COPY.signer.paperForm;
  if (s.role === "ero") return COPY.signer.ero(firm);
  if (s.role === "countersigner") return COPY.signer.countersigns(firm);
  return s.me ? COPY.signer.toSign : COPY.signer.separate;
}

function signerVM(
  s: PortalSignerOut,
  view: PortalEnvelopeView,
  firm: string,
  now: Date,
): SignerVM {
  return {
    id: s.id,
    name: s.name,
    isViewer: s.me,
    status: s.status,
    // The kit knows the client's methods; another signer's isn't the viewer's to read.
    method: s.me && view.identity_method !== "firm_sso" ? view.identity_method : "email_code",
    detail: signerDetail(s, firm, now),
  };
}

/** A joint return's chips: every client signer, when there is more than one (POR-06e). */
function chipsOf(view: PortalEnvelopeView, now: Date): SignerChipVM[] {
  const clients = view.signers.filter((s) => s.role === "signer");
  if (clients.length < 2) return [];
  return clients.map((s) => ({
    signerId: s.id,
    name: s.name.split(" ")[0] ?? s.name,
    status: s.status,
    ...(s.signed_at === null ? {} : { date: date(s.signed_at, { now, tz: DEFAULT_TZ }) }),
  }));
}

/** POR-06e: another client signer in the viewer's group, still to sign with their own link. */
function separateSigner(view: PortalEnvelopeView): string | undefined {
  const me = view.signers.find((s) => s.me);
  if (me === undefined || view.family !== "efile_authorization") return undefined;
  const other = view.signers.find(
    (s) =>
      !s.me &&
      s.role === "signer" &&
      s.routing_group === me.routing_group &&
      s.status !== "signed",
  );
  return other === undefined ? undefined : (other.name.split(" ")[0] ?? other.name);
}

const EMPTY: EnvelopeVM = {
  id: "",
  title: "",
  status: "sent",
  signedCount: 0,
  signerCount: 0,
  documents: [],
  signers: [],
  fields: [],
  steps: [],
};

function SignList({
  mobile = false,
  frame = false,
  onNavigate,
  onOpenEnvelope,
}: POR06Props): JSX.Element | null {
  const now = useNow();
  const bar = usePortalToolbar(null);
  const list = usePortalEnvelopes();
  if (bar === undefined) return null;
  const rows = list.data?.items ?? [];
  const toSign = rows.filter((r) => r.my_status !== "signed");
  const signed = rows.filter((r) => r.my_status === "signed");
  const row = (r: PortalEnvelopeRow): JSX.Element => (
    <li key={r.id}>
      <button
        type="button"
        data-envelope={r.id}
        onClick={() => onOpenEnvelope?.(r.id)}
        className="flex min-h-[56px] w-full items-center gap-[10px] border-t-[0.5px] border-hair px-[12px] py-[10px] text-left hover:bg-tonal-hover"
      >
        <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
          <span className="text-body font-medium text-ink">{r.title}</span>
          {r.due_on !== null && (
            <span className="text-meta text-ink-3">
              {COPY.due(date(onDay(r.due_on), { now, tz: DEFAULT_TZ }))}
            </span>
          )}
        </span>
        <RegistryStatus object="envelope" code={r.status} client />
      </button>
    </li>
  );
  const body =
    list.data === undefined ? (
      <div role="status" aria-busy="true" className="h-[120px]" />
    ) : (
      <div className="flex flex-col">
        {toSign.length === 0 ? (
          <EmptyState icon="pen-line" title={COPY.nothingToSign} />
        ) : (
          <ul aria-label={COPY.listTitle}>{toSign.map(row)}</ul>
        )}
        {signed.length > 0 && (
          <>
            <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-section">
              {COPY.signedBand}
            </h3>
            <ul aria-label={COPY.signedBand}>{signed.map(row)}</ul>
          </>
        )}
      </div>
    );
  return (
    <div data-screen="POR-06" className="flex min-h-0 flex-1 flex-col">
      <PortalLayout
        variant={mobile ? "mobile" : "reduced"}
        user={bar.user}
        nav={bar.nav}
        active={COPY.nav}
        frame={frame}
        {...(frame ? { height: mobile ? 844 : 860 } : {})}
        {...(onNavigate === undefined ? {} : { onNavigate })}
      >
        <Pane title={COPY.listTitle} titleAlign="center">
          {body}
        </Pane>
      </PortalLayout>
    </div>
  );
}

function Envelope({
  envelopeId = "",
  session,
  mobile = false,
  frame = false,
  onNavigate,
  onBack,
}: POR06Props): JSX.Element | null {
  const brand = usePortalBrand();
  const firm = brand.portalName ?? brand.name;
  const now = useNow();
  const bar = usePortalToolbar(null);
  const returned = session !== undefined;
  const envelope = usePortalEnvelope(envelopeId, returned);
  const back = useSigningReturn(envelopeId, session);
  const act = useEnvelopeActions(envelopeId);
  const view = envelope.data;
  const doc =
    view === undefined ? undefined : [...view.documents].sort((a, b) => a.order - b.order)[0];
  const pages = doc?.page_count ?? 0;
  const urls = usePageUrls(envelopeId, doc?.id, pages);
  const [seen, setSeen] = useState(0);
  const [consenting, setConsenting] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (envelopeId === "" || returned) return;
    act.viewed().catch(() => undefined);
    // Once per envelope opened.
  }, [envelopeId]);

  const onPageSeen = useCallback(
    (_documentId: string, n: number) => {
      setSeen((was) => {
        if (n <= was) return was;
        act.progress(n).catch(() => undefined);
        return n;
      });
    },
    // `act` is rebuilt each render; its calls only read the envelope id.
    [envelopeId],
  );

  if (bar === undefined) return null;
  const settle = (work: Promise<unknown>): void => {
    setBusy(true);
    work
      .catch(() => {
        toast.show({ kind: "error", text: COPY.failed });
      })
      .finally(() => {
        setBusy(false);
      });
  };

  // Restricted: not a signer on this envelope (or no such envelope): one state, no oracle.
  if (envelope.isError && isMissing(envelope.error)) {
    return (
      <div data-screen="POR-06" data-signing="restricted" className="flex min-h-0 flex-1 flex-col">
        <PortalLayout
          variant={mobile ? "mobile" : "reduced"}
          user={bar.user}
          nav={bar.nav}
          active={COPY.nav}
          frame={frame}
          {...(frame ? { height: mobile ? 844 : 860 } : {})}
          {...(onNavigate === undefined ? {} : { onNavigate })}
        >
          <Pane title={COPY.listTitle} titleAlign="center">
            <EmptyState icon="lock" title={COPY.restrictedTitle}>
              {COPY.restrictedBody(firm)}
            </EmptyState>
          </Pane>
        </PortalLayout>
      </div>
    );
  }

  const phase = view === undefined ? "review" : phaseOf(view, consenting);
  const kba = view?.identity_method === "kba";
  const opensOn = view?.signing_opens_on == null ? undefined : longDate(view.signing_opens_on);
  const vm: EnvelopeVM =
    view === undefined
      ? EMPTY
      : (() => {
          const me = view.signers.find((s) => s.me);
          const signer = me?.id ?? view.my_fields[0]?.signer_id ?? view.row.id;
          const chips = chipsOf(view, now);
          const mapped = toEnvelopeVM(view, {
            viewer:
              me === undefined
                ? {
                    id: signer,
                    name: bar.user,
                    isViewer: true,
                    status: view.row.my_status,
                    method: "email_code",
                    detail: "",
                  }
                : signerVM(me, view, firm, now),
            others: view.signers.filter((s) => !s.me).map((s) => signerVM(s, view, firm, now)),
            steps: stepsOf(phase, seen, pages, {
              kba,
              ...(opensOn === undefined ? {} : { opensOn }),
            }),
            fieldLabels: COPY.fieldLabels,
            ...(kba && phase !== "signed" ? { authorizing: COPY.kbaCard } : {}),
            ...(chips.length === 0
              ? {}
              : { chips: Object.fromEntries(view.documents.map((d) => [d.id, chips])) }),
            ...(phase === "signed"
              ? {
                  evidence: [
                    ...view.documents
                      .filter((d) => d.sha256 !== null)
                      .map((d) => ({
                        label: COPY.evidenceLabels.fingerprint,
                        value: COPY.fingerprint(d.sha256 ?? ""),
                      })),
                    {
                      label: COPY.evidenceLabels.signers,
                      value: COPY.signedOf(view.signers_signed, view.signers_total),
                    },
                  ],
                }
              : {}),
          });
          return {
            ...mapped,
            // The page images arrive as blob URLs (the route needs the bearer token); until one
            // has, the kit draws the page's placeholder.
            documents: mapped.documents.map((d) => ({
              ...d,
              pages: d.pages.map((p) => ({ ...p, src: urls[p.n] ?? "" })),
            })),
          };
        })();

  const lastPage = pages;
  let action: JSX.Element | null = null;
  if (view !== undefined) {
    if (phase === "declined") {
      action = (
        <Button
          variant="secondary"
          size="md"
          className="w-full"
          disabled={busy}
          onClick={() => {
            settle(act.withdraw());
          }}
        >
          {COPY.withdraw}
        </Button>
      );
    } else if (phase === "review") {
      const read = seen >= lastPage && lastPage > 0;
      // POR-06f: the server holds signing until the letter's date; reading does not open it.
      const ready = read && opensOn === undefined;
      action = (
        <div className="flex w-full flex-col gap-[6px]">
          {opensOn !== undefined && (
            <p
              id="por06-dated"
              data-signing="dated"
              className="rounded-nested bg-amber-tint p-[12px] text-dense text-amber-ink"
            >
              {COPY.datedNote(opensOn, firm)}
            </p>
          )}
          <Button
            variant="primary"
            size="md"
            className="w-full"
            disabled={!ready}
            aria-describedby={!read ? "por06-continue-hint" : ready ? undefined : "por06-dated"}
            onClick={() => {
              setConsenting(true);
            }}
          >
            {COPY.continue}
          </Button>
          {!read && (
            <span id="por06-continue-hint" className="text-meta text-ink-3">
              {COPY.continueHint(lastPage)}
            </span>
          )}
        </div>
      );
    } else if (phase === "consent") {
      action = (
        <section
          data-signing="consent"
          aria-label={COPY.consent.title}
          className="flex w-full flex-col gap-[10px] rounded-nested bg-shell p-[12px]"
        >
          <span className="text-body font-medium text-ink">{COPY.consent.title}</span>
          <Checkbox label={COPY.consent.agree} checked={agreed} onChange={setAgreed} />
          <Button
            variant="primary"
            size="md"
            className="w-full"
            disabled={!agreed || busy}
            onClick={() => {
              settle(act.consentAndOpen(view.disclosure_version_id));
            }}
          >
            {COPY.consent.confirm}
          </Button>
        </section>
      );
    } else if (phase === "ready") {
      action = (
        <Button
          variant="primary"
          size="md"
          className="w-full"
          disabled={busy}
          onClick={() => {
            settle(act.consentAndOpen(null));
          }}
        >
          {COPY.continue}
        </Button>
      );
    }
  }

  const remaining = view === undefined ? 0 : view.signers_total - view.signers_signed;
  const first = bar.user.split(" ")[0] ?? bar.user;
  const other = view === undefined ? undefined : separateSigner(view);
  return (
    <div data-screen="POR-06" data-phase={phase} className="flex min-h-0 flex-1 flex-col">
      <SigningCeremony
        envelope={vm}
        user={bar.user}
        nav={bar.nav}
        backLabel={COPY.back}
        view={
          envelope.isError || back.isError ? "error" : view === undefined ? "loading" : "ready"
        }
        copy={outcomeCopy(firm, doc?.title ?? vm.title)}
        completion={{
          title: COPY.completedTitle(first),
          ...(other !== undefined
            ? { note: COPY.separately(other) }
            : remaining > 0
              ? { note: COPY.waiting(remaining) }
              : {}),
        }}
        providerReturned={returned}
        action={action}
        onPageSeen={onPageSeen}
        onRetry={() => void envelope.refetch()}
        onDecline={({ reason, note }) => {
          const code = DECLINE_CODES[reason];
          if (code !== undefined) settle(act.decline(code, note));
        }}
        frame={frame}
        {...(frame ? { height: mobile ? 844 : 860 } : {})}
        {...(mobile ? { layout: "phone" as const, stickyBarHeight: 64 as const } : {})}
        {...(onBack === undefined ? {} : { onBack })}
        {...(onNavigate === undefined ? {} : { onNavigate })}
      />
    </div>
  );
}

export function POR06(props: POR06Props): JSX.Element | null {
  return props.envelopeId === undefined ? <SignList {...props} /> : <Envelope {...props} />;
}

/** The page: the firm's branding first, then the Sign area under its brand. */
export function PortalSign(props: POR06Props): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <POR06 {...props} />
    </PortalBrandProvider>
  );
}
