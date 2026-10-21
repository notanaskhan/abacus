import { Check, Minus } from "lucide-react";
import { type JSX, type KeyboardEvent, useId, useRef, useState } from "react";
import { cn } from "../cn";
import { type ForceState, forceAttr } from "../force-state";
import { PRESS } from "./control-classes";
import { HIT } from "./hit-area";
import { nextTab } from "./tabs";

// Toggle, Checkbox, Radio and RadioGroup (Component Sheet family F; C-13; F-05-T15). Each is a
// button with the ARIA role of the control it draws (`switch`, `checkbox`, `radio`), not a native
// input: the kit draws its own, and the real keyboard behaviour is here and tested. Anything
// under 24px keeps a 24px hit area from a pseudo-element (SC 2.5.8, `hit-area.ts`): the 22 and
// 20px switches, the 15px checkbox, the 17px radio and the 13px issue ring.
//
// The ring of an unchecked box or radio is `ink-3`, not the bundle's .30, which is 1.9:1 against
// white and fails SC 1.4.11; see tokens/DECISIONS.md, "Inputs and tabs (F-05-T15)".

/** A control holds a value of its own until the caller passes one (controlled by default). */
function useValue<T>(
  value: T | undefined,
  initial: T,
  onChange: ((next: T) => void) | undefined,
): [T, (next: T) => void] {
  const [own, setOwn] = useState(initial);
  const current = value ?? own;
  return [
    current,
    (next) => {
      if (value === undefined) setOwn(next);
      onChange?.(next);
    },
  ];
}

type HeldState = Extract<ForceState, "hover" | "focus" | "pressed">;

// ---- Toggle -----------------------------------------------------------------------------------

export type ToggleSize = "default" | "small";

const TOGGLE: Record<ToggleSize, { box: string; knob: string; on: string; hit: string }> = {
  default: {
    box: "h-[22px] w-[38px]",
    knob: "size-[18px]",
    on: "translate-x-[16px]",
    hit: HIT.switch22,
  },
  small: {
    box: "h-[20px] w-[34px]",
    knob: "size-[16px]",
    on: "translate-x-[14px]",
    hit: HIT.switch20,
  },
};

export interface ToggleProps {
  checked?: boolean;
  defaultChecked?: boolean;
  onChange?: (checked: boolean) => void;
  /** What the switch turns on or off: its accessible name. */
  label: string;
  /** 38 × 22, or 34 × 20 in a dense row. */
  size?: ToggleSize;
  disabled?: boolean;
  /** Hold the toggle in a state for a specimen. */
  forceState?: Exclude<HeldState, "hover">;
  className?: string;
  id?: string;
  "aria-labelledby"?: string;
}

/** An on/off switch (`role="switch"`): olive when on, a greige track when off; the white knob
 * moves in 180ms. Never blue. */
export function Toggle({
  checked,
  defaultChecked = false,
  onChange,
  label,
  size = "default",
  disabled = false,
  forceState,
  className,
  id,
  "aria-labelledby": labelledBy,
}: ToggleProps): JSX.Element {
  const [on, set] = useValue(checked, defaultChecked, onChange);
  const spec = TOGGLE[size];
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={on}
      {...(labelledBy === undefined ? { "aria-label": label } : { "aria-labelledby": labelledBy })}
      disabled={disabled}
      data-size={size}
      className={cn(
        "relative inline-block shrink-0 rounded-pill forced-edge disabled:opacity-40",
        PRESS,
        spec.box,
        spec.hit,
        on ? "bg-green" : "bg-surface-deep inset-shadow-sel",
        className,
      )}
      {...forceAttr(forceState)}
      onClick={() => {
        set(!on);
      }}
    >
      <span
        aria-hidden="true"
        className={cn(
          "absolute top-[2px] left-[2px] block rounded-pill bg-card shadow-cta transition-transform duration-[180ms] ease-out",
          spec.knob,
          on && spec.on,
        )}
      />
    </button>
  );
}

// ---- Checkbox ---------------------------------------------------------------------------------

export interface CheckboxProps {
  /** `"mixed"` is a parent of partly chosen children: a minus. */
  checked?: boolean | "mixed";
  defaultChecked?: boolean;
  /** A click on a mixed box chooses it. */
  onChange?: (checked: boolean) => void;
  /** The accessible name, and the visible text beside the box when `showLabel`. */
  label: string;
  showLabel?: boolean;
  disabled?: boolean;
  forceState?: HeldState;
  className?: string;
}

const CHECK_OFF =
  "inset-ring-[1.3px] inset-ring-ink-3 hover:inset-ring-ink-2 data-[force=hover]:inset-ring-ink-2";

/** A 15px box, radius 4 (`role="checkbox"`): an unchecked ring, espresso with a check when on or
 * a minus when mixed. */
