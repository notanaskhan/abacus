import { X } from "lucide-react";
import {
  type InputHTMLAttributes,
  type JSX,
  type KeyboardEvent,
  type ReactNode,
  useId,
  useState,
} from "react";
import { cn } from "../cn";
import { type ForceState, forceAttr } from "../force-state";
import { Icon, type IconName } from "../icons";
import { PILL_WHITE, PRESS } from "./control-classes";
import { HIT } from "./hit-area";
import { Menu } from "./popover";
import { Toggle } from "./toggles";

// Inputs (Component Sheet family F and C-13; F-05-T15): SearchField, Picker, FilterChip and
// ValueRow. There is no native select and no boxed input: a search is a nested pill, a choice is
// a pill that opens a menu of radio items, and a form value is right-aligned text on a row, one
// decision a row. Each takes `forceState` so the gallery draws hover, focus and open without a
// pointer.

/** Controlled when `value` is given, otherwise it keeps its own. */
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

// ---- SearchField ------------------------------------------------------------------------------

export interface SearchFieldProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "value" | "defaultValue" | "onChange" | "type" | "size" | "aria-label" | "className"
> {
  value?: string;
  defaultValue?: string;
  /** Called with the text, not the event. */
  onChange?: (value: string) => void;
  /** The field's accessible name ("Search clients"). */
  label: string;
  /** The name of the clear button. */
  clearLabel?: string;
  /** Hold the field focused for a specimen. */
  forceState?: Extract<ForceState, "focus">;
  /** Sizes the field: 180 wide by default. */
  className?: string;
}

/** A search pill (Component Sheet F): 28 high, nested on a hair ring, a 13px search icon and a
 * 16px clear button once there is text. On focus it turns white with a firmer ring. */
export function SearchField({
  value,
  defaultValue = "",
  onChange,
  label,
  clearLabel = "Clear search",
  placeholder = "Search",
  forceState,
  className,
  ...props
}: SearchFieldProps): JSX.Element {
  const [text, set] = useValue(value, defaultValue, onChange);
  return (
    <span className={cn("relative inline-flex w-[180px]", className)}>
      <Icon
        name="search"
        size={13}
        className="pointer-events-none absolute top-1/2 left-[10px] -translate-y-1/2 text-ink-3"
      />
      <input
        type="search"
        aria-label={label}
        placeholder={placeholder}
        value={text}
        className="h-[28px] w-full rounded-pill bg-nested pr-[28px] pl-[30px] text-body text-ink inset-shadow-hair transition-colors duration-[180ms] placeholder:text-ink-3 focus:bg-card focus:inset-shadow-sel data-[force=focus]:bg-card data-[force=focus]:inset-shadow-sel forced-edge [&::-webkit-search-cancel-button]:appearance-none"
        {...forceAttr(forceState)}
        {...props}
        onChange={(event) => {
          set(event.target.value);
        }}
        onKeyDown={(event: KeyboardEvent<HTMLInputElement>) => {
          props.onKeyDown?.(event);
          if (event.key === "Escape" && text !== "") {
            event.preventDefault();
            set("");
          }
        }}
      />
      {text !== "" && (
        <button
          type="button"
          aria-label={clearLabel}
          className={cn(
            "absolute top-1/2 right-[6px] inline-flex size-[16px] -translate-y-1/2 items-center justify-center rounded-pill bg-surface-deep text-ink",
            HIT.clear,
          )}
          onClick={() => {
            set("");
          }}
        >
          <X aria-hidden="true" size={10} strokeWidth={2} />
        </button>
      )}
    </span>
  );
}

// ---- Picker -----------------------------------------------------------------------------------

export interface PickerOption {
  value: string;
  label: string;
  disabled?: boolean;
  /** A short line under the label in the menu. */
  hint?: string;
}

/** `white` is the pill on e1, `fill` the nav-fill picker with the up-down chevrons, `filter` the
 * icon-only filter button. */
export type PickerVariant = "white" | "fill" | "filter";

