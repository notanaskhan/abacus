import { type JSX, type ReactNode, useState } from "react";
import { PortalBrandProvider } from "../brand";
import { Row, Sheet } from "./frame";
import { Artboard, BRIGHTWATER_BRAND } from "./portal";
import { FIRM } from "./seed-figures";
import { PortalLayout, portalNav } from "../templates/portal-layout";
import {
  type CategoryKey,
  MarkAsDone,
  type RequestBinderProps,
  RequestDocuments,
  type RequestItem,
  RequestMobile,
  RequestRail,
  RequestRow,
  RequestSection,
  type RequestSectionData,
  type UploadInFlight,
  doneButton,
  useRequestBinder,
  withoutKeys,
} from "../requests";

// C-16 Request kit, portal variant (F-05-T36): the row states, then T7a to T7g and T7-M (the T7
// handoff, Marcus & Dana Whitley's 2025 Binder and the Feld reduced pane), then TPL-07a to TPL-07f
// and TPL-07-M (Claire Feld's 2025 Binder, Wave 0 - Templates `TP7`). Every name, file and date is
// the canvas's own. TPL-07a has exactly two open requests, the firm's Intake 2 on the Feld return.

const TODAY = "Sep 14";
const INDIVIDUAL = portalNav("individual");

// ---- T7: Marcus & Dana Whitley ----------------------------------------------------------------

const T7_SECTIONS: readonly RequestSectionData[] = [
  { key: "w2", category: "income", title: "W-2s", icon: "banknote" },
  {
    key: "1099",
    category: "income",
    title: "1099s (all types), interest, dividends",
    icon: "banknote",
  },
  { key: "mort", category: "home", title: "Mortgage interest and property taxes", icon: "house" },
  {
    key: "retire",
    category: "retire",
    title: "Retirement account contributions",
    icon: "piggy-bank",
  },
  { key: "hsa", category: "health", title: "Health savings account", icon: "heart" },
  { key: "give", category: "charity", title: "Charitable gifts", icon: "hand-heart" },
  { key: "other", category: "other", title: "Other documents you uploaded", icon: "ellipsis" },
];

const T7_REQUESTS: readonly (readonly [string, string, string, string])[] = [
  ["w2m", "w2", "2025 W-2 From Alpine Ridge Engineering, Inc.", "Whitley_2025_W2_AlpineRidge.pdf"],
  ["w2d", "w2", "2025 W-2 From Cherry Creek Pediatrics", "Whitley_2025_W2_CherryCreek.pdf"],
  [
    "int",
    "1099",
    "2025 Form 1099-INT From Bellco Credit Union",
    "Whitley_2025_1099-INT_Bellco.pdf",
  ],
  [
    "brk",
    "1099",
    "Consolidated 1099 From Fidelity Investments (account ending 2219)",
    "Whitley_2025_1099_Composite_Fidelity.pdf",
  ],
  ["1098", "mort", "2025 Form 1098 From Mile High Home Loans", "Whitley_2025_1098_MileHigh.pdf"],
  [
    "ptax",
    "mort",
    "2025 Property tax statement · Denver County",
    "Whitley_2025_Property_Tax_Denver.pdf",
  ],
  [
    "ira",
    "retire",
    "2025 Form 5498 From Fidelity Investments (IRA ending 7730)",
    "Whitley_2025_5498_Fidelity.pdf",
  ],
  ["hsa", "hsa", "2025 Form 5498-SA From HealthEquity", "Whitley_2025_5498-SA_HealthEquity.pdf"],
  ["gift", "give", "Receipts for gifts of $250 or more", "Whitley_2025_Charitable_Receipts.pdf"],
];

/** The canvas's `mk`: each request is open, uploaded on a date, ignored, or back for follow-up. */
function whitley(ups: Readonly<Record<string, string>>): RequestItem[] {
  return T7_REQUESTS.map(([id, sec, title, f]) => {
    const base = { id, sec, title, req: "Sep 8", fname: f };
    const u = ups[id];
    if (u === undefined) return { ...base, st: "req" as const };
    if (u === "na") return { ...base, st: "na" as const, reason: "Not applicable this year" };
    if (u === "fu") {
      return {
        ...base,
        st: "fu" as const,
        file: f.replace("2025", "2024"),
        up: "Sep 12",
        note: "This one shows 2024. Could you download the 2025 form from Bellco and upload it here?",
      };
    }
    return { ...base, st: "up" as const, file: f, on: u };
  });
}

