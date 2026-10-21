import { type JSX, useState } from "react";
import { Checkbox, Radio, RadioGroup, Toggle } from "../components/toggles";
import { Held, Row, Sheet } from "./frame";

// Toggle, Radio, issue ring and Checkbox specimens (Component Sheet family F; F-05-T15): every size
// and every value (off, on, mixed, disabled) with each held state. Anything under 24px has a 24px
// hit area; the sheet says so beside it.

const SIZES = [
  { size: "default", name: "38 × 22", hit: "hit area 38 × 24" },
  { size: "small", name: "34 × 20", hit: "hit area 34 × 24" },
] as const;

export function ToggleSpecimen(): JSX.Element {
  const [on, setOn] = useState(false);
  return (
    <Sheet
      title="Toggle"
      meta="role=switch · olive when on · the knob moves in 180ms · never blue"
    >
      {SIZES.map(({ size, name, hit }) => (
        <Row key={size} name={name} spec={hit}>
          <Held name="off">
            <Toggle label={`Off ${name}`} size={size} />
          </Held>
          <Held name="on">
            <Toggle label={`On ${name}`} size={size} defaultChecked />
          </Held>
          <Held name="disabled, on">
            <Toggle label={`Disabled on ${name}`} size={size} defaultChecked disabled />
          </Held>
          <Held name="disabled, off">
            <Toggle label={`Disabled off ${name}`} size={size} disabled />
          </Held>
          {(["focus", "pressed"] as const).map((state) => (
            <Held key={state} name={state}>
              <Toggle label={`${state} ${name}`} size={size} forceState={state} />
            </Held>
          ))}
        </Row>
      ))}
      <Row name="Live" meaning="Click or press Space">
        <Toggle label="Live" checked={on} onChange={setOn} />
        <span className="text-meta text-ink-3">{on ? "On" : "Off"}</span>
      </Row>
    </Sheet>
  );
}

export function RadioSpecimen(): JSX.Element {
  const [value, setValue] = useState("weekly");
  return (
    <Sheet
      title="Radio"
      meta="17px, 1.3px ring · chosen is an olive disc with a check · arrows wrap in a group"
    >
      <Row name="17px" spec="hit area 25 × 25">
        <Held name="off">
          <Radio checked={false} label="Off" />
        </Held>
        <Held name="hover">
          <Radio checked={false} label="Hover" forceState="hover" />
        </Held>
        <Held name="on">
          <Radio checked label="On" />
        </Held>
        <Held name="disabled">
          <Radio checked={false} label="Disabled" disabled />
        </Held>
        <Held name="focus">
          <Radio checked={false} label="Focus" forceState="focus" />
        </Held>
        <Held name="pressed">
          <Radio checked={false} label="Pressed" forceState="pressed" />
        </Held>
      </Row>
      <Row name="Issue ring 13px" meaning="Open, hover, resolved" spec="hit area 25 × 25">
        <Held name="open">
          <Radio checked={false} label="Open issue" size="issue" />
        </Held>
        <Held name="hover">
          <Radio checked={false} label="Hover issue" size="issue" forceState="hover" />
        </Held>
        <Held name="resolved">
          <Radio checked label="Resolved issue" size="issue" />
        </Held>
        <Held name="disabled">
          <Radio checked={false} label="Disabled issue" size="issue" disabled />
        </Held>
        <Held name="focus">
          <Radio checked={false} label="Focus issue" size="issue" forceState="focus" />
        </Held>
      </Row>
      <Row name="RadioGroup" meaning="One tab stop; arrows choose and wrap">
        <RadioGroup
          label="Repeats"
          value={value}
          onChange={setValue}
          options={[
            { value: "daily", label: "Daily" },
            { value: "weekly", label: "Weekly" },
            { value: "monthly", label: "Monthly" },
            { value: "quarterly", label: "Quarterly", disabled: true },
          ]}
        />
        <RadioGroup
          label="Repeats, across"
          orientation="horizontal"
          defaultValue="a"
          options={[
            { value: "a", label: "Owner" },
            { value: "b", label: "Manager" },
          ]}
        />
      </Row>
    </Sheet>
  );
}

export function CheckboxSpecimen(): JSX.Element {
  const [checked, setChecked] = useState<boolean | "mixed">("mixed");
  return (
    <Sheet title="Checkbox" meta="15px, radius 4 · espresso with a check, or a minus when mixed">
      <Row name="15px" spec="hit area 25 × 25">
        <Held name="off">
          <Checkbox label="Off" />
        </Held>
        <Held name="on">
          <Checkbox label="On" defaultChecked />
        </Held>
        <Held name="mixed">
          <Checkbox label="Mixed" checked="mixed" />
        </Held>
        <Held name="disabled, off">
          <Checkbox label="Disabled off" disabled />
        </Held>
        <Held name="disabled, on">
          <Checkbox label="Disabled on" defaultChecked disabled />
        </Held>
        {(["hover", "focus", "pressed"] as const).map((state) => (
          <Held key={state} name={state}>
            <Checkbox label={`Held ${state}`} forceState={state} />
          </Held>
        ))}
      </Row>
      <Row name="With a label" meaning="A click on the words chooses the box">
        <Checkbox label="Remember this device" showLabel />
        <Checkbox label="Disabled" showLabel disabled />
      </Row>
      <Row name="Live" meaning="A click on a mixed box chooses it">
        <Checkbox label="All requests" checked={checked} onChange={setChecked} showLabel />
        <span className="text-meta text-ink-3">{String(checked)}</span>
      </Row>
    </Sheet>
  );
}
