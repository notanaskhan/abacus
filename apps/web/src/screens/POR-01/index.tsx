import {
  AUTH_FIELD,
  AuthButton,
  AuthCard,
  AuthFrame,
  CodeInput,
  Icon,
  PortalBrandProvider,
  Spinner,
  Toggle,
  cn,
  toast,
  usePortalBrand,
} from "@abacus/ui";
import { type JSX, type ReactNode, useEffect, useId, useRef, useState } from "react";
import { useNow } from "../../app-core/clock";
import {
  type InvitationPreviewOut,
  type PortalLanding,
  type PortalMfaSetupOut,
  type PortalSignInStartOut,
  type PortalSignInVerifyOut,
  type SignInFailure,
  type SignInOpening,
  brandOf,
  failureOf,
  failureWords,
  invitation,
  portalAccessToken,
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
// Part 2 (P-08-T19):
//
//   c  the second step for a person the firm's MFA floor covers: the authenticator's six digits,
//      "Trust this device for 30 days", Verify, and "Use a backup code" (a one-time code instead)
//   c′ its first-time setup (DF-17): the authenticator link and the manual key, the first code,
//      then the 8 backup codes shown once behind "I've saved these codes"; nothing keeps them
//   d  an invitation (`/accept#token=…`): the preview (one 404 for every failure), the read-only
//      email, Name, Organization and Access, the terms toggle; "Accept and continue" asks for a
//      code with the invitation's token, and after the code (and any second step) the invitation
//      is accepted with the invitee's own session and the person goes to their landing
//
// A signed-in answer routes by the person's landing (POR-02, POR-14, …; `onSignedIn`). At 390 the
// card fills the width with 42 × 50 boxes and the primary button pinned 16 px above the bottom
// (DF-03).

const MIN_SPINNER_MS = 600;

type Step =
  | "email"
  | "code"
  | "expired"
  | "locked"
  | "second"
  | "setup"
  | "codes"
  | "invite"
  | "invalid"
  | "done";

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
  // c and c′: the single-use second-step token (memory only), and what the person types.
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [useBackup, setUseBackup] = useState(false);
  const [totp, setTotp] = useState("");
  const [backupCode, setBackupCode] = useState("");
  const [trust, setTrust] = useState(false);
  const [setupKey, setSetupKey] = useState<PortalMfaSetupOut | null>(null);
  const setupAsked = useRef<string | null>(null);
  // The 8 backup codes, shown once: dropped from memory when the person continues.
  const [backupCodes, setBackupCodes] = useState<readonly string[] | null>(null);
  const [saved, setSaved] = useState(false);
  const [afterCodes, setAfterCodes] = useState<PortalSignInVerifyOut | null>(null);
  // d: the invitation's token (memory only), its preview, the terms toggle, and once accepted.
  const [invitationToken] = useState(opening?.invitationToken);
  const [invite, setInvite] = useState<InvitationPreviewOut | null>(null);
  const [terms, setTerms] = useState(false);
  const accepted = useRef(false);

  const fail = (f: SignInFailure): void => {
    if (f.code === "sign_in_locked" || f.code === "mfa_locked") {
      setMfaToken(null);
      setStep("locked");
      return;
    }
    if (f.code === "mfa_expired") {
      // The step's token is spent: start again from the email (no session without it).
      setMfaToken(null);
      setStep(invite === null ? "email" : "invite");
      setCode("");
      setTotp("");
      setChallenge(null);
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
          ...(invitationToken === undefined ? {} : { invitation_token: invitationToken }),
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
      await finish(answer);
    } catch (error) {
      fail(failureOf(error));
    } finally {
      setBusy(false);
    }
  };

  /** A sign-in answer: a session (then, on an invitation, its acceptance), or a second step. */
  const finish = async (answer: PortalSignInVerifyOut): Promise<void> => {
    if (answer.state !== "signed_in") {
      setMfaToken(answer.mfa_token ?? null);
      setTotp("");
      setUseBackup(false);
      setStep(answer.state === "mfa_setup_required" ? "setup" : "second");
      return;
    }
    // The token and its lifetime into the auth client's memory (P-08-T11).
    setPortalSession(answer);
    if (invitationToken !== undefined && invite !== null && !accepted.current) {
      await accept();
      return;
    }
    onSignedIn?.(answer.landing ?? "none");
  };

  /** d, after the code: the invitee's own session accepts, with the terms version shown. */
  const accept = async (): Promise<void> => {
    const bearer = portalAccessToken();
    if (invitationToken === undefined || invite === null || bearer === null) return;
    try {
      const done = await invitation.accept(
        {
          token: invitationToken,
          ...(invite.terms_version == null ? {} : { terms_version: invite.terms_version }),
        },
        bearer,
      );
      accepted.current = true;
      const next = done.session;
      if (next != null && next.state !== "signed_in") {
        await finish(next); // the new access asks for the second step (P-08-T17)
        return;
      }
      onSignedIn?.(next?.landing ?? "none");
    } catch {
      setStep("invalid");
    }
  };

  /** c: the authenticator's code, or a backup code, with "trust this device". */
  const secondStep = async (): Promise<void> => {
    if (mfaToken === null) return;
    setBusy(true);
    setFailure(null);
    try {
      const answer = await signIn.mfa({
        mfa_token: mfaToken,
        ...(useBackup ? { backup_code: backupCode.trim() } : { totp }),
        trust_device: trust,
      });
      await finish(answer);
    } catch (error) {
      fail(failureOf(error));
    } finally {
      setBusy(false);
    }
  };

  /** c′: the first code enrols the factor; the backup codes come back once. */
  const verifySetup = async (digits: string): Promise<void> => {
    if (mfaToken === null || digits.length !== 6) return;
    setBusy(true);
    setFailure(null);
    try {
      const done = await signIn.mfaSetupVerify(mfaToken, digits);
      setMfaToken(null);
      setBackupCodes(done.backup_codes);
      setAfterCodes(done.session);
      setStep("codes");
    } catch (error) {
      fail(failureOf(error));
    } finally {
      setBusy(false);
    }
  };

  /** Leave the backup codes: they are dropped from memory and never drawn again. */
  const leaveCodes = async (): Promise<void> => {
    const next = afterCodes;
    setBackupCodes(null);
    setAfterCodes(null);
    setStep("done"); // the codes are gone from the page and from memory
    if (next !== null) await finish(next);
  };

  // c′ opens: ask once per token for the authenticator's key.
  useEffect(() => {
    if (step !== "setup" || mfaToken === null || setupAsked.current === mfaToken) return;
    setupAsked.current = mfaToken;
    void signIn
      .mfaSetup(mfaToken)
      .then(setSetupKey)
      .catch((error: unknown) => {
        fail(failureOf(error));
      });
  }, [step, mfaToken]);

  // d opens: the invitation's preview, or the one answer every failure gets.
  useEffect(() => {
    if (invitationToken === undefined) return;
    if (invitationToken === "") {
      setStep("invalid"); // /accept without a token: the same answer as any bad one
      return;
    }
    setStep("invite");
    void invitation
      .preview(invitationToken)
      .then((found) => {
        setInvite(found);
        setEmail(found.invitee_email);
      })
      .catch(() => {
        setStep("invalid");
      });
  }, [invitationToken]);

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
      : (failure.code === "code_mismatch" || failure.code === "mfa_mismatch") &&
          failure.triesLeft !== undefined
        ? COPY.f.helper(failure.triesLeft)
        : failure.code === "mfa_expired"
          ? COPY.c.expired
          : failure.code === "mfa_unavailable"
            ? COPY.c.unavailable
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
  } else if (step === "second") {
    const invalid = failure?.code === "mfa_mismatch";
    card = (
      <AuthCard
        brand="header"
        fluid={mobile}
        title={COPY.c.title}
        lead={useBackup ? COPY.c.backupBody : COPY.c.body}
        footer={footer}
      >
        {useBackup ? (
          <label className="flex flex-col gap-[6px]">
            <span className="text-dense text-ink-2">{COPY.c.backupField}</span>
            <input
              type="text"
              name="backup-code"
              autoComplete="one-time-code"
              autoCapitalize="characters"
              spellCheck={false}
              value={backupCode}
              aria-invalid={invalid}
              aria-describedby={helperId}
              onChange={(e) => {
                setBackupCode(e.target.value);
                if (failure !== null) setFailure(null);
              }}
              className={cn(
                AUTH_FIELD,
                "h-[40px] rounded-pill px-[16px] font-mono tabular-nums inset-shadow-hair",
                invalid && "inset-ring-1 inset-ring-red-ink",
              )}
            />
          </label>
        ) : (
          <CodeInput
            value={totp}
            onChange={(v) => {
              setTotp(v);
              if (failure !== null) setFailure(null);
            }}
            onComplete={() => undefined}
            label={COPY.c.code}
            autoFocus
            gap={mobile ? 6 : 8}
            compact={mobile}
            invalid={invalid}
            describedBy={helperId}
          />
        )}
        <Helper id={helperId} text={words} />
        <div className="flex min-h-[34px] items-center justify-between gap-[12px]">
          <span id={`${helperId}-trust`} className="text-dense text-ink">
            {COPY.c.trust}
          </span>
          <Toggle
            checked={trust}
            onChange={setTrust}
            label={COPY.c.trust}
            aria-labelledby={`${helperId}-trust`}
          />
        </div>
        {primary(
          <AuthButton
            disabled={busy || (useBackup ? backupCode.trim().length < 16 : totp.length !== 6)}
            onClick={() => void secondStep()}
          >
            {COPY.c.verify}
          </AuthButton>,
        )}
        <button
          type="button"
          onClick={() => {
            setUseBackup(!useBackup);
            setFailure(null);
          }}
          className="inline-flex min-h-[24px] items-center self-center text-dense font-medium text-ink"
        >
          {useBackup ? COPY.c.useApp : COPY.c.backup}
        </button>
      </AuthCard>
    );
  } else if (step === "setup") {
    const invalid = failure?.code === "mfa_mismatch";
    card = (
      <AuthCard
        brand="header"
        fluid={mobile}
        title={COPY.setup.title}
        lead={named ? COPY.setup.body(firm) : COPY.setup.bodyNeutral}
        footer={footer}
      >
        {setupKey === null ? (
          <Spinner label={COPY.setup.title} size={12} showLabel={false} />
        ) : (
          <div className="flex flex-col gap-[8px] rounded-[10px] bg-nested p-[14px]">
            <a
              href={setupKey.otpauth_uri}
              className="inline-flex min-h-[24px] items-center text-dense font-medium text-ink"
            >
              {COPY.setup.open}
            </a>
            <span className="text-meta text-ink-3">{COPY.setup.key}</span>
            <code
              data-testid="manual-key"
              className="select-all break-all text-dense tabular-nums text-ink"
            >
              {setupKey.manual_key}
            </code>
          </div>
        )}
        <CodeInput
          value={totp}
          onChange={(v) => {
            setTotp(v);
            if (failure !== null) setFailure(null);
          }}
          onComplete={(v) => void verifySetup(v)}
          label={COPY.c.code}
          autoFocus={false}
          gap={mobile ? 6 : 8}
          compact={mobile}
          invalid={invalid}
          describedBy={helperId}
        />
        <Helper id={helperId} text={words} />
        {primary(
          <AuthButton
            disabled={busy || setupKey === null || totp.length !== 6}
            onClick={() => void verifySetup(totp)}
          >
            {COPY.setup.verify}
          </AuthButton>,
        )}
      </AuthCard>
    );
  } else if (step === "codes") {
    card = (
      <AuthCard
        brand="header"
        fluid={mobile}
        title={COPY.setup.codesTitle}
        lead={COPY.setup.codesBody}
        footer={footer}
      >
        <ul
          aria-label={COPY.setup.codesList}
          className="grid grid-cols-2 gap-[8px] rounded-[10px] bg-nested p-[14px]"
        >
          {(backupCodes ?? []).map((c) => (
            <li key={c} className="text-dense tabular-nums text-ink">
              {c}
            </li>
          ))}
        </ul>
        <div className="flex min-h-[34px] items-center justify-between gap-[12px]">
          <span id={`${helperId}-saved`} className="text-dense text-ink">
            {COPY.setup.saved}
          </span>
          <Toggle
            checked={saved}
            onChange={setSaved}
            label={COPY.setup.saved}
            aria-labelledby={`${helperId}-saved`}
          />
        </div>
        {primary(
          <AuthButton disabled={!saved || busy} onClick={() => void leaveCodes()}>
            {COPY.setup.done}
          </AuthButton>,
        )}
      </AuthCard>
    );
  } else if (step === "invite") {
    const delegated =
      invite?.access.kind === "delegate" &&
      invite.access.item_count != null &&
      invite.organisation_name != null;
    const inviter = invite?.firm_name ?? firm;
    card = (
      <AuthCard
        brand="header"
        fluid={mobile}
        title={COPY.d.title(firm === "" ? inviter : firm)}
        lead={
          invite === null
            ? undefined
            : delegated
              ? COPY.d.body(
                  invite.firm_name,
                  invite.access.scope_label,
                  invite.organisation_name ?? "",
                  invite.access.item_count ?? 0,
                )
              : COPY.d.bodyScope(invite.firm_name, invite.access.scope_label)
        }
        footer={footer}
      >
        {invite === null ? (
          <Spinner label={COPY.d.accept} size={12} showLabel={false} />
        ) : (
          <>
            <label className="relative flex items-center">
              <span className="sr-only">{COPY.d.email}</span>
              <Icon
                name="mail"
                size={14}
                className="pointer-events-none absolute left-[14px] text-ink-3"
              />
              <input
                type="email"
                name="email"
                value={invite.invitee_email}
                readOnly
                aria-readonly="true"
                className={cn(
                  AUTH_FIELD,
                  "h-[40px] rounded-pill pl-[36px] text-ink-2 inset-shadow-hair",
                )}
              />
            </label>
            <dl className="flex flex-col">
              {invite.invitee_name != null && (
                <Kv term={COPY.d.name} value={invite.invitee_name} />
              )}
              {invite.organisation_name != null && (
                <Kv term={COPY.d.organization} value={invite.organisation_name} />
              )}
              <Kv
                term={COPY.d.access}
                value={
                  invite.access.kind === "delegate" ? COPY.d.delegated : invite.access.scope_label
                }
              />
            </dl>
            <div className="flex min-h-[34px] items-center justify-between gap-[12px]">
              <span id={`${helperId}-terms`} className="text-dense text-ink-2">
                {COPY.d.agree}{" "}
                {invite.terms_url == null ? (
                  <span className="font-medium text-ink">{COPY.d.terms(firm || inviter)}</span>
                ) : (
                  <a
                    href={invite.terms_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex min-h-[24px] items-center font-medium text-ink"
                  >
                    {COPY.d.terms(firm || inviter)}
                    <span aria-hidden="true" className="ml-[4px] text-ink-3">
                      →
                    </span>
                  </a>
                )}
              </span>
              <Toggle
                checked={terms}
                onChange={setTerms}
                label={`${COPY.d.agree} ${COPY.d.terms(firm || inviter)}`}
                aria-labelledby={`${helperId}-terms`}
              />
            </div>
            {words !== null && <Helper id={helperId} text={words} />}
            {primary(
              <AuthButton
                disabled={!terms || busy}
                onClick={() => void start(invite.invitee_email)}
              >
                {COPY.d.accept}
              </AuthButton>,
            )}
          </>
        )}
      </AuthCard>
    );
  } else if (step === "done") {
    card = (
      <AuthCard brand="header" fluid={mobile} title={COPY.c.title} footer={footer}>
        <Spinner label={COPY.c.title} size={12} showLabel={false} />
      </AuthCard>
    );
  } else {
    // An invitation that can't be used: one answer for every failure (no oracle).
    card = (
      <AuthCard
        brand="header"
        fluid={mobile}
        tile={{ icon: "clock", tone: "neutral" }}
        title={COPY.d.invalidTitle}
        lead={named ? COPY.d.invalid(firm) : COPY.d.invalidNeutral}
        footer={footer}
      />
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

/** d's 34 px key-value rows: Name, Organization, Access. */
function Kv({ term, value }: { term: string; value: string }): JSX.Element {
  return (
    <div className="flex min-h-[34px] items-center justify-between gap-[12px] border-b-[0.5px] border-hair last:border-b-0">
      <dt className="text-dense text-ink-3">{term}</dt>
      <dd className="text-right text-dense font-medium text-ink">{value}</dd>
    </div>
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