const PART = { w2m: "Sep 12", w2d: "Sep 12", brk: "Sep 13", "1098": "Sep 12", int: "fu" };
const INCOME = { w2m: "Sep 12", w2d: "Sep 12", int: "Sep 13", brk: "Sep 13", "1098": "Sep 12" };
const ALL = { ...INCOME, ptax: "Sep 14", ira: "Sep 14", hsa: "na", gift: "Sep 14" };
const T7_UPLOADS: readonly UploadInFlight[] = [
  { name: "Whitley_2025_5498_Fidelity.pdf", size: "214 KB", p: 0.68 },
  { name: "Whitley_2025_Property_Tax_Denver.pdf", size: "1.1 MB", p: 0.31 },
];

const FELD_SECTIONS: readonly RequestSectionData[] = [
  { key: "w2", category: "income", title: "W-2s", icon: "banknote" },
  {
    key: "1099",
    category: "income",
    title: "1099s (all types), interest, dividends",
    icon: "banknote",
  },
  { key: "mort", category: "home", title: "Mortgage interest and property taxes", icon: "house" },
  { key: "give", category: "charity", title: "Charitable gifts", icon: "hand-heart" },
];

const FELD_T7G: readonly RequestItem[] = [
  {
    id: "fw2",
    sec: "w2",
    title: "2025 W-2 From Lakeview Medical Group",
    file: "Feld_2025_W2_LakeviewMedical.pdf",
    st: "acc",
    on: "Aug 9",
    up: "Aug 7",
    req: "Jul 14",
  },
  {
    id: "fbrk",
    sec: "1099",
    title: "2025 Composite 1099 From Brightline Securities",
    file: "Feld_2025_1099_Composite_Brightline.pdf",
    st: "up",
    on: "Aug 7",
    req: "Jul 14",
  },
  {
    id: "f1098",
    sec: "mort",
    title: "2025 Form 1098 From Prairie State Bank",
    file: "Feld_2025_1098_PrairieState.pdf",
    st: "up",
    on: "Aug 7",
    req: "Jul 14",
  },
  {
    id: "fptax",
    sec: "mort",
    title: "2025 Property tax bill · Cook County",
    st: "req",
    req: "Sep 11",
    fname: "Feld_2025_Property_Tax_Cook.pdf",
  },
  {
    id: "fgift",
    sec: "give",
    title: "Receipts for gifts of $250 or more",
    st: "req",
    req: "Sep 11",
    fname: "Feld_2025_Charitable_Receipts.pdf",
  },
];

// ---- TPL-07: Claire Feld ------------------------------------------------------------------------

const TPL07_SECTIONS: readonly RequestSectionData[] = [
  { key: "w2", category: "income", title: "W-2s", icon: "banknote" },
  {
    key: "1099",
    category: "income",
    title: "1099s (all types), interest, dividends",
    icon: "banknote",
  },
  { key: "k1", category: "income", title: "Partnership K-1s", icon: "briefcase" },
  { key: "mort", category: "home", title: "Mortgage interest and property taxes", icon: "house" },
  { key: "aca", category: "health", title: "Health insurance", icon: "heart" },
  { key: "give", category: "charity", title: "Charitable contributions", icon: "hand-heart" },
  { key: "est", category: "other", title: "Estimated tax payments", icon: "ellipsis" },
];

