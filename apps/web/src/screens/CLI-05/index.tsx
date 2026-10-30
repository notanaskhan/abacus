import type { ConsentOut, TaxProfileIdentityOut, TaxProfileOut } from "@abacus/api-client";
import { taxProfileOptions } from "@abacus/api-client/query";
import {
  Button,
  Icon,
  Pill,
  RecordCockpit,
  Segmented,
  Skeleton,
  StatusDisc,
  Tooltip,
  date,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX, ReactNode } from "react";
import { useNow } from "../../app-core/clock";
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
// Elections, Authorizations and Transcripts (a, b, c, e, g) are part 2 (T-01-T43 to T46).
// Each consent is its own signed document; nothing here combines two purposes in one.

export type Cli05Section = "elections" | "authorizations" | "consents" | "transcripts";
const BUILT: ReadonlySet<Cli05Section> = new Set(["consents"]);

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

function Rail({
  profile,
  section,
  onSection,
}: {
  profile: TaxProfileOut;
  section: Cli05Section;
  onSection: (section: Cli05Section) => void;
}): JSX.Element {
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
          sub={profile.elections.length === 0 ? COPY.rail.noElections : null}
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
          sub={null}
          disc="todo"
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

export interface CLI05Props {
  clientEntityId: string;
  section?: Cli05Section;
  onSection?: (section: Cli05Section) => void;
  onBack?: () => void;
  frame?: boolean;
}

export function CLI05({
  clientEntityId,
  section = "consents",
  onSection,
  onBack,
  frame = false,
}: CLI05Props): JSX.Element {
  const profile = useQuery(taxProfileOptions({ path: { client_entity_id: clientEntityId } }));
  const shown: Cli05Section = BUILT.has(section) ? section : "consents";
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
          <Rail
            profile={data}
            section={shown}
            onSection={(next) => {
              onSection?.(next);
            }}
          />
        )
      }
      canvas={{
        title: COPY.consents.title,
        controls: (
          <Segmented
            size="small"
            label={COPY.sections.label}
            options={[
              { label: COPY.sections.elections, disabled: true },
              { label: COPY.sections.authorizations, disabled: true },
              { label: COPY.sections.consents },
              { label: COPY.sections.transcripts, disabled: true },
            ]}
            active={COPY.sections.consents}
          />
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
        children: data === undefined ? null : <Consents profile={data} />,
      }}
    />
  );
}

const SECTIONS: readonly Cli05Section[] = [
  "elections",
  "authorizations",
  "consents",
  "transcripts",
];

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
