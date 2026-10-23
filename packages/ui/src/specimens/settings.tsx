import { type JSX, useState } from "react";
import { Fieldset, FieldsetAdd } from "../components/fieldset";
import { ValueRow } from "../components/inputs";
import { Toast } from "../components/toast";
import { FirmMark } from "../brand/firm-mark";
import { type SettingsGroup, SettingsLayout, SettingsLock } from "../templates/settings-layout";
import guards from "../../scope-guards.gen.json";
import { Artboard } from "./portal";
import { FIRM, RETURNS_BY_OFFICE } from "./seed-figures";

// T12 SettingsLayout (F-05-T45): T12a to T12d (Wave 0 - Foundations `#t12`, Agents & AI) and
// TPL-12a to TPL-12e (Wave 0 - Templates TPL-12, Firm settings › General for Grace Holloway). Every
// string is the canvas's own; the offices' returns are the seed's TY2025 split (98 + 64 + 62 = 224).
// The form state lives here, as it does in a screen: the template draws Save only when dirty and
// valid, Discard only when dirty, and no actions at all in read-only.

const NAV = guards.nav.map((label) => ({ label }));
const TOOLBAR = {
  nav: NAV,
  firm: FIRM,
  firmShort: "Brightwater",
  firmTitle: "Brightwater Hale LLP",
  holdLabelWidth: false,
} as const;

const READ_ONLY = "Only firm admins can edit these settings.";

// ---- Form data ------------------------------------------------------------------------------------

type Row =
  | { kind: "toggle"; id: string; label: string; value: boolean; help?: string; indent?: boolean }
  | {
      kind: "select" | "time";
      id: string;
      label: string;
      value: string;
      options: readonly string[];
      help?: string;
      indent?: boolean;
    }
  | {
      kind: "text";
      id: string;
      label: string;
      value: string;
      help?: string;
      indent?: boolean;
      /** Emptying it reads "Required" with this line under the label. */
      required?: string;
      /** A percentage from 50 to 100 (T12d). */
      pct?: boolean;
    }
  | {
      kind: "value";
      id: string;
      label: string;
      value: string;
      help?: string;
      amber?: boolean;
      trailing?: "lock" | "chevron-right";
    }
  | { kind: "sub"; label: string }
  | { kind: "total"; label: string; value: string }
  | { kind: "logo"; label: string };

interface FormSet {
  title: string;
  add?: string;
  rows: readonly Row[];
}

const TIMES = ["7:00 AM", "8:00 AM", "8:30 AM", "9:00 AM", "7:00 PM", "8:00 PM"] as const;

/** T12's Agents & AI form (canvas `T12.FORMS.agents`). */
const AGENTS: readonly FormSet[] = [
  {
    title: "Agent permissions",
    add: "Add",
    rows: [
      { kind: "toggle", id: "draft", label: "Agents can prepare workpapers", value: true },
      { kind: "toggle", id: "issues", label: "Agents can raise issues", value: true },
      {
        kind: "toggle",
        id: "email",
        label: "Agents can send client email",
        value: false,
        help: "A person sends every client message. Agents only draft.",
      },
      { kind: "text", id: "limit", label: "Approval needed for changes over", value: "2,500" },
    ],
  },
  {
    title: "Schedules",
    rows: [
      { kind: "time", id: "runs", label: "Weekday agent runs", value: "9:00 AM", options: TIMES },
      {
        kind: "select",
        id: "tz",
        label: "Time zone",
        value: "Central Time (Chicago)",
        options: ["Central Time (Chicago)", "Mountain Time (Denver)", "Eastern Time (New York)"],
      },
      { kind: "toggle", id: "quiet", label: "Quiet hours", value: true },
      { kind: "time", id: "qfrom", label: "From", value: "7:00 PM", options: TIMES, indent: true },
      { kind: "time", id: "qto", label: "Until", value: "7:00 AM", options: TIMES, indent: true },
    ],
  },
  {
    title: "Data and citations",
    rows: [
      {
        kind: "select",
        id: "res",
        label: "Data residency",
        value: "United States",
        options: ["United States"],
      },
      {
        kind: "select",
        id: "logs",
        label: "Keep agent run logs",
        value: "7 years",
        options: ["3 years", "7 years", "10 years"],
      },
      { kind: "sub", label: "Citations" },
      { kind: "toggle", id: "cite", label: "Require a citation for every figure", value: true },
      {
        kind: "text",
        id: "cover",
        label: "Minimum citation coverage",
        value: "100%",
        indent: true,
        pct: true,
      },
    ],
  },
];

