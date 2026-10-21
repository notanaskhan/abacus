import type { JSX, ReactNode } from "react";
import {
  BUTTON_SIZES,
  BUTTON_VARIANTS,
  Button,
  type ButtonForceState,
  type ButtonSize,
  type ButtonVariant,
  ICON_BUTTON_VARIANTS,
  IconButton,
  type IconButtonVariant,
} from "../components/button";
import {
  CheckPill,
  Count,
  DoneCount,
  PILL_SIZES,
  PILL_VARIANTS,
  Pill,
  Tag,
} from "../components/pill";
import { Row, Sheet } from "./status";

// The controls' specimens (C-00 Button and IconButton, C-06 Pill family; F-05-T14). Every variant
// and size is drawn, and every forceState (hover, focus, pressed, loading) is held with the
// `forceState` prop, so nothing here simulates a pointer. Disabled is the attribute. Sample labels
// are plain UI words; no human-only verb (Approve, Send, Post ...) sits on a specimen control.

type Cell = { name: string; state?: ButtonForceState; disabled?: boolean };

const STATES: readonly Cell[] = [
  { name: "default" },
  { name: "hover", state: "hover" },
  { name: "focus", state: "focus" },
  { name: "pressed", state: "pressed" },
  { name: "disabled", disabled: true },
  { name: "loading", state: "loading" },
];

function Held({ name, children }: { name: string; children: ReactNode }): JSX.Element {
  return (
    <span className="flex flex-col items-start gap-1.5">
      {children}
      <span className="text-meta text-ink-3">{name}</span>
    </span>
  );
}

const LABEL: Record<ButtonVariant, { rest: string; busy: string; icon: "check" | "pencil" }> = {
  primary: { rest: "Save", busy: "Saving", icon: "check" },
  secondary: { rest: "Rename…", busy: "Renaming", icon: "pencil" },
  tonal: { rest: "Edit…", busy: "Opening", icon: "pencil" },
  ghost: { rest: "Skip", busy: "Skipping", icon: "check" },
  destructive: { rest: "Delete…", busy: "Deleting", icon: "check" },
  success: { rest: "Mark as Done", busy: "Marking", icon: "check" },
  link: { rest: "View work", busy: "Opening", icon: "pencil" },
};

const OPENS_DIALOG: readonly ButtonVariant[] = ["secondary", "tonal", "destructive"];

export function ButtonSpecimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      <Sheet
        title="Button variants and states"
        meta="Pills: radius 999, 30 high, press scales to .985"
      >
        {BUTTON_VARIANTS.map((variant) => (
          <Row key={variant} name={variant}>
            {STATES.map(({ name, state, disabled }) => (
              <Held key={name} name={name}>
                <Button
                  variant={variant}
                  {...(state === undefined ? {} : { forceState: state })}
                  {...(disabled === true ? { disabled: true } : {})}
                  {...(OPENS_DIALOG.includes(variant) && state !== "loading"
                    ? { opensDialog: true }
                    : {})}
                >
                  {state === "loading" ? LABEL[variant].busy : LABEL[variant].rest}
                </Button>
              </Held>
            ))}
          </Row>
        ))}
      </Sheet>
      <Sheet
        title="Button sizes"
        meta="Heights 23, 28, 30, 32, 34 and 36; xs keeps a 24px hit area"
      >
        {BUTTON_SIZES.map((size: ButtonSize) => (
          <Row key={size} name={size}>
            <Button size={size}>Label</Button>
            <Button size={size} variant="secondary" icon="check">
              With icon
            </Button>
            <Button size={size} variant="secondary" loading>
              Loading
            </Button>
            <Button size={size} variant="ghost">
              Ghost
            </Button>
            <Button size={size} variant="link" iconAfter="arrow-right">
              Link
            </Button>
          </Row>
        ))}
      </Sheet>
      <Sheet title="Icon, ellipsis and link" meta="A label that opens a dialog ends with U+2026">
        <Row name="icon" meaning="A registry icon before the label">
          <Button icon="plus">New request</Button>
          <Button variant="secondary" icon="pencil">
            Edit
          </Button>
          <Button variant="success" icon="check">
            Mark as Done
          </Button>
        </Row>
        <Row name="opensDialog" meaning="Ends with …, never three full stops">
          <Button variant="secondary" opensDialog>
            Rename…
          </Button>
          <Button variant="destructive" opensDialog>
            Delete…
          </Button>
          <Button variant="tonal" opensDialog>
            Edit…
          </Button>
        </Row>
        <Row name="link" meaning="Value, row action, upload">
          <Button variant="link" iconAfter="arrow-right" className="text-ink">
            Open record
          </Button>
          <Button variant="link">View work</Button>
          <Button variant="link" className="font-medium text-espresso" opensDialog>
            Upload…
          </Button>
        </Row>
      </Sheet>
    </div>
  );
}

