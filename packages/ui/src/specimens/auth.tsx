import { type JSX, useState } from "react";
import { PortalBrandProvider, type SignInMethod } from "../brand";
import { HumanAction } from "../attribution";
import { Checkbox } from "../components/toggles";
import { Fieldset } from "../components/fieldset";
import { StatusDisc } from "../components/status";
import { amount, parseDecimal } from "../format";
import { Icon } from "../icons";
import {
  AUTH_FIELD,
  AuthButton,
  AuthCard,
  AuthChoices,
  AuthFooter,
  AuthFrame,
  AuthPage,
  CodeInput,
} from "../templates/auth-card";
import { Artboard, BRIGHTWATER_BRAND } from "./portal";

// T15 AuthCard (F-05-T37): T15a to T15c (Wave 0 - Foundations `T15`) and TPL-15a to TPL-15j
// (Wave 0 - Templates `TP15`): Jonah Feld's passwordless sign-in for the Feld Household and two
// customers' balance confirmations for the Granite Peak audit, at 1400 and 390. Every string is the
// canvas's own; the second steps render from the brand's sign-in methods; the confirmation's
// difference is computed in cents, never in floating point.

const BRAND = BRIGHTWATER_BRAND;
/** The people who act on these pages: Send is a human verb (INV-1), so its controls are
 * HumanActions for a named person. */
const JONAH = { kind: "human", name: "Jonah Feld" } as const;
const DANA = { kind: "human", name: "Dana Whitley" } as const;
const WIDE = "w-full";
const SECURE_LINE = "Brightwater Hale uses secure sign-in. We’ll never ask for your password.";

/** The second steps' labels (TPL-15c); which ones show comes from the brand. */
const SECOND_STEP: Partial<Record<SignInMethod, string>> = {
  sms_code: "Text a code to •••-•••-0142",
  passkey: "Use a passkey on this device",
};

function Branded({ children }: { children: JSX.Element }): JSX.Element {
  return <PortalBrandProvider brand={BRAND}>{children}</PortalBrandProvider>;
}

// ---- T15 --------------------------------------------------------------------------------------

function T15SignIn(): JSX.Element {
  const [email, setEmail] = useState("dana.whitley@gmail.com");
  return (
    <AuthCard
      brand="inside"
      title="Sign in to Brightwater Hale"
      lead="Your client portal for documents, questions and signatures."
      footer={<AuthFooter dots={false} />}
    >
      <label className="flex flex-col gap-[6px] text-left">
        <span className="text-dense text-ink-2">Email</span>
        <input
          className={AUTH_FIELD}
          value={email}
          aria-label="Email"
          onChange={(e) => {
            setEmail(e.target.value);
          }}
        />
      </label>
      <AuthButton>Continue</AuthButton>
      <div className="flex items-center gap-[10px] text-meta text-ink-3">
        <span className="h-px flex-1 hairline-t" />
        or
        <span className="h-px flex-1 hairline-t" />
      </div>
      <AuthButton kind="secondary" icon="mail">
        Email Me a Sign-in Link
      </AuthButton>
    </AuthCard>
  );
}

function T15Code(): JSX.Element {
  const [code, setCode] = useState("481");
  return (
    <AuthCard
      brand="inside"
      title="Check your email"
      lead="We sent a 6-digit code to d•••@gmail.com."
      footer={<AuthFooter dots={false} />}
    >
      <CodeInput value={code} onChange={setCode} label="Verification code" forceFocus />
      <AuthButton disabled={code.length < 6}>Verify</AuthButton>
      <button type="button" className="self-center text-body font-medium hover:underline">
        Resend code <span className="text-ink-3">›</span>
      </button>
    </AuthCard>
  );
}

const CP2000_FACTS = [
  ["Notice date", "August 24, 2026"],
  ["Proposed additional tax", "412"],
  ["Respond by", "September 23, 2026"],
] as const;

