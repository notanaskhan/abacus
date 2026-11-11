import { Button, Icon, type IconName, Pill, Segmented, Spinner, Tag, Toggle } from "@abacus/ui";
import { type JSX, type ReactNode, useState } from "react";
import {
  APPROVED_AT,
  AT,
  CODES,
  CODES_FOR,
  DUAL_DATE_LINE,
  E,
  FRAMES,
  type Frame,
  LETTERHEAD,
  MODS,
  MODW,
  type Mod,
  NAMES,
  OPH,
  REISSUE_VERSION,
  RV,
  TEMPLATE,
  type VersionRow,
} from "./copy";

// AUD-23 · Report builder in fixture mode on T10 (A-07-T34; handoff AUD-23 and revision R2). The
// report is built from structured choices only: no paragraph is free text (Edit explains that).
// A change records a version and the paper re-renders; a modification needs the engagement
// partner's decision card (SHL-11); going concern follows AUD-19 and is never a choice here.
// "Approve report" is the partner's (SHL-12 at L4) and opens through `onApprove`; release lives
// only in AUD-24, and the firm signature stays a placeholder until then. Nothing is agent-owned.

export type { Frame } from "./copy";

export interface ReportBuilderProps {
  frame: Frame;
  /** The viewer may approve at L4 (the server's `allowed_actions`: `sign_off.l4`). */
  canApprove?: boolean;
  onBack?: () => void;
  /** SHL-12 at Partner level; the host records the sign-off. */
  onApprove?: () => void;
  onCompare?: (from: string, to: string) => void;
  onRequestDecision?: (modification: Exclude<Mod, "none">) => void;
  onGoToRelease?: () => void;
  onOpen?: (target: string) => void;
}

type ParaKey = "eom" | "om";
type Tab = "rep" | "ver" | "apr";
type Disc = "done" | "todo";

interface Choice {
  mod: Mod;
  eom: boolean;
  eomC: string;
  om: boolean;
  omC: string;
}

function ValueRow({
  label,
  lit,
  help,
  children,
}: {
  label: string;
  lit?: boolean;
  help?: ReactNode;
  children: ReactNode;
}): JSX.Element {
  return (
    <div
      data-lit={lit === true ? "true" : undefined}
      className={lit === true ? "bg-match-bg" : ""}
    >
      <div className="flex min-h-[34px] items-center justify-between gap-2 px-[14px]">
        <span className="text-[13px] text-ink-2">{label}</span>
        <span className="flex items-center gap-2 text-[13px] font-medium">{children}</span>
      </div>
      {help !== undefined && (
        <div className="px-[14px] pb-[6px] text-right text-[11.5px] text-ink-3">{help}</div>
      )}
    </div>
  );
}

function Band({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section aria-label={title}>
      <h3 className="flex h-[31px] items-center bg-band-hd px-[14px] text-dense font-medium">
        {title}
      </h3>
      {children}
    </section>
  );
}

