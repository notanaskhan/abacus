import { type JSX, type ReactNode, useState } from "react";
import { Button } from "../components/button";
import { Fieldset, FieldsetAdd } from "../components/fieldset";
import { Pill, Tag } from "../components/pill";
import { StatusDisc } from "../components/status";
import { Icon } from "../icons";
import { AppShell } from "../layout/app-shell";
import { Pane } from "../layout/pane";
import { Wizard, type WizardStep } from "../overlays/wizard";
import {
  type CatalogueGroup,
  GateCard,
  TypeCatalogue,
  WizardSummary,
} from "../templates/wizard-kit";
import guards from "../../scope-guards.gen.json";
import { Artboard } from "./portal";
import { FIRM, RIDGELINE, STAFF } from "./seed-figures";

// TPL-18 (F-05-T38): the O6 stepper wizard over Engagements for Daniel Reyes, Wave 0 - Templates
// `#tpl18`, Mon Sep 14, 2026, 9:05 AM CT. Five frames, intentionally out of step order (a: step 1,
// b: step 4, c: step 3, d: step 6, e: the blocked gate). Every string is the canvas's own. The type
// catalogue is data: the firm's entitlements decide AUP and SOC (none at E0, so both read Coming
// soon), and Single audit is Coming soon whatever they say (D1, D10).

const NAV = guards.nav.map((label) => ({ label }));
const TOOLBAR = {
  nav: NAV,
  firm: FIRM,
  firmShort: "Brightwater",
  firmTitle: "Brightwater Hale LLP",
  active: "Engagements",
  holdLabelWidth: false,
} as const;

const STEPS = [
  "Client & type",
  "Standards & methodology",
  "Period & deadlines",
  "Team & independence",
  "Binder & portal",
  "Letter & review",
] as const;

/** The catalogue as `GET /v1/engagement-types` would send it (canvas `TP18.GROUPS`). */
export const TPL18_CATALOGUE: readonly CatalogueGroup[] = [
  {
    id: "tax",
    label: "Tax",
    tone: "clay",
    icon: "file-text",
    types: [
      { id: "1040", label: "Form 1040", sub: "Individuals" },
      { id: "1041", label: "Form 1041", sub: "Estates and trusts" },
      { id: "1065", label: "Form 1065", sub: "Partnerships" },
      { id: "1120s", label: "Form 1120-S", sub: "S corporations" },
      { id: "1120", label: "Form 1120", sub: "C corporations" },
      { id: "990", label: "Form 990", sub: "Exempt organizations" },
      { id: "706", label: "Form 706 / 709", sub: "Estate and gift tax" },
      { id: "notice", label: "Notice response", sub: "IRS and state notices" },
    ],
  },
  {
    id: "assurance",
    label: "Assurance",
    tone: "espresso",
    icon: "file-search",
    types: [
      { id: "ebp", label: "EBP audit", sub: "Employee benefit plans" },
      { id: "fsa", label: "FS audit", sub: "Financial statements" },
      { id: "rev", label: "Review", sub: "AR-C 90 · Limited assurance" },
      { id: "comp", label: "Compilation", sub: "AR-C 80 · No assurance" },
      { id: "prep", label: "Preparation", sub: "AR-C 70 · Nonattest" },
    ],
  },
  {
    id: "accounting",
    label: "Accounting",
    tone: "green",
    icon: "landmark",
    types: [{ id: "close", label: "Monthly close", sub: "Recurring accounting" }],
  },
  {
    id: "advisory",
    label: "Advisory & other",
    tone: "amber",
    icon: "notebook-text",
    types: [
      { id: "adv", label: "Advisory project", sub: "Fixed-scope advice" },
      { id: "aup", label: "Agreed-upon procedures", entitlement: "attest" },
      { id: "soc", label: "SOC 1 / SOC 2", entitlement: "attest" },
      { id: "single", label: "Single audit", comingSoon: true },
    ],
  },
];