const OFFICE = RETURNS_BY_OFFICE;

/** TPL-12's General form (canvas `TP12.SETS`). */
const GENERAL: readonly FormSet[] = [
  {
    title: "Firm profile",
    rows: [
      { kind: "text", id: "legal", label: "Legal name", value: "Brightwater Hale LLP" },
      {
        kind: "text",
        id: "display",
        label: "Display name",
        value: FIRM,
        required: "Enter the name clients see in the portal.",
      },
      {
        kind: "value",
        id: "region",
        label: "Primary region",
        value: "United States",
        trailing: "lock",
        help: "Fixed at provisioning. Client data, logs and AI inference stay in the US.",
      },
      {
        kind: "select",
        id: "tz",
        label: "Default time zone",
        value: "Central Time (CT)",
        options: [
          "Eastern Time (ET)",
          "Central Time (CT)",
          "Mountain Time (MT)",
          "Pacific Time (PT)",
        ],
      },
      { kind: "text", id: "mailbox", label: "Intake mailbox", value: "docs@brightwaterhale.com" },
      { kind: "text", id: "web", label: "Website", value: "brightwaterhale.com" },
      { kind: "logo", label: "Logo" },
    ],
  },
  {
    title: "Offices",
    add: "Office",
    rows: [
      {
        kind: "value",
        id: "chi",
        label: "Chicago · HQ",
        value: `22 seats · ${String(OFFICE.Chicago)} TY2025 returns`,
        trailing: "chevron-right",
      },
      {
        kind: "value",
        id: "den",
        label: "Denver",
        value: `14 seats · ${String(OFFICE.Denver)} returns`,
        trailing: "chevron-right",
      },
      {
        kind: "value",
        id: "nyc",
        label: "New York",
        value: `10 seats · ${String(OFFICE["New York"])} returns`,
        trailing: "chevron-right",
      },
      { kind: "total", label: "All offices", value: "46 seats · 224 returns" },
    ],
  },
  {
    title: "Plan & seats",
    rows: [
      {
        kind: "value",
        id: "seats",
        label: "Seats",
        value: "46 of 46 used",
        help: "All seats are assigned. Add seats before inviting another user.",
        amber: true,
      },
      {
        kind: "value",
        id: "people",
        label: "People",
        value: "52",
        help: "7 partners · 37 professional staff · 8 operations; 6 back-office staff hold no seat",
      },
      {
        kind: "value",
        id: "modules",
        label: "Modules",
        value: "Tax · Audit & assurance · Client accounting · Advisory",
      },
      { kind: "value", id: "renewal", label: "Renewal", value: "Jan 1, 2027" },
      {
        kind: "select",
        id: "billing",
        label: "Billing contact",
        value: "Grace Holloway",
        options: ["Grace Holloway", "Margaret Okonkwo", "Felix Andersen"],
      },
    ],
  },
  {
    title: "Defaults",
    rows: [
      {
        kind: "select",
        id: "approval",
        label: "Return approval policy",
        value: "BH-TAX-02",
        options: ["BH-TAX-01", "BH-TAX-02", "BH-TAX-03"],
        help: "The signing partner gives final approval on returns he or she signs.",
      },
      {
        kind: "select",
        id: "aje",
        label: "AJE threshold policy",
        value: "BH AJE thresholds v2",
        options: ["BH AJE thresholds v1", "BH AJE thresholds v2"],
      },
      { kind: "toggle", id: "auto", label: "Auto mode for new audits", value: false },
      {
        kind: "toggle",
        id: "secured",
        label: "Show “Secured by Accrued” in the client portal footer",
        value: false,
      },
      {
        kind: "select",
        id: "week",
        label: "Week starts on",
        value: "Monday",
        options: ["Sunday", "Monday"],
      },
    ],
  },
];