const TPL07_REQUESTS: readonly RequestItem[] = [
  {
    id: "w2",
    sec: "w2",
    title: "2025 W-2 From Mercer Hill Health",
    file: "Claire_Feld_2025_W2_MercerHill.pdf",
    st: "up",
    on: "Aug 3",
    upText: "Received by email Aug 3",
    req: "Jul 14",
  },
  {
    id: "brk",
    sec: "1099",
    title: "2025 Consolidated 1099 From Halvard Securities (Acct ••3318)",
    file: "Jonah_Feld_2025_1099_Composite_Halvard.pdf",
    st: "up",
    on: "Aug 5",
    upText: "Jonah uploaded Aug 5",
    req: "Jul 14",
  },
  {
    id: "k1",
    sec: "k1",
    title: "Schedule K-1 from Ridgeline Property Partners, LP",
    st: "firm",
    note: "Brightwater Hale prepares this K-1 and adds it for you. Nothing to upload.",
    req: "Jul 14",
  },
  {
    id: "m1098",
    sec: "mort",
    title: "2025 Form 1098 From Hudson Mutual Savings (co-op loan)",
    file: "Claire_Feld_2025_1098_HudsonMutual.pdf",
    st: "up",
    on: "Aug 3",
    upText: "Received by email Aug 3",
    req: "Jul 14",
  },
  {
    id: "aca",
    sec: "aca",
    title: "Form 1095-C From Mercer Hill Health",
    st: "req",
    req: "Sep 11",
    fname: "Claire_Feld_2025_1095-C_MercerHill.pdf",
  },
  {
    id: "gift",
    sec: "give",
    title: "2025 donation receipts and acknowledgment letters",
    file: "Feld_2025_Donations.pdf",
    st: "up",
    on: "Aug 7",
    upText: "You uploaded Aug 7",
    req: "Jul 14",
  },
  {
    id: "est",
    sec: "est",
    title: "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
    st: "req",
    req: "Sep 11",
    fname: "Feld_2025_Estimated_Payments.pdf",
    uploading: "Uploading 2 files…",
  },
];

const EST: Partial<RequestItem> = {
  st: "up",
  file: "Feld_2025_Estimated_Payments.pdf",
  on: "Sep 14",
  upText: "You uploaded Sep 14",
  matched: true,
};
const ACA: Partial<RequestItem> = {
  st: "up",
  file: "Claire_Feld_2025_1095-C_MercerHill.pdf",
  on: "Sep 14",
  upText: "Received by email Sep 14",
};
const TPL07_UPLOADS: readonly UploadInFlight[] = [
  { name: "Feld_2025_Estimated_Payments.pdf", size: "1.1 MB", p: 0.64 },
  { name: "Feld_2025_IT2105_Confirmations.pdf", size: "380 KB", p: 0.38 },
];

function withPatch(patch: Readonly<Record<string, Partial<RequestItem>>>): RequestItem[] {
  return TPL07_REQUESTS.map((r) => {
    const p = patch[r.id];
    if (p === undefined) return r;
    return { ...withoutKeys(r, ["uploading"]), ...p };
  });
}

// ---- Frames -------------------------------------------------------------------------------------

interface BoardProps extends Omit<RequestBinderProps, "firm" | "today" | "binder"> {
  user: string;
  variant?: "split" | "reduced";
}

/** One 1400 × 860 artboard: the portal toolbar over the Request kit's rail and Documents pane. */
function PortalBoard({ user, variant = "split", ...binderProps }: BoardProps): JSX.Element {
  const binder = useRequestBinder({
    firm: FIRM,
    today: TODAY,
    binder: "2025 Binder",
    viewer: { kind: "human", name: user },
    ...binderProps,
  });
  const [active, setActive] = useState("Documents");
  return (
    <PortalBrandProvider brand={BRIGHTWATER_BRAND}>
      <PortalLayout
        variant={variant}
        user={user}
        nav={INDIVIDUAL}
        active={active}
        onNavigate={setActive}
        frame
        height={860}
        {...(variant === "split" ? { rail: <RequestRail binder={binder} /> } : {})}
      >
        <RequestDocuments binder={binder} reduced={variant === "reduced"} />
      </PortalLayout>
    </PortalBrandProvider>
  );
}

/** The 390 × 844 phone: the binder in one column over the bottom tab bar. */
function MobileBoard({ user, ...binderProps }: BoardProps): JSX.Element {
  const binder = useRequestBinder({
    firm: FIRM,
    today: TODAY,
    binder: "2025 Binder",
    viewer: { kind: "human", name: user },
    ...binderProps,
  });
  const [active, setActive] = useState("Documents");
  return (
    <PortalBrandProvider brand={BRIGHTWATER_BRAND}>
      <PortalLayout
        variant="mobile"
        user={user}
        nav={INDIVIDUAL}
        active={active}
        onNavigate={setActive}
        frame
      >
        <RequestMobile binder={binder} />
      </PortalLayout>
    </PortalBrandProvider>
  );
}

function Boards({ children }: { children: ReactNode }): JSX.Element {
  return <div className="flex flex-col gap-6">{children}</div>;
}