export interface PickerProps {
  options: readonly PickerOption[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  /** What is being chosen ("Status"): the accessible name, with the current choice after it. */
  label: string;
  variant?: PickerVariant;
  /** Shown when nothing is chosen. */
  placeholder?: string;
  disabled?: boolean;
  /** The menu's width in px (220 by default). */
  menuWidth?: number;
  forceState?: Extract<ForceState, "hover" | "focus" | "pressed" | "open">;
  className?: string;
}

const PICKER: Record<PickerVariant, string> = {
  white: cn("gap-[5px] pr-[9px] pl-[11px] data-[state=open]:bg-nav-fill", PILL_WHITE),
  fill: "gap-[5px] bg-nav-fill pr-[9px] pl-[12px] hover:bg-sel-bg data-[force=hover]:bg-sel-bg data-[state=open]:bg-sel-bg",
  filter: cn("gap-[4px] pr-[8px] pl-[9px] data-[state=open]:bg-nav-fill", PILL_WHITE),
};

/** A choice among options, in place of a native select (Component Sheet F): a 28px pill that
 * opens a menu of radio items; ↓ opens it, ↑ ↓ move, Escape closes and returns focus. */
export function Picker({
  options,
  value,
  defaultValue,
  onChange,
  label,
  variant = "white",
  placeholder,
  disabled = false,
  menuWidth,
  forceState,
  className,
}: PickerProps): JSX.Element {
  const [chosen, set] = useValue<string | undefined>(value, defaultValue, (next) => {
    if (next !== undefined) onChange?.(next);
  });
  const current = options.find((o) => o.value === chosen);
  const shown = current?.label ?? placeholder ?? "";
  const open = forceState === "open";
  return (
    <Menu
      label={label}
      align="start"
      disabled={disabled}
      {...(menuWidth === undefined ? {} : { width: menuWidth })}
      {...(open ? { forceState: "open" as const } : {})}
      sections={[
        options.map((option) => ({
          label: option.label,
          checked: option.value === chosen,
          ...(option.disabled === true ? { disabled: true } : {}),
          ...(option.hint === undefined ? {} : { hint: option.hint }),
          onSelect: () => {
            set(option.value);
          },
        })),
      ]}
      trigger={
        <button
          type="button"
          aria-label={shown === "" ? label : `${label}: ${shown}`}
          disabled={disabled}
          data-variant={variant}
          className={cn(
            "relative inline-flex h-[28px] shrink-0 items-center rounded-pill text-body text-ink disabled:pointer-events-none disabled:text-ink-4",
            PRESS,
            PICKER[variant],
            className,
          )}
          {...(open ? {} : forceAttr(forceState))}
        >
          {variant === "filter" ? <Icon name="list-filter" size={14} /> : shown}
          <Icon
            name={variant === "fill" ? "chevrons-up-down" : "chevron-down"}
            size={12}
            className="text-ink-3"
          />
        </button>
      }
    />
  );
}

// ---- FilterChip -------------------------------------------------------------------------------

export interface FilterChipProps {
  /** What is filtered: "Client". */
  label: string;
  icon?: IconName;
  options: readonly PickerOption[];
  /** The chosen option's value, or null when the filter is empty. */
  value?: string | null;
  onChange?: (value: string | null) => void;
  /** Shown while the filter is empty. */
  placeholder?: string;
  /** An item above the options that empties the filter ("Any client"); the caller owns the words. */
  clearLabel?: string;
  menuWidth?: number;
  forceState?: Extract<ForceState, "hover" | "focus" | "pressed" | "open">;
  className?: string;
}

/** A filter on a list (Component Sheet F): a pill split into what is filtered and its value, white
 * while empty and amber once a value is chosen. It opens a menu of the options. */
export function FilterChip({
  label,
  icon,
  options,
  value,
  onChange,
  placeholder = "Select",
  clearLabel,
  menuWidth,
  forceState,
  className,
}: FilterChipProps): JSX.Element {
  const [chosen, set] = useValue<string | null>(value, null, onChange);
  const current = options.find((o) => o.value === chosen);
  const active = current !== undefined;
  const open = forceState === "open";
  return (
    <Menu
      label={label}
      align="start"
      {...(menuWidth === undefined ? {} : { width: menuWidth })}
      {...(open ? { forceState: "open" as const } : {})}
      sections={[
        ...(clearLabel === undefined
          ? []
          : [
              [
                {
                  label: clearLabel,
                  onSelect: () => {
                    set(null);
                  },
                },
              ],
            ]),
        options.map((option) => ({
          label: option.label,
          checked: option.value === chosen,
          ...(option.disabled === true ? { disabled: true } : {}),
          ...(option.hint === undefined ? {} : { hint: option.hint }),
          onSelect: () => {
            set(option.value);
          },
        })),
      ]}
      trigger={
        <button
          type="button"
          aria-label={`${label}: ${current?.label ?? placeholder}`}
          data-active={active}
          className={cn(
            "relative inline-flex h-[28px] shrink-0 items-stretch overflow-hidden rounded-pill text-body",
            PRESS,
            active
              ? "bg-amber-tint text-amber-ink ring-[0.5px] ring-amber-line hover:bg-amber-tint-hover data-[force=hover]:bg-amber-tint-hover"
              : "bg-card shadow-e1 hover:bg-nav-fill data-[force=hover]:bg-nav-fill",
            className,
          )}
          {...(open ? {} : forceAttr(forceState))}
        >
          <span
            className={cn(
              "inline-flex items-center gap-[6px] border-r-[0.5px] pr-[9px] pl-[10px]",
              active ? "border-amber-line" : "border-hair text-ink-2",
            )}
          >
            {icon !== undefined && <Icon name={icon} size={13} />}
            {label}
          </span>
          <span
            className={cn(
              "inline-flex items-center gap-[5px] pr-[8px] pl-[9px]",
              active ? "font-medium" : "text-ink-3",
            )}
          >
            {current?.label ?? placeholder}
            <Icon name="chevrons-up-down" size={12} />
          </span>
        </button>
      }
    />
  );
}

// ---- ValueRow ---------------------------------------------------------------------------------

interface RowBase {
  /** The label, ink-2, at the left; never centred. */
  label: string;
  /** An invalid row turns its value brick and says why under it (`role="alert"`). */
  error?: string;
  /** Under a schedule: 24px of left padding rather than 12. */
  indented?: boolean;
  /** A line under the label, 11.5 ink-3 ("A person sends every client message."), or amber ink
   * for a limit reached (TPL-12 "All seats are assigned."). */
  help?: ReactNode;
  helpTone?: "muted" | "amber";
  /** Where `error` is said: under the value (the default) or under the label (T12, TPL-12c). */
  errorAt?: "value" | "label";
  /** The viewer may not edit (T12c, TPL-12d): the value reads in ink-2 and nothing opens. */
  readOnly?: boolean;
  /** A 12px lock before the value (T12c: every row of a read-only form). */
  lock?: boolean;
  className?: string;
}

export type ValueRowProps = RowBase &
  (
    | {
        /** A choice: the value's text with up-down chevrons, which opens a menu. `time` draws a
         * clock in their place. */
        kind: "select" | "time";
        value?: string;
        options: readonly PickerOption[];
        onChange?: (value: string) => void;
        placeholder?: string;
        menuWidth?: number;
        forceState?: Extract<ForceState, "hover" | "open">;
      }
    | {
        /** Right-aligned borderless text, 500; the placeholder is the requirement ("Required"). */
        kind: "text";
        value?: string;
        defaultValue?: string;
        onChange?: (value: string) => void;
        placeholder?: string;
        forceState?: Extract<ForceState, "focus">;
      }
    | {
        kind: "toggle";
        checked?: boolean;
        onChange?: (checked: boolean) => void;
        disabled?: boolean;
      }
    | { kind: "info"; children: ReactNode }
    | {
        /** A fixed value, 500 ink ("46 of 46 used"), with an optional glyph after it: a lock for a
         * value set at provisioning, a chevron for a row that opens its own screen. */
        kind: "value";
        children: ReactNode;
        trailing?: IconName;
      }
    | {
        /** A stacked row: the label, then a borderless multi-line field. */
        kind: "paragraph";
        value?: string;
        defaultValue?: string;
        onChange?: (value: string) => void;
        placeholder?: string;
        rows?: number;
      }
  );

const ROW = "flex min-h-[34px] items-center gap-[10px] px-[12px] text-body";

function TextValue({
  id,
  helpId,
  invalid,
  value,
  defaultValue = "",
  onChange,
  placeholder,
  forceState,
}: {
  id: string;
  helpId: string | undefined;
  invalid: boolean;
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  forceState?: "focus";
}): JSX.Element {
  const [text, set] = useValue(value, defaultValue, onChange);
  return (
    <input
      id={id}
      type="text"
      value={text}
      {...(placeholder === undefined ? {} : { placeholder })}
      aria-invalid={invalid}
      {...(helpId === undefined ? {} : { "aria-describedby": helpId })}
      className={cn(
        "h-[30px] w-full min-w-0 bg-transparent text-right font-medium outline-offset-[-2px] placeholder:font-medium",
        invalid ? "text-red-ink placeholder:text-red-ink" : "text-ink placeholder:text-ink-3",
      )}
      {...forceAttr(forceState)}
      onChange={(event) => {
        set(event.target.value);
      }}
    />
  );
}

function SelectValue({
  props,
  invalid,
}: {
  props: Extract<ValueRowProps, { kind: "select" | "time" }>;
  invalid: boolean;
}): JSX.Element {
  const [chosen, set] = useValue<string | undefined>(props.value, undefined, (next) => {
    if (next !== undefined) props.onChange?.(next);
  });
  const current = props.options.find((o) => o.value === chosen);
  const shown = current?.label ?? props.placeholder ?? "";
  const open = props.forceState === "open";
  return (
    <Menu
      label={props.label}
      align="end"
      {...(props.menuWidth === undefined ? {} : { width: props.menuWidth })}
      {...(open ? { forceState: "open" as const } : {})}
      sections={[
        props.options.map((option) => ({
          label: option.label,
          checked: option.value === chosen,
          ...(option.disabled === true ? { disabled: true } : {}),
          ...(option.hint === undefined ? {} : { hint: option.hint }),
          onSelect: () => {
            set(option.value);
          },
        })),
      ]}
      trigger={
        <button
          type="button"
          aria-label={shown === "" ? props.label : `${props.label}: ${shown}`}
          aria-invalid={invalid}
          className={cn(
            "inline-flex min-h-[26px] max-w-full items-center gap-[5px] rounded-sheet pr-[2px] pl-[6px] text-right font-medium transition-colors duration-[180ms] hover:bg-nav-fill data-[force=hover]:bg-nav-fill data-[state=open]:bg-nav-fill",
            invalid ? "text-red-ink" : "text-ink",
          )}
          {...(props.forceState === "hover" ? forceAttr("hover") : {})}
        >
          <span className="min-w-0 truncate">{shown}</span>
          <Icon
            name={props.kind === "time" ? "clock" : "chevrons-up-down"}
            size={12}
            className="text-ink-3"
          />
        </button>
      }
    />
  );
}

/** One decision on a row (C-13): the label at the left, the value as right-aligned text at the
 * right, never a boxed input or a native select. 34 high on a hairline. */
export function ValueRow(props: ValueRowProps): JSX.Element {
  const id = useId();
  const labelId = `${id}-label`;
  const helpId = props.error === undefined ? undefined : `${id}-help`;
  const pad = props.indented === true ? "pl-[24px]" : "";
  const readOnly = props.readOnly === true;

  if (props.kind === "paragraph") {
    return (
      <div
        className={cn(
          "flex flex-col gap-[3px] px-[12px] pt-[8px] pb-[9px] text-body",
          props.className,
        )}
      >
        <label id={labelId} htmlFor={id} className="text-ink-2">
          {props.label}
        </label>
        <ParagraphField id={id} props={props} helpId={helpId} />
        {props.error !== undefined && (
          <p id={helpId} role="alert" className="text-right text-meta text-red-ink">
            {props.error}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className={props.className}>
      <div className={cn(ROW, pad)}>
        <label id={labelId} htmlFor={id} className="flex-none whitespace-nowrap text-ink-2">
          {props.label}
        </label>
        <span className="flex min-w-0 flex-1 items-center justify-end gap-[8px]">
          {props.lock === true && (
            <Icon name="lock" size={12} label="Locked" className="shrink-0 text-ink-4" />
          )}
          {props.kind === "toggle" ? (
            <Toggle
              id={id}
              label={props.label}
              aria-labelledby={labelId}
              {...(props.checked === undefined ? {} : { checked: props.checked })}
              {...(props.onChange === undefined ? {} : { onChange: props.onChange })}
              {...(props.disabled === undefined && !readOnly
                ? {}
                : { disabled: readOnly || props.disabled === true })}
            />
          ) : props.kind === "info" ? (
            <span className="text-right text-ink-3">{props.children}</span>
          ) : props.kind === "value" ? (
            <span
              className={cn(
                "inline-flex items-center gap-[5px] text-right font-medium",
                readOnly ? "text-ink-2" : "text-ink",
              )}
            >
              {props.children}
              {props.trailing !== undefined && (
                <Icon name={props.trailing} size={12} className="text-ink-3" />
              )}
            </span>
          ) : readOnly ? (
            <span
              id={id}
              className="inline-flex items-center gap-[5px] pr-[2px] text-right font-medium text-ink-2"
            >
              {props.kind === "text"
                ? (props.value ?? props.defaultValue ?? "")
                : (props.options.find((o) => o.value === props.value)?.label ?? props.value ?? "")}
              {props.kind !== "text" && (
                <Icon
                  name={props.kind === "time" ? "clock" : "chevrons-up-down"}
                  size={12}
                  className="text-ink-3"
                />
              )}
            </span>
          ) : props.kind === "text" ? (
            <TextValue
              id={id}
              helpId={helpId}
              invalid={props.error !== undefined}
              {...(props.value === undefined ? {} : { value: props.value })}
              {...(props.defaultValue === undefined ? {} : { defaultValue: props.defaultValue })}
              {...(props.onChange === undefined ? {} : { onChange: props.onChange })}
              {...(props.placeholder === undefined ? {} : { placeholder: props.placeholder })}
              {...(props.forceState === undefined ? {} : { forceState: props.forceState })}
            />
          ) : (
            <SelectValue props={props} invalid={props.error !== undefined} />
          )}
        </span>
      </div>
      {props.help !== undefined && (props.error === undefined || props.errorAt !== "label") && (
        <p
          className={cn(
            "-mt-[4px] px-[12px] pb-[8px] text-meta",
            props.helpTone === "amber" ? "text-amber-ink" : "text-ink-3",
            pad && "pl-[24px]",
          )}
        >
          {props.help}
        </p>
      )}
      {props.error !== undefined && (
        <p
          id={helpId}
          role="alert"
          className={cn(
            "px-[12px] pb-[8px] text-meta text-red-ink",
            props.errorAt === "label" ? "-mt-[4px] text-left" : "text-right",
            pad && "pl-[24px]",
          )}
        >
          {props.error}
        </p>
      )}
    </div>
  );
}

function ParagraphField({
  id,
  props,
  helpId,
}: {
  id: string;
  props: Extract<ValueRowProps, { kind: "paragraph" }>;
  helpId: string | undefined;
}): JSX.Element {
  const [text, set] = useValue(props.value, props.defaultValue ?? "", props.onChange);
  return (
    <textarea
      id={id}
      value={text}
      rows={props.rows ?? 3}
      {...(props.placeholder === undefined ? {} : { placeholder: props.placeholder })}
      aria-invalid={props.error !== undefined}
      {...(helpId === undefined ? {} : { "aria-describedby": helpId })}
      className="w-full resize-none bg-transparent text-body leading-[1.5] text-ink outline-offset-[-2px] placeholder:text-ink-3"
      onChange={(event) => {
        set(event.target.value);
      }}
    />
  );
}