function T15Page(): JSX.Element {
  const [pick, setPick] = useState<string | null>("agree");
  const [sent, setSent] = useState(false);
  return (
    <AuthPage
      letterhead={{
        name: "Brightwater Hale LLP",
        line: "1700 Lincoln Street, Suite 2100 · Denver, CO 80203",
      }}
      title="IRS Notice CP2000 for your 2024 return"
      footer={<AuthFooter dots={false} />}
    >
      <p className="text-body leading-[1.55]">
        Marcus and Dana, the IRS sent a CP2000 notice proposing changes to your 2024 return. It
        says a 1099-INT from Bellco Credit Union was not reported. We checked the notice against
        your return and the forms you uploaded.
      </p>
      <dl className="overflow-hidden rounded-nested shadow-e1">
        {CP2000_FACTS.map(([k, v]) => (
          <div
            key={k}
            className="flex h-[34px] items-center justify-between px-[12px] text-body hairline-t first:border-t-0"
          >
            <dt className="text-ink-2">{k}</dt>
            <dd className="font-medium tabular-nums">{v}</dd>
          </div>
        ))}
      </dl>
      <span className="text-section">How should we respond?</span>
      <AuthChoices
        label="How should we respond?"
        rows="tinted"
        value={pick}
        onChange={(v) => {
          setPick(v);
          setSent(false);
        }}
        options={[
          {
            value: "agree",
            label: "I agree with the changes",
            detail: "We’ll sign the response and arrange payment of 412 plus interest.",
          },
          {
            value: "part",
            label: "I agree with part of it",
            detail: "Tell us which items are right and we’ll answer the rest.",
          },
          {
            value: "disagree",
            label: "I disagree",
            detail: "We’ll write to the IRS with your 2024 Bellco statement as support.",
          },
        ]}
      />
      <textarea
        rows={3}
        placeholder="Anything we should know? (optional)"
        aria-label="Note for Brightwater Hale"
        className="min-h-[76px] w-full resize-none rounded-nested bg-nested px-[12px] py-[9px] text-body outline-none placeholder:text-ink-3 focus-visible:inset-ring-1 focus-visible:inset-ring-stroke"
      />
      <div className="flex items-center justify-between gap-[12px]">
        <span className={sent ? "text-dense text-green-ink" : "text-dense text-ink-3"}>
          {sent
            ? "Brightwater Hale has your response and will follow up by email."
            : "Samuel Ito reviews your response before anything goes to the IRS."}
        </span>
        {sent ? (
          <span className="inline-flex h-[36px] items-center rounded-pill bg-nested px-[18px] text-btn text-ink-4">
            Sent
          </span>
        ) : (
          <HumanAction
            verb="Send"
            object="Response"
            actor={DANA}
            size="xl"
            disabled={pick === null}
            onClick={() => {
              setSent(true);
            }}
          />
        )}
      </div>
    </AuthPage>
  );
}

/** T15a to T15c (the T15 handoff). */
export function T15Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      <Artboard
        id="t15a"
        badge="T15a"
        name="Sign in"
        note="Dana Whitley signs in to the Brightwater Hale portal"
      >
        <Branded>
          <AuthFrame layout="card" frame>
            <T15SignIn />
          </AuthFrame>
        </Branded>
      </Artboard>
      <Artboard
        id="t15b"
        badge="T15b"
        name="Code"
        note="Three of six digits entered; Verify waits for all six"
      >
        <Branded>
          <AuthFrame layout="card" frame>
            <T15Code />
          </AuthFrame>
        </Branded>
      </Artboard>
      <Artboard
        id="t15c"
        badge="T15c"
        name="Single page · POR-17"
        note="The 720 CP2000 response page: letterhead, statement and response form"
      >
        <Branded>
          <AuthFrame layout="page" frame>
            <T15Page />
          </AuthFrame>
        </Branded>
      </Artboard>
    </div>
  );
}

// ---- TPL-15: sign-in --------------------------------------------------------------------------

type Step = "invite" | "code" | "second" | "expired";