/** T7a to T7g and T7-M (the T7 handoff). */
export function T7Specimen(): JSX.Element {
  return (
    <Boards>
      <Artboard
        id="t7a"
        badge="T7a"
        name="First visit"
        note="Nothing is uploaded yet, so every request is open"
      >
        <PortalBoard user="Dana Whitley" requests={whitley({})} sections={T7_SECTIONS} />
      </Artboard>
      <Artboard
        id="t7b"
        badge="T7b"
        name="Uploading"
        note="Two files upload while the arc fills. One W-2 is back with a follow-up"
      >
        <PortalBoard
          user="Dana Whitley"
          requests={whitley(PART)}
          sections={T7_SECTIONS}
          uploads={T7_UPLOADS}
        />
      </Artboard>
      <Artboard
        id="t7c"
        badge="T7c"
        name="Drop target"
        note="Files dragged over the list: the well turns the nested fill with a 2px espresso ring"
      >
        <PortalBoard
          user="Dana Whitley"
          requests={whitley(PART)}
          sections={T7_SECTIONS}
          drag={{ count: 3 }}
        />
      </Artboard>
      <Artboard
        id="t7d"
        badge="T7d"
        name="Category complete"
        note="Every Income Sources request is in, so its category shows the green check"
      >
        <PortalBoard user="Dana Whitley" requests={whitley(INCOME)} sections={T7_SECTIONS} />
      </Artboard>
      <Artboard
        id="t7e"
        badge="T7e"
        name="All done"
        note="Every request is satisfied and Mark as Done turns olive"
      >
        <PortalBoard user="Dana Whitley" requests={whitley(ALL)} sections={T7_SECTIONS} />
      </Artboard>
      <Artboard
        id="t7f"
        badge="T7f"
        name="Empty"
        note="Nothing is requested, so the pane reads “You’re all caught up.”"
      >
        <PortalBoard user="Dana Whitley" requests={[]} sections={T7_SECTIONS} />
      </Artboard>
      <Artboard
        id="t7g"
        badge="T7g"
        name="Reduced"
        note="One centered 720 pane for Jonah & Claire Feld’s 2 open requests"
      >
        <PortalBoard
          user="Claire Feld"
          variant="reduced"
          requests={FELD_T7G}
          sections={FELD_SECTIONS}
        />
      </Artboard>
      <Artboard id="t7-m" badge="T7-M" name="Mobile" note="390 wide, for Dana Whitley">
        <MobileBoard user="Dana Whitley" requests={whitley(PART)} sections={T7_SECTIONS} />
      </Artboard>
    </Boards>
  );
}

const PERSONAL: readonly CategoryKey[] = ["personal"];

/** TPL-07a to TPL-07f and TPL-07-M (Wave 0 - Templates, `TP7`). */
export function Tpl07Specimen(): JSX.Element {
  return (
    <Boards>
      <Artboard
        id="tpl-07a"
        badge="TPL-07a"
        name="Default"
        note="Two open requests, matching Intake 2 on the firm side. Two files upload in the rail"
      >
        <PortalBoard
          user="Claire Feld"
          requests={TPL07_REQUESTS}
          sections={TPL07_SECTIONS}
          uploads={TPL07_UPLOADS}
          doneCats={PERSONAL}
        />
      </Artboard>
      <Artboard
        id="tpl-07b"
        badge="TPL-07b"
        name="Drop target"
        note="Three files over the list: the well turns the nested fill with a 2px espresso ring"
      >
        <PortalBoard
          user="Claire Feld"
          requests={TPL07_REQUESTS}
          sections={TPL07_SECTIONS}
          uploads={TPL07_UPLOADS}
          doneCats={PERSONAL}
          drag={{
            count: 3,
            names: [
              "Claire_Feld_2025_1095-C_MercerHill.pdf",
              "Feld_2025_Estimated_Payments.pdf",
              "Feld_2025_IT2105_Confirmations.pdf",
            ],
          }}
        />
      </Artboard>
      <Artboard
        id="tpl-07c"
        badge="TPL-07c"
        name="Uploads finished"
        note="The estimated payments match their request, so Other Activity gets its tick"
      >
        <PortalBoard
          user="Claire Feld"
          requests={withPatch({ est: EST })}
          sections={TPL07_SECTIONS}
          doneCats={PERSONAL}
        />
      </Artboard>
      <Artboard
        id="tpl-07d"
        badge="TPL-07d"
        name="All done"
        note="The firm filed Claire’s emailed 1095-C, so Mark as Done turns olive"
      >
        <PortalBoard
          user="Claire Feld"
          requests={withPatch({ est: EST, aca: ACA })}
          sections={TPL07_SECTIONS}
          doneCats={PERSONAL}
        />
      </Artboard>
      <Artboard
        id="tpl-07e"
        badge="TPL-07e"
        name="Empty"
        note="Brightwater Hale hasn’t requested anything new"
      >
        <PortalBoard user="Claire Feld" requests={[]} sections={TPL07_SECTIONS} />
      </Artboard>
      <Artboard
        id="tpl-07f"
        badge="TPL-07f"
        name="Ignore menu"
        note="Ignore on the 1095-C opens its three reasons"
      >
        <PortalBoard
          user="Claire Feld"
          requests={TPL07_REQUESTS}
          sections={TPL07_SECTIONS}
          doneCats={PERSONAL}
          openIgnore="aca"
        />
      </Artboard>
      <Artboard
        id="tpl-07-m"
        badge="TPL-07-M"
        name="Mobile 390"
        note="The same binder for Claire Feld, with the bottom tab bar"
      >
        <MobileBoard user="Claire Feld" requests={TPL07_REQUESTS} sections={TPL07_SECTIONS} />
      </Artboard>
    </Boards>
  );
}

