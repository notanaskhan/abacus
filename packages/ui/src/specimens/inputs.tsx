import { type JSX, useState } from "react";
import { Fieldset, FieldsetAdd } from "../components/fieldset";
import {
  FilterChip,
  Picker,
  type PickerOption,
  type PickerVariant,
  SearchField,
  ValueRow,
} from "../components/inputs";
import { Held, Row, Sheet } from "./frame";

// The inputs' specimens (Component Sheet family F and C-13; F-05-T15): the search pill, the
// pickers, the filter chip, the value rows and the fieldset. There is no native select and no
// boxed input on this page. Every variant is drawn with each held state (hover, focus, pressed,
// open) and disabled; the open ones are held in place and sit in reserved space. Option words are
// UI vocabulary (the schedule choices of C-13, status words); nothing here is sample data.

const STATUS: PickerOption[] = [
  { value: "all", label: "All" },
  { value: "requested", label: "Requested" },
  { value: "received", label: "Received" },
  { value: "archived", label: "Archived", disabled: true },
];
const CLIENTS: PickerOption[] = [
  { value: "summit", label: "Summit Trail" },
  { value: "alpine", label: "Alpine Ridge" },
];
const REPEATS: PickerOption[] = [
  { value: "hourly", label: "Hourly" },
  { value: "daily", label: "Daily" },
  { value: "weekdays", label: "Weekdays" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
];
const TIME_ZONES: PickerOption[] = [
  { value: "et", label: "Eastern Time (ET)" },
  { value: "ct", label: "Central Time (CT)" },
  { value: "mt", label: "Mountain Time (MT)" },
  { value: "az", label: "Arizona (MST)" },
  { value: "pt", label: "Pacific Time (PT)" },
];
const TIMES: PickerOption[] = [
  { value: "0900", label: "09:00 AM" },
  { value: "0930", label: "09:30 AM" },
  { value: "1000", label: "10:00 AM" },
];

const VARIANTS: readonly { variant: PickerVariant; name: string; meaning: string }[] = [
  { variant: "white", name: "white", meaning: "Pill on e1, chevron-down" },
  { variant: "fill", name: "fill", meaning: "nav-fill, up-down chevrons" },
  { variant: "filter", name: "filter", meaning: "Icon only: list-filter and a chevron" },
];

export function SearchFieldSpecimen(): JSX.Element {
  const [text, setText] = useState("");
  return (
    <Sheet
      title="SearchField"
      meta="28 high pill, nested on a hair ring · white and firmer on focus"
    >
      <Row name="Empty">
        <SearchField label="Search, empty" />
      </Row>
      <Row name="Focus" meaning="Held">
        <SearchField label="Search, focus" forceState="focus" />
      </Row>
      <Row name="Filled" meaning="A 16px clear button, with a 24px hit area">
        <SearchField label="Search, filled" defaultValue="Summit Trail" />
      </Row>
      <Row name="Live" meaning="Type; Escape or the button clears">
        <SearchField label="Search, live" value={text} onChange={setText} />
        <span className="text-meta text-ink-3">{`${String(text.length)} characters`}</span>
      </Row>
    </Sheet>
  );
}

export function PickerSpecimen(): JSX.Element {
  const [value, setValue] = useState("all");
  return (
    <Sheet
      title="Picker"
      meta="In place of a native select · a menu of radio items · ↓ opens, Escape closes"
    >
      {VARIANTS.map(({ variant, name, meaning }) => (
        <Row key={variant} name={name} meaning={meaning}>
          <Held name="default">
            <Picker
              label={`Status ${name}`}
              variant={variant}
              options={STATUS}
              defaultValue="all"
            />
          </Held>
          {(["hover", "focus", "pressed"] as const).map((state) => (
            <Held key={state} name={state}>
              <Picker
                label={`Status ${name} ${state}`}
                variant={variant}
                options={STATUS}
                defaultValue="all"
                forceState={state}
              />
            </Held>
          ))}
          <Held name="disabled">
            <Picker
              label={`Status ${name} disabled`}
              variant={variant}
              options={STATUS}
              defaultValue="all"
              disabled
            />
          </Held>
          <Held name="placeholder">
            <Picker
              label={`Status ${name} empty`}
              variant={variant}
              options={STATUS}
              placeholder="Any"
            />
          </Held>
        </Row>
      ))}
      <Row name="Open" meaning="Held in place; the current option is checked, one is disabled">
        <div className="flex min-h-[200px] items-start gap-[260px]">
          <Held name="white">
            <Picker
              label="Status open"
              options={STATUS}
              defaultValue="requested"
              forceState="open"
            />
          </Held>
        </div>
      </Row>
      <Row name="Live" meaning="Choose an option">
        <Picker label="Status live" options={STATUS} value={value} onChange={setValue} />
        <span className="text-meta text-ink-3">{`Chosen: ${value}`}</span>
      </Row>
    </Sheet>
  );
}

export function FilterChipSpecimen(): JSX.Element {
  const [client, setClient] = useState<string | null>(null);
  return (
    <Sheet
      title="FilterChip"
      meta="Split pill: what is filtered, then its value · amber once a value is chosen"
    >
      <Row name="Empty" meaning="White on e1">
        <Held name="default">
          <FilterChip label="Client" icon="building-2" options={CLIENTS} />
        </Held>
        {(["hover", "focus", "pressed"] as const).map((state) => (
          <Held key={state} name={state}>
            <FilterChip
              label={`Client ${state}`}
              icon="building-2"
              options={CLIENTS}
              forceState={state}
            />
          </Held>
        ))}
      </Row>
      <Row name="Active" meaning="Amber tint, the value in 500">
        <Held name="default">
          <FilterChip label="Client" icon="building-2" options={CLIENTS} value="summit" />
        </Held>
        {(["hover", "focus", "pressed"] as const).map((state) => (
          <Held key={state} name={state}>
            <FilterChip
              label={`Client ${state}`}
              icon="building-2"
              options={CLIENTS}
              value="summit"
              forceState={state}
            />
          </Held>
        ))}
        <Held name="no icon">
          <FilterChip label="Status" options={STATUS} value="requested" />
        </Held>
      </Row>
      <Row name="Open" meaning="Held in place">
        <div className="flex min-h-[190px] items-start">
          <FilterChip
            label="Client open"
            icon="building-2"
            options={CLIENTS}
            value="alpine"
            clearLabel="Any client"
            forceState="open"
          />
        </div>
      </Row>
      <Row name="Live" meaning="Choose, or clear with the first item">
        <FilterChip
          label="Client live"
          icon="building-2"
          options={CLIENTS}
          value={client}
          clearLabel="Any client"
          onChange={setClient}
        />
        <span className="text-meta text-ink-3">{`Chosen: ${client ?? "none"}`}</span>
      </Row>
    </Sheet>
  );
}

export function ValueRowSpecimen(): JSX.Element {
  const [name, setName] = useState("");
  const [on, setOn] = useState(true);
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <Sheet
        title="ValueRow"
        meta="34 high · label at the left, value at the right · no boxed inputs"
      >
        <Fieldset flush className="m-[12px]">
          <ValueRow kind="select" label="Repeats" value="daily" options={REPEATS} />
          <ValueRow
            kind="select"
            label="Time zone"
            value="ct"
            options={TIME_ZONES}
            menuWidth={230}
          />
          <ValueRow kind="time" label="Time" value="0900" options={TIMES} menuWidth={150} />
          <ValueRow
            kind="select"
            label="Hover"
            value="daily"
            options={REPEATS}
            forceState="hover"
          />
          <ValueRow
            kind="text"
            label="Name"
            placeholder="Required"
            value={name}
            onChange={setName}
          />
          <ValueRow kind="text" label="Name, focus" defaultValue="Chaser" forceState="focus" />
          <ValueRow kind="toggle" label="Enabled" checked={on} onChange={setOn} />
          <ValueRow kind="toggle" label="Disabled" disabled />
          <ValueRow kind="info" label="Next run">
            Paused
          </ValueRow>
          <ValueRow kind="select" label="Indented" indented value="weekly" options={REPEATS} />
        </Fieldset>
      </Sheet>
      <Sheet
        title="ValueRow: validation and paragraph"
        meta="Brick value and an alert line under it"
      >
        <Fieldset flush className="m-[12px]">
          <ValueRow
            kind="text"
            label="Name"
            placeholder="Required"
            error="Give the agent a name."
          />
          <ValueRow
            kind="select"
            label="Days"
            value="weekly"
            options={REPEATS}
            error="Pick at least one day."
          />
          <ValueRow
            kind="text"
            label="Name, indented"
            indented
            placeholder="Required"
            error="Give the agent a name."
          />
          <ValueRow kind="paragraph" label="Description" placeholder="What this agent does" />
        </Fieldset>
        <div className="flex min-h-[230px] items-start px-3 pb-3">
          <Held name="select, open">
            <div className="w-[300px] rounded-nested bg-card shadow-e1">
              <ValueRow
                kind="select"
                label="Repeats"
                value="daily"
                options={REPEATS.slice(0, 4)}
                forceState="open"
              />
            </div>
          </Held>
        </div>
      </Sheet>
    </div>
  );
}