function SignIn({
  start,
  code: startCode = "",
  mobile = false,
}: {
  start: Step;
  code?: string;
  mobile?: boolean;
}): JSX.Element {
  const [step, setStep] = useState<Step>(start);
  const [code, setCode] = useState(startCode);
  const methods = BRAND.signInMethods.flatMap((m) => {
    const label = SECOND_STEP[m];
    return label === undefined ? [] : [{ value: m, label }];
  });
  const [method, setMethod] = useState<string>(methods[0]?.value ?? "");
  const [remember, setRemember] = useState(true);
  const footer = <AuthFooter line={SECURE_LINE} />;
  const shared = { fluid: mobile, footer };
  if (step === "invite") {
    return (
      <AuthCard
        {...shared}
        title="Welcome, Jonah"
        lead="Kevin Osei invited you to Brightwater Hale’s secure client portal for the Feld Household."
      >
        <div className="flex flex-col gap-[6px]">
          <span className="text-dense text-ink-2">Email</span>
          <span
            className={`${AUTH_FIELD} flex items-center justify-between inset-ring-[0.5px] inset-ring-hair`}
          >
            <span>jonah.feld@example.com</span>
            <Icon name="lock" size={12} className="text-ink-3" />
          </span>
        </div>
        <HumanAction
          verb="Send"
          object="me a code"
          actor={JONAH}
          size="xl"
          className={WIDE}
          onClick={() => {
            setCode("");
            setStep("code");
          }}
        />
      </AuthCard>
    );
  }
  if (step === "code") {
    return (
      <AuthCard
        {...shared}
        title="Check your email"
        lead="We sent a 6-digit code to jonah.feld@example.com. It expires in 10 minutes."
      >
        <CodeInput
          value={code}
          onChange={setCode}
          label="6-digit code"
          forceFocus
          gap={mobile ? 6 : 8}
        />
        <span className="text-dense text-ink-3">Resend code in 0:38</span>
        <AuthButton
          disabled={code.length < 6}
          onClick={() => {
            setStep("second");
          }}
        >
          Continue
        </AuthButton>
      </AuthCard>
    );
  }
  if (step === "second") {
    return (
      <AuthCard {...shared} title="One more step" lead="Choose how to confirm it’s you.">
        <AuthChoices
          label="How to confirm it’s you"
          options={methods}
          value={method}
          onChange={setMethod}
        />
        <Checkbox
          label="Remember this device for 30 days"
          showLabel
          checked={remember}
          onChange={setRemember}
        />
        <AuthButton title="Opens POR-02 · portal home">Continue</AuthButton>
      </AuthCard>
    );
  }
  return (
    <AuthCard
      {...shared}
      title="This invite link has expired"
      lead="Invites last 14 days. We can send you a new one."
      tile={{ icon: "clock", tone: "red" }}
    >
      <HumanAction
        verb="Send"
        object="a new invite link"
        actor={JONAH}
        size="xl"
        className={WIDE}
      />
      <button type="button" className="self-center text-body font-medium hover:underline">
        Contact Brightwater Hale
      </button>
    </AuthCard>
  );
}

// ---- TPL-15: confirmation response ------------------------------------------------------------

interface Customer {
  name: string;
  ref: string;
  /** The balance per the client's records, a decimal string. */
  balance: string;
  who: readonly [string, string, string, string];
  verified: boolean;
  authorized: boolean;
  amount?: string;
  explanation?: string;
  file?: string;
}

const SUMMIT: Customer = {
  name: "Summit Trail Outfitters",
  ref: "GPO-AR-0412",
  balance: "412600.00",
  who: [
    "Rachel Imholt",
    "Accounts Payable Manager",
    "Summit Trail Outfitters",
    "r.imholt@example.com",
  ],
  verified: true,
  authorized: true,
};

const ALPINE: Customer = {
  name: "Alpine Ridge Sports",
  ref: "GPO-AR-0413",
  balance: "286900.00",
  who: ["", "", "Alpine Ridge Sports", ""],
  verified: false,
  authorized: false,
  amount: "282,600.00",
  explanation: "Credit memo CM-0628 for $4,300.00 dated June 28, 2026 (returned goods).",
  file: "CM-0628.pdf",
};

/** The difference between two decimal strings, in whole cents (code computes; ADR-050). */
function difference(a: string, b: string): string | null {
  const clean = b.replace(/[$,\s]/g, "");
  if (!/^\d+(\.\d{1,2})?$/.test(clean)) return null;
  const cents = (v: string): bigint => {
    const { units, scale } = parseDecimal(v);
    return scale >= 2 ? units / 10n ** BigInt(scale - 2) : units * 10n ** BigInt(2 - scale);
  };
  const d = cents(a) - cents(clean);
  const abs = d < 0n ? -d : d;
  return `${String(abs / 100n)}.${String(abs % 100n).padStart(2, "0")}`;
}