const T12_GROUPS: readonly SettingsGroup[] = [
  {
    label: "FIRM",
    sections: [
      { id: "general", label: "General", icon: "building-2" },
      { id: "offices", label: "Offices", icon: "map-pin" },
      { id: "members", label: "Members", icon: "users" },
      { id: "billing", label: "Billing", icon: "credit-card" },
    ],
  },
  {
    label: "SECURITY & AI",
    sections: [
      { id: "security", label: "Security", icon: "shield-check" },
      { id: "agents", label: "Agents & AI", icon: "sparkles" },
      { id: "integrations", label: "Integrations", icon: "plug" },
      { id: "audit", label: "Audit Log", icon: "scroll-text" },
    ],
  },
  {
    label: "CLIENTS",
    sections: [
      { id: "portal", label: "Client Portal", icon: "globe" },
      { id: "notify", label: "Notifications", icon: "bell" },
    ],
  },
  {
    label: "QUALITY",
    sections: [
      { id: "review", label: "Review Policy", icon: "check" },
      { id: "retention", label: "Retention", icon: "clock" },
    ],
  },
];

const TPL12_GROUPS: readonly SettingsGroup[] = [
  {
    label: "Firm",
    sections: [
      { id: "general", label: "General", icon: "building-2" },
      { id: "people", label: "People", icon: "users-round" },
      { id: "offices", label: "Offices & teams", icon: "map-pin" },
    ],
  },
  {
    label: "Security & AI",
    sections: [
      { id: "security", label: "Security", icon: "lock" },
      { id: "ai", label: "AI policy", icon: "sparkles" },
      { id: "consents", label: "Consents", icon: "signature" },
      { id: "dev", label: "Developer", icon: "code" },
    ],
  },
  {
    label: "Clients",
    sections: [
      { id: "integrations", label: "Integrations", icon: "plug" },
      { id: "portal", label: "Portal", icon: "panels-top-left" },
    ],
  },
  {
    label: "Quality",
    sections: [
      { id: "quality", label: "Quality", icon: "shield-check" },
      { id: "monitoring", label: "Monitoring", icon: "gauge" },
      { id: "audit", label: "Audit log", icon: "scroll-text" },
    ],
  },
];

// ---- Form state -----------------------------------------------------------------------------------

type Values = Readonly<Record<string, string | boolean>>;

function baseOf(sets: readonly FormSet[]): Map<string, string | boolean> {
  const base = new Map<string, string | boolean>();
  for (const set of sets)
    for (const row of set.rows)
      if ("id" in row && row.kind !== "value") base.set(row.id, row.value);
  return base;
}

/** The row's problem, or none: a required text emptied, or a percentage outside 50 to 100. */
function problemOf(row: Row, value: string | boolean | undefined): string | undefined {
  if (row.kind !== "text" || typeof value !== "string") return undefined;
  if (row.required !== undefined && value.trim() === "") return row.required;
  if (row.pct === true) {
    const n = Number(value.replace("%", ""));
    if (!(n >= 50 && n <= 100)) return "Enter a value from 50% to 100%.";
  }
  return undefined;
}

interface FormProps {
  sets: readonly FormSet[];
  values: Values;
  onChange: (id: string, value: string | boolean) => void;
  readOnly: boolean;
  /** T12c: a lock on every row; TPL-12d: a lock on each fieldset header. */
  locks: "rows" | "sets";
}

