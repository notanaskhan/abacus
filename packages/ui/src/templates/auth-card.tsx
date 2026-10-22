import { Check } from "lucide-react";
import {
  type ClipboardEvent,
  type JSX,
  type KeyboardEvent,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import { FirmMark, usePortalBrand } from "../brand";
import { cn } from "../cn";
import { PRESS } from "../components/control-classes";
import { Icon, type IconName } from "../icons";
import { MobileHeader } from "../layout/mobile-tab-bar";
import { PortalFooter } from "../layout/portal-toolbar";

// T15 AuthCard (F-05-T37; T15 and TPL-15 handoff, DEC-22, ADR P-54): the portal's front door and
// its one-page responses, under the firm's brand only. A full window on the shell colour with no
// toolbar: the 400 card (radius 14, e2, padding 28 28 24, title 16/500, 36 buttons, 44 × 52 code
// boxes) or the 720 single page (POR-17). At 390 the card fills the width under the 56 header.
// The brand comes from `PortalBrandProvider`; the sign-in methods a card offers come from the
// branding data the screen passes, never constants. No password field exists here.

// ---- Frame ------------------------------------------------------------------------------------

export interface AuthFrameProps {
  /** `card` centres the 400 card; `page` tops the 720 paper; `mobile` is the 390 phone. */
  layout: "card" | "page" | "mobile";
  /** Presentation only (the gallery): a 1400 × 860 window, or a 390 × 844 phone. */
  frame?: boolean;
  /** `card`: the card's block starts 133 from the top (TPL-15) instead of centring (T15). */
  top?: boolean;
  children?: ReactNode;
  className?: string;
}

/** The window an auth surface sits in: no toolbar, the shell colour, the firm's footer if on. */
export function AuthFrame({
  layout,
  frame = false,
  top = false,
  children,
  className,
}: AuthFrameProps): JSX.Element {
  const brand = usePortalBrand();
  const name = brand.portalName ?? brand.name;
  const mobile = layout === "mobile";
  const surface = (
    <div
      data-shell="app"
      data-variant={mobile ? "auth-mobile" : `auth-${layout}`}
      style={frame ? { height: mobile ? 844 : 860 } : undefined}
      className={cn(
        "relative flex flex-col overflow-hidden bg-shell",
        frame
          ? mobile
            ? "w-[390px] flex-none rounded-phone shadow-e1"
            : "w-(--app-w) flex-none rounded-window shadow-e1"
          : "min-h-dvh w-full",
        className,
      )}
    >
      {mobile && (
        <MobileHeader
          firm={name}
          {...(brand.logo === undefined ? {} : { logo: brand.logo })}
          {...(brand.mark === undefined ? {} : { mark: brand.mark })}
        />
      )}
      <main
        data-auth="body"
        className={cn(
          "flex min-h-0 flex-1 flex-col overflow-y-auto",
          layout === "card" &&
            (top
              ? "items-center px-[16px] pt-[133px] pb-[40px]"
              : "items-center justify-center px-[16px] py-[40px]"),
          layout === "page" && "items-center px-[16px] py-[40px]",
          mobile && "px-[16px] pt-[16px] pb-[24px]",
        )}
      >
        {children}
        {brand.securedFooter && <PortalFooter className="mt-[16px]" />}
      </main>
    </div>
  );
  if (!frame) return surface;
  return (
    <div
      data-shell="stage"
      className={cn(
        "flex items-start justify-center bg-presentation",
        mobile ? "px-[25px] py-[28px]" : "p-[20px]",
      )}
    >
      {surface}
    </div>
  );
}

// ---- Brand -------------------------------------------------------------------------------------

/** The firm's 34 mark on its tile, with the name beside it (above the card) or alone (inside). */
export function AuthBrand({ placement }: { placement: "above" | "inside" }): JSX.Element {
  const brand = usePortalBrand();
  const name = brand.portalName ?? brand.name;
  const mark = (
    <span
      aria-hidden={placement === "above" ? true : undefined}
      className="inline-flex size-[34px] flex-none items-center justify-center rounded-tile-lg bg-nav-fill"
    >
      <FirmMark
        name={name}
        size={20}
        {...(brand.logo === undefined ? {} : { src: brand.logo })}
        {...(brand.mark === undefined ? {} : { mark: brand.mark })}
      />
    </span>
  );
  if (placement === "inside") {
    return <div className="flex justify-center pb-[14px]">{mark}</div>;
  }
  return (
    <div data-auth="brand" className="mb-[24px] flex items-center justify-center gap-[10px]">
      {mark}
      <span className="text-brand">{name}</span>
    </div>
  );
}

// ---- Card --------------------------------------------------------------------------------------

export interface AuthCardProps {
  title: string;
  /** Under the title: 12.5/1.5 ink-2. */
  lead?: ReactNode;
  /** The firm's mark above the card with its name (TPL-15), or in the card over a centred title
   * (T15a). */
  brand?: "above" | "inside";
  /** A 34 tile over the title: the expired clock, the done check. */
  tile?: { icon: IconName; tone: "red" | "green" };
  /** Fill the width (390) instead of 400. */
  fluid?: boolean;
  /** Under the card: the secure sign-in line and the links. */
  footer?: ReactNode;
  children?: ReactNode;
}

/** The 400 card: radius 14, e2, padding 28 28 24, a 16/500 title. */
export function AuthCard({
  title,
  lead,
  brand = "above",
  tile,
  fluid = false,
  footer,
  children,
}: AuthCardProps): JSX.Element {
  const centred = brand === "inside";
  return (
    <div className={cn("flex flex-col", fluid ? "w-full" : "w-[400px] max-w-full")}>
      {brand === "above" && !fluid && <AuthBrand placement="above" />}
      <section
        data-auth="card"
        aria-label={title}
        className={cn(
          "flex flex-col gap-[14px] rounded-dialog bg-card px-[28px] pt-[28px] pb-[24px] shadow-e2",
          centred && "text-center",
        )}
      >
        {centred && <AuthBrand placement="inside" />}
        {tile !== undefined && (
          <span
            aria-hidden="true"
            className={cn(
              "inline-flex size-[34px] items-center justify-center rounded-tile-lg",
              tile.tone === "red" ? "bg-red-tint text-red-ink" : "bg-green-tint text-green-ink",
            )}
          >
            <Icon name={tile.icon} size={17} />
          </span>
        )}
        <div className="flex flex-col gap-[6px]">
          <h1 className="text-brand">{title}</h1>
          {lead !== undefined && <p className="text-dense leading-[1.5] text-ink-2">{lead}</p>}
        </div>
        {children}
      </section>
      {footer}
    </div>
  );
}

/** Under the card: an optional line, then Privacy · Terms · Help from the branding links. */
export function AuthFooter({ line, dots = true }: { line?: string; dots?: boolean }): JSX.Element {
  const brand = usePortalBrand();
  const links: { label: string; href: string | undefined }[] = [
    { label: "Privacy", href: brand.privacyUrl },
    { label: "Terms", href: undefined },
    { label: "Help", href: brand.helpUrl },
  ];
  return (
    <div className="mt-[16px] flex flex-col items-center gap-[8px] text-center text-meta text-ink-3">
      {line !== undefined && <span>{line}</span>}
      <span className={cn("flex items-center", dots ? "gap-[6px]" : "gap-[14px]")}>
        {links.map((l, i) => (
          <span key={l.label} className="flex items-center gap-[6px]">
            {dots && i > 0 && <span aria-hidden="true">·</span>}
            <a
              {...(l.href === undefined ? {} : { href: l.href })}
              className="inline-flex min-h-[24px] items-center hover:text-ink"
            >
              {l.label}
            </a>
          </span>
        ))}
      </span>
    </div>
  );
}

// ---- Buttons and fields -------------------------------------------------------------------------

const PRIMARY =
  "inline-flex h-[36px] w-full items-center justify-center gap-[7px] rounded-pill bg-espresso px-[16px] text-btn-lg font-medium text-on-dark shadow-cta hover:bg-cta-hover disabled:bg-nested disabled:text-ink-4 disabled:shadow-none";
const SECONDARY =
  "inline-flex h-[36px] w-full items-center justify-center gap-[7px] rounded-pill bg-card px-[16px] text-btn-lg shadow-e1 hover:bg-nav-fill disabled:text-ink-4";

/** The full-width 36 button: primary (one per card) or secondary. */
export function AuthButton({
  kind = "primary",
  icon,
  disabled = false,
  onClick,
  title,
  children,
}: {
  kind?: "primary" | "secondary";
  icon?: IconName;
  disabled?: boolean;
  onClick?: () => void;
  title?: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      {...(title === undefined ? {} : { title })}
      className={cn(kind === "primary" ? PRIMARY : SECONDARY, PRESS)}
    >
      {icon !== undefined && <Icon name={icon} size={14} />}
      {children}
    </button>
  );
}

/** The boxed field (the only boxed inputs in the product): 36, radius 10, nested, no border. */
export const AUTH_FIELD =
  "h-[36px] w-full min-w-0 rounded-nested bg-nested px-[12px] text-body text-ink outline-none placeholder:text-ink-3 focus-visible:inset-ring-1 focus-visible:inset-ring-stroke";

// ---- CodeInput ---------------------------------------------------------------------------------

export interface CodeInputProps {
  /** The digits typed so far, at most `length`. */
  value: string;
  onChange: (value: string) => void;
  /** Six digits; called once the last one lands (typed or pasted). */
  onComplete?: (value: string) => void;
  length?: number;
  /** The group's name: "6-digit code". */
  label: string;
  /** Take focus on mount (the code step opens on the person's own action). */
  autoFocus?: boolean;
  /** Draw the next empty box as focused, with no focus taken (a specimen). */
  forceFocus?: boolean;
  /** 8 between boxes at 400, 6 at 390. */
  gap?: 6 | 8;
}

/** Six 44 × 52 code boxes (radius 10, nested; the focused one white with a 2px ring). Typing a
 * digit moves on, Backspace on an empty box moves back, ← → move, and a paste fills every box. */
export function CodeInput({
  value,
  onChange,
  onComplete,
  length = 6,
  label,
  autoFocus = false,
  forceFocus = false,
  gap = 8,
}: CodeInputProps): JSX.Element {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const [focused, setFocused] = useState<number | null>(null);
  const digits = value.replace(/\D/g, "").slice(0, length);
  const next = Math.min(digits.length, length - 1);
  // The digits as of the last keystroke: focus moves before the parent re-renders.
  const latest = useRef(digits);
  latest.current = digits;

  useEffect(() => {
    // Mount only: later focus follows typing.
    if (autoFocus) refs.current[next]?.focus();
  }, []);

  const set = (v: string, focusAt: number): void => {
    const clean = v.replace(/\D/g, "").slice(0, length);
    latest.current = clean;
    onChange(clean);
    refs.current[Math.min(focusAt, length - 1)]?.focus();
    if (clean.length === length && digits.length !== length) onComplete?.(clean);
  };
  const onKey = (event: KeyboardEvent<HTMLInputElement>, i: number): void => {
    if (event.key === "Backspace") {
      event.preventDefault();
      if (i < digits.length) set(digits.slice(0, i) + digits.slice(i + 1), i);
      else if (i > 0) set(digits.slice(0, i - 1), i - 1);
    } else if (event.key === "ArrowLeft" && i > 0) {
      event.preventDefault();
      refs.current[i - 1]?.focus();
    } else if (event.key === "ArrowRight" && i < Math.min(digits.length, length - 1)) {
      event.preventDefault();
      refs.current[i + 1]?.focus();
    }
  };
  const onPaste = (event: ClipboardEvent<HTMLInputElement>, i: number): void => {
    event.preventDefault();
    const pasted = event.clipboardData.getData("text").replace(/\D/g, "");
    if (pasted === "") return;
    const merged = (digits.slice(0, i) + pasted).slice(0, length);
    set(merged, merged.length);
  };

  return (
    <div
      role="group"
      aria-label={label}
      data-auth="code"
      className={cn("flex justify-center", gap === 8 ? "gap-[8px]" : "gap-[6px]")}
    >
      {Array.from({ length }, (_, i) => {
        const on = focused === i || (forceFocus && focused === null && i === next);
        return (
          <input
            key={i}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="text"
            inputMode="numeric"
            autoComplete={i === 0 ? "one-time-code" : "off"}
            maxLength={length}
            aria-label={`Digit ${String(i + 1)} of ${String(length)}`}
            value={digits[i] ?? ""}
            data-focus={on ? "true" : "false"}
            // A box past the next empty one cannot be typed into: focus jumps to the next empty.
            onFocus={() => {
              if (i > latest.current.length) refs.current[latest.current.length]?.focus();
              else setFocused(i);
            }}
            onBlur={() => {
              setFocused(null);
            }}
            onKeyDown={(event) => {
              onKey(event, i);
            }}
            onPaste={(event) => {
              onPaste(event, i);
            }}
            onChange={(event) => {
              let typed = event.target.value.replace(/\D/g, "");
              if (typed === "") return;
              // The box still holds its old digit: what was typed is what follows it.
              const prev = digits[i];
              if (prev !== undefined && typed.length > 1 && typed.startsWith(prev)) {
                typed = typed.slice(1);
              }
              // One digit replaces this box; several (an autofill) fill on from here.
              const merged =
                typed.length === 1
                  ? digits.slice(0, i) + typed + digits.slice(i + 1)
                  : digits.slice(0, i) + typed;
              set(merged, i + typed.length);
            }}
            className={cn(
              "h-[52px] w-[44px] min-w-0 flex-none rounded-nested text-center text-[20px] font-normal tabular-nums caret-transparent outline-none transition-[background-color,box-shadow] duration-[180ms]",
              on ? "bg-card ring-2 ring-stroke" : "bg-nested",
            )}
          />
        );
      })}
    </div>
  );
}

// ---- Choices -----------------------------------------------------------------------------------

export interface AuthChoice {
  value: string;
  label: string;
  /** A line under the label (T15c). */
  detail?: string;
}

/** A radio group of full-width rows (52 in the card, 44 in a fieldset): the olive disc with a check
 * when chosen. ↑ ↓ move and choose. */
export function AuthChoices({
  label,
  options,
  value,
  onChange,
  rows = "card",
}: {
  label: string;
  options: readonly AuthChoice[];
  value: string | null;
  onChange: (value: string) => void;
  /** `card`: rows inside a hairline box; `fieldset`: rows in a fieldset; `tinted`: chosen row
   * filled (T15c). */
  rows?: "card" | "fieldset" | "tinted";
}): JSX.Element {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const at = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  );
  const move = (to: number): void => {
    const n = (to + options.length) % options.length;
    const o = options[n];
    if (o === undefined) return;
    onChange(o.value);
    refs.current[n]?.focus();
  };
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        "flex flex-col",
        rows === "card" && "overflow-hidden rounded-nested shadow-e1",
        rows === "tinted" && "gap-[2px]",
      )}
    >
      {options.map((o, i) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="radio"
            aria-checked={on}
            tabIndex={i === at ? 0 : -1}
            onClick={() => {
              onChange(o.value);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown" || event.key === "ArrowRight") move(i + 1);
              else if (event.key === "ArrowUp" || event.key === "ArrowLeft") move(i - 1);
              else return;
              event.preventDefault();
            }}
            className={cn(
              "flex w-full items-center gap-[12px] px-[14px] text-left text-body outline-offset-[-2px]",
              rows === "card" && "min-h-[52px] bg-card hairline-t first:border-t-0",
              rows === "fieldset" && "min-h-[44px] bg-card hairline-t first:border-t-0",
              rows === "tinted" &&
                "min-h-[44px] items-start rounded-nested py-[8px] hover:bg-nav-fill",
              rows === "tinted" && on && "bg-nav-fill",
            )}
          >
            <span
              aria-hidden="true"
              className={cn(
                "inline-flex size-[17px] flex-none items-center justify-center rounded-pill",
                rows === "tinted" && "mt-px",
                on ? "bg-green text-on-dark" : "inset-ring-[1.3px] inset-ring-ink-3",
              )}
            >
              {on && <Check size={11} strokeWidth={3} />}
            </span>
            <span className="flex min-w-0 flex-col gap-[2px]">
              <span
                className={cn(
                  rows === "tinted" && "text-section tracking-normal",
                  on && rows === "tinted" && "font-medium",
                  !on && "font-normal",
                )}
              >
                {o.label}
              </span>
              {o.detail !== undefined && <span className="text-dense text-ink-2">{o.detail}</span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ---- Single page -------------------------------------------------------------------------------

export interface AuthPageProps {
  /** Fill the width (390, padding 20) instead of 720 (padding 32 40). */
  fluid?: boolean;
  /** The letterhead: the firm's mark, its legal name and a line, and a right-hand reference. */
  letterhead: { name: string; line: string; reference?: string };
  title: string;
  /** The title in Gelasio (a legal heading, POR-17) or the product type (T15c). */
  legal?: boolean;
  children?: ReactNode;
  footer?: ReactNode;
}

/** The 720 single page (POR-17): white paper, radius 14, e2, a letterhead over a hairline. */
export function AuthPage({
  fluid = false,
  letterhead,
  title,
  legal = false,
  children,
  footer,
}: AuthPageProps): JSX.Element {
  const brand = usePortalBrand();
  return (
    <div className={cn("flex flex-col", fluid ? "w-full" : "w-[720px] max-w-full")}>
      <article
        data-auth="page"
        aria-label={title}
        className={cn(
          "flex flex-col gap-[16px] rounded-dialog bg-card shadow-e2",
          fluid ? "p-[20px]" : "px-[40px] py-[32px]",
        )}
      >
        <header
          className={cn(
            "flex gap-[12px] pb-[16px] hairline-b",
            fluid ? "flex-col" : "items-start justify-between",
          )}
        >
          <span className="flex min-w-0 items-center gap-[10px]">
            <span
              aria-hidden="true"
              className="inline-flex size-[34px] flex-none items-center justify-center rounded-tile-lg bg-nav-fill"
            >
              <FirmMark
                name={letterhead.name}
                size={20}
                {...(brand.logo === undefined ? {} : { src: brand.logo })}
                {...(brand.mark === undefined ? {} : { mark: brand.mark })}
              />
            </span>
            <span className="flex min-w-0 flex-col gap-[2px]">
              <span className="text-brand">{letterhead.name}</span>
              <span className="text-meta text-ink-3">{letterhead.line}</span>
            </span>
          </span>
          {letterhead.reference !== undefined && (
            <span className="text-pill font-normal text-ink-3">{letterhead.reference}</span>
          )}
        </header>
        {legal ? (
          // A legal heading: Gelasio at 700, which only a document scope may set.
          <h1 data-doc="" className="font-legal text-[22px] leading-[1.25] text-ink">
            <span className="doc-bold">{title}</span>
          </h1>
        ) : (
          <h1 className="text-title font-medium">{title}</h1>
        )}
        {children}
      </article>
      {footer}
    </div>
  );
}