const DETAILS = [
  ["Name", "Your name"],
  ["Title", "Your title"],
  ["Company", "Company name"],
  ["Work email", "name@company.com"],
] as const;

function Confirmation({
  customer,
  start = "agree",
  stage = "form",
  mobile = false,
}: {
  customer: Customer;
  start?: "agree" | "dis";
  stage?: "form" | "submitted" | "answered";
  mobile?: boolean;
}): JSX.Element {
  const [resp, setResp] = useState<string>(start);
  const [who, setWho] = useState<string[]>([...customer.who]);
  const [amt, setAmt] = useState(customer.amount ?? "");
  const [authorized, setAuthorized] = useState(customer.authorized);
  const [verified] = useState(customer.verified);
  const [submitted, setSubmitted] = useState(stage === "submitted");
  const diff = difference(customer.balance, amt);
  const ok = verified && authorized;
  const contact = "Questions about this request: confirmations@brightwaterhale.com";
  const letterhead = {
    name: "Brightwater Hale LLP",
    line: "Certified Public Accountants · Chicago · Denver · New York",
    reference: `Reference ${customer.ref} · October 1, 2026`,
  };
  const page = (body: JSX.Element): JSX.Element => (
    <AuthPage fluid={mobile} letterhead={letterhead} title="Confirmation of account balance" legal>
      {body}
    </AuthPage>
  );
  if (stage === "answered") {
    return page(
      <div className="flex flex-col items-start gap-[8px]">
        <span className="inline-flex size-[34px] items-center justify-center rounded-tile-lg bg-nested text-ink-2">
          <Icon name="circle-check" size={17} />
        </span>
        <span className="text-btn-lg font-medium">
          This confirmation has already been answered
        </span>
        <span className="text-dense leading-[1.5] text-ink-2">
          {`Brightwater Hale received a response to ${customer.ref} on Oct 1, 2026. If something has changed, contact the firm directly.`}
        </span>
        <button type="button" className="text-body font-medium hover:underline">
          Contact Brightwater Hale<span className="text-ink-3"> →</span>
        </button>
      </div>,
    );
  }
  if (submitted) {
    const rows = [
      ["Reference", customer.ref],
      ["Response", resp === "dis" ? `Disagree · ${amount(diff ?? "").text} difference` : "Agree"],
      ["Received", "Oct 1, 2026, 10:15 AM CT"],
      [
        "Responder",
        `${who[0] === "" || who[0] === undefined ? "Respondent" : who[0]}, verified email`,
      ],
    ] as const;
    return page(
      <div className="flex flex-col gap-[14px]">
        <div className="flex items-center gap-[10px]">
          <span className="inline-flex size-[34px] items-center justify-center rounded-tile-lg bg-green text-on-dark">
            <Icon name="check" size={17} strokeWidth={2.2} />
          </span>
          <span className="text-btn-lg font-medium">Thank you. Your response was received.</span>
        </div>
        <dl className="overflow-hidden rounded-nested shadow-e1">
          {rows.map(([k, v]) => (
            <div
              key={k}
              className="flex min-h-[36px] items-center justify-between gap-[12px] px-[12px] text-body hairline-t first:border-t-0"
            >
              <dt className="text-ink-2">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
        <span className="text-meta text-ink-3">{contact}</span>
      </div>,
    );
  }
  return page(
    <>
      <div className="flex flex-col gap-[4px] rounded-nested bg-shell px-[14px] py-[12px] text-dense leading-[1.55] inset-ring-[0.5px] inset-ring-hair">
        <span>
          Granite Peak Outdoor Supply, Inc. authorizes you to confirm the information below
          directly to its auditors, Brightwater Hale LLP.
        </span>
        <span className="text-ink-2">Luis Ferrante, Chief Financial Officer</span>
      </div>
      <div className="flex flex-col gap-[2px]">
        <span className="text-body leading-[1.55]">
          {`Our client’s records show the following balance owed by ${customer.name} at June 30, 2026:`}
        </span>
        <span
          data-amount="balance"
          className={mobile ? "text-[20px] tabular-nums" : "text-kpi tabular-nums"}
        >
          {amount(customer.balance).text}
        </span>
        <span className="text-pill font-normal text-ink-3">
          This is not a request for payment. Please do not send payment to Brightwater Hale.
        </span>
      </div>
      <Fieldset title="Your response" flush className="mb-0">
        <AuthChoices
          label="Your response"
          rows="fieldset"
          value={resp}
          onChange={setResp}
          options={[
            { value: "agree", label: "Agree — this balance is correct" },
            { value: "dis", label: "Disagree — our records show a different amount" },
          ]}
        />
        {resp === "dis" && (
          <div className="flex flex-col gap-[10px] bg-card px-[14px] py-[12px]">
            <label className="grid grid-cols-[160px_1fr] items-center gap-[12px] text-body">
              <span className="text-ink-2">Amount per your records</span>
              <span
                className={`${AUTH_FIELD} flex items-center gap-[6px] focus-within:inset-ring-1 focus-within:inset-ring-stroke`}
              >
                <span className="text-ink-3">$</span>
                <input
                  value={amt}
                  aria-label="Amount per your records"
                  inputMode="decimal"
                  onChange={(e) => {
                    setAmt(e.target.value);
                  }}
                  className="min-w-0 flex-1 bg-transparent tabular-nums outline-none"
                />
              </span>
            </label>
            <div className="grid grid-cols-[160px_1fr] items-center gap-[12px] text-body">
              <span className="text-ink-2">Difference</span>
              <span data-amount="difference" className="font-medium text-red-ink tabular-nums">
                {diff === null ? "—" : amount(diff).text}
              </span>
            </div>
            <label className="grid grid-cols-[160px_1fr] items-start gap-[12px] text-body">
              <span className="pt-[8px] text-ink-2">Explanation</span>
              <textarea
                rows={3}
                aria-label="Explanation"
                defaultValue={customer.explanation}
                className="w-full resize-none rounded-nested bg-nested px-[12px] py-[8px] text-body outline-none focus-visible:inset-ring-1 focus-visible:inset-ring-stroke"
              />
            </label>
            {customer.file !== undefined && (
              <span className="ml-[172px] inline-flex h-[28px] w-fit items-center gap-[6px] rounded-pill bg-card pr-[12px] pl-[10px] text-body shadow-e1">
                <Icon name="file-text" size={13} className="text-ink-3" />
                {customer.file}
              </span>
            )}
          </div>
        )}
      </Fieldset>
      <Fieldset title="Your details" className="mb-0">
        <div className="flex flex-col gap-[8px]">
          {DETAILS.map(([k, ph], i) => (
            <label
              key={k}
              className={
                mobile
                  ? "flex flex-col gap-[4px] text-body"
                  : "grid grid-cols-[120px_1fr] items-center gap-[12px] text-body"
              }
            >
              <span className="text-ink-2">{k}</span>
              <input
                className={AUTH_FIELD}
                value={who[i] ?? ""}
                placeholder={ph}
                aria-label={k}
                onChange={(e) => {
                  const next = [...who];
                  next[i] = e.target.value;
                  setWho(next);
                }}
              />
            </label>
          ))}
          <div className={mobile ? "" : "pl-[132px]"}>
            {verified ? (
              <span className="flex items-center gap-[6px] text-dense font-medium text-green-ink">
                <StatusDisc state="done" size={15} />
                Verified 10:14 AM
              </span>
            ) : (
              <button
                type="button"
                disabled={!(who[3] ?? "").includes("@")}
                className="inline-flex h-[28px] items-center rounded-pill bg-card px-[12px] text-dense shadow-e1 hover:bg-nav-fill disabled:bg-nested disabled:text-ink-4 disabled:shadow-none"
              >
                Verify email
              </button>
            )}
          </div>
          <Checkbox
            label={`I am authorized to respond for ${customer.name}.`}
            showLabel
            checked={authorized}
            onChange={setAuthorized}
          />
        </div>
      </Fieldset>
      <button
        type="button"
        className="flex h-[72px] w-full items-center justify-center gap-[8px] rounded-pane bg-nested text-body text-ink-2 inset-ring-1 inset-ring-hair hover:inset-ring-stroke"
      >
        <Icon name="upload" size={15} />
        Attach support (optional)
      </button>
      <div
        className={
          mobile
            ? "flex flex-col items-stretch gap-[10px]"
            : "flex items-center justify-between gap-[12px]"
        }
      >
        <button
          type="button"
          disabled={!ok}
          title={ok ? undefined : "Verify your work email and confirm your authority first"}
          onClick={() => {
            if (ok) setSubmitted(true);
          }}
          className="inline-flex h-[36px] items-center justify-center rounded-pill bg-espresso px-[18px] text-btn-lg font-medium text-on-dark shadow-cta hover:bg-cta-hover disabled:bg-nested disabled:text-ink-4 disabled:shadow-none"
        >
          Submit response
        </button>
        <span className="text-meta text-ink-3">{contact}</span>
      </div>
    </>,
  );
}

/** TPL-15a to TPL-15j (Wave 0 - Templates `TP15`). */
export function Tpl15Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      <Artboard
        id="tpl-15a"
        badge="TPL-15a"
        name="Invite acceptance"
        note="Kevin Osei’s invite for the Feld Household"
      >
        <Branded>
          <AuthFrame layout="card" frame top>
            <SignIn start="invite" />
          </AuthFrame>
        </Branded>
      </Artboard>
      <Artboard
        id="tpl-15b"
        badge="TPL-15b"
        name="Email code"
        note="Three of six digits; Continue waits for all six"
      >
        <Branded>
          <AuthFrame layout="card" frame top>
            <SignIn start="code" code="729" />
          </AuthFrame>
        </Branded>
      </Artboard>
      <Artboard
        id="tpl-15c"
        badge="TPL-15c"
        name="Second step"
        note="Text a code or use a passkey; no password"
      >
        <Branded>
          <AuthFrame layout="card" frame top>
            <SignIn start="second" />
          </AuthFrame>
        </Branded>
      </Artboard>
      <Artboard id="tpl-15d" badge="TPL-15d" name="Expired invite" note="Invites last 14 days">
        <Branded>
          <AuthFrame layout="card" frame top>
            <SignIn start="expired" />
          </AuthFrame>
        </Branded>
      </Artboard>
      <Artboard id="tpl-15e" badge="TPL-15e" name="390" note="Frame 2 on a phone">
        <Branded>
          <AuthFrame layout="mobile" frame>
            <SignIn start="code" code="729" mobile />
          </AuthFrame>
        </Branded>
      </Artboard>
      <Artboard
        id="tpl-15f"
        badge="TPL-15f"
        name="Confirmation · Agree"
        note="Summit Trail confirms $412,600.00"
      >
        <Branded>
          <AuthFrame layout="page" frame>
            <Confirmation customer={SUMMIT} />
          </AuthFrame>
        </Branded>
      </Artboard>
      <Artboard
        id="tpl-15g"
        badge="TPL-15g"
        name="Confirmation · Disagree"
        note="Alpine Ridge is $4,300.00 lower; Submit waits on verification"
      >
        <Branded>
          <AuthFrame layout="page" frame>
            <Confirmation customer={ALPINE} start="dis" />
          </AuthFrame>
        </Branded>
      </Artboard>
      <Artboard id="tpl-15h" badge="TPL-15h" name="Submitted" note="Lands in AUD-14 as Agrees">
        <Branded>
          <AuthFrame layout="page" frame>
            <Confirmation customer={SUMMIT} stage="submitted" />
          </AuthFrame>
        </Branded>
      </Artboard>
      <Artboard
        id="tpl-15i"
        badge="TPL-15i"
        name="Already answered"
        note="No form; an expired link reads the same way"
      >
        <Branded>
          <AuthFrame layout="page" frame>
            <Confirmation customer={SUMMIT} stage="answered" />
          </AuthFrame>
        </Branded>
      </Artboard>
      <Artboard id="tpl-15j" badge="TPL-15j" name="390" note="Frame 6 on a phone">
        <Branded>
          <AuthFrame layout="mobile" frame>
            <Confirmation customer={SUMMIT} mobile />
          </AuthFrame>
        </Branded>
      </Artboard>
    </div>
  );
}