const ICON_LABEL: Record<IconButtonVariant, { icon: "pencil" | "plus" | "x"; label: string }> = {
  white: { icon: "pencil", label: "Edit" },
  fill: { icon: "x", label: "Close" },
  dark: { icon: "plus", label: "New" },
};

const ICON_SPEC: Record<IconButtonVariant, string> = {
  white: "28, white on e1, icon 12",
  fill: "30, nav-fill, icon 14",
  dark: "29 round, espresso, icon 14 at stroke 2",
};

export function IconButtonSpecimen(): JSX.Element {
  return (
    <Sheet
      title="IconButton variants and states"
      meta="Named by label; the icon is the registry's"
    >
      {ICON_BUTTON_VARIANTS.map((variant) => (
        <Row key={variant} name={variant} spec={ICON_SPEC[variant]}>
          {STATES.map(({ name, state, disabled }) => (
            <Held key={name} name={name}>
              <IconButton
                variant={variant}
                icon={ICON_LABEL[variant].icon}
                label={ICON_LABEL[variant].label}
                {...(state === undefined ? {} : { forceState: state })}
                {...(disabled === true ? { disabled: true } : {})}
              />
            </Held>
          ))}
        </Row>
      ))}
      <Row name="opensDialog" meaning="The label ends with …">
        <IconButton icon="pencil" label="Rename…" opensDialog />
        <IconButton variant="dark" icon="plus" label="New request…" opensDialog />
      </Row>
      <Row name="pressed" meaning="aria-pressed holds the hover fill">
        <IconButton icon="bug" label="Trace" aria-pressed />
      </Row>
    </Sheet>
  );
}

// ---- The Pill family ---------------------------------------------------------------------------

export function PillSpecimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      <Sheet title="Pill variants by size" meta="Radius 999, weight 500, never uppercase">
        {PILL_VARIANTS.map((variant) => (
          <Row key={variant} name={variant}>
            {PILL_SIZES.map((size) => (
              <Held key={size} name={size}>
                <Pill variant={variant} size={size}>
                  Word
                </Pill>
              </Held>
            ))}
          </Row>
        ))}
      </Sheet>
      <Sheet title="Check, spinner and chevron" meta="The only things inside a pill besides words">
        <Row name="check" meaning="A finished state">
          <Pill variant="green" check>
            Complete
          </Pill>
        </Row>
        <Row name="spin" meaning="Work in flight">
          <Pill variant="amber" spin>
            Working
          </Pill>
        </Row>
        <Row name="chevron" meaning="A picker">
          <Pill variant="neutral" size="status">
            Not started
          </Pill>
        </Row>
      </Sheet>
    </div>
  );
}

export function CountSpecimen(): JSX.Element {
  return (
    <Sheet title="Count" meta="19 high, 19 wide at least, 11.5 / 500, centred">
      <Row name="default" meaning="Numbers on tabs and headers">
        <Count value={1} />
        <Count value={7} />
        <Count value={38} />
        <Count value={1204} />
      </Row>
      <Row name="bad" meaning="Something in it is wrong">
        <Count value={16} tone="bad" />
      </Row>
      <Row name="segment" meaning="Inside a Segmented option">
        <Count value={7} tone="segment" />
      </Row>
    </Sheet>
  );
}

export function TagSpecimen(): JSX.Element {
  return (
    <Sheet title="Tag" meta="A category, never a state: 23 high, nested fill and a hair">
      <Row name="tag" meaning="Categories">
        <Tag>Category</Tag>
        <Tag>Two words</Tag>
        <Tag>Longer category name</Tag>
      </Row>
    </Sheet>
  );
}

export function DoneCountSpecimen(): JSX.Element {
  return (
    <Sheet title="DoneCount" meta="Done of total on a task group's header">
      <Row name="complete" meaning="Solid green and a check">
        <DoneCount done={5} total={5} />
      </Row>
      <Row name="partial" meaning="Neutral and a turning ring">
        <DoneCount done={4} total={5} />
      </Row>
      <Row name="none" meaning="Neutral, nothing done">
        <DoneCount done={0} total={5} />
      </Row>
    </Sheet>
  );
}

export function CheckPillSpecimen(): JSX.Element {
  return (
    <Sheet title="CheckPill" meta="White, 21 high, on e1; never a green fill or green text">
      <Row name="approved" meaning="Ink check and an ink-2 count">
        <CheckPill approved count={1} />
        <CheckPill approved count={3} />
        <CheckPill approved />
      </Row>
      <Row name="unapproved" meaning="A bare ink-3 check, 21 square">
        <CheckPill approved={false} />
      </Row>
    </Sheet>
  );
}