/** Brightwater Hale's entitlements at E0: no `attest`, so AUP and SOC are not offered. */
const ENTITLEMENTS: readonly string[] = [];

const NAMES = new Map(TPL18_CATALOGUE.flatMap((g) => g.types.map((t) => [t.id, t.label])));

interface Variant {
  type: string;
  client: string;
  blocked: boolean;
  kv: readonly (readonly [string, string, boolean?])[];
  rows: readonly (readonly [number, string, string])[];
}

const ADVISORY: Variant = {
  type: "adv",
  client: RIDGELINE,
  blocked: false,
  kv: [
    ["Client", RIDGELINE],
    ["Relationship", "Existing client"],
    ["Proposal", "Accepted · $18,500 fixed", true],
  ],
  rows: [
    [0, "Type", "Advisory project"],
    [0, "Client", RIDGELINE],
    [1, "Standards", "AICPA SSTS · CS 100 · Circular 230 §10.37"],
    [1, "Methodology", "BH Tax Advisory v1"],
    [2, "Period", "Sep 14, 2026 – Feb 15, 2027"],
    [3, "Team", "DR / SI / OB"],
    [3, "Third party", "Tallgrass Cost Engineering, LLC"],
    [3, "Fee", "$18,500 fixed · 50% on signature · 50% on Form 3115 delivery"],
    [4, "Binder", "Cost segregation data request v2 · 6 requests · visible to Owen Calder"],
    [5, "Letter", "Engagement letter — advisory (fixed fee) · signers Owen Calder, Daniel Reyes"],
  ],
};

const FS_AUDIT: Variant = {
  type: "fsa",
  client: "Fairhaven Foods, Inc.",
  blocked: true,
  kv: [
    ["Client", "Fairhaven Foods, Inc."],
    ["Relationship", "Prospect"],
    ["Proposal", "Draft · not sent", true],
  ],
  rows: [
    [0, "Type", "FS audit"],
    [0, "Client", "Fairhaven Foods, Inc. · prospect"],
    [1, "Standards", "AICPA AU-C · SQMS No. 1"],
    [1, "Methodology", "BH Audit Methodology · FS v2"],
    [2, "Period", "FY2026 · year ending Dec 31, 2026"],
    [3, "Team", "MO / HL / MD"],
    [3, "Independence", "Confirmed for MO, HL and MD"],
    [4, "Binder", "FS audit request list v3 · 24 requests"],
    [5, "Letter", "Engagement letter — financial statement audit"],
  ],
};

const KEY_DATES: readonly (readonly [string, string?])[] = [
  ["§754 election statement — with the TY2025 Form 1065, due Sep 15, 2026"],
  [
    "If the election is not made by then: automatic 12-month relief under Reg. §301.9100-2, to Sep 15, 2027",
  ],
  ["Engineer’s cost-segregation report — Tallgrass, due Oct 30, 2026"],
  [
    "Form 3115 package — Feb 15, 2027",
    "Form 3115, automatic change DCN 7, with a §481(a) adjustment on the TY2026 return",
  ],
];

const TEAM: readonly (readonly [string, string, string])[] = [
  [STAFF.daniel, "Engagement partner (signer)", "New York"],
  [STAFF.samuel, "Manager", "New York"],
  [STAFF.olivia, "Senior", "Denver"],
];

const BUDGET: readonly (readonly [string, string, boolean, string?])[] = [
  ["Fee", "Fixed $18,500", true, "From the ENG-09 proposal"],
  ["Hours", "64", true],
  ["Billing", "50% on signature · 50% on Form 3115 delivery", true],
  [
    "Engineer’s fee",
    "Est. $9,800 · billed by Tallgrass",
    false,
    "Contracted and billed directly to Ridgeline; not in the firm fee",
  ],
];

const SAVED = "Draft saved 9:05 AM";

// ---- Rows ---------------------------------------------------------------------------------------

