import { type JSX, type ReactNode, type RefObject, useEffect, useRef, useState } from "react";
import { usePortalBrand } from "../../brand";
import { EmptyState, ErrorState, Skeleton } from "../../components/states";
import { AppShell } from "../../layout/app-shell";
import { PortalLayout, portalNav } from "../portal-layout";
import {
  AuthorizingCard,
  CompletionCard,
  EnvelopeHeader,
  SignCallToAction,
  SigningDocumentList,
  SigningSteps,
  envelopePill,
} from "../../signing/parts";
import {
  DeclineDialog,
  MobileSignBar,
  PendingConfirmation,
  ProviderSigningFrame,
  StepChips,
  VerificationFailedCard,
} from "../../signing/outcomes";
import {
  SignFieldLayer,
  type SignFieldLayerHandle,
  openFieldsOf,
} from "../../signing/sign-field-layer";
import type { EnvelopeVM, SignerVM, SigningCeremonyProps } from "../../signing/types";

// T16 SigningCeremony (F-06-T04, T05, T06; T16 and TPL-16 handoff; F-06.md §3 F1, §5.2): the portal
// toolbar 46, the envelope header 46, then three columns: documents 240, the page well (816,
// holding the 680 page on the shell ground) and the steps 300. Provider mode only: identity and
// the signature itself run in the provider's view (DF-12), which `ProviderSigningFrame` hosts in the
// well; this frame draws what the server says and asks for nothing it may not have.
//
// Every state is data: `restricted` when no signer is the viewer, the completion card once the
// envelope is `completed` and carries its evidence, DF-11's card when the viewer's identity failed
// (no retry), "checking" after the provider returns until the server says signed, a pending field
// set otherwise. "1 of 2 signed" is the server's count. The page is an image from the E5 pipeline
// (no pdf.js). At 390 (`layout="phone"`, TPL-16g) the same envelope is one column: header, step
// chips, the full-width page, and a sticky sign bar.

const SIGNING_NOTE =
  "Signing records the date, time, your IP address and the verification result.";
/** The phone column's page width: 390 less the column's 12 a side. */
const PHONE_PAGE_PX = 366;

function Loading(): JSX.Element {
  return (
    <>
      <div className="w-[240px] flex-none rounded-pane bg-card p-3 shadow-e2">
        <Skeleton className="h-16" />
      </div>
      <div className="flex min-w-0 flex-1 justify-center rounded-pane bg-shell p-[14px]">
        <Skeleton className="h-full w-[680px]" />
      </div>
      <div className="w-[300px] flex-none rounded-pane bg-card p-3 shadow-e2">
        <Skeleton className="h-40" />
      </div>
    </>
  );
}

/** N-02-T26: each page of the shown document that comes half into view, once per page, reported
 * to `onPageSeen` (review progress). No observer in the environment (jsdom), no reports. */
function usePagesSeen(
  well: RefObject<HTMLElement | null>,
  documentId: string | undefined,
  onPageSeen: ((documentId: string, page: number) => void) | undefined,
): void {
  useEffect(() => {
    const root = well.current;
    if (root === null || documentId === undefined || onPageSeen === undefined) return undefined;
    if (typeof IntersectionObserver === "undefined") return undefined;
    const seen = new Set<number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const n = Number((entry.target as HTMLElement).dataset.page);
          if (entry.isIntersecting && Number.isInteger(n) && !seen.has(n)) {
            seen.add(n);
            onPageSeen(documentId, n);
          }
        }
      },
      { root, threshold: 0.5 },
    );
    for (const page of root.querySelectorAll("[data-signing='page']")) observer.observe(page);
    return () => {
      observer.disconnect();
    };
  }, [well, documentId, onPageSeen]);
}

function failed(envelope: EnvelopeVM, viewer: SignerVM | null): boolean {
  return envelope.outcome === "verification_failed" || viewer?.status === "verification_failed";
}

