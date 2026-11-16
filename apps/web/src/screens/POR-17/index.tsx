import {
  type RespondentReceiptOut,
  type RespondentRequestOut,
  requestCode,
  submitResponse,
  uploadAttachment,
  verifyCode,
} from "@abacus/api-client";
import { respondentViewOptions } from "@abacus/api-client/query";
import {
  Button,
  CodeInput,
  EmptyState,
  ErrorState,
  Icon,
  Skeleton,
  Toggle,
  ValueRow,
  amount,
  bytes,
  longDate,
  parseDecimal,
  prose,
  time,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { COPY } from "./copy";

// POR-17 Confirmation response (S47 partials, TASK-8355; A-08-T19 backend, DEC-5325): the one
// page a confirmation respondent sees at `/confirm/<token>`, with no sign-in and no portal
// navigation. GET /v1/confirm/{token} gives `open` (the request), `answered` or the uniform
// `expired` (DV-7). The respondent agrees or states the difference (code computes it as they
// type, exactly), lists accounts (bank), verifies their email with a 6-digit code (the server
// sets the link cookie and returns the CSRF value), attaches support and attests; the receipt is
// state b. White-labelled: only the firm the API names, never the product.

const CSRF = "X-Abacus-CSRF";
const CELL =
  "h-[30px] w-full rounded-tile bg-transparent px-[6px] text-[12.5px] placeholder:text-ink-3 focus:bg-nested data-[amount]:text-right data-[amount]:tabular-nums";

/** a − b in cents, exactly; null while either is not a number. */
export function differenceOf(a: string, b: string): string | null {
  try {
    const cents = (v: string): bigint => {
      const s = parseDecimal(v);
      return s.scale <= 2
        ? s.units * 10n ** BigInt(2 - s.scale)
        : s.units / 10n ** BigInt(s.scale - 2);
    };
    if (a.trim() === "" || b.trim() === "") return null;
    const d = cents(a) - cents(b);
    const abs = d < 0n ? -d : d;
    return `${d < 0n ? "-" : ""}${String(abs / 100n)}.${String(abs % 100n).padStart(2, "0")}`;
  } catch {
    return null;
  }
}

function Card({ title, children }: { title?: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-pane bg-card px-[24px] py-[16px] shadow-e2">
      {title !== undefined && <h2 className="mb-[10px] text-[14px] font-medium">{title}</h2>}
      {children}
    </section>
  );
}

function Header({ firm, reference }: { firm?: string; reference?: string }): JSX.Element {
  return (
    <header className="flex h-[46px] items-center justify-between bg-card px-[16px] shadow-hair">
      <span className="text-[14px] font-medium">{firm ?? ""}</span>
      {reference !== undefined && (
        <span className="flex items-center gap-[6px] text-meta text-ink-3">
          <Icon name="lock" size={13} />
          {COPY.secure(reference)}
        </span>
      )}
    </header>
  );
}

function Page({
  firm,
  reference,
  children,
}: {
  firm?: string;
  reference?: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <div data-screen="POR-17" className="min-h-screen bg-shell">
      <Header
        {...(firm === undefined ? {} : { firm })}
        {...(reference === undefined ? {} : { reference })}
      />
      <main className="mx-auto flex max-w-[720px] flex-col gap-[12px] px-[16px] py-[20px]">
        {children}
      </main>
    </div>
  );
}

export function POR17({ token }: { token: string }): JSX.Element {
  const view = useQuery(respondentViewOptions({ path: { token } }));
  const [receipt, setReceipt] = useState<RespondentReceiptOut | null>(null);
  if (view.isError) {
    return (
      <Page>
        <ErrorState
          onRetry={() => {
            void view.refetch();
          }}
        />
      </Page>
    );
  }
  if (view.data === undefined) {
    return (
      <Page>
        <Skeleton className="h-[480px]" />
      </Page>
    );
  }
  const data = view.data;
  if (receipt !== null && data.request != null) {
    return <Submitted receipt={receipt} request={data.request} />;
  }
  if (data.state === "answered") {
    return (
      <Page>
        <Card>
          <EmptyState
            icon="circle-check"
            title={COPY.answered(longDate(data.answered_on ?? ""))}
          />
        </Card>
      </Page>
    );
  }
  if (data.state === "expired" || data.request == null) {
    return (
      <Page>
        <Card>
          <EmptyState icon="clock" title={COPY.expired.title}>
            {COPY.expired.body}
          </EmptyState>
        </Card>
      </Page>
    );
  }
  return <Open token={token} request={data.request} onSubmitted={setReceipt} />;
}

function Submitted({
  receipt,
  request,
}: {
  receipt: RespondentReceiptOut;
  request: RespondentRequestOut;
}): JSX.Element {
  const D = COPY.done;
  const given = receipt.respondent_balance ?? request.balance_per_client ?? "";
  const rows: [string, string][] = [
    [D.response, receipt.agrees ? D.agrees(prose(given)) : D.differs(prose(given))],
    [D.submitted, `${longDate(receipt.submitted_at)} · ${time(receipt.submitted_at)}`],
    [D.verified, receipt.verified_email],
    [D.reference, receipt.reference],
  ];
  return (
    <Page firm={request.firm_name} reference={request.reference}>
      <Card>
        <div className="flex flex-col items-center gap-[10px] py-[12px] text-center">
          <span className="flex size-[34px] items-center justify-center rounded-pill bg-green text-card">
            <Icon name="check" size={17} />
          </span>
          <p className="text-[15px] font-medium">{D.title(request.firm_name)}</p>
        </div>
        <dl className="mt-[8px] flex flex-col">
          {rows.map(([k, v]) => (
            <div key={k} className="flex h-[34px] items-center justify-between shadow-hair-b">
              <dt className="text-ink-2">{k}</dt>
              <dd className="tabular-nums">{v}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-[12px] text-meta text-ink-3">{D.close}</p>
      </Card>
    </Page>
  );
}

interface AccountRow {
  account: string;
  type: string;
  balance: string;
}

function Open({
  token,
  request,
  onSubmitted,
}: {
  token: string;
  request: RespondentRequestOut;
  onSubmitted: (receipt: RespondentReceiptOut) => void;
}): JSX.Element {
  const R = COPY.response;
  const W = COPY.who;
  const bank = request.type === "bank";
  const asOf = longDate(request.as_of);
  const client = request.client_name;
  const [agrees, setAgrees] = useState<boolean | null>(null);
  const [theirs, setTheirs] = useState("");
  const [explanation, setExplanation] = useState("");
  const [accounts, setAccounts] = useState<AccountRow[]>(
    request.list_every_account ? [{ account: "", type: "", balance: "" }] : [],
  );
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState(request.respondent_org);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [csrf, setCsrf] = useState<string | null>(null);
  const [attest, setAttest] = useState(false);
  const [files, setFiles] = useState<{ id: string; name: string; size: number }[]>([]);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const difference =
    agrees === false && request.balance_per_client !== null
      ? differenceOf(request.balance_per_client, theirs)
      : null;
  const ready =
    agrees !== null &&
    csrf !== null &&
    attest &&
    name.trim() !== "" &&
    company.trim() !== "" &&
    (agrees || bank || (difference !== null && explanation.trim() !== ""));

  const sendCode = async (): Promise<void> => {
    setFailed(false);
    try {
      await requestCode({ path: { token }, body: { email }, throwOnError: true });
      setCodeSent(true);
    } catch {
      setFailed(true);
    }
  };
  const verify = async (value: string): Promise<void> => {
    setFailed(false);
    try {
      const { data, response } = await verifyCode({
        path: { token },
        body: { code: value },
        throwOnError: true,
      });
      const value_ = response.headers.get(CSRF);
      if (data.verified && value_ !== null) setCsrf(value_);
      else setFailed(true);
    } catch {
      setFailed(true);
    }
  };
  const attach = async (file: File): Promise<void> => {
    if (csrf === null) return;
    setFailed(false);
    try {
      const { data } = await uploadAttachment({
        path: { token },
        query: { filename: file.name },
        body: file as never,
        bodySerializer: null,
        headers: { [CSRF]: csrf, "Content-Type": file.type || "application/octet-stream" },
        throwOnError: true,
      });
      setFiles((f) => [
        ...f,
        { id: data.attachment_id, name: data.file_name, size: data.size_bytes },
      ]);
    } catch {
      setFailed(true);
    }
  };
  const submit = async (): Promise<void> => {
    if (!ready) return;
    setBusy(true);
    setFailed(false);
    try {
      const { data } = await submitResponse({
        path: { token },
        headers: { [CSRF]: csrf },
        body: {
          agrees,
          attestation: true,
          respondent_name: name.trim(),
          respondent_title: title.trim() === "" ? null : title.trim(),
          respondent_company: company.trim(),
          explanation: explanation.trim() === "" ? null : explanation.trim(),
          ...(agrees || theirs.trim() === "" ? {} : { balances: [{ amount: theirs.trim() }] }),
          ...(bank
            ? {
                accounts: accounts
                  .filter((a) => a.account.trim() !== "" && a.balance.trim() !== "")
                  .map((a) => ({
                    description:
                      a.type.trim() === ""
                        ? a.account.trim()
                        : `${a.account.trim()} (${a.type.trim()})`,
                    balance: a.balance.trim(),
                  })),
              }
            : {}),
          attachment_ids: files.map((f) => f.id),
        },
        throwOnError: true,
      });
      onSubmitted(data);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  const fileSlot = (label: string): JSX.Element => (
    <label className="mt-[10px] flex h-[64px] items-center gap-[10px] rounded-card bg-nested px-[16px] text-ink-2">
      <Icon name="paperclip" size={14} />
      <span className="flex-1">
        {files.length === 0 ? label : files.map((f) => `${f.name} · ${bytes(f.size)}`).join(", ")}
      </span>
      <input
        type="file"
        className="sr-only"
        disabled={csrf === null}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file !== undefined) void attach(file);
        }}
      />
      <span className="rounded-pill bg-card px-[12px] py-[6px] text-ink shadow-e1">
        {R.chooseFile}
      </span>
    </label>
  );

  const tile = (value: boolean, label: string): JSX.Element => (
    <button
      type="button"
      aria-pressed={agrees === value}
      onClick={() => {
        setAgrees(value);
      }}
      className={
        agrees === value
          ? "flex h-[64px] flex-1 items-center gap-[8px] rounded-card bg-card px-[16px] text-left font-medium shadow-[inset_0_0_0_1.5px_var(--color-cta-deep)]"
          : "flex h-[64px] flex-1 items-center gap-[8px] rounded-card bg-card px-[16px] text-left font-medium shadow-e1"
      }
    >
      <span className="flex-1">{label}</span>
      {agrees === value && <Icon name="check" size={13} className="text-green" />}
    </button>
  );

  return (
    <Page firm={request.firm_name} reference={request.reference}>
      <Card>
        <p className="text-meta text-ink-3">{COPY.from(request.firm_name, client)}</p>
        <h1 className="mt-[6px] text-[16px] font-medium">
          {bank ? COPY.heading.bank(client, asOf) : COPY.heading.receivable(client, asOf)}
        </h1>
        <blockquote className="mt-[12px] border-l-2 border-stroke pl-[12px] text-para text-ink-2">
          <p>{request.authorization_text}</p>
          <p className="mt-[6px]">
            {COPY.authorized(request.authorized_by, client, longDate(request.authorized_on))}
          </p>
        </blockquote>
      </Card>

      <Card title={bank ? COPY.balancesTitle(client) : COPY.balanceTitle(client)}>
        {bank ? (
          <ul className="rounded-card shadow-e1">
            {request.client_accounts.map((a) => (
              <li
                key={a.description}
                className="flex h-[40px] items-center justify-between px-[16px] shadow-hair-b"
              >
                <span>{COPY.perClient(a.description, client)}</span>
                <span className="font-medium tabular-nums">{prose(a.balance_per_client)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <>
            <p className="text-[22px] tabular-nums">{prose(request.balance_per_client ?? "")}</p>
            {request.invoices.length > 0 && (
              <table className="mt-[10px] w-full text-[12.5px]">
                <thead>
                  <tr className="h-[28px] bg-band-hd text-th text-ink-2">
                    <th className="text-left font-normal">{COPY.table.invoice}</th>
                    <th className="text-left font-normal">{COPY.table.date}</th>
                    <th className="text-right font-normal">{COPY.table.amount}</th>
                  </tr>
                </thead>
                <tbody>
                  {request.invoices.map((inv) => (
                    <tr key={inv.number} className="h-[32px] shadow-hair-b">
                      <td>{inv.number}</td>
                      <td>{longDate(inv.invoice_date)}</td>
                      <td className="text-right tabular-nums">
                        {amount(inv.amount, "cents").text}
                      </td>
                    </tr>
                  ))}
                  <tr className="h-[32px] font-medium">
                    <td colSpan={2}>{COPY.table.total}</td>
                    <td className="text-right tabular-nums">
                      {amount(request.balance_per_client ?? "", "cents").text}
                    </td>
                  </tr>
                </tbody>
              </table>
            )}
          </>
        )}
        {bank && request.list_every_account && (
          <>
            <p className="mt-[12px] text-para text-ink-2">{COPY.listEvery(client, asOf)}</p>
            <div className="mt-[10px] rounded-card shadow-e1">
              <div className="grid h-[32px] grid-cols-[1fr_200px_160px_32px] items-center bg-band-hd px-[16px] text-th text-ink-2">
                <span>{COPY.accounts.account}</span>
                <span>{COPY.accounts.type}</span>
                <span className="text-right">{COPY.accounts.balanceAt(asOf)}</span>
                <span />
              </div>
              {accounts.map((a, i) => (
                <div
                  key={i}
                  className="grid grid-cols-[1fr_200px_160px_32px] items-center gap-[8px] px-[16px] py-[6px] shadow-hair-b"
                >
                  <input
                    className={CELL}
                    aria-label={COPY.accounts.account}
                    placeholder={COPY.accounts.accountPlaceholder}
                    value={a.account}
                    onChange={(e) => {
                      const v = e.target.value;
                      setAccounts((rows) =>
                        rows.map((r, j) => (j === i ? { ...r, account: v } : r)),
                      );
                    }}
                  />
                  <input
                    className={CELL}
                    aria-label={COPY.accounts.type}
                    placeholder={COPY.accounts.typePlaceholder}
                    value={a.type}
                    onChange={(e) => {
                      const v = e.target.value;
                      setAccounts((rows) => rows.map((r, j) => (j === i ? { ...r, type: v } : r)));
                    }}
                  />
                  <input
                    className={CELL}
                    aria-label={COPY.accounts.balanceAt(asOf)}
                    data-amount
                    inputMode="decimal"
                    placeholder="0.00"
                    value={a.balance}
                    onChange={(e) => {
                      const v = e.target.value;
                      setAccounts((rows) =>
                        rows.map((r, j) => (j === i ? { ...r, balance: v } : r)),
                      );
                    }}
                  />
                  <button
                    type="button"
                    aria-label={COPY.accounts.remove}
                    className="text-ink-3"
                    onClick={() => {
                      setAccounts((rows) => rows.filter((_, j) => j !== i));
                    }}
                  >
                    <Icon name="x" size={13} />
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="flex h-[40px] items-center gap-[6px] px-[16px]"
                onClick={() => {
                  setAccounts((rows) => [...rows, { account: "", type: "", balance: "" }]);
                }}
              >
                <Icon name="plus" size={13} />
                {COPY.accounts.add}
              </button>
            </div>
          </>
        )}
      </Card>

      <Card title={R.title}>
        <div className="flex gap-[12px]">
          {tile(true, bank ? R.agreesMany : R.agrees)}
          {tile(false, bank ? R.differsMany : R.differs)}
        </div>
        {agrees === false && !bank && (
          <div className="mt-[12px] flex flex-col gap-[8px]">
            <ValueRow kind="text" label={R.perOurRecords} value={theirs} onChange={setTheirs} />
            <ValueRow kind="value" label={R.difference}>
              <span className="text-amber-ink tabular-nums">
                {difference === null ? "" : prose(difference)}
              </span>
            </ValueRow>
            <ValueRow
              kind="paragraph"
              label={R.explain}
              value={explanation}
              onChange={setExplanation}
            />
          </div>
        )}
        {fileSlot(
          agrees === false && !bank
            ? R.attachSupport
            : bank
              ? R.attachBankStatement
              : R.attachStatement,
        )}
      </Card>

      <Card title={W.title}>
        <div className="flex flex-col gap-[6px]">
          <ValueRow
            kind="text"
            label={W.name}
            placeholder={W.namePlaceholder}
            value={name}
            onChange={setName}
          />
          <ValueRow kind="text" label={W.title_} value={title} onChange={setTitle} />
          <ValueRow kind="text" label={W.company} value={company} onChange={setCompany} />
          <ValueRow
            kind="text"
            label={W.email}
            value={email}
            readOnly={csrf !== null}
            onChange={setEmail}
          />
          <div className="flex items-center justify-end gap-[12px] px-[12px]">
            {codeSent && csrf === null && (
              <CodeInput
                value={code}
                onChange={setCode}
                onComplete={(v) => void verify(v)}
                label={W.code}
              />
            )}
            <Button
              size="sm"
              variant="secondary"
              disabled={email.trim() === "" || csrf !== null}
              onClick={() => void sendCode()}
            >
              {W.sendCode}
            </Button>
          </div>
          <label className="mt-[6px] flex items-center gap-[10px]">
            <Toggle checked={attest} onChange={setAttest} label={W.attest} />
            <span>{W.attest}</span>
          </label>
        </div>
      </Card>

      <div className="flex h-[60px] items-center justify-between rounded-pane bg-card px-[24px] shadow-e2">
        <p className="text-meta text-ink-3">{COPY.submitNote(request.firm_name, client)}</p>
        <Button disabled={!ready || busy} onClick={() => void submit()}>
          {COPY.submit}
        </Button>
      </div>
      {failed && <ErrorState className="py-[8px]" />}
      <p className="text-center text-meta text-ink-3">
        {request.firm_name} · {COPY.footer}
      </p>
    </Page>
  );
}