function Form({ sets, values, onChange, readOnly, locks }: FormProps): JSX.Element {
  const rowLock = readOnly && locks === "rows";
  return (
    <>
      {sets.map((set) => (
        <Fieldset
          key={set.title}
          title={set.title}
          flush
          className="mb-0"
          {...(readOnly && locks === "sets"
            ? { action: <SettingsLock /> }
            : set.add !== undefined
              ? {
                  action: (
                    <FieldsetAdd disabled={readOnly} className={readOnly ? "text-ink-3" : ""}>
                      {set.add}
                    </FieldsetAdd>
                  ),
                }
              : {})}
        >
          {set.rows.map((row) => {
            if (row.kind === "sub")
              return (
                <div
                  key={row.label}
                  className="flex h-[30px] items-center bg-nested px-[12px] text-dense font-medium"
                >
                  {row.label}
                </div>
              );
            if (row.kind === "total")
              return (
                <div
                  key={row.label}
                  data-settings="total"
                  className="flex h-[30px] items-center justify-between bg-sel-bg px-[12px] text-body font-medium"
                >
                  <span>{row.label}</span>
                  <span>{row.value}</span>
                </div>
              );
            if (row.kind === "logo")
              return (
                <ValueRow key={row.label} kind="value" label={row.label} readOnly={readOnly}>
                  <FirmMark name={FIRM} mark="wave" size={20} />
                  {!readOnly && <span>Replace…</span>}
                </ValueRow>
              );
            const help = row.help;
            const common = {
              label: row.label,
              readOnly,
              lock: rowLock,
              ...("indent" in row && row.indent ? { indented: true } : {}),
              ...(help === undefined ? {} : { help }),
            };
            if (row.kind === "value")
              return (
                <ValueRow
                  key={row.id}
                  kind="value"
                  {...common}
                  {...(row.amber === true ? { helpTone: "amber" as const } : {})}
                  {...(row.trailing === undefined ? {} : { trailing: row.trailing })}
                >
                  {row.value}
                </ValueRow>
              );
            const value = values[row.id] ?? row.value;
            if (row.kind === "toggle")
              return (
                <ValueRow
                  key={row.id}
                  kind="toggle"
                  {...common}
                  checked={value === true}
                  onChange={(on) => {
                    onChange(row.id, on);
                  }}
                />
              );
            if (row.kind === "text") {
              const problem = problemOf(row, value);
              return (
                <ValueRow
                  key={row.id}
                  kind="text"
                  {...common}
                  value={String(value)}
                  {...(row.required === undefined ? {} : { placeholder: "Required" })}
                  {...(problem === undefined ? {} : { error: problem, errorAt: "label" as const })}
                  onChange={(text) => {
                    onChange(row.id, text);
                  }}
                />
              );
            }
            return (
              <ValueRow
                key={row.id}
                kind={row.kind}
                {...common}
                value={String(value)}
                options={row.options.map((o) => ({ value: o, label: o }))}
                onChange={(next) => {
                  onChange(row.id, next);
                }}
              />
            );
          })}
        </Fieldset>
      ))}
    </>
  );
}

// ---- Frames ---------------------------------------------------------------------------------------

interface FrameSpec {
  id: string;
  badge: string;
  name: string;
  note: string;
  groups: readonly SettingsGroup[];
  section: string;
  sets: readonly FormSet[];
  edits?: Values;
  readOnly?: boolean;
  readOnlyAt?: "bar" | "form";
  toast?: boolean;
}

function SettingsFrame({ frame }: { frame: FrameSpec }): JSX.Element {
  const base = baseOf(frame.sets);
  const [edits, setEdits] = useState<Values>(frame.edits ?? {});
  const [section, setSection] = useState(frame.section);
  const [toast, setToast] = useState(frame.toast === true);
  const readOnly = frame.readOnly === true;
  const values = edits;
  const dirty = Object.keys(edits).length > 0;
  const invalid = frame.sets.some((set) =>
    set.rows.some(
      (row) => "id" in row && problemOf(row, values[row.id] ?? baseValue(row)) !== undefined,
    ),
  );
  const shown = section === frame.section;
  return (
    <Artboard id={frame.id} badge={frame.badge} name={frame.name} note={frame.note}>
      <SettingsLayout
        embedded
        height={860}
        toolbar={TOOLBAR}
        title="Firm settings"
        context="Brightwater Hale LLP"
        navTitle="Settings"
        groups={frame.groups}
        active={section}
        onSelect={setSection}
        dirty={dirty}
        invalid={invalid}
        readOnly={readOnly}
        readOnlyText={READ_ONLY}
        readOnlyAt={frame.readOnlyAt ?? "bar"}
        onDiscard={() => {
          setEdits({});
        }}
        onSave={() => {
          setEdits({});
          setToast(true);
        }}
        overlay={
          toast ? (
            <div className="pointer-events-none absolute bottom-[20px] left-1/2 -translate-x-1/2">
              <Toast text="Firm settings saved" still />
            </div>
          ) : undefined
        }
      >
        {shown ? (
          <Form
            sets={frame.sets}
            values={values}
            readOnly={readOnly}
            locks={frame.readOnlyAt === "form" ? "rows" : "sets"}
            onChange={(id, value) => {
              setToast(false);
              setEdits((current) => {
                const rest = Object.fromEntries(Object.entries(current).filter(([k]) => k !== id));
                return base.get(id) === value ? rest : { ...rest, [id]: value };
              });
            }}
          />
        ) : (
          <p className="px-[2px] text-body text-ink-3">
            {`${frame.groups.flatMap((g) => g.sections).find((s) => s.id === section)?.label ?? ""} has its own screen. This specimen shows ${frame.groups.flatMap((g) => g.sections).find((s) => s.id === frame.section)?.label ?? ""}.`}
          </p>
        )}
      </SettingsLayout>
    </Artboard>
  );
}

