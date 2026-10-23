import { me } from "@abacus/api-client";
import { meQueryKey } from "@abacus/api-client/query";
import { AuthButton, AuthCard, Monogram, Spinner, Wordmark, cn } from "@abacus/ui";
import { useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useEffect, useRef, useState } from "react";
import { lastRefreshFailure, safeReturnTo, signIn, startSession } from "../../app-core/auth";
import { COPY, type SignInError, isSignInError } from "./copy";

// SHL-06g · Signing in (P-01-T11; P-01 AC 5.1.3; docs/screens/SHL-06.md). The hosted sign-in
// (a–f) is the provider's; the BFF's callback lands the browser here with `?to=<safe path>`, or
// with `?error=<code>` when it refused. This page asks the BFF for an in-memory access token
// (`POST /v1/auth/refresh`), loads `/v1/me` and opens the return path. Nothing is stored.

/** The firm app's own sign-in marks: the 22 wordmark above the card, the 34 monogram in it. */
const MARKS = { above: <Wordmark size={22} />, inside: <Monogram size={34} /> };

export interface SHL06Props {
  /** The landing's query string: `?to=…` or `?error=…`. */
  search: string;
  /** Open the return path (the route replaces history; the gallery stays on g). */
  onDone: (path: string) => void;
  /** Presentation only (the gallery): the 1400 × 860 window on the stage. */
  frame?: boolean;
}

export function SHL06({ search, onDone, frame = false }: SHL06Props): JSX.Element {
  const params = new URLSearchParams(search);
  const to = safeReturnTo(params.get("to"));
  const refused = params.get("error");
  const queryClient = useQueryClient();
  const [error, setError] = useState<SignInError | null>(() =>
    refused === null ? null : isSignInError(refused) ? refused : "sign_in_failed",
  );
  // The cookie rotates on every refresh: start the session once, even under StrictMode.
  const started = useRef(false);

  useEffect(() => {
    if (refused !== null || started.current) return;
    started.current = true;
    void (async () => {
      if (!(await startSession())) {
        const code = lastRefreshFailure();
        setError(isSignInError(code) ? code : "sign_in_failed");
        return;
      }
      const { data, response } = await me({ throwOnError: false });
      if (response?.status === 401) {
        setError("session_rejected");
        return;
      }
      // A 403 (no firm yet) or any other answer is the shell's to show; the account is cached.
      if (data !== undefined) queryClient.setQueryData(meQueryKey(), data);
      onDone(to);
    })().catch(() => {
      setError("sign_in_failed");
    });
  }, [refused, to, onDone, queryClient]);

  return (
    <div data-screen="SHL-06" className="contents">
      <FirmAuthFrame frame={frame}>
        {error === null ? (
          <AuthCard brand="marks" marks={MARKS} title={COPY.title} footer={<Links />}>
            <div aria-live="polite">
              <AuthButton disabled>
                <Spinner label={COPY.signingIn} size={15} className="text-btn-lg text-ink-4" />
              </AuthButton>
            </div>
          </AuthCard>
        ) : (
          <AuthCard
            brand="marks"
            marks={MARKS}
            title={COPY.error.title}
            lead={COPY.error.reasons[error]}
            tile={{ icon: "lock", tone: "red" }}
            footer={<Links />}
          >
            <AuthButton
              onClick={() => {
                signIn(to);
              }}
            >
              {COPY.error.retry}
            </AuthButton>
          </AuthCard>
        )}
      </FirmAuthFrame>
    </div>
  );
}

/** T15's window for the firm app: the shell colour, no toolbar, the block 133 from the top. The
 * portal's AuthFrame draws the firm's brand from its provider; this page is Accrued's own. */
function FirmAuthFrame({ frame, children }: { frame: boolean; children: ReactNode }): JSX.Element {
  const surface = (
    <div
      data-shell="app"
      data-variant="auth-card"
      className={cn(
        "relative flex flex-col overflow-hidden bg-shell",
        frame ? "h-[860px] w-(--app-w) flex-none rounded-window shadow-e1" : "min-h-dvh w-full",
      )}
    >
      <main
        data-auth="body"
        className="flex min-h-0 flex-1 flex-col items-center overflow-y-auto px-[16px] pt-[133px] pb-[40px]"
      >
        {children}
      </main>
    </div>
  );
  if (!frame) return surface;
  return (
    <div data-shell="stage" className="flex items-start justify-center bg-presentation p-[20px]">
      {surface}
    </div>
  );
}

/** "Privacy · Terms · System status", 16 under the card. */
function Links(): JSX.Element {
  return (
    <p className="mt-[16px] flex items-center justify-center gap-[6px] text-meta text-ink-3">
      {COPY.links.map((label, i) => (
        <span key={label} className="flex items-center gap-[6px]">
          {i > 0 && <span aria-hidden="true">·</span>}
          {label}
        </span>
      ))}
    </p>
  );
}
