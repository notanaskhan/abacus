import { type JSX, type ReactNode, useRef, useState } from "react";
import { usePortalBrand } from "../../brand";
import { EmptyState, ErrorState, Skeleton } from "../../components/states";
import { AppShell } from "../../layout/app-shell";
import { portalNav } from "../portal-layout";
import {
  AuthorizingCard,
  CompletionCard,
  EnvelopeHeader,
  SignCallToAction,
  SigningDocumentList,
  SigningSteps,
} from "../../signing/parts";
import {
  SignFieldLayer,
  type SignFieldLayerHandle,
  openFieldsOf,
} from "../../signing/sign-field-layer";
import type { SigningCeremonyProps } from "../../signing/types";

// T16 SigningCeremony (F-06-T04; T16 and TPL-16 handoff; F-06.md §3 F1, §5.2): the portal toolbar
// 46, the envelope header 46, then three columns: documents 240, the page well (816, holding the
// 680 page on the shell ground) and the steps 300. Provider mode only: identity and the signature
// itself run in the provider's view (DF-12), which F-06-T05's ProviderSigningFrame hosts; this
// frame draws what the server says and asks for nothing it may not have.
//
// Every state is data: `restricted` when no signer is the viewer, the completion card once the
// envelope is `completed` and carries its evidence, a pending field set otherwise. "1 of 2
// signed" is the server's count. The page is an image from the E5 pipeline (no pdf.js).

const SIGNING_NOTE =
  "Signing records the date, time, your IP address and the verification result.";

function Columns({ children }: { children: ReactNode }): JSX.Element {
  return <>{children}</>;
}

function Loading(): JSX.Element {
  return (
    <Columns>
      <div className="w-[240px] flex-none rounded-pane bg-card p-3 shadow-e2">
        <Skeleton className="h-16" />
      </div>
      <div className="flex min-w-0 flex-1 justify-center rounded-pane bg-shell p-[14px]">
        <Skeleton className="h-full w-[680px]" />
      </div>
      <div className="w-[300px] flex-none rounded-pane bg-card p-3 shadow-e2">
        <Skeleton className="h-40" />
      </div>
    </Columns>
  );
}

export function SigningCeremony(props: SigningCeremonyProps): JSX.Element {
  const brand = usePortalBrand();
  const { envelope, view = "ready", frame = false, height } = props;
  const viewer = envelope.signers.find((s) => s.isViewer) ?? null;
  const [selected, setSelected] = useState(envelope.documents[0]?.id ?? "");
  const layer = useRef<SignFieldLayerHandle | null>(null);
  const open = openFieldsOf(envelope.fields, viewer?.id ?? null);
  const nextOpen = open[0] ?? null;
  const completed = envelope.status === "completed" && envelope.evidence !== undefined;
  const canSign = viewer !== null && !completed && envelope.outcome === undefined;
  const doc = envelope.documents.find((d) => d.id === selected) ?? envelope.documents[0];
  const current = envelope.steps.find((s) => s.state === "current")?.key;

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
      <Columns>
        <SigningDocumentList
          documents={envelope.documents}
          selected={doc?.id ?? ""}
          onSelect={setSelected}
          signers={envelope.signers}
        />
        <section
          aria-label={doc?.name ?? "Document"}
          data-signing="well"
          className="flex w-[816px] min-w-0 flex-none flex-col items-center gap-[14px] overflow-y-auto rounded-pane bg-shell p-[14px]"
        >
          {doc?.pages.map((page) => (
            <SignFieldLayer
              key={`${doc.id}:${String(page.n)}`}
              page={page}
              documentName={doc.name.split(" — ")[0] ?? doc.name}
              fields={envelope.fields.filter((f) => f.documentId === doc.id)}
              viewerId={viewer.id}
              nextOpenId={nextOpen?.documentId === doc.id ? nextOpen.id : null}
              handle={layer}
              {...(props.onSignField === undefined ? {} : { onSignField: props.onSignField })}
            />
          ))}
        </section>
        <aside
          aria-label="Steps"
          data-signing="steps"
          className="flex w-[300px] flex-none flex-col gap-3 overflow-y-auto rounded-pane bg-card p-[12px] shadow-e2"
        >
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
              {canSign && current === "sign" && (
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
      </Columns>
    );
  }

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
        ...(brand.logo === undefined ? {} : { logo: brand.logo }),
        ...(brand.mark === undefined ? {} : { mark: brand.mark }),
      }}
      record={
        <EnvelopeHeader
          envelope={envelope}
          backLabel={props.backLabel}
          canDecline={canSign}
          {...(props.onBack === undefined ? {} : { onBack: props.onBack })}
          {...(props.onOpenDecline === undefined ? {} : { onOpenDecline: props.onOpenDecline })}
          {...(props.onDownload === undefined ? {} : { onDownload: props.onDownload })}
        />
      }
    >
      <div data-template="t16" className="flex min-h-0 flex-1 gap-[10px]">
        {body}
      </div>
    </AppShell>
  );
}