function baseValue(row: Row): string | boolean | undefined {
  return "value" in row && row.kind !== "total" ? row.value : undefined;
}

const T12_FRAMES: readonly FrameSpec[] = [
  {
    id: "t12a",
    badge: "T12a",
    name: "Clean",
    note: "Agents & AI with nothing changed, so Save stays disabled",
    groups: T12_GROUPS,
    section: "agents",
    sets: AGENTS,
  },
  {
    id: "t12b",
    badge: "T12b",
    name: "Dirty",
    note: "Two changes made: Unsaved changes, Discard and Save",
    groups: T12_GROUPS,
    section: "agents",
    sets: AGENTS,
    edits: { runs: "8:30 AM", email: true },
  },
  {
    id: "t12c",
    badge: "T12c",
    name: "Read-only",
    note: "Kevin Osei isn’t an admin: the banner, locks and ink-2 values",
    groups: T12_GROUPS,
    section: "agents",
    sets: AGENTS,
    readOnly: true,
    readOnlyAt: "form",
  },
  {
    id: "t12d",
    badge: "T12d",
    name: "Validation error",
    note: "Coverage over 100% shows in red ink with its helper",
    groups: T12_GROUPS,
    section: "agents",
    sets: AGENTS,
    edits: { cover: "120%" },
  },
];

const TPL12_FRAMES: readonly FrameSpec[] = [
  {
    id: "tpl-12a",
    badge: "TPL-12a",
    name: "Clean",
    note: "Grace Holloway, firm admin. Save stays disabled until something changes",
    groups: TPL12_GROUPS,
    section: "general",
    sets: GENERAL,
  },
  {
    id: "tpl-12b",
    badge: "TPL-12b",
    name: "Dirty",
    note: "Default time zone changed to Eastern Time (ET)",
    groups: TPL12_GROUPS,
    section: "general",
    sets: GENERAL,
    edits: { tz: "Eastern Time (ET)" },
  },
  {
    id: "tpl-12c",
    badge: "TPL-12c",
    name: "Validation",
    note: "Display name emptied, so it reads Required and Save is blocked",
    groups: TPL12_GROUPS,
    section: "general",
    sets: GENERAL,
    edits: { display: "" },
  },
  {
    id: "tpl-12d",
    badge: "TPL-12d",
    name: "Read-only",
    note: "Hannah Leclerc sees every value, locked",
    groups: TPL12_GROUPS,
    section: "general",
    sets: GENERAL,
    readOnly: true,
  },
  {
    id: "tpl-12e",
    badge: "TPL-12e",
    name: "Saved",
    note: "The toast confirms the save",
    groups: TPL12_GROUPS,
    section: "general",
    sets: GENERAL,
    toast: true,
  },
];

/** T12a to T12d (Wave 0 - Foundations `#t12`). */
export function T12Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {T12_FRAMES.map((frame) => (
        <SettingsFrame key={frame.id} frame={frame} />
      ))}
    </div>
  );
}

/** TPL-12a to TPL-12e (Wave 0 - Templates TPL-12). */
export function Tpl12Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      {TPL12_FRAMES.map((frame) => (
        <SettingsFrame key={frame.id} frame={frame} />
      ))}
    </div>
  );
}