// ---- Row states ---------------------------------------------------------------------------------

const STATE_ROWS: readonly {
  name: string;
  meaning: string;
  item: RequestItem;
  sections: readonly RequestSectionData[];
  hover?: boolean;
}[] = [
  {
    name: "Uploaded",
    meaning: "Your own upload, hovered: Trash2 at the end",
    item: TPL07_REQUESTS[5] as RequestItem,
    sections: TPL07_SECTIONS,
    hover: true,
  },
  {
    name: "Accepted",
    meaning: "The firm accepted it",
    item: FELD_T7G[0] as RequestItem,
    sections: FELD_SECTIONS,
  },
  {
    name: "Requested",
    meaning: "Missing is neutral: Upload… and Ignore, never red",
    item: TPL07_REQUESTS[4] as RequestItem,
    sections: TPL07_SECTIONS,
  },
  {
    name: "Needs follow-up",
    meaning: "The firm's note and Reply…",
    item: whitley(PART)[2] as RequestItem,
    sections: T7_SECTIONS,
  },
  {
    name: "Not applicable",
    meaning: "Ignored with a reason, with Undo",
    item: whitley(ALL)[7] as RequestItem,
    sections: T7_SECTIONS,
  },
  {
    name: "Firm-provided",
    meaning: "Nothing to upload",
    item: TPL07_REQUESTS[2] as RequestItem,
    sections: TPL07_SECTIONS,
  },
];

function StateSection({ row }: { row: (typeof STATE_ROWS)[number] }): JSX.Element {
  const section = row.sections.find((x) => x.key === row.item.sec);
  return (
    <RequestSection title={section?.title ?? ""} icon={section?.icon ?? "file-text"}>
      <RequestRow
        item={row.item}
        firm={FIRM}
        today={TODAY}
        hover={row.hover ?? false}
        viewer={{ kind: "human", name: "Dana Whitley" }}
      />
    </RequestSection>
  );
}

/** C-16 RequestRow states and the Mark as Done header button, tonal and olive. */
export function RequestRowsSpecimen(): JSX.Element {
  return (
    <Sheet title="RequestRow" meta="Client side · padding 12 14 · hairline between rows">
      {STATE_ROWS.map((s) => (
        <Row key={s.name} name={s.name} meaning={s.meaning}>
          <div className="w-[640px]">
            <StateSection row={s} />
          </div>
        </Row>
      ))}
      <Row name="Mark as Done" meaning="Tonal while requests are open, olive when all are in">
        <MarkAsDone view={doneButton(TPL07_REQUESTS, false)} onClick={() => undefined} />
        <MarkAsDone
          view={doneButton(withPatch({ est: EST, aca: ACA }), false)}
          onClick={() => undefined}
        />
      </Row>
    </Sheet>
  );
}
