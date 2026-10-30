import type {
  ConsentOut,
  TaxAuthorizationOut,
  TaxElectionOut,
  TaxProfileIdentityOut,
  TaxProfileOut,
  TranscriptComparisonOut,
  TranscriptOut,
} from "@abacus/api-client";
import {
  compareTranscriptMutation,
  latestComparisonQueryKey,
  latestComparisonOptions,
  listTranscriptsOptions,
  listTranscriptsQueryKey,
  taxProfileOptions,
} from "@abacus/api-client/query";
import {
  AgentText,
  Button,
  EmptyState,
  Icon,
  Pill,
  RecordCockpit,
  RegistryStatus,
  Segmented,
  Skeleton,
  StatusDisc,
  TallyPill,
  Tooltip,
  amount,
  date,
  time,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { MaskedTin, useClientRecord } from "../../domain/clients";
import { COPY } from "./copy";

// CLI-05 · Tax profile, authorizations & consents (T-01-T14, part 1; docs/screens/CLI-05.md):
// the T2 cockpit inside the client record (rail 330, canvas 1036, no dock). Built here: the rail
// rows with discs, the Open notices band (planned link), the Identity band (last four only, Reveal
// (logged) through P-07's service, re-masked after 10 s), the small Segmented, and the Consents
// section:
//
//   d  Whitley: Use · AI disclosure (§7216, 2 consents), Marcus ✓ Dana ✓, one sub-row per signed
//      document; Disclosure to offshore preparers "Not requested"
//   f  Ferris: the amber banner (Kai Ferris has not signed) with Resend…
//
// Part 2 (T-01-T34, fixture mode) adds:
//
//   b  Transcripts, none yet: "No transcripts yet." with Upload transcript… (the register and the
//      comparison, a, arrive with T-01-T43/T45's transcript routes)
//   c  Authorizations: the Federal fieldset (Form 8821, designees with CAF ••••last4 only, tax
//      matters, years, received, On file), the 8821-versus-2848 note with Draft Form 2848…, and
//      the State fieldset with + Add
//   e  Elections on Ridgeline: §754 pending, PTET IL, CO and NY, BBA representative, BBA opt-out
//      not eligible, §163(j) exempt, accrual (the server sends codes and amounts; words are here)
//   g  None on file (Santos): "No 8821 or 2848 on file" with Request Form 8821…
//
// No full CAF number or SSN reaches the DOM: the profile carries last fours only. Every control
// that opens a later screen (SIG-02, the upload) is drawn disabled with its "Opens …" hint.
// Each consent is its own signed document; nothing here combines two purposes in one.

export type Cli05Section = "elections" | "authorizations" | "consents" | "transcripts";
const BUILT: ReadonlySet<Cli05Section> = new Set([
  "elections",
  "authorizations",
  "consents",
  "transcripts",
]);

function setOf(consents: readonly ConsentOut[]): ConsentOut[] {
  return consents.filter((c) => c.purpose === "use" || c.purpose === "ai_disclosure");
}

function signersLine(c: ConsentOut): string {
  return (c.signers ?? [])
    .map((s) => `${s.name.split(" ")[0] ?? s.name} ${s.signed_at === null ? "○" : "✓"}`)
    .join(" · ");
}

function unsignedName(c: ConsentOut): string | null {
  return (c.signers ?? []).find((s) => s.required && s.signed_at === null)?.name ?? null;
}

function Band({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section aria-label={title} className="border-t-[0.5px] border-hair">
      <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-meta font-medium text-ink-2">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Kv({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex h-[33px] items-center gap-[10px] px-[12px] text-dense">
      <span className="w-[130px] flex-none text-ink-3">{label}</span>
      <span className="min-w-0 truncate">{children}</span>
    </div>
  );
}

function RailRow({
  title,
  sub,
  disc,
  selected,
  built,
  onOpen,
}: {
  title: string;
  sub: string | null;
  disc: "done" | "warn" | "todo";
  selected: boolean;
  built: boolean;
  onOpen: () => void;
}): JSX.Element {
  const body = (
    <>
      <StatusDisc state={disc} />
      <span className="flex min-w-0 flex-1 flex-col text-left">
        <span className="text-body font-medium">{title}</span>
        {sub !== null && (
          <span
            className={
              disc === "warn"
                ? "truncate text-meta text-amber-ink"
                : "truncate text-meta text-ink-3"
            }
          >
            {sub}
          </span>
        )}
      </span>
      {built && <Icon name="chevron-right" size={14} />}
    </>
  );
  const classes = `flex h-[52px] w-full items-center gap-[10px] px-[12px] ${selected ? "bg-sel-bg" : ""}`;
  return built ? (
    <button
      type="button"
      aria-current={selected ? "true" : undefined}
      className={`${classes} press`}
      onClick={onOpen}
    >
      {body}
    </button>
  ) : (
    <Tooltip content={COPY.rail.openTip}>
      <div className={classes}>{body}</div>
    </Tooltip>
  );
}

/** The Transcripts rail row: the first pull with differences ("TY2024 · 2 differences", amber),
 * else the newest that agrees, else "None yet". */
function transcriptsRow(rows: readonly TranscriptOut[]): {
  sub: string;
  disc: "done" | "warn" | "todo";
} {
  const off = rows.find((t) => t.result === "differences");
  if (off !== undefined) {
    return {
      sub: COPY.transcripts.railDifferences(off.tax_year, off.difference_count ?? 0),
      disc: "warn",
    };
  }
  const agrees = [...rows].reverse().find((t) => t.result === "agrees");
  if (agrees !== undefined)
    return { sub: COPY.transcripts.railAgrees(agrees.tax_year), disc: "done" };
  return { sub: COPY.rail.noTranscripts, disc: "todo" };
}

function Rail({
  profile,
  transcripts,
  section,
  onSection,
}: {
  profile: TaxProfileOut;
  transcripts: readonly TranscriptOut[];
  section: Cli05Section;
  onSection: (section: Cli05Section) => void;
}): JSX.Element {
  const transcriptRow = transcriptsRow(transcripts);
  const now = useNow();
  const set = setOf(profile.consents);
  const first = set[0];
  const consentStatus =
    first === undefined
      ? COPY.consents.notRequested
      : first.status === "requested"
        ? COPY.consents.requested(first.signed_count, first.signer_count)
        : `Signed · expires ${date(first.expires_at, { now, withYear: true }).replace(",", "")}`;
  const authorization = profile.authorizations.find((a) => a.status === "on_file");
  const years = authorization?.tax_years ?? [];
  const yearSpan =
    years.length === 0 ? "" : `${String(Math.min(...years))}–${String(Math.max(...years))}`;
  const identity = (role: TaxProfileIdentityOut["role"]): TaxProfileIdentityOut | undefined =>
    (profile.identity ?? []).find((i) => i.role === role);
  const canReveal = profile.allowed_actions.includes("tin.reveal");
  const person = (who: TaxProfileIdentityOut | undefined): ReactNode =>
    who === undefined ? null : (
      <span className="inline-flex items-center gap-[6px]">
        {who.name}
        <span aria-hidden="true">·</span>
        <MaskedTin
          entity={{ id: who.client_entity_id, name: who.name, tin: who.masked_tin ?? null }}
          canReveal={canReveal && who.role === "taxpayer"}
        />
      </span>
    );
  return (
    <section aria-label={COPY.rail.title} className="pane flex min-h-0 flex-1 flex-col">
      <div className="flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
        <h2 className="text-pane font-medium tracking-[-0.012em]">{COPY.rail.title}</h2>
      </div>
      <nav aria-label={COPY.sections.label} className="flex flex-col">
        <RailRow
          title={COPY.rail.elections}
          sub={profile.elections.length === 0 ? COPY.rail.noElections : COPY.rail.electionsOnFile}
          disc="done"
          selected={section === "elections"}
          built={BUILT.has("elections")}
          onOpen={() => {
            onSection("elections");
          }}
        />
        <RailRow
          title={COPY.rail.authorizations}
          sub={
            authorization === undefined
              ? COPY.rail.noAuthorization
              : COPY.rail.authorizationLine(authorization.form, yearSpan)
          }
          disc={authorization === undefined ? "warn" : "done"}
          selected={section === "authorizations"}
          built={BUILT.has("authorizations")}
          onOpen={() => {
            onSection("authorizations");
          }}
        />
        <RailRow
          title={COPY.rail.consents}
          sub={COPY.rail.consentLine(consentStatus)}
          disc={first?.status === "signed" ? "done" : "warn"}
          selected={section === "consents"}
          built
          onOpen={() => {
            onSection("consents");
          }}
        />
        <RailRow
          title={COPY.rail.transcripts}
          sub={transcriptRow.sub}
          disc={transcriptRow.disc}
          selected={section === "transcripts"}
          built={BUILT.has("transcripts")}
          onOpen={() => {
            onSection("transcripts");
          }}
        />
      </nav>
      {(profile.open_notices ?? 0) > 0 && (
        <Band title={COPY.notices.band}>
          <Tooltip content={COPY.notices.tip}>
            <p className="flex h-[40px] items-center px-[12px] text-dense text-ink-2">
              {COPY.notices.count(profile.open_notices ?? 0)}
            </p>
          </Tooltip>
        </Band>
      )}
      <Band title={COPY.identity.band}>
        <Kv label={COPY.identity.taxpayer}>{person(identity("taxpayer"))}</Kv>
        {identity("spouse") !== undefined && (
          <Kv label={COPY.identity.spouse}>{person(identity("spouse"))}</Kv>
        )}
        {profile.portal_user_name != null && (
          <Kv label={COPY.identity.portalUser}>{profile.portal_user_name}</Kv>
        )}
        {profile.resident_state != null && (
          <Kv label={COPY.identity.residentState}>{profile.resident_state}</Kv>
        )}
      </Band>
    </section>
  );
}

function Consents({ profile }: { profile: TaxProfileOut }): JSX.Element {
  const now = useNow();
  const set = setOf(profile.consents);
  const first = set[0];
  const recipient = profile.consents
    .flatMap((c) => c.recipients)
    .find((r) => r.kind === "provider");
  const offshore = profile.consents.find((c) => c.purpose === "offshore_disclosure");
  const unsigned = first?.status === "requested" ? unsignedName(first) : null;
  return (
    <div className="flex flex-col gap-[10px] p-[12px]">
      {unsigned !== null && (
        <div
          role="status"
          className="flex items-center gap-[12px] rounded-pane bg-amber-tint px-[14px] py-[10px] text-dense text-amber-ink"
        >
          <span className="flex-1">{COPY.partial.banner(unsigned)}</span>
          <Tooltip content={COPY.partial.resendTip}>
            <span>
              <Button size="sm" variant="secondary" disabled>
                {COPY.partial.resend}
              </Button>
            </span>
          </Tooltip>
        </div>
      )}
      <table className="w-full table-fixed text-body">
        <thead>
          <tr className="h-[30px] bg-band-hd text-meta font-medium text-ink-2">
            <th className="w-[260px] px-[12px] text-left">{COPY.consents.columns.purpose}</th>
            <th className="px-[12px] text-left">{COPY.consents.columns.scope}</th>
            <th className="w-[200px] px-[12px] text-left">{COPY.consents.columns.signed}</th>
            <th className="w-[110px] px-[12px] text-left">{COPY.consents.columns.expires}</th>
            <th className="w-[170px] px-[12px] text-left">{COPY.consents.columns.status}</th>
          </tr>
        </thead>
        <tbody>
          {first !== undefined && (
            <>
              <tr data-row="set" className="h-[40px] border-t-[0.5px] border-hair">
                <td className="px-[12px] font-medium">{COPY.consents.setPurpose}</td>
                <td className="truncate px-[12px] text-ink-2">
                  {recipient === undefined
                    ? (first.scope.label ?? "")
                    : COPY.consents.scope(recipient.name, recipient.country ?? "")}
                </td>
                <td className="px-[12px] tabular-nums">
                  {first.signed_at === null
                    ? signersLine(first)
                    : `${date(first.signed_at, { now, withYear: true })} · ${signersLine(first)}`}
                </td>
                <td className="px-[12px] tabular-nums">
                  {date(first.expires_at, { now, withYear: true })}
                </td>
                <td className="px-[12px]">
                  {first.status === "signed" ? (
                    <Pill variant="green">{COPY.consents.signed}</Pill>
                  ) : (
                    <Pill variant="amber">
                      {COPY.consents.requested(first.signed_count, first.signer_count)}
                    </Pill>
                  )}
                </td>
              </tr>
              {set.map((c) => (
                <tr key={c.id} data-row="document" className="h-[30px] text-dense text-ink-2">
                  <td colSpan={5} className="px-[12px] pl-[32px]">
                    <span className="inline-flex items-center gap-[6px]">
                      <Icon name="file-text" size={12} />
                      {[
                        c.purpose === "use"
                          ? COPY.consents.document.use
                          : COPY.consents.document.ai_disclosure,
                        c.template_name,
                        signersLine(c),
                      ]
                        .filter((part) => part !== null && part !== undefined && part !== "")
                        .join(" · ")}
                    </span>
                  </td>
                </tr>
              ))}
            </>
          )}
          {offshore === undefined && (
            <tr data-row="offshore" className="h-[40px] border-t-[0.5px] border-hair">
              <td className="px-[12px] font-medium">{COPY.consents.offshore}</td>
              <td className="px-[12px] text-ink-4">—</td>
              <td className="px-[12px] text-ink-4">—</td>
              <td className="px-[12px] text-ink-4">—</td>
              <td className="px-[12px]">
                <Pill variant="neutral">{COPY.consents.notRequested}</Pill>
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <p className="text-meta text-ink-3">{COPY.consents.note}</p>
      <div>
        <Tooltip content={COPY.consents.requestTip}>
          <span>
            <Button disabled>{COPY.consents.request}</Button>
          </span>
        </Tooltip>
      </div>
    </div>
  );
}

/** A planned control: drawn disabled with its "Opens …" hint (chapter 04 §2.1 rule 4). */
function Planned({
  tip,
  children,
  variant = "secondary",
}: {
  tip: string;
  children: string;
  variant?: "primary" | "secondary";
}): JSX.Element {
  return (
    <Tooltip content={tip}>
      <span>
        <Button size="sm" variant={variant} disabled>
          {children}
        </Button>
      </span>
    </Tooltip>
  );
}

function Fieldset({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section aria-label={title} className="overflow-hidden rounded-pane bg-card shadow-e1">
      <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-meta font-medium text-ink-2">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-[36px] items-center gap-[12px] border-t-[0.5px] border-hair px-[12px] py-[8px] text-dense first-of-type:border-t-0">
      <span className="w-[220px] flex-none text-ink-3">{label}</span>
      <span className="min-w-0 flex-1">{children}</span>
    </div>
  );
}

function yearsOf(years: readonly number[]): string {
  if (years.length === 0) return "—";
  return `${String(Math.min(...years))}–${String(Math.max(...years))}`;
}

function electionWords(e: TaxElectionOut): ReactNode {
  const w = COPY.elections;
  switch (`${e.kind}:${e.status_code}`) {
    case "section_754:pending":
      return <span className="text-amber-ink">{w.pending754(e.tax_year)}</span>;
    case "bba_representative:designated":
      return w.designated;
    case "bba_opt_out:not_eligible":
      return w.optOutNotEligible;
    case "section_163j:exempt":
      return w.exempt163j;
    case "accounting_method:accrual":
      return w.accrual;
    case "accounting_method:cash":
      return w.cash;
    default:
      return e.status_code;
  }
}

function Elections({ profile }: { profile: TaxProfileOut }): JSX.Element {
  const rows = COPY.elections.rows;
  const ptet = profile.elections.filter((e) => e.kind === "ptet");
  const others = profile.elections.filter((e) => e.kind !== "ptet");
  const labelOf = (e: TaxElectionOut): string =>
    e.kind in rows && e.kind !== "ptet"
      ? rows[e.kind as Exclude<keyof typeof rows, "ptet">]
      : e.kind;
  if (profile.elections.length === 0) {
    return (
      <div className="p-[12px]">
        <EmptyState title={COPY.rail.noElections} icon="file-text" />
      </div>
    );
  }
  const first = others[0];
  return (
    <div className="flex flex-col gap-[10px] p-[12px]">
      <Fieldset title={COPY.elections.title}>
        {first !== undefined && first.kind === "section_754" && (
          <Row label={labelOf(first)}>{electionWords(first)}</Row>
        )}
        {ptet.length > 0 && (
          <Row label={rows.ptet(ptet[0]?.tax_year ?? 0)}>
            <span data-election="ptet" className="flex flex-wrap gap-x-[12px] gap-y-[4px]">
              {ptet.map((e) => (
                <span key={e.jurisdiction ?? ""} className="tabular-nums">
                  {e.jurisdiction} {COPY.elections.elected} ·{" "}
                  {e.amount === null ? "—" : amount(e.amount, "whole").text}
                </span>
              ))}
            </span>
          </Row>
        )}
        {others
          .filter((e) => e !== first || e.kind !== "section_754")
          .map((e) => (
            <Row key={`${e.kind}:${String(e.tax_year)}`} label={labelOf(e)}>
              <span data-election={e.kind}>{electionWords(e)}</span>
            </Row>
          ))}
      </Fieldset>
    </div>
  );
}

function signersOf(profile: TaxProfileOut): string {
  // The taxpayer and spouse rows: the people who sign for the household.
  const names = (profile.identity ?? []).map((i) => i.name.split(" ")[0] ?? i.name);
  return names.join(" and ");
}

function Federal({ a, profile }: { a: TaxAuthorizationOut; profile: TaxProfileOut }): JSX.Element {
  const now = useNow();
  const A = COPY.authorizations;
  return (
    <>
      <Fieldset title={A.federal}>
        <Row label={A.form(a.form)}>{A.formName[a.form]}</Row>
        <Row label={A.designees}>
          <span data-designees="">
            {a.designees.map((d) => A.designee(d.name, d.caf_last4)).join(" · ")}
          </span>
        </Row>
        <Row label={A.taxMatters}>{a.tax_matters.join(" · ")}</Row>
        <Row label={A.years}>{yearsOf(a.tax_years)}</Row>
        <Row label={A.received}>
          {a.received_on === null ? "—" : date(a.received_on, { now, withYear: true })}
        </Row>
        <Row label={A.status}>
          <RegistryStatus object="tax_authorization" code={a.status} />
        </Row>
      </Fieldset>
      {a.form === "8821" && (
        <div
          role="note"
          className="flex items-center gap-[12px] rounded-pane bg-amber-tint px-[14px] py-[10px] text-dense text-amber-ink"
        >
          <span className="flex-1">{A.note8821(signersOf(profile))}</span>
          <Planned tip={A.draft2848Tip}>{A.draft2848}</Planned>
        </div>
      )}
    </>
  );
}

function Authorizations({ profile }: { profile: TaxProfileOut }): JSX.Element {
  const A = COPY.authorizations;
  const federal = profile.authorizations.filter((a) => a.form !== "state");
  const state = profile.authorizations.filter((a) => a.form === "state");
  if (federal.length === 0 && state.length === 0) {
    return (
      <div className="p-[12px]">
        <EmptyState
          title={A.none}
          icon="file-text"
          action={
            <Planned tip={A.request8821Tip} variant="primary">
              {A.request8821}
            </Planned>
          }
        />
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-[10px] p-[12px]">
      {federal.map((a) => (
        <Federal key={a.id} a={a} profile={profile} />
      ))}
      {(state.length > 0 || profile.resident_state != null) && (
        <Fieldset title={A.state}>
          {state.length > 0 ? (
            state.map((a) => (
              <Row key={a.id} label={A.state}>
                {A.stateOnFile(a.state_form_code ?? "")}
              </Row>
            ))
          ) : (
            <div className="flex min-h-[36px] items-center gap-[12px] px-[12px] text-dense">
              <span className="flex-1">{A.stateNotOnFile(profile.resident_state ?? "")}</span>
              <Planned tip={A.addTip}>{A.add}</Planned>
            </div>
          )}
        </Fieldset>
      )}
    </div>
  );
}

export interface AgentNote {
  text: string;
  sources: readonly string[];
}

/** "Forms W-2 × 2, Form 1098, Form 1099-INT × 1": a form named twice on the transcript (once
 * agreeing, once not) keeps its count even when it is one. */
function agreeingParts(c: TranscriptComparisonOut): string[] {
  const differing = new Set(c.lines.filter((l) => l.status !== "agrees").map((l) => l.form));
  return (c.agreeing ?? []).map((a) =>
    COPY.transcripts.agreeingPart(a.form, a.count, a.count > 1 || differing.has(a.form)),
  );
}

function ResultCell({
  t,
  comparing,
  now,
}: {
  t: TranscriptOut;
  comparing: boolean;
  now: Date;
}): JSX.Element {
  const T = COPY.transcripts;
  if (comparing) {
    return (
      <Pill variant="neutral" spin>
        {T.comparing}
      </Pill>
    );
  }
  if (t.parse_status === "failed") return <Pill variant="red-tint">{T.failed}</Pill>;
  if (t.result === "differences") {
    return <Pill variant="red-tint">{T.differences(t.difference_count ?? 0)}</Pill>;
  }
  if (t.result === "agrees") return <Pill variant="green-tint">{T.agrees}</Pill>;
  const key = t.key_transaction;
  if (key == null) return <span className="text-ink-4">—</span>;
  const on = date(key.posted_on, { now, withYear: true });
  // TC 922 is the IRS review of unreported income, not an assessment: a neutral fact.
  return key.code === "150" && t.account_balance != null ? (
    <Pill variant="green-tint">
      {T.tcBalance(key.code, on, amount(t.account_balance, "cents", { zero: "explicit" }).text)}
    </Pill>
  ) : (
    <Pill variant="neutral">{T.tc(key.code, on)}</Pill>
  );
}

function Comparison({
  t,
  comparison,
  note,
}: {
  t: TranscriptOut;
  comparison: TranscriptComparisonOut;
  note: AgentNote | undefined;
}): JSX.Element {
  const T = COPY.transcripts;
  const differing = comparison.lines.filter((l) => l.status !== "agrees");
  const total = comparison.difference_total ?? "0";
  const onReturn = differing.reduce(
    (sum, l) => sum + Math.round(Number(l.return_amount ?? "0") * 100),
    0,
  );
  const onTranscript = differing.reduce(
    (sum, l) => sum + Math.round(Number(l.transcript_amount) * 100),
    0,
  );
  const agreeing = (comparison.agreeing ?? []).reduce((n, a) => n + a.count, 0);
  const cents = (n: number): string =>
    amount(
      `${String(Math.trunc(n / 100))}.${String(Math.abs(n % 100)).padStart(2, "0")}`,
      "cents",
      {
        zero: "explicit",
      },
    ).text;
  return (
    <section
      aria-label={T.detail(T.kind[t.kind], t.tax_year)}
      data-comparison={comparison.id}
      className="m-[12px] overflow-hidden rounded-pane bg-card shadow-e1"
    >
      <h3 className="flex h-[34px] items-center gap-[8px] bg-band-hd px-[12px] text-meta font-medium text-ink-2">
        <span className="flex-1">{T.detail(T.kind[t.kind], t.tax_year)}</span>
        {comparison.result === "differences" ? (
          <TallyPill code="off" vars={{ amount: amount(total, "whole").text }} />
        ) : (
          <TallyPill code="tie" />
        )}
      </h3>
      {differing.length > 0 && (
        <table className="w-full table-fixed text-cell tabular-nums">
          <thead>
            <tr className="h-[30px] bg-band-hd text-meta font-medium text-ink-2">
              {T.detailHeads.map((h, i) => (
                <th
                  key={h}
                  className={
                    i >= 2 && i <= 4
                      ? "w-[120px] px-[12px] text-right"
                      : i === 0
                        ? "w-[260px] px-[12px] text-left"
                        : i === 1
                          ? "w-[220px] px-[12px] text-left"
                          : "w-[150px] px-[12px] text-left"
                  }
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {differing.map((l) => (
              <tr
                key={`${l.form}:${String(l.line_no ?? 0)}`}
                data-line={l.line_no ?? undefined}
                className="h-[36px] border-t-[0.5px] border-hair"
              >
                <td className="px-[12px]">{T.form(l.form)}</td>
                <td className="truncate px-[12px]">{l.payer_name ?? "—"}</td>
                <td className="px-[12px] text-right">
                  {amount(l.transcript_amount, "cents").text}
                </td>
                <td className="px-[12px] text-right text-ink-4">
                  {l.return_amount == null ? "—" : amount(l.return_amount, "cents").text}
                </td>
                <td className="px-[12px] text-right">
                  {PLANNED_VISIBLE ? (
                    <Tooltip content={T.differenceTip}>
                      <span data-difference="" className="font-medium text-red-ink">
                        {amount(l.difference ?? "0", "cents").text}
                      </span>
                    </Tooltip>
                  ) : (
                    <span data-difference="" className="font-medium text-red-ink">
                      {amount(l.difference ?? "0", "cents").text}
                    </span>
                  )}
                </td>
                <td className="px-[12px]">
                  <Pill variant="red-tint">
                    {l.status === "not_on_return" ? T.notOnReturn : T.differs}
                  </Pill>
                </td>
              </tr>
            ))}
            <tr data-row="total" className="h-[36px] border-t-[0.5px] border-ink-3 font-medium">
              <td className="px-[12px]">{T.total}</td>
              <td />
              <td className="px-[12px] text-right">{cents(onTranscript)}</td>
              <td className="px-[12px] text-right">{cents(onReturn)}</td>
              <td className="px-[12px] text-right">{amount(total, "cents").text}</td>
              <td />
            </tr>
          </tbody>
        </table>
      )}
      <p data-agreeing="" className="px-[12px] py-[10px] text-dense text-ink-3">
        {differing.length === 0 ? T.allAgree : T.agreeingLine(agreeing, agreeingParts(comparison))}
      </p>
      {note !== undefined && (
        <>
          <h4 className="flex h-[31px] items-center gap-[8px] border-t-[0.5px] border-hair bg-band-hd px-[12px] text-meta font-medium text-ink-2">
            <StatusDisc state="done" size={15} />
            {T.why}
          </h4>
          <div data-agent-note="" className="px-[12px] py-[10px] text-dense text-ink-2">
            <AgentText text={note.text} />
          </div>
          <ul className="flex flex-col px-[12px] pb-[8px]">
            {note.sources.map((src) => (
              <li key={src} className="flex h-[28px] items-center gap-[8px] text-dense text-ink-2">
                <Icon name="file-text" size={15} className="text-ink-3" />
                {src}
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="flex h-[48px] items-center gap-[8px] border-t-[0.5px] border-hair px-[12px]">
        {PLANNED_VISIBLE && (
          <>
            <Planned tip={T.openNoticeTip} variant="primary">
              {T.openNotice}
            </Planned>
            <Planned tip={T.flagTip}>{T.flag}</Planned>
          </>
        )}
      </div>
    </section>
  );
}

function Transcripts({
  rows,
  selected,
  onSelect,
  comparing,
  note,
}: {
  rows: readonly TranscriptOut[];
  selected: TranscriptOut | undefined;
  onSelect: (id: string) => void;
  comparing: boolean;
  note: AgentNote | undefined;
}): JSX.Element {
  const T = COPY.transcripts;
  const now = useNow();
  const comparison = useQuery({
    ...latestComparisonOptions({ path: { transcript_id: selected?.id ?? "" } }),
    enabled: selected?.result != null,
  });
  if (rows.length === 0) {
    return (
      <div className="p-[12px]">
        <EmptyState
          title={T.none}
          icon="file-text"
          action={<Planned tip={T.uploadTip}>{T.upload}</Planned>}
        >
          {T.noneBody}
        </EmptyState>
      </div>
    );
  }
  return (
    <div>
      <table aria-label={T.register} className="w-full table-fixed text-body">
        <thead>
          <tr className="h-[30px] bg-band-hd text-meta font-medium text-ink-2">
            <th className="w-[300px] px-[12px] text-left">{T.heads[0]}</th>
            <th className="w-[90px] px-[12px] text-left">{T.heads[1]}</th>
            <th className="w-[220px] px-[12px] text-left">{T.heads[2]}</th>
            <th className="w-[120px] px-[12px] text-left">{T.heads[3]}</th>
            <th className="w-[200px] px-[12px] text-left">{T.heads[4]}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => {
            const isSelected = t.id === selected?.id;
            return (
              <tr
                key={t.id}
                data-transcript={t.id}
                aria-selected={isSelected}
                onClick={() => {
                  onSelect(t.id);
                }}
                className={`h-[40px] cursor-pointer border-t-[0.5px] border-hair ${isSelected ? "bg-sel-bg" : "hover:bg-nav-fill"}`}
              >
                <td className="px-[12px]">
                  <button
                    type="button"
                    className="text-left font-medium"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect(t.id);
                    }}
                  >
                    {T.kind[t.kind]}
                  </button>
                </td>
                <td className="px-[12px] tabular-nums">{t.tax_year}</td>
                <td className="truncate px-[12px] tabular-nums">
                  {T.pulled(
                    `${date(t.pulled_at, { now })}, ${time(t.pulled_at)}`,
                    t.pulled_by_name ?? "",
                  )}
                </td>
                <td className="px-[12px]">
                  {t.authorization_form == null ? "—" : T.under(t.authorization_form)}
                </td>
                <td className="px-[12px]">
                  <ResultCell t={t} comparing={comparing && isSelected} now={now} />
                </td>
                <td />
              </tr>
            );
          })}
        </tbody>
      </table>
      {selected !== undefined && comparison.data !== undefined && (
        <Comparison t={selected} comparison={comparison.data} note={note} />
      )}
      {selected !== undefined && selected.kind === "wage_income" && selected.result == null && (
        <p className="m-[12px] text-dense text-ink-3">{T.notCompared}</p>
      )}
    </div>
  );
}

/** The register row the canvas opens on: the first Wage & Income pull with differences, else the
 * first row. */
function firstSelected(rows: readonly TranscriptOut[]): string | undefined {
  return (rows.find((t) => t.result === "differences") ?? rows[0])?.id;
}

const SECTIONS: readonly Cli05Section[] = [
  "elections",
  "authorizations",
  "consents",
  "transcripts",
];

export interface CLI05Props {
  clientEntityId: string;
  section?: Cli05Section;
  /** CLI-05 a's agent note: fixture-only (gallery and scenario tests); never in production. */
  agentNote?: AgentNote;
  onSection?: (section: Cli05Section) => void;
  onBack?: () => void;
  frame?: boolean;
}

export function CLI05({
  clientEntityId,
  section = "consents",
  agentNote,
  onSection,
  onBack,
  frame = false,
}: CLI05Props): JSX.Element {
  const profile = useQuery(taxProfileOptions({ path: { client_entity_id: clientEntityId } }));
  const path = { client_entity_id: clientEntityId };
  const transcripts = useQuery(listTranscriptsOptions({ path }));
  const rows = transcripts.data ?? [];
  const [picked, setPicked] = useState<string | undefined>(undefined);
  const selected = rows.find((t) => t.id === (picked ?? firstSelected(rows)));
  const queryClient = useQueryClient();
  const compare = useMutation({
    ...compareTranscriptMutation(),
    onSuccess: (_, vars) => {
      void queryClient.invalidateQueries({ queryKey: listTranscriptsQueryKey({ path }) });
      void queryClient.invalidateQueries({
        queryKey: latestComparisonQueryKey({ path: vars.path }),
      });
    },
  });
  const lastReturn = useQuery({
    ...latestComparisonOptions({ path: { transcript_id: selected?.id ?? "" } }),
    enabled: selected?.result != null,
  }).data?.return_id;
  // Compare re-runs the selected Wage & Income pull against the return it was last compared with
  // (DEC-1652); a first comparison starts from the return (TAX-09 sync), not from here.
  const canCompare =
    selected?.kind === "wage_income" && lastReturn !== undefined && !compare.isPending;
  const [current, setCurrent] = useState<Cli05Section>(section);
  const shown: Cli05Section = BUILT.has(current) ? current : "consents";
  const go = (next: Cli05Section): void => {
    setCurrent(next);
    onSection?.(next);
  };
  const data: TaxProfileOut | undefined = profile.data;
  const header = (
    <div className="flex h-[42px] items-center gap-[12px] px-[12px]">
      <button type="button" className="text-dense text-ink-2 hover:underline" onClick={onBack}>
        {COPY.back}
      </button>
      <span className="flex flex-1 items-center justify-center gap-[8px]">
        <h1 className="text-[15px] font-medium">{data?.client_name ?? ""}</h1>
        {data?.client_kind != null && <Pill variant="neutral">{data.client_kind}</Pill>}
      </span>
      {data?.partner_name != null && data.office_name != null && (
        <span className="text-dense text-ink-3">
          {COPY.partnerLine(data.partner_name, data.office_name)}
        </span>
      )}
    </div>
  );
  return (
    <RecordCockpit
      frame={frame}
      {...(frame ? { height: 860 } : {})}
      header={header}
      rail={
        data === undefined ? (
          <Skeleton />
        ) : (
          <Rail profile={data} transcripts={rows} section={shown} onSection={go} />
        )
      }
      canvas={{
        title: COPY.sections[shown],
        ...(shown === "transcripts"
          ? {
              actions: (
                <span className="flex items-center gap-[8px]">
                  {PLANNED_VISIBLE && (
                    <Planned tip={COPY.transcripts.uploadTip}>{COPY.transcripts.upload}</Planned>
                  )}
                  <Tooltip content={COPY.transcripts.compareTip}>
                    <span>
                      <Button
                        size="sm"
                        variant="primary"
                        disabled={!canCompare}
                        onClick={() => {
                          if (selected === undefined || lastReturn === undefined) return;
                          compare.mutate({
                            path: { transcript_id: selected.id },
                            body: { return_id: lastReturn },
                          });
                        }}
                      >
                        {COPY.transcripts.compare}
                      </Button>
                    </span>
                  </Tooltip>
                </span>
              ),
            }
          : {}),
        controls: (
          <span className="flex w-full items-center gap-[12px]">
            <Segmented
              size="small"
              label={COPY.sections.label}
              options={SECTIONS.map((s) => COPY.sections[s])}
              active={COPY.sections[shown]}
              onChange={(label) => {
                const next = SECTIONS.find((s) => COPY.sections[s] === label);
                if (next !== undefined) go(next);
              }}
            />
            {shown === "transcripts" && (
              <span className="ml-auto text-dense text-ink-3">{COPY.transcripts.pulledHint}</span>
            )}
          </span>
        ),
        state: profile.isPending
          ? { kind: "loading" }
          : profile.isError
            ? {
                kind: "error",
                retry: () => {
                  void profile.refetch();
                },
              }
            : { kind: "ready" },
        children:
          data === undefined ? null : shown === "elections" ? (
            <Elections profile={data} />
          ) : shown === "authorizations" ? (
            <Authorizations profile={data} />
          ) : shown === "transcripts" ? (
            <Transcripts
              rows={rows}
              selected={selected}
              onSelect={setPicked}
              comparing={compare.isPending}
              note={agentNote}
            />
          ) : (
            <Consents profile={data} />
          ),
      }}
    />
  );
}

/** The routed page: `clientEntityId` when the URL names it, else the record's first entity. */
export function TaxProfilePage({
  clientId,
  clientEntityId,
  section,
  onSection,
  onBack,
}: {
  clientId: string;
  clientEntityId?: string;
  section: string;
  onSection?: (section: Cli05Section) => void;
  onBack?: () => void;
}): JSX.Element | null {
  const record = useClientRecord(clientId);
  const entity = clientEntityId ?? record.data?.entities[0]?.id;
  if (entity === undefined) return null;
  const sub = SECTIONS.find((s) => s === section) ?? "consents";
  return (
    <CLI05
      clientEntityId={entity}
      section={sub}
      {...(onSection === undefined ? {} : { onSection })}
      {...(onBack === undefined ? {} : { onBack })}
    />
  );
}