/** A read-only fieldset row: key ink-2 at the left, the value 13/500 at the right. */
function Kv({
  k,
  children,
  help,
  picker = false,
  link = false,
}: {
  k: string;
  children: ReactNode;
  help?: string | undefined;
  picker?: boolean;
  link?: boolean;
}): JSX.Element {
  return (
    <div className="flex min-h-[34px] items-center justify-between gap-[16px] px-[12px] py-[6px] text-body">
      <span className="shrink-0 text-ink-2">{k}</span>
      <span className="flex min-w-0 flex-col items-end text-right">
        <span className="inline-flex items-center gap-[5px] font-medium">
          {children}
          {picker && <Icon name="chevrons-up-down" size={12} className="text-ink-3" />}
          {link && <Icon name="chevron-right" size={12} className="text-ink-3" />}
        </span>
        {help !== undefined && <span className="text-meta text-ink-3">{help}</span>}
      </span>
    </div>
  );
}

function Body({ children }: { children: ReactNode }): JSX.Element {
  return <div className="mx-auto flex max-w-[760px] flex-col gap-[12px] pt-[2px]">{children}</div>;
}

function ClientAndType({
  v,
  type,
  onType,
}: {
  v: Variant;
  type: string | null;
  onType: (id: string | null) => void;
}): JSX.Element {
  return (
    <Body>
      <Fieldset title="Client" flush className="mb-0">
        {v.kv.map(([k, value, link]) => (
          <Kv key={k} k={k} link={link === true}>
            {value}
          </Kv>
        ))}
      </Fieldset>
      <TypeCatalogue
        heading="What kind of engagement?"
        groups={TPL18_CATALOGUE}
        entitlements={ENTITLEMENTS}
        selected={type}
        onSelect={onType}
        soonHint="Out of scope for v1"
      />
    </Body>
  );
}

function Generated({ v, step }: { v: Variant; step: number }): JSX.Element {
  return (
    <Body>
      <Fieldset title={STEPS[step] ?? ""} flush className="mb-0">
        {v.rows
          .filter(([s]) => s === step)
          .map(([, k, value]) => (
            <Kv key={k} k={k}>
              {value}
            </Kv>
          ))}
      </Fieldset>
    </Body>
  );
}

function Period(): JSX.Element {
  return (
    <Body>
      <Fieldset title="Period" flush className="mb-0">
        <Kv k="Engagement period" picker>
          Sep 14, 2026 – Feb 15, 2027
        </Kv>
        <Kv k="Tax year affected">
          TY2025 (6/30/2025 transfer) and TY2026 (cost-segregation change)
        </Kv>
      </Fieldset>
      <Fieldset title="Key dates" flush className="mb-0">
        {KEY_DATES.map(([text, sub]) => (
          <div key={text} className="flex gap-[10px] px-[12px] py-[9px] text-body">
            <Icon name="calendar" size={14} className="mt-[2px] shrink-0 text-ink-3" />
            <span className="flex flex-col gap-[2px]">
              <span>{text}</span>
              {sub !== undefined && <span className="text-meta text-ink-3">{sub}</span>}
            </span>
          </div>
        ))}
      </Fieldset>
    </Body>
  );
}