export function Checkbox({
  checked,
  defaultChecked = false,
  onChange,
  label,
  showLabel = false,
  disabled = false,
  forceState,
  className,
}: CheckboxProps): JSX.Element {
  const [state, set] = useValue<boolean | "mixed">(checked, defaultChecked, (next) => {
    onChange?.(next === true);
  });
  const id = useId();
  const on = state !== false;
  const box = (
    <button
      type="button"
      role="checkbox"
      id={id}
      aria-checked={state}
      {...(showLabel ? {} : { "aria-label": label })}
      disabled={disabled}
      className={cn(
        "relative inline-flex size-[15px] shrink-0 items-center justify-center rounded-value forced-edge",
        PRESS,
        HIT.checkbox,
        on ? "bg-espresso text-on-dark" : CHECK_OFF,
        disabled &&
          (on ? "bg-nested text-ink-4" : "bg-nested inset-ring-rule hover:inset-ring-rule"),
        !showLabel && className,
      )}
      {...forceAttr(forceState)}
      onClick={() => {
        set(state !== true);
      }}
    >
      {state === true && <Check aria-hidden="true" size={11} strokeWidth={2.8} />}
      {state === "mixed" && <Minus aria-hidden="true" size={11} strokeWidth={2.8} />}
    </button>
  );
  if (!showLabel) return box;
  return (
    <span className={cn("inline-flex items-center gap-[8px] text-body", className)}>
      {box}
      <label htmlFor={id} className={disabled ? "text-ink-4" : "text-ink"}>
        {label}
      </label>
    </span>
  );
}

// ---- Radio ------------------------------------------------------------------------------------

/** 17px by default; 13px is the issue ring of an issue row (open, hover, resolved). */
export type RadioSize = "default" | "issue";

const RADIO: Record<RadioSize, { box: string; hit: string; check: readonly [number, number] }> = {
  default: { box: "size-[17px]", hit: HIT.radio, check: [11, 3] },
  issue: { box: "size-[13px]", hit: HIT.issue, check: [9, 3.2] },
};

export interface RadioProps {
  checked: boolean;
  /** Fires when the radio is chosen; a chosen radio does not unchoose. */
  onSelect?: () => void;
  label: string;
  size?: RadioSize;
  disabled?: boolean;
  forceState?: HeldState;
  className?: string;
  tabIndex?: number;
  onKeyDown?: (event: KeyboardEvent<HTMLButtonElement>) => void;
  buttonRef?: (element: HTMLButtonElement | null) => void;
}

/** A radio (`role="radio"`): an unchecked ring that darkens on hover, and an olive disc with a
 * check when chosen. Alone it is a mark; chosen among others it is in a `RadioGroup`. */
export function Radio({
  checked,
  onSelect,
  label,
  size = "default",
  disabled = false,
  forceState,
  className,
  tabIndex,
  onKeyDown,
  buttonRef,
}: RadioProps): JSX.Element {
  const spec = RADIO[size];
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      data-size={size}
      {...(tabIndex === undefined ? {} : { tabIndex })}
      {...(buttonRef === undefined ? {} : { ref: buttonRef })}
      className={cn(
        "relative inline-flex shrink-0 items-center justify-center rounded-pill forced-edge",
        PRESS,
        spec.box,
        spec.hit,
        checked ? "bg-green text-on-dark" : CHECK_OFF,
        disabled && "bg-nested text-ink-4 inset-ring-rule hover:inset-ring-rule",
        className,
      )}
      {...forceAttr(forceState)}
      {...(onKeyDown === undefined ? {} : { onKeyDown })}
      onClick={() => {
        if (!checked) onSelect?.();
      }}
    >
      {checked && <Check aria-hidden="true" size={spec.check[0]} strokeWidth={spec.check[1]} />}
    </button>
  );
}

export interface RadioOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface RadioGroupProps {
  options: readonly RadioOption[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  /** The group's accessible name. */
  label: string;
  size?: RadioSize;
  orientation?: "vertical" | "horizontal";
  className?: string;
}

/** One choice among several (`role="radiogroup"`): a roving tabindex, arrows that move and choose
 * and wrap past the ends, skipping disabled options; Home and End jump. */
export function RadioGroup({
  options,
  value,
  defaultValue,
  onChange,
  label,
  size = "default",
  orientation = "vertical",
  className,
}: RadioGroupProps): JSX.Element {
  const [chosen, set] = useValue<string | undefined>(value, defaultValue, (next) => {
    if (next !== undefined) onChange?.(next);
  });
  const items = useRef<(HTMLButtonElement | null)[]>([]);
  const disabled = options.map((o) => o.disabled === true);
  const stop = options.find((o) => o.value === chosen && o.disabled !== true)?.value;
  const entry = stop ?? options.find((o) => o.disabled !== true)?.value;
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        "flex gap-[8px]",
        orientation === "vertical" ? "flex-col items-start" : "flex-row items-center",
        className,
      )}
    >
      {options.map((option, index) => (
        <label key={option.value} className="inline-flex items-center gap-[8px] text-body">
          <Radio
            checked={option.value === chosen}
            label={option.label}
            size={size}
            disabled={option.disabled === true}
            tabIndex={option.value === entry ? 0 : -1}
            buttonRef={(element) => {
              items.current[index] = element;
            }}
            onSelect={() => {
              set(option.value);
            }}
            onKeyDown={(event) => {
              const target = nextTab(event.key, index, disabled);
              const next = options[target];
              if (next === undefined) return;
              event.preventDefault();
              set(next.value);
              items.current[target]?.focus();
            }}
          />
          <span
            {...(option.disabled === true ? { "aria-disabled": true } : {})}
            className={option.disabled === true ? "text-ink-4" : "text-ink"}
          >
            {option.label}
          </span>
        </label>
      ))}
    </div>
  );
}