export function FieldsetSpecimen(): JSX.Element {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <Sheet
        title="Fieldset"
        meta="Radius 10, white on e1 · band header 33 high · hairlines between rows"
      >
        <div className="flex flex-col p-3">
          <Fieldset title="Details" flush>
            <ValueRow kind="text" label="Name" placeholder="Required" />
            <ValueRow
              kind="select"
              label="Visibility"
              value="firm"
              options={[{ value: "firm", label: "Firm" }]}
            />
          </Fieldset>
          <Fieldset title="Schedule" flush action={<FieldsetAdd>Schedule</FieldsetAdd>}>
            <ValueRow kind="toggle" label="Enabled" />
            <ValueRow kind="info" label="Next run">
              Paused
            </ValueRow>
          </Fieldset>
        </div>
      </Sheet>
      <Sheet
        title="Fieldset: free content and empty"
        meta="Padded body in a drawer, and the empty line"
      >
        <div className="flex flex-col p-3">
          <Fieldset title="Message">
            <p className="text-ink-2">Free content sits in a padded body.</p>
          </Fieldset>
          <Fieldset>
            <p className="text-ink-2">No header without a title.</p>
          </Fieldset>
          <Fieldset title="Inputs">
            <p className="text-dense text-ink-3">No inputs. This agent runs without a form.</p>
          </Fieldset>
        </div>
      </Sheet>
    </div>
  );
}