function Team({ consent }: { consent: boolean }): JSX.Element {
  return (
    <Body>
      <Fieldset title="Team" flush className="mb-0" action={<FieldsetAdd>Add</FieldsetAdd>}>
        {TEAM.map(([name, role, office]) => (
          <div
            key={name}
            className="flex min-h-[44px] items-center gap-[10px] px-[12px] text-body"
          >
            <span className="inline-flex size-[26px] shrink-0 items-center justify-center rounded-full bg-nested text-ink-3">
              <Icon name="user" size={13} />
            </span>
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="font-medium">{name}</span>
              <span className="text-meta text-ink-3">{role}</span>
            </span>
            <Tag>{office}</Tag>
            <Pill variant="muted" size="outline">
              Independence not required — non-attest
            </Pill>
          </div>
        ))}
      </Fieldset>
      <Fieldset title="Third parties" flush className="mb-0">
        <div className="flex min-h-[52px] items-center gap-[10px] px-[12px] text-body">
          <span className="inline-flex size-[26px] shrink-0 items-center justify-center rounded-full bg-nested text-ink-3">
            <Icon name="building-2" size={13} />
          </span>
          <span className="flex min-w-0 flex-1 flex-col">
            <span>
              <span className="font-medium">Tallgrass Cost Engineering, LLC</span> ·
              cost-segregation engineer · external
            </span>
            <span className="text-meta text-ink-3">
              Scoped to 1 request: Engineering study inputs
            </span>
          </span>
          <Pill variant="amber" size="outline">
            {consent ? "Consent requested with the letter" : "Needs §7216 consent"}
          </Pill>
        </div>
      </Fieldset>
      <div className="flex gap-[10px] rounded-nested bg-card px-[14px] py-[11px] text-body shadow-e1">
        <span className="flex h-[19px] items-center">
          <StatusDisc state="done" size={15} />
        </span>
        <span className="flex flex-col gap-[2px]">
          <span className="font-medium">Conflict check</span>
          <span className="text-ink-2">
            No conflicts found · checked 9:04 AM against 16 clients and their owners, partners and
            related parties
          </span>
        </span>
      </div>
      <Fieldset title="Budget" flush className="mb-0">
        {BUDGET.map(([k, value, picker, help]) => (
          <Kv key={k} k={k} picker={picker} help={help}>
            {value}
          </Kv>
        ))}
      </Fieldset>
    </Body>
  );
}

function Review({
  v,
  type,
  consent,
  onConsent,
}: {
  v: Variant;
  type: string | null;
  consent: boolean;
  onConsent: () => void;
}): JSX.Element {
  return (
    <Body>
      <Fieldset title="Review" flush className="mb-0">
        {v.rows.map(([, k, value]) => (
          <Kv key={k} k={k}>
            {k === "Type" && type !== null ? (NAMES.get(type) ?? value) : value}
          </Kv>
        ))}
      </Fieldset>
      {v.blocked ? (
        <GateCard
          tone="blocked"
          link={
            <Button variant="link" size="sm">
              Start acceptance (CLI-07) →
            </Button>
          }
        >
          {`Acceptance decision required (Gate G1) — ${STAFF.margaret} must approve acceptance before a letter can be created`}
        </GateCard>
      ) : (
        <>
          <GateCard
            tone="needs"
            action={
              consent ? (
                <Pill variant="amber" size="outline">
                  Consent requested with the letter
                </Pill>
              ) : (
                <Button variant="secondary" size="md" onClick={onConsent}>
                  Request consent with the letter
                </Button>
              )
            }
          >
            Disclosing Ridgeline’s return information to Tallgrass Cost Engineering, LLC needs a
            signed §7216 consent to disclose. It isn’t on file.
          </GateCard>
          <GateCard tone="met">Continuance: existing client, accepted Jan 2026 (G1)</GateCard>
        </>
      )}
    </Body>
  );
}

// ---- Frames -------------------------------------------------------------------------------------

interface FrameSpec {
  id: string;
  name: string;
  note: string;
  step: number;
  done: number;
  v: Variant;
}

