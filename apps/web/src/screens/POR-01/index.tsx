import {
  AUTH_FIELD,
  AuthButton,
  AuthCard,
  AuthFrame,
  CodeInput,
  Icon,
  PortalBrandProvider,
  Spinner,
  cn,
  toast,
  usePortalBrand,
} from "@abacus/ui";
import { type JSX, type ReactNode, useEffect, useId, useRef, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import {
  type PortalLanding,
  type PortalSignInStartOut,
  type SignInFailure,
  type SignInOpening,
  brandOf,
  failureOf,
  failureWords,
  setPortalSession,
  signIn,
  useBranding,
} from "../../domain/portal";
import { COPY } from "./copy";

// POR-01 · Portal sign-in, part 1 (P-08-T09; docs/screens/POR-01.md). The T15 auth card under the
// firm's brand only (nowhere the product's name), passwordless: an email, then a 6-digit code.
// Each artboard is a state of the same card, reached through the pre-session routes:
//
//   a  the email step: Continue shows the 12 px spinner for at least 600 ms, then asks for a code
//   b  the code step: six boxes (paste fills them, the sixth digit submits), Sign in, the
//      server-timed resend countdown, "Use a different email"
//   e  a reminder link older than 14 days: "Email me a new link" and its toast
//   f  a wrong code: the inset red-ink ring and "2 tries left" in a polite live region
//   g  locked for 15 minutes, naming the firm's support contact; focus moves to the title
//
// A signed-in answer routes by the person's landing (POR-02, POR-14, …; `onSignedIn`). The
// two-step card (c, c′) and invitation acceptance (d) are P-08-T19's. At 390 the card fills the
// width with 42 × 50 boxes and the primary button pinned 16 px above the bottom (DF-03).

const MIN_SPINNER_MS = 600;

type Step = "email" | "code" | "expired" | "locked" | "second";

export interface POR01Props {
  /** What the page has done when it opens (an artboard opens part-way). */
  opening?: SignInOpening;
  /** The 390 layout (DF-03). */
  mobile?: boolean;
  /** A signed-in answer: where the person lands. */
  onSignedIn?: (landing: PortalLanding) => void;
}

/** "0:42" */
export function countdown(ms: number): string {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${String(Math.floor(s / 60))}:${String(s % 60).padStart(2, "0")}`;
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

/** The page: the firm's branding first, then the card under its brand. */
export function PortalSignIn(props: POR01Props): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <POR01 {...props} />
    </PortalBrandProvider>
  );
}

export function POR01({ opening, mobile = false, onSignedIn }: POR01Props): JSX.Element {
  const brand = usePortalBrand();
  const firm = brand.portalName ?? brand.name;
  const named = firm !== "";
  const now = useNow(1000);
  const helperId = useId();
  const titleRef = useRef<HTMLDivElement>(null);

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState(opening?.email ?? "");
  const [linkToken] = useState(opening?.linkToken);
  const [challenge, setChallenge] = useState<PortalSignInStartOut | null>(null);
  const [code, setCode] = useState("");
  const [failure, setFailure] = useState<SignInFailure | null>(null);
  const [busy, setBusy] = useState(false);
  const opened = useRef(false);

  const fail = (f: SignInFailure): void => {
    if (f.code === "sign_in_locked") {
      setStep("locked");
      return;
    }
    if (f.code === "link_expired") {
      setStep("expired");
      return;
    }
    if (f.code === "resend_too_soon" && f.resendAvailableAt !== undefined && challenge !== null) {
      setChallenge({ ...challenge, resend_available_at: f.resendAvailableAt });
    }
    setFailure(f);
  };

  const start = async (address: string): Promise<PortalSignInStartOut | null> => {
    setBusy(true);
    setFailure(null);
    try {
      const [answer] = await Promise.all([
        signIn.start({
          email: address.trim(),
          ...(linkToken === undefined ? {} : { link_token: linkToken }),
        }),
        wait(MIN_SPINNER_MS),
      ]);
      setChallenge(answer);
      setStep("code");
      return answer;
    } catch (error) {
      fail(failureOf(error));
      return null;
    } finally {
      setBusy(false);
    }
  };

  const verify = async (
    digits: string,
    against: PortalSignInStartOut | null = challenge,
  ): Promise<void> => {
    if (against === null || digits.length !== 6) return;
    setBusy(true);
    setFailure(null);
    try {
      const answer = await signIn.verify({ challenge_id: against.challenge_id, code: digits });
      if (answer.state === "signed_in") {
        // The token and its lifetime into the auth client's memory (P-08-T11).
        setPortalSession(answer);
        onSignedIn?.(answer.landing ?? "none");
      } else {
        setStep("second");
      }
    } catch (error) {
      fail(failureOf(error));
    } finally {
      setBusy(false);
    }
  };

  // An artboard (or a reminder link with a remembered address) opens part-way: replay it once.
  useEffect(() => {
    if (opened.current || opening?.start !== true) return;
    opened.current = true;
    void (async () => {
      const answer = await start(opening.email);
      if (answer === null) return;
      if (opening.code !== undefined) setCode(opening.code);
      if (opening.verify === true && opening.code !== undefined)
        await verify(opening.code, answer);
    })();
  }, []);

  useEffect(() => {
    // The lock moves focus to the title (P-08 §5.6), so a screen reader reads it first.
    const title = step === "locked" ? titleRef.current?.querySelector("h1") : null;
    if (title == null) return;
    title.tabIndex = -1;
    title.focus();
  }, [step]);

  const resendIn =
    challenge === null ? 0 : Date.parse(challenge.resend_available_at) - now.getTime();
  const words =
    failure === null
      ? null
      : failure.code === "code_mismatch" && failure.triesLeft !== undefined
        ? COPY.f.helper(failure.triesLeft)
        : failureWords(failure.code, { person: brand.supportContactName, firm });

  const footer = <SignInFooter />;
  const footnote = (
    <p className="border-t-[0.5px] border-hair pt-[12px] text-center text-meta text-ink-3">
      {named ? COPY.footnote(firm) : COPY.neutral.footnote}
    </p>
  );
  const primary = (button: ReactNode): ReactNode =>
    mobile ? <div className="sticky bottom-[16px] z-10">{button}</div> : button;

  let card: JSX.Element;
  if (step === "email") {
    card = (
      <AuthCard
        brand="header"
        fluid={mobile}
        title={COPY.a.title}
        lead={named ? COPY.a.body(firm) : COPY.neutral.body}
        footer={footer}
      >
        <form
          className="flex flex-col gap-[12px]"
          onSubmit={(e) => {
            e.preventDefault();
            if (!busy && email.trim() !== "") void start(email);
          }}
        >
          <label className="relative flex items-center">
            <span className="sr-only">{COPY.a.email}</span>
            <Icon
              name="mail"
              size={14}
              className="pointer-events-none absolute left-[14px] text-ink-3"
            />
            <input
              type="email"
              name="email"
              autoComplete="email"
              inputMode="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
              }}
              className={cn(AUTH_FIELD, "h-[40px] rounded-pill pl-[36px] inset-shadow-hair")}
            />
          </label>
          {words !== null && <Helper id={helperId} text={words} />}
          {primary(
            <button
              type="submit"
              disabled={email.trim() === ""}
              aria-busy={busy}
              className="inline-flex h-[36px] w-full items-center justify-center gap-[7px] rounded-pill bg-espresso px-[16px] text-btn-lg font-medium text-on-dark shadow-cta hover:bg-cta-hover disabled:bg-nested disabled:text-ink-4 disabled:shadow-none"
            >
              {busy && (
                <Spinner
                  label={COPY.a.sending}
                  size={12}
                  showLabel={false}
                  className="text-on-dark"
                />
              )}
              {COPY.a.continue}
            </button>,
          )}
        </form>
        {footnote}
      </AuthCard>
    );
  } else if (step === "code") {
    const invalid = failure?.code === "code_mismatch";
    card = (
      <AuthCard
        brand="header"
        fluid={mobile}
        title={COPY.b.title}
        lead={COPY.b.body(email)}
        footer={footer}
      >
        <CodeInput
          value={code}
          onChange={(v) => {
            setCode(v);
            if (failure !== null) setFailure(null);
          }}
          onComplete={(v) => void verify(v)}
          label={COPY.b.code}
          autoFocus={opening?.code === undefined}
          gap={mobile ? 6 : 8}
          compact={mobile}
          invalid={invalid}
          describedBy={helperId}
        />
        <Helper id={helperId} text={words} />
        {primary(
          <AuthButton disabled={busy || code.length !== 6} onClick={() => void verify(code)}>
            {COPY.b.signIn}
          </AuthButton>,
        )}
        <div className="flex items-center justify-center gap-[10px] text-dense">
          <span className="text-ink-3">{COPY.b.didntGet}</span>
          <button
            type="button"
            disabled={resendIn > 0 || busy}
            onClick={() => {
              if (challenge === null) return;
              void signIn
                .resend({ challenge_id: challenge.challenge_id })
                .then((next) => {
                  setChallenge(next);
                  setCode("");
                })
                .catch((error: unknown) => {
                  fail(failureOf(error));
                });
            }}
            className="inline-flex min-h-[24px] items-center gap-[6px] font-medium text-ink disabled:text-ink-3"
          >
            {COPY.b.resend}
            {resendIn > 0 && (
              <span className="tabular-nums text-ink-3">{countdown(resendIn)}</span>
            )}
          </button>
        </div>
        <button
          type="button"
          onClick={() => {
            setStep("email");
            setCode("");
            setFailure(null);
            setChallenge(null);
          }}
          className="inline-flex min-h-[24px] items-center self-center text-dense font-medium text-ink"
        >
          {COPY.b.differentEmail}
        </button>
        {footnote}
      </AuthCard>
    );
  } else if (step === "expired") {
    card = (
      <AuthCard
        brand="header"
        fluid={mobile}
        tile={{ icon: "clock", tone: "neutral" }}
        title={COPY.e.title}
        lead={COPY.e.body}
        footer={footer}
      >
        {primary(
          <AuthButton
            disabled={busy || linkToken === undefined}
            onClick={() => {
              if (linkToken === undefined) return;
              setBusy(true);
              void signIn
                .renewLink({ link_token: linkToken })
                .then(() => {
                  toast.show({ kind: "success", text: COPY.e.toast(email) });
                })
                .catch((error: unknown) => {
                  fail(failureOf(error));
                })
                .finally(() => {
                  setBusy(false);
                });
            }}
          >
            {COPY.e.renew}
          </AuthButton>,
        )}
        {words !== null && <Helper id={helperId} text={words} />}
      </AuthCard>
    );
  } else if (step === "locked") {
    const person = brand.supportContactName;
    card = (
      <div ref={titleRef} className="contents">
        <AuthCard
          brand="header"
          fluid={mobile}
          title={COPY.g.title}
          lead={
            named && person !== undefined ? COPY.g.body(person, firm) : COPY.neutral.lockedBody
          }
          footer={footer}
        >
          {named && brand.helpUrl !== undefined && (
            <AuthButton
              kind="secondary"
              onClick={() => {
                if (brand.helpUrl !== undefined) window.location.assign(brand.helpUrl);
              }}
            >
              {COPY.g.contact(firm)}
            </AuthButton>
          )}
        </AuthCard>
      </div>
    );
  } else {
    // c and c′ (two-step) are P-08-T19's: a planned state, drawn only in fixture builds.
    card = (
      <AuthCard brand="header" fluid={mobile} title={COPY.c.title} footer={footer}>
        {PLANNED_VISIBLE && <p className="text-dense text-ink-3">{COPY.notBuilt}</p>}
      </AuthCard>
    );
  }

  return (
    <AuthFrame layout={mobile ? "mobile" : "card"}>
      <div
        data-screen="POR-01"
        data-step={step}
        className={cn("flex w-full flex-col items-center")}
      >
        {card}
      </div>
    </AuthFrame>
  );
}

/** The helper under the boxes: red-ink words in a polite live region (empty when all is well). */
function Helper({ id, text }: { id: string; text: string | null }): JSX.Element {
  return (
    <p
      id={id}
      aria-live="polite"
      className={cn(
        "min-h-[16px] text-center text-dense text-red-ink",
        text === null && "sr-only",
      )}
    >
      {text ?? ""}
    </p>
  );
}

/** Under the card: "Help · Privacy · <the firm's address line>", from the branding. */
function SignInFooter(): JSX.Element {
  const brand = usePortalBrand();
  return (
    <p className="mt-[16px] flex flex-wrap items-center justify-center gap-x-[6px] text-center text-meta text-ink-3">
      {brand.helpUrl !== undefined && (
        <a href={brand.helpUrl} className="inline-flex min-h-[24px] items-center hover:text-ink">
          {COPY.footer.help}
        </a>
      )}
      {brand.privacyUrl !== undefined && (
        <>
          <span aria-hidden="true">·</span>
          <a
            href={brand.privacyUrl}
            className="inline-flex min-h-[24px] items-center hover:text-ink"
          >
            {COPY.footer.privacy}
          </a>
        </>
      )}
      {brand.addressLine !== undefined && (
        <>
          <span aria-hidden="true">·</span>
          <span>{brand.addressLine}</span>
        </>
      )}
    </p>
  );
}