export function SigningCeremony(props: SigningCeremonyProps): JSX.Element {
  const brand = usePortalBrand();
  const { envelope, view = "ready", frame = false, height, copy } = props;
  const viewer = envelope.signers.find((s) => s.isViewer) ?? null;
  const [selected, setSelected] = useState(envelope.documents[0]?.id ?? "");
  const [declining, setDeclining] = useState(props.declineForceState === "open");
  const layer = useRef<SignFieldLayerHandle | null>(null);
  const well = useRef<HTMLElement | null>(null);
  const open = openFieldsOf(envelope.fields, viewer?.id ?? null);
  const nextOpen = open[0] ?? null;
  // The completion card once the envelope is completed, or (N-02-T26, POR-06c) once the server
  // says the viewer signed and another signer still has to (Owen signed; Daniel countersigns).
  const completed =
    (envelope.status === "completed" || viewer?.status === "signed") &&
    envelope.evidence !== undefined;
  const identityFailed = failed(envelope, viewer);
  const canSign =
    viewer !== null && !completed && envelope.outcome === undefined && !identityFailed;
  const doc = envelope.documents.find((d) => d.id === selected) ?? envelope.documents[0];
  const current = envelope.steps.find((s) => s.state === "current")?.key;
  // Story 1.1: the provider's return is a hint. Until the server reports the viewer signed, the
  // kit says it is checking, never Completed.
  const confirming =
    props.providerReturned === true && viewer !== null && viewer.status !== "signed" && !completed;
  // The provider's view hosts identity (the 8879 family's KBA) or, where identity was the portal's
  // email code (letters, DF-11), the signature: the verify or the sign step (N-02-T26).
  const providerOpen =
    canSign &&
    !confirming &&
    envelope.signingSession !== undefined &&
    (current === "verify" || current === "sign");
  const declineEnabled = canSign && props.onDecline !== undefined && copy !== undefined;
  usePagesSeen(well, providerOpen ? undefined : doc?.id, props.onPageSeen);

  const pages = (width?: number): ReactNode =>
    viewer !== null &&
    doc?.pages.map((page) => (
      <SignFieldLayer
        key={`${doc.id}:${String(page.n)}`}
        page={page}
        documentName={doc.name.split(" — ")[0] ?? doc.name}
        fields={envelope.fields.filter((f) => f.documentId === doc.id)}
        viewerId={viewer.id}
        nextOpenId={nextOpen?.documentId === doc.id ? nextOpen.id : null}
        handle={layer}
        {...(width === undefined ? {} : { widthPx: width })}
        {...(props.onSignField === undefined ? {} : { onSignField: props.onSignField })}
      />
    ));

  const wellContent = (): ReactNode => {
    if (identityFailed && copy !== undefined) {
      return (
        <VerificationFailedCard title={copy.verifyFailedTitle} body={copy.verifyFailedBody} />
      );
    }
    if (providerOpen && envelope.signingSession !== undefined && copy !== undefined) {
      return (
        <ProviderSigningFrame
          session={envelope.signingSession}
          title={copy.providerTitle}
          continueLabel={copy.providerContinue}
          unavailable={copy.providerUnavailable}
          {...(props.onContinueToVerify === undefined
            ? {}
            : { onContinue: props.onContinueToVerify })}
        />
      );
    }
    return pages();
  };

  const declineCopy = declineEnabled ? copy.decline : undefined;
  const declineDialog =
    declineCopy !== undefined ? (
      <DeclineDialog
        copy={declineCopy}
        open={declining}
        onOpenChange={setDeclining}
        onDecline={(choice) => {
          props.onDecline?.(choice);
          setDeclining(false);
        }}
        {...(props.declineForceState === undefined ? {} : { forceState: props.declineForceState })}
        {...(props.declineHeldScrim === undefined ? {} : { heldScrim: props.declineHeldScrim })}
      />
    ) : null;

  if (props.layout === "phone" && view === "ready" && viewer !== null) {
    return (
      <PortalLayout
        variant="mobile"
        user={props.user}
        nav={props.nav ?? []}
        active="Sign"
        {...(props.onNavigate === undefined ? {} : { onNavigate: props.onNavigate })}
        frame={frame}
        {...(height === undefined ? {} : { height })}
        {...(props.action !== undefined && props.action !== null && !completed
          ? {
              mobileFooter: (
                <div
                  data-signing="mobile-action"
                  style={{ minHeight: props.stickyBarHeight ?? 64 }}
                  className="flex items-center gap-[8px] px-[12px]"
                >
                  {props.action}
                </div>
              ),
            }
          : // A container that owns the step control (`action`, even `null` while the
            // provider's view or the return is showing) gets no kit sign bar (N-02-T26).
            props.action === undefined && canSign && !providerOpen && current === "sign"
            ? {
                mobileFooter: (
                  <MobileSignBar
                    viewer={viewer.name}
                    height={props.stickyBarHeight ?? 64}
                    disabled={nextOpen === null}
                    onClick={() => {
                      if (nextOpen !== null) props.onSignField?.(nextOpen.id);
                    }}
                  />
                ),
              }
            : {})}
      >
        <div data-template="t16" data-layout="phone" className="flex flex-col gap-[10px]">
          <div className="flex min-h-[44px] flex-wrap items-center gap-[8px]">
            <h1 className="text-body font-medium text-ink">{envelope.title}</h1>
            {envelopePill(envelope)}
          </div>
          {copy !== undefined && <StepChips steps={envelope.steps} names={copy.stepNames} />}
          {confirming && copy !== undefined && (
            <PendingConfirmation title={copy.pendingTitle} body={copy.pendingBody} />
          )}
          {/* Scroll padding keeps the active field above the sticky bar (Story 1.6). */}
          <section
            ref={well}
            aria-label={doc?.name ?? "Document"}
            data-signing="well"
            style={{ scrollPaddingBottom: (props.stickyBarHeight ?? 64) + 16 }}
            className="flex flex-col items-center gap-[10px]"
          >
            {/* DF-11's card or the provider's view (N-02-T26: POR-06 on a phone) take the well. */}
            {(identityFailed || providerOpen) && copy !== undefined
              ? wellContent()
              : pages(PHONE_PAGE_PX)}
          </section>
          {completed && (
            <CompletionCard
              title={props.completion?.title ?? "Signed."}
              evidence={envelope.evidence ?? []}
              {...(props.completion?.note === undefined ? {} : { note: props.completion.note })}
            />
          )}
        </div>
      </PortalLayout>
    );
  }

  let body: JSX.Element;
  if (view === "loading") body = <Loading />;
  else if (view === "error") {
    body = (
      <div className="flex flex-1 items-center justify-center rounded-pane bg-card shadow-e2">
        <ErrorState
          noun="this envelope"
          audience="portal"
          {...(props.onRetry === undefined ? {} : { onRetry: props.onRetry })}
        />
      </div>
    );
  } else if (viewer === null) {
    // Restricted (Story 1.2): a viewer who is not a signer sees no page and no field.
    body = (
      <div
        data-signing="restricted"
        className="flex flex-1 items-center justify-center rounded-pane bg-card shadow-e2"
      >
        <EmptyState title="You aren't a signer on this envelope." icon="lock">
          {`Ask ${brand.portalName ?? brand.name} who should sign it.`}
        </EmptyState>
      </div>
    );
  } else {
    body = (
      <>
        <SigningDocumentList
          documents={envelope.documents}
          selected={doc?.id ?? ""}
          onSelect={setSelected}
          signers={envelope.signers}
          {...(props.documentsTitle === undefined ? {} : { title: props.documentsTitle })}
          {...(props.showSigners === undefined ? {} : { showSigners: props.showSigners })}
        />
        {/* A scrollable region takes keyboard focus so the pages scroll without a pointer (axe
            scrollable-region-focusable; as Pane's scroll region). */}
        <section
          ref={well}
          aria-label={doc?.name ?? "Document"}
          tabIndex={0}
          data-signing="well"
          className="flex w-[816px] min-w-0 flex-none flex-col items-center gap-[14px] overflow-y-auto rounded-pane bg-shell p-[14px]"
        >
          {wellContent()}
        </section>
        <aside
          aria-label="Steps"
          data-signing="steps"
          className="flex w-[300px] flex-none flex-col gap-3 overflow-y-auto rounded-pane bg-card p-[12px] shadow-e2"
        >
          {props.stepsTitle !== undefined && (
            <h2 className="-mx-[12px] -mt-[12px] flex h-[46px] flex-none items-center justify-center border-b-[0.5px] border-hair text-section">
              {props.stepsTitle}
            </h2>
          )}
          {completed ? (
            <CompletionCard
              title={props.completion?.title ?? "Signed."}
              evidence={envelope.evidence ?? []}
              {...(props.completion?.note === undefined ? {} : { note: props.completion.note })}
            />
          ) : (
            <SigningSteps steps={envelope.steps}>
              {envelope.authorizing !== undefined && (
                <AuthorizingCard authorizing={envelope.authorizing} />
              )}
              {confirming && copy !== undefined && (
                <PendingConfirmation title={copy.pendingTitle} body={copy.pendingBody} />
              )}
              {props.action}
              {props.action === undefined &&
                canSign &&
                !confirming &&
                current === "sign" &&
                props.signPanel}
              {props.action === undefined &&
                canSign &&
                !confirming &&
                current === "sign" &&
                props.signPanel === undefined && (
                  <SignCallToAction
                    viewer={viewer}
                    note={SIGNING_NOTE}
                    disabled={nextOpen === null}
                    onClick={() => {
                      if (nextOpen === null) return;
                      props.onSignField?.(nextOpen.id);
                    }}
                  />
                )}
            </SigningSteps>
          )}
        </aside>
      </>
    );
  }

  const openDecline = declineEnabled
    ? () => {
        setDeclining(true);
      }
    : props.onOpenDecline;

  return (
    <AppShell
      variant="portal"
      frame={frame}
      {...(height === undefined ? {} : { height })}
      securedFooter={brand.securedFooter}
      toolbar={{
        firm: brand.portalName ?? brand.name,
        user: props.user,
        nav: props.nav ?? portalNav("individual"),
        active: "Sign",
        ...(props.onNavigate === undefined ? {} : { onNavigate: props.onNavigate }),
        ...(brand.logo === undefined ? {} : { logo: brand.logo }),
        ...(brand.mark === undefined ? {} : { mark: brand.mark }),
      }}
      record={
        <EnvelopeHeader
          envelope={envelope}
          {...(props.backLabel === undefined ? {} : { backLabel: props.backLabel })}
          canDecline={canSign}
          {...(props.onBack === undefined ? {} : { onBack: props.onBack })}
          {...(openDecline === undefined ? {} : { onOpenDecline: openDecline })}
          {...(props.onDownload === undefined ? {} : { onDownload: props.onDownload })}
        />
      }
    >
      <div data-template="t16" className="flex min-h-0 flex-1 gap-[10px]">
        {body}
      </div>
      {declineDialog}
    </AppShell>
  );
}