/** A paper section that fades in and out (220 ms) as the choices change. */
function PaperSection({
  heading,
  shown = true,
  children,
}: {
  heading?: string;
  shown?: boolean;
  children: ReactNode;
}): JSX.Element {
  return (
    <div
      data-section={heading ?? ""}
      aria-hidden={shown ? undefined : "true"}
      className={`grid transition-[grid-template-rows,opacity] duration-[220ms] ease-out ${shown ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}
    >
      <div className="overflow-hidden">
        {heading !== undefined && heading !== "" && (
          <h4 className="pt-[10px] text-[13.5px] font-medium">{heading}</h4>
        )}
        {shown && children}
      </div>
    </div>
  );
}

/** AUD-23: the structured choices and the live report. */
export function ReportBuilder(props: ReportBuilderProps): JSX.Element {
  const seed = FRAMES[props.frame];
  const copy = E[seed.m];
  const audit = seed.m === "audit";
  const reissue = seed.re === true;
  const word = audit ? "opinion" : seed.m === "rev" ? "conclusion" : "report";

  const [tab, setTab] = useState<Tab>("rep");
  const [choice, setChoice] = useState<Choice>({
    mod: seed.mod ?? "none",
    eom: false,
    eomC: "",
    om: false,
    omC: "",
  });
  const [added, setAdded] = useState<VersionRow[]>([]);
  const [menu, setMenu] = useState<"mod" | null>(null);
  const [pop, setPop] = useState<"supp" | ParaKey | null>(null);
  const [lit, setLit] = useState<number | null>(null);
  const [fullAud, setFullAud] = useState(false);
  const [gen, setGen] = useState(seed.gen ?? null);
  const [stale, setStale] = useState(seed.stale === true);
  const [sheet, setSheet] = useState(false);
  const [toast, setToast] = useState(
    seed.toast === true ? "Northwind PY2025 auditor's report v2.docx generated · DRAFT" : "",
  );

  const base = [...copy.vers, ...(reissue ? [REISSUE_VERSION] : [])];
  const versions = [...base, ...added];
  const current = versions[versions.length - 1]?.[0] ?? "v1";
  const approved = seed.appr === true;
  // An approved report is locked; a reissue reopens it until the partner approves the reissue.
  const lock = approved && !reissue;
  const rows = lit !== null ? (copy.mk[lit]?.[0] ?? []) : [];
  const isLit = (key: string): boolean => rows.includes(key);

  const record = (next: Partial<Choice>, what: string): void => {
    if (lock) return;
    const n = `v${String(base.length + added.length + 1)}`;
    setChoice((c) => ({ ...c, ...next }));
    setAdded((v) => [...v, [n, "MO", what, seed.now]]);
    setMenu(null);
    setPop(null);
    if (gen === "done") setStale(true);
    setToast(`Saved as ${n} · ${what}`);
  };

  const blocked: "dec" | "gc" | "code" | null =
    choice.mod !== "none"
      ? "dec"
      : seed.gc === true
        ? "gc"
        : (choice.eom && choice.eomC === "") || (choice.om && choice.omC === "")
          ? "code"
          : null;
  const blockedTip: Readonly<Record<"dec" | "gc" | "code", string>> = {
    dec: "Decision required first",
    gc: "Illustrative frame · AUD-19 concluded no substantial doubt",
    code: "Pick a reason code first",
  };
  const mw = choice.mod === "none" ? "" : MODW[choice.mod];

  const approvals: readonly (readonly [Disc, string, string])[] = audit
    ? [
        ["done", "Drafted · Hannah Leclerc · Oct 2", "Oct 2, 11:20 AM · v2 · L1 · hash 4be1…09c2"],
        [
          "done",
          "EQR concurred · Thomas Whitcombe · Oct 5",
          "Oct 5, 4:40 PM · v2 · G6 · hash 7a3f…d518",
        ],
        approved
          ? [
              "done",
              "Engagement partner approval · Margaret Okonkwo · Oct 7",
              `${APPROVED_AT} · v2 · L4 · hash c91e…2a07`,
            ]
          : ["todo", "Engagement partner approval", "Pending · reserved to Margaret Okonkwo"],
        ...(reissue
          ? [
              [
                "todo",
                "Reissue approval · engagement partner",
                "Pending · reserved to Margaret Okonkwo",
              ] as const,
            ]
          : []),
      ]
    : [
        ["done", "Prepared · Nov 10", "Nov 10, 11:15 AM · v1 · L1 · hash 2f6a…81dd"],
        ["todo", "Engagement partner approval", "Pending · engagement partner"],
      ];

  const marker = (n: number): JSX.Element | null => {
    const m = copy.mk[n];
    if (m === undefined) return null;
    return (
      <button
        type="button"
        data-marker={n}
        title={`${m[1]} · ${m[2]}`}
        aria-label={`Citation ${String(n)}: ${m[1]}`}
        onMouseEnter={() => {
          setLit(n);
        }}
        onMouseLeave={() => {
          setLit(null);
        }}
        onFocus={() => {
          setLit(n);
        }}
        onBlur={() => {
          setLit(null);
        }}
        className={`ml-[3px] rounded-[4px] px-[4px] text-[10.5px] ${lit === n ? "bg-match-bg text-match-ink" : "bg-nested text-ink-2"}`}
      >
        {n}
      </button>
    );
  };

  const codePopover = (key: "supp" | ParaKey, currentCode: string): JSX.Element | null =>
    pop !== key ? null : (
      <div
        role="dialog"
        aria-label="Reason codes"
        className="absolute right-[10px] z-10 w-[300px] rounded-pane bg-card p-[6px] shadow-e3"
      >
        {CODES.map(([c, t, sub]) => {
          const ok = CODES_FOR[key].includes(c);
          const shownSub = ok
            ? sub
            : c === "EOM-GC" && key === "eom"
              ? audit
                ? "AUD-19: no substantial doubt"
                : "No going-concern conditions identified"
              : "Not used for this section";
          return (
            <button
              key={c}
              type="button"
              disabled={!ok || lock}
              aria-pressed={c === currentCode}
              className="flex w-full flex-col items-start rounded-[6px] px-[8px] py-[6px] text-left disabled:opacity-55"
              onClick={() => {
                if (key === "supp" || c === currentCode) {
                  setPop(null);
                  return;
                }
                record(
                  key === "eom" ? { eomC: c } : { omC: c },
                  `picked ${c} for ${key === "eom" ? "Emphasis of matter" : "Other matter"}`,
                );
              }}
            >
              <span className="text-[12.5px] font-medium">
                {c} · {t}
              </span>
              <span className="text-[11.5px] text-ink-3">{shownSub}</span>
            </button>
          );
        })}
      </div>
    );

  const paraRow = (key: ParaKey, label: string): JSX.Element => {
    const on = choice[key];
    const code = choice[key === "eom" ? "eomC" : "omC"];
    return (
      <div className="relative">
        <div className="flex min-h-[34px] items-center gap-2 px-[14px]">
          <span className="flex-1 text-[13px] text-ink-2">{label}</span>
          {on && (
            <button
              type="button"
              aria-haspopup="dialog"
              onClick={() => {
                setPop(pop === key ? null : key);
              }}
            >
              <Tag className={code === "" ? "text-amber-ink" : ""}>{code || "Reason code…"}</Tag>
            </button>
          )}
          <Toggle
            size="small"
            label={label}
            checked={on}
            disabled={lock}
            onChange={() => {
              const off: Partial<Choice> =
                key === "eom" ? { eom: false, eomC: "" } : { om: false, omC: "" };
              const turnOn: Partial<Choice> = key === "eom" ? { eom: true } : { om: true };
              record(on ? off : turnOn, on ? `turned ${label} off` : `turned ${label} on`);
              if (!on) setPop(key);
            }}
          />
        </div>
        <div
          className={`px-[14px] pb-[6px] text-[11.5px] ${on && code === "" ? "text-amber-ink" : "text-ink-3"}`}
        >
          {on && code === ""
            ? "Pick a reason code"
            : on
              ? `Does not modify the ${word}`
              : "No reason code"}
        </div>
        {codePopover(key, code)}
      </div>
    );
  };

  const fixedToggle = (
    label: string,
    on: boolean,
    help: string,
    tip: string,
    tag?: ReactNode,
  ): JSX.Element => (
    <div className="relative" title={tip}>
      <div className="flex min-h-[34px] items-center gap-2 px-[14px]">
        <span className="flex-1 text-[13px] text-ink-2">{label}</span>
        {tag}
        <Toggle size="small" label={label} checked={on} disabled />
      </div>
      <div className="px-[14px] pb-[6px] text-[11.5px] text-ink-3">{help}</div>
    </div>
  );

  const forms = {
    audit: ["ERISA §103(a)(3)(C) (AU-C 703)", "Full-scope ERISA audit (AU-C 703)"],
    rev: ["Review conclusion (AR-C 90)", "Compilation report (AR-C 80)"],
    comp: ["Compilation report (AR-C 80)", "Review conclusion (AR-C 90)"],
  }[seed.m];
  const modLabel = MODS.find(([k]) => k === choice.mod)?.[1] ?? "None — unmodified";

  const structure = (
    <>
      <Band title="Engagement">
        <ValueRow
          label="Type"
          lit={isLit("type")}
          help={
            audit
              ? "§103(a)(3)(C) election in the engagement letter · Harborline certification"
              : `Engagement letter · ${seed.m === "rev" ? "AR-C 90 review" : "AR-C 80 compilation"}`
          }
        >
          {audit
            ? "Employee benefit plan audit"
            : seed.m === "rev"
              ? "Review engagement"
              : "Compilation engagement"}
        </ValueRow>
        <ValueRow label="Framework">{audit ? "US GAAP (ASC 962)" : "US GAAP (ASC 958)"}</ValueRow>
        <ValueRow label="Standards set">
          {audit
            ? "GAAS nonissuer · AU-C 703"
            : seed.m === "rev"
              ? "SSARS · AR-C 90"
              : "SSARS · AR-C 80"}
        </ValueRow>
        <ValueRow label="Template">
          <button type="button" onClick={() => props.onOpen?.("KNW-03")}>
            {audit
              ? TEMPLATE
              : seed.m === "rev"
                ? "BH Report · Review AR-C 90 v2"
                : "BH Report · Compilation AR-C 80 v2"}{" "}
            <span className="text-ink-3">→</span>
          </button>
        </ValueRow>
      </Band>
      <Band title={audit ? "Opinion" : seed.m === "rev" ? "Conclusion" : "Report"}>
        <ValueRow label="Form" lit={isLit("form")}>
          {forms[0]}
          <Icon name="chevrons-up-down" size={12} />
        </ValueRow>
        {seed.m === "comp" ? (
          <ValueRow label="Independence">Independent · no paragraph needed</ValueRow>
        ) : (
          <div className="relative">
            <ValueRow
              label="Modification"
              help={
                choice.mod === "none" ? undefined : (
                  <span className="flex items-center justify-end gap-2">
                    Requires a partner decision card
                    <button
                      type="button"
                      className="text-ink underline"
                      onClick={() => {
                        if (choice.mod !== "none") props.onRequestDecision?.(choice.mod);
                      }}
                    >
                      Request partner decision…
                    </button>
                  </span>
                )
              }
            >
              {choice.mod !== "none" && <Pill variant="amber">Decision required</Pill>}
              <button
                type="button"
                aria-haspopup="menu"
                aria-expanded={menu === "mod"}
                disabled={lock}
                className="flex items-center gap-1"
                onClick={() => {
                  setMenu(menu === "mod" ? null : "mod");
                }}
              >
                {modLabel}
                <Icon name="chevrons-up-down" size={12} />
              </button>
            </ValueRow>
            {menu === "mod" && (
              <div
                role="menu"
                className="absolute right-[10px] z-10 w-[260px] rounded-pane bg-card p-[6px] shadow-e3"
              >
                {MODS.map(([k, l]) => (
                  <button
                    key={k}
                    type="button"
                    role="menuitemradio"
                    aria-checked={k === choice.mod}
                    className="flex w-full flex-col items-start rounded-[6px] px-[8px] py-[6px] text-left"
                    onClick={() => {
                      if (k === choice.mod) {
                        setMenu(null);
                        return;
                      }
                      if (!audit) {
                        setMenu(null);
                        setToast(`Modifying the ${word} needs a partner decision card · SHL-11`);
                        return;
                      }
                      record({ mod: k }, `set Modification to ${l}`);
                    }}
                  >
                    <span className="text-[13px]">{l}</span>
                    {k !== "none" && (
                      <span className="text-[11.5px] text-ink-3">
                        Requires a partner decision card
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        <ValueRow label="Cites" lit={isLit("cites")}>
          <button type="button" onClick={() => props.onOpen?.(audit ? "SHL-11" : "AUD-26")}>
            <Tag>
              {audit
                ? "Decision · Opinion form · MO Oct 2"
                : seed.m === "rev"
                  ? "AUD-26 · review conclusion"
                  : "AUD-26 · compilation"}
            </Tag>
          </button>
        </ValueRow>
      </Band>
      <Band title="Paragraphs">
        {audit &&
          fixedToggle(
            "Going concern section",
            seed.gc === true,
            `AUD-19: no substantial doubt (MO Sep 30)${seed.gc === true ? " · shown on for illustration" : ""}`,
            "AUD-19 concluded no substantial doubt",
          )}
        {paraRow("eom", "Emphasis of matter")}
        {paraRow("om", "Other matter")}
        {audit ? (
          <>
            <div
              data-lit={isLit("supp") ? "true" : undefined}
              className={`relative ${isLit("supp") ? "bg-match-bg" : ""}`}
            >
              {fixedToggle(
                "Supplemental schedules required by ERISA (AU-C 703 section)",
                true,
                "Schedule H line 4a · line 4i",
                "Required by AU-C 703 for this plan",
                <button
                  type="button"
                  aria-haspopup="dialog"
                  onClick={() => {
                    setPop(pop === "supp" ? null : "supp");
                  }}
                >
                  <Tag>ERISA-SUPP</Tag>
                </button>,
              )}
              {codePopover("supp", "ERISA-SUPP")}
            </div>
            {fixedToggle(
              "Other information (AU-C 720)",
              false,
              "No annual report other than Form 5500",
              "Nothing to report on",
            )}
            {fixedToggle(
              "Report on other legal and regulatory requirements",
              false,
              "Not applicable",
              "Not applicable",
            )}
          </>
        ) : (
          fixedToggle("Supplementary information", false, "None presented", "None presented")
        )}
      </Band>
      <Band title="Dates & signature">
        <ValueRow
          label="Report date"
          help={
            reissue
              ? "Dual date · Note 12 as of January 15, 2027"
              : audit
                ? "= rep letter date · not before evidence is complete"
                : `= date the ${seed.m === "rev" ? "review" : "compilation"} is complete`
          }
        >
          {reissue && <Pill variant="red-tint">Reissued report</Pill>}
          {copy.date}
        </ValueRow>
        <ValueRow label="City">Chicago, Illinois</ValueRow>
        <ValueRow label="Firm signature">
          <Pill variant="muted">Applied at release (EP only)</Pill>
          Brightwater Hale LLP
        </ValueRow>
        <ValueRow label="Dual dating">{reissue ? "Note 12 · January 15, 2027" : "None"}</ValueRow>
      </Band>
      <Band title="Approvals">
        <ul>
          {approvals.map(([d, l]) => (
            <li
              key={l}
              data-approval={d}
              className="flex min-h-[34px] items-center gap-2 px-[14px] text-[13px]"
            >
              <Icon
                name={(d === "done" ? "circle-check" : "circle") satisfies IconName}
                size={15}
              />
              {l}
            </li>
          ))}
          {audit && (
            <li className="flex min-h-[34px] items-center justify-between gap-2 px-[14px] text-[13px]">
              <button type="button" onClick={() => props.onOpen?.("FSP-06")}>
                Generated documents <span className="text-ink-3">→</span>
              </button>
              <span className="flex items-center gap-2">
                <span className="text-ink-2">
                  {gen === "done" ? `1 · ${current} draft · Oct 6` : "None yet"}
                </span>
                {gen === "done" && stale && (
                  <button
                    type="button"
                    onClick={() => {
                      generate();
                    }}
                  >
                    <Pill variant="amber">Out of date · Update from data</Pill>
                  </button>
                )}
                {gen === "done" && !stale && (
                  <Button size="sm" variant="ghost" onClick={() => props.onOpen?.("XLA-02")}>
                    Open in Word
                  </Button>
                )}
              </span>
            </li>
          )}
        </ul>
      </Band>
    </>
  );

  function generate(): void {
    setSheet(false);
    setGen("run");
    setTimeout(() => {
      setGen("done");
      setStale(false);
      setToast(`Northwind PY2025 auditor's report ${current}.docx generated · DRAFT`);
    }, 1600);
  }

  const banners: { icon: IconName; text: string; variant: "green-tint" | "red-tint" | "amber" }[] =
    [];
  if (reissue) {
    banners.push({
      icon: "history",
      text: "Reissued report · dual-dated for Note 12 (AUD-30) · the October 9, 2026 report stays in the file",
      variant: "red-tint",
    });
  } else if (approved) {
    banners.push({
      icon: "lock",
      text: `Approved by Margaret Okonkwo · ${APPROVED_AT} · locked · the firm signature is applied at release (AUD-24)`,
      variant: "green-tint",
    });
  }
  if (!lock && blocked === "dec") {
    banners.push({
      icon: "triangle-alert",
      text: `The ${mw} needs a partner decision card before the report can be approved`,
      variant: "amber",
    });
  }
  if (!lock && blocked === "code") {
    banners.push({
      icon: "triangle-alert",
      text: "Pick a reason code for each paragraph you turned on",
      variant: "amber",
    });
  }

  const p = (text: string, n?: number, muted?: boolean): JSX.Element => (
    <p className={muted === true ? "text-ink-2" : ""}>
      {text}
      {n !== undefined && marker(n)}
    </p>
  );
  const placeholder = (text: string): JSX.Element => <p className="text-ink-3">{text}</p>;
  const eomSection = (
    <PaperSection heading="Emphasis of Matter" shown={choice.eom}>
      {placeholder(
        choice.eomC
          ? `Drafted from ${choice.eomC} · cites the note it emphasizes. It does not modify the ${word}.`
          : "Pick a reason code (EOM-CHG) to draft this paragraph.",
      )}
    </PaperSection>
  );
  const omSection = (
    <PaperSection heading="Other Matter" shown={choice.om}>
      {placeholder(
        choice.omC
          ? `Drafted from ${choice.omC} · cites the matter it describes. It does not modify the ${word}.`
          : "Pick a reason code (OM-OTHER) to draft this paragraph.",
      )}
    </PaperSection>
  );

  const paper = audit ? (
    <>
      <PaperSection heading="Scope and Nature of the ERISA Section 103(a)(3)(C) Audit">
        {p(AT.scope, 1)}
      </PaperSection>
      <PaperSection heading={OPH[choice.mod]}>
        {choice.mod === "none"
          ? p(AT.op, 2)
          : placeholder(
              `Drafted from the partner decision card (SHL-11). The ${mw}, the matter and its effect are reserved to Margaret Okonkwo.`,
            )}
      </PaperSection>
      <PaperSection heading={`Basis for ${OPH[choice.mod]}`}>
        {choice.mod !== "none" &&
          placeholder(
            `Describes the matter behind the ${mw} and its effect on the financial statements, from the decision card.`,
          )}
        {p(AT.basis, undefined, true)}
      </PaperSection>
      <PaperSection
        heading="Substantial Doubt About the Plan’s Ability to Continue as a Going Concern"
        shown={seed.gc === true}
      >
        {placeholder(AT.gc)}
      </PaperSection>
      {eomSection}
      {omSection}
      <PaperSection heading="Responsibilities of Management for the Financial Statements">
        {p(AT.mgmt, undefined, true)}
      </PaperSection>
      <PaperSection heading="Auditor’s Responsibilities for the Audit of the Financial Statements">
        {p(fullAud ? `${AT.aud1} ${AT.aud2}` : AT.aud1, undefined, true)}
        <button
          type="button"
          className="flex items-center gap-1 text-[11.5px] text-ink-3"
          onClick={() => {
            setFullAud(!fullAud);
          }}
        >
          {fullAud ? "Show less" : "Show full paragraph"}
          <Icon name={fullAud ? "chevron-up" : "chevron-down"} size={12} />
        </button>
      </PaperSection>
      <PaperSection heading="Supplemental Schedules Required by ERISA">
        {p(AT.supp, 3)}
      </PaperSection>
    </>
  ) : seed.m === "rev" ? (
    <>
      <PaperSection>{p(RV.intro, 1)}</PaperSection>
      <PaperSection heading="Management’s Responsibility for the Financial Statements">
        {p(RV.mgmt, undefined, true)}
      </PaperSection>
      <PaperSection heading="Accountant’s Responsibility">
        {p(RV.acct, undefined, true)}
      </PaperSection>
      <PaperSection heading="Accountant’s Conclusion">{p(RV.concl, 2)}</PaperSection>
      {eomSection}
      {omSection}
    </>
  ) : (
    <>
      <PaperSection>{p(RV.comp, 1)}</PaperSection>
      {eomSection}
      {omSection}
    </>
  );

  const primaryLabel = lock
    ? "Go to issuance & release"
    : reissue
      ? "Approve reissue"
      : "Approve report";
  const primaryDisabled = !lock && blocked !== null;

  return (
    <div data-screen="AUD-23" data-frame={props.frame} className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[50px] items-center px-[12px]">
        <Button size="sm" variant="ghost" onClick={props.onBack}>
          ‹ Cockpit
        </Button>
        <div className="flex flex-1 justify-center">
          <Segmented
            size="small"
            label="Report views"
            options={["Report", `Versions ${String(versions.length)}`, "Approvals"]}
            active={
              tab === "rep"
                ? "Report"
                : tab === "ver"
                  ? `Versions ${String(versions.length)}`
                  : "Approvals"
            }
            onChange={(v) => {
              setTab(v === "Report" ? "rep" : v === "Approvals" ? "apr" : "ver");
            }}
          />
        </div>
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px] pb-[12px]">
        <section
          aria-label="Structure"
          className="w-[470px] shrink-0 overflow-y-auto rounded-pane bg-card shadow-e1"
        >
          <h2 className="flex h-[32px] items-center px-[14px] text-[12.5px] font-medium text-ink-2">
            Report › {copy.ttl}
          </h2>
          {tab === "rep" && structure}
          {tab === "ver" && (
            <ol aria-label="Versions">
              <li className="px-[14px] py-[6px] text-[11.5px] text-ink-3">
                {versions.length} {versions.length > 1 ? "versions" : "version"}
              </li>
              {versions
                .slice()
                .reverse()
                .map(([n, who, what, at], i) => (
                  <li
                    key={n}
                    data-version={n}
                    className="flex min-h-[44px] items-center gap-2 px-[14px] text-[13px]"
                  >
                    <span className="font-medium">{n}</span>
                    <span className="min-w-0 flex-1">
                      {NAMES[who]} {what}
                      <span className="block text-[11.5px] text-ink-3">{at}</span>
                    </span>
                    {i === 0 && <Pill variant="muted">Current</Pill>}
                  </li>
                ))}
            </ol>
          )}
          {tab === "apr" && (
            <ul aria-label="Approvals">
              {approvals.map(([d, l, det]) => (
                <li key={l} className="flex min-h-[44px] items-center gap-2 px-[14px] text-[13px]">
                  <Icon name={d === "done" ? "circle-check" : "circle"} size={15} />
                  <span>
                    {l}
                    <span className="block text-[11.5px] text-ink-3">{det}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section aria-label="Paper" className="flex min-w-0 flex-1 flex-col rounded-pane bg-shell">
          <header className="relative flex h-[46px] items-center justify-center">
            <h2 className="text-[14.5px] font-medium">
              {copy.ttl} · {current}
              {reissue ? " · reissue" : ""}
            </h2>
            <div className="absolute right-[10px] flex gap-2">
              <Button
                size="sm"
                variant="secondary"
                disabled={lock}
                title={
                  lock
                    ? "Approved reports are locked"
                    : "Report text comes from the structured choices"
                }
                onClick={() => {
                  setToast(
                    "Report text comes from the structured choices · edits are logged against the template",
                  );
                }}
              >
                Edit
              </Button>
              <Button size="sm" variant="ghost" onClick={() => props.onCompare?.("v1", current)}>
                Compare v1
              </Button>
              {audit && gen !== "run" && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setSheet(true);
                  }}
                >
                  <Icon name="file-down" size={14} />
                  Generate .docx…
                </Button>
              )}
              {audit && gen === "run" && (
                <Button size="sm" variant="secondary" disabled>
                  <Spinner label="Generating…" size={12} showLabel={false} />
                  Generating…
                </Button>
              )}
              {(props.canApprove === true || lock) && (
                <Button
                  size="sm"
                  disabled={primaryDisabled}
                  title={!lock && blocked !== null ? blockedTip[blocked] : undefined}
                  onClick={() => {
                    if (lock) props.onGoToRelease?.();
                    else if (blocked === null) props.onApprove?.();
                  }}
                >
                  <Icon name={lock ? "arrow-right" : "check"} size={14} />
                  {primaryLabel}
                </Button>
              )}
            </div>
          </header>
          {banners.map((b) => (
            <div key={b.text} className="px-[14px] pb-[6px]">
              <Pill variant={b.variant} lead={<Icon name={b.icon} size={12} />}>
                {b.text}
              </Pill>
            </div>
          ))}
          <div
            // A scrolling region is reachable by keyboard (axe scrollable-region-focusable).
            tabIndex={0}
            role="region"
            aria-label="Paper content"
            className="min-h-0 flex-1 overflow-y-auto p-[14px]"
          >
            <article className="relative mx-auto w-[600px] overflow-hidden rounded-pane bg-card px-[26px] pb-[26px] pt-[22px] text-[12px] leading-[1.55] shadow-e2">
              {!lock && (
                <span
                  aria-hidden="true"
                  data-watermark="draft"
                  className="pointer-events-none absolute inset-0 flex -rotate-[30deg] items-center justify-center text-[72px] font-medium text-ink/[.06] before:content-['DRAFT']"
                />
              )}
              <p className="text-[13.5px] font-medium">{LETTERHEAD[0]}</p>
              <p className="text-[11.5px] text-ink-3">{LETTERHEAD[1]}</p>
              <hr className="my-[8px] border-hair" />
              <h3 className="text-[16px] font-medium">{copy.h3}</h3>
              <p className="pb-[4px]">{copy.addressee}</p>
              {paper}
              <div className="pt-[14px]">
                <div
                  data-signature="placeholder"
                  className="rounded-[6px] border border-dashed border-hair px-[10px] py-[8px]"
                >
                  <p className="font-medium">Brightwater Hale LLP</p>
                  <p className="text-[11px] text-ink-3">Firm signature applied at release</p>
                </div>
                <p>Chicago, Illinois</p>
                <p>{reissue ? DUAL_DATE_LINE : copy.date}</p>
              </div>
            </article>
          </div>
        </section>
      </div>
      {sheet && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Generate from template"
          className="fixed inset-0 z-20 flex items-start justify-center pt-[80px]"
        >
          <div className="w-[500px] rounded-pane bg-card shadow-e3">
            <header className="flex h-[46px] items-center justify-between px-[14px]">
              <h2 className="text-[14.5px] font-medium">Generate from template</h2>
              <Button
                size="sm"
                variant="ghost"
                aria-label="Close"
                onClick={() => {
                  setSheet(false);
                }}
              >
                <Icon name="x" size={14} />
              </Button>
            </header>
            <p className="px-[14px] text-[11.5px] text-ink-3">
              {copy.ttl} · {current}
            </p>
            <dl className="px-[14px] py-[6px] text-[13px]">
              <div className="flex h-[34px] items-center justify-between">
                <dt className="text-ink-2">Template</dt>
                <dd>
                  <button type="button" onClick={() => props.onOpen?.("FSP-06")}>
                    {TEMPLATE} <span className="text-ink-3">→</span>
                  </button>
                </dd>
              </div>
              <div className="flex h-[34px] items-center justify-between">
                <dt className="text-ink-2">Report version</dt>
                <dd>{current}</dd>
              </div>
              <div className="flex h-[34px] items-center justify-between">
                <dt className="text-ink-2">Watermark</dt>
                <dd
                  className="flex items-center gap-2"
                  title="The DRAFT watermark stays on until release in AUD-24"
                >
                  DRAFT
                  <Toggle size="small" label="Watermark" checked disabled />
                </dd>
              </div>
              <div className="flex h-[34px] items-center justify-between">
                <dt className="text-ink-2">Signature</dt>
                <dd className="flex items-center gap-1">
                  Placeholder — applied at release (AUD-24)
                  <Icon name="lock" size={12} />
                </dd>
              </div>
            </dl>
            <p className="px-[14px] text-[11.5px] text-ink-3">
              Deterministic render: the same inputs always give the same file.
            </p>
            <footer className="flex justify-end px-[14px] py-[10px]">
              <Button
                size="sm"
                onClick={() => {
                  generate();
                }}
              >
                Generate
              </Button>
            </footer>
          </div>
        </div>
      )}
      {toast !== "" && (
        <div
          role="status"
          className="fixed bottom-[20px] left-1/2 z-30 -translate-x-1/2 rounded-pane bg-ink px-[12px] py-[8px] text-[12.5px] text-card shadow-e3"
        >
          {toast}
        </div>
      )}
    </div>
  );
}