const FRAMES: readonly FrameSpec[] = [
  {
    id: "tpl-18a",
    name: "Step 1 · Client & type",
    note: "Advisory project picked for Ridgeline; three types are coming soon",
    step: 0,
    done: 0,
    v: ADVISORY,
  },
  {
    id: "tpl-18b",
    name: "Step 4 · Team & independence",
    note: "Default frame. Non-attest, so independence shows but never blocks",
    step: 3,
    done: 3,
    v: ADVISORY,
  },
  {
    id: "tpl-18c",
    name: "Step 3 · Period & deadlines",
    note: "The §754 election, §301.9100-2 relief, the engineer’s report and Form 3115",
    step: 2,
    done: 2,
    v: ADVISORY,
  },
  {
    id: "tpl-18d",
    name: "Step 6 · Letter & review",
    note: "The §7216 consent gate for Tallgrass; continuance is already met",
    step: 5,
    done: 5,
    v: ADVISORY,
  },
  {
    id: "tpl-18e",
    name: "Blocked gate",
    note: "FS audit for a prospect: Create waits on the G1 acceptance decision",
    step: 5,
    done: 5,
    v: FS_AUDIT,
  },
];

function stepsOf(step: number, done: number): WizardStep[] {
  return STEPS.map((label, i) => ({
    id: String(i),
    label,
    state: i === step ? "current" : i < done ? "done" : "todo",
  }));
}

function WizardFrame({ frame }: { frame: FrameSpec }): JSX.Element {
  const { v } = frame;
  const [step, setStep] = useState(frame.step);
  const [done, setDone] = useState(frame.done);
  const [type, setType] = useState<string | null>(v.type);
  const [consent, setConsent] = useState(false);
  const fs = v === FS_AUDIT;
  const generated = fs ? step >= 1 && step <= 4 : step === 1 || step === 4;
  const last = step === STEPS.length - 1;
  const summary = `${type === null ? "No type yet" : (NAMES.get(type) ?? "")} · ${v.client}`;
  const noop = (): void => undefined;
  return (
    <Artboard
      id={frame.id}
      badge={`TPL-18${frame.id.slice(-1)}`}
      name={frame.name}
      note={frame.note}
    >
      <AppShell
        embedded
        height={860}
        toolbar={TOOLBAR}
        overlay={
          <div className="absolute inset-0 bg-(--scrim-sheet)">
            <div className="absolute inset-x-[14px] top-[60px] bottom-[14px]">
              <Wizard
                forceState="open"
                open={false}
                onOpenChange={noop}
                title="New engagement"
                subtitle={SAVED}
                subtitleAt="start"
                steps={stepsOf(step, done)}
                onStepChange={(id) => {
                  setStep(Number(id));
                }}
                aside={<WizardSummary>{summary}</WizardSummary>}
                onBack={() => {
                  setStep((s) => Math.max(0, s - 1));
                }}
                onNext={() => {
                  setDone((d) => Math.max(d, step + 1));
                  setStep((s) => Math.min(STEPS.length - 1, s + 1));
                }}
                nextDisabled={step === 0 && type === null}
                onSaveDraft={noop}
                {...(last
                  ? {
                      actions: (
                        <>
                          <Button variant="ghost" size="lg">
                            Save draft
                          </Button>
                          <Button variant="secondary" size="lg" disabled={v.blocked}>
                            Create & send letter
                          </Button>
                          <span data-overlay-action="" className="contents">
                            <Button size="lg" disabled={v.blocked}>
                              Create
                            </Button>
                          </span>
                        </>
                      ),
                    }
                  : {})}
              >
                {step === 0 ? (
                  <ClientAndType v={v} type={type} onType={setType} />
                ) : generated ? (
                  <Generated v={v} step={step} />
                ) : step === 2 ? (
                  <Period />
                ) : step === 3 ? (
                  <Team consent={consent} />
                ) : (
                  <Review
                    v={v}
                    type={type}
                    consent={consent}
                    onConsent={() => {
                      setConsent(true);
                    }}
                  />
                )}
              </Wizard>
            </div>
          </div>
        }
      >
        <Pane title="Engagements" />
      </AppShell>
    </Artboard>
  );
}

/** TPL-18a to TPL-18e (Wave 0 - Templates `#tpl18`). */
export function Tpl18Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {FRAMES.map((frame) => (
        <WizardFrame key={frame.id} frame={frame} />
      ))}
    </div>
  );
}
