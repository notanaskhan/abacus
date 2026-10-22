// The design-system lint rules (SPEC-048 AC-5, ADR-155, F-05-T07), shared by apps/web and
// packages/ui. They are plain `no-restricted-*` entries, so each config composes them with its own
// architecture rules (ADR-011, ADR-065) and an override can drop a subset for one file.
//
// The palette is read from packages/ui/src/theme.css, so a new `--color-*` token is admitted
// without touching this file, and a removed one is refused.
import { readFileSync } from "node:fs";

const THEME = readFileSync(`${import.meta.dirname}/src/theme.css`, "utf8");

/** Names of the colour tokens: `--color-green-tint` is `green-tint`. */
export const COLOUR_TOKENS = [...THEME.matchAll(/^\s*--color-([a-z0-9-]+)\s*:/gm)].flatMap((m) =>
  m[1] === undefined ? [] : [m[1]],
);

// Tailwind's colour families, v4 included. A family that is also a token name (`red`, `green`,
// `amber`) is admitted bare, and with its token suffixes (`red-ink`, `green-tint`), but not with
// a numbered shade (`red-700`). Every other family is refused in any form.
const FAMILIES = [
  "slate",
  "gray",
  "zinc",
  "neutral",
  "stone",
  "taupe",
  "mauve",
  "mist",
  "olive",
  "red",
  "orange",
  "amber",
  "yellow",
  "lime",
  "green",
  "emerald",
  "teal",
  "cyan",
  "sky",
  "blue",
  "indigo",
  "violet",
  "purple",
  "fuchsia",
  "pink",
  "rose",
  "white",
  "black",
];
const TOKEN_FAMILIES = FAMILIES.filter((f) => COLOUR_TOKENS.includes(f));
const OTHER_FAMILIES = FAMILIES.filter((f) => !COLOUR_TOKENS.includes(f));

// Utilities that take a colour.
const PREFIX =
  "bg|text|border(?:-[trblxyse])?|ring(?:-offset)?|outline|divide|fill|stroke|placeholder|from|via|to|accent|caret|decoration|shadow|inset-shadow|inset-ring";
// Not preceded by a word character or a hyphen, so `md:bg-…` and `hover:bg-…` match and `x-bg-…` does not.
const START = "(?<![\\w-])";
const END = "(?![A-Za-z0-9])";

/** Regex source: a Tailwind palette class that is not an Accrued token utility. */
export const PALETTE_SOURCE =
  `${START}(?:${PREFIX})-(?:${OTHER_FAMILIES.join("|")})${END}` +
  `|${START}(?:${PREFIX})-(?:${TOKEN_FAMILIES.join("|")})-[0-9]{2,3}${END}`;
// The retired Atelier tokens (F-05-T34, DS-32, F-05 J3). theme.css no longer defines them, so their
// utilities would compile to nothing; the ban makes a new use fail lint instead of rendering
// unstyled. The replacements are exact value matches: ground -> shell, muted -> ink-3,
// line -> hair, accent -> espresso (accent-hover -> cta-hover, accent-soft -> sel-bg,
// on-accent -> on-dark), info -> amber-ink (info-soft -> amber-tint), ai -> ink-3, ai-line -> stroke.
export const RETIRED_TOKENS = [
  "ground",
  "muted",
  "line",
  "accent",
  "accent-hover",
  "accent-soft",
  "on-accent",
  "info",
  "info-soft",
  "ai",
  "ai-line",
];
/** Regex source: a utility on a retired Atelier token, such as `text-muted` or `hover:bg-accent`. */
export const RETIRED_TOKEN_SOURCE = `${START}(?:${PREFIX})-(?:${RETIRED_TOKENS.join("|")})(?![\\w-])`;
/** Regex source: an arbitrary colour value such as `bg-[#fff]` or `text-[rgb(0,0,0)]`. */
export const ARBITRARY_COLOUR_SOURCE = `${START}(?:${PREFIX})-\\[(?:#|(?:rgba?|hsla?|hwb|oklch|oklab|lab|lch|color)\\()`;
const HEX_SOURCE = "(?<![\\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z])";
const COLOUR_FUNCTION_SOURCE = "\\b(?:rgba?|hsla?|hwb|oklch|oklab|lab|lch)\\(";
const FONT_WEIGHT_SOURCE = `${START}font-(?:thin|extralight|light|semibold|bold|extrabold|black)(?![\\w-])`;
const SHADOW_SOURCE = `${START}(?:inset-)?shadow-(?:2xs|xs|sm|md|lg|xl|2xl|inner)(?![\\w-])`;
const TYPE_SCALE_SOURCE = `${START}text-(?:xs|sm|base|lg|xl|[2-9]xl)(?![\\w-])`;
const LARGE_TYPE_SOURCE = `${START}text-[4-9]xl(?![\\w-])`;
const ACCRUAL_SOURCE = "\\bAccrual\\b";
// Emoji: astral pictographs and flags, the BMP symbols that default to emoji presentation, and the
// emoji variation selector. Text arrows, ticks and (c) are not emoji and stay allowed.
const EMOJI_SOURCE =
  "[\\uD83C-\\uD83E][\\uDC00-\\uDFFF]|[\\u231A\\u231B\\u23E9-\\u23F3\\u25FD\\u25FE\\u2614\\u2615\\u2648-\\u2653\\u267F\\u2693\\u26A1\\u26AA\\u26AB\\u26BD\\u26BE\\u26C4\\u26C5\\u26CE\\u26D4\\u26EA\\u26F2-\\u26F5\\u26FA\\u26FD\\u2705\\u270A\\u270B\\u2728\\u274C\\u274E\\u2753-\\u2755\\u2757\\u2795-\\u2797\\u27B0\\u27BF\\u2B1B\\u2B1C\\u2B50\\u2B55\\uFE0F]";

/** A selector matching a string, a template chunk or JSX text whose text matches `source`. */
function textMatching(source, { jsx = false } = {}) {
  const parts = [`Literal[value=/${source}/]`, `TemplateElement[value.raw=/${source}/]`];
  if (jsx) parts.push(`JSXText[value=/${source}/]`);
  return parts.join(", ");
}

/**
 * Design-system bans on strings, as `no-restricted-syntax` entries. Colour literals are separate
 * (`colourLiteralSyntax`) because packages/ui tokens/ and brand/ may hold them.
 */
export const designSyntax = [
  {
    selector: textMatching(PALETTE_SOURCE),
    message:
      "Use the design tokens (bg-card, text-ink-3, bg-green-tint, …), not Tailwind's palette (SPEC-016, SPEC-048).",
  },
  {
    selector: textMatching(RETIRED_TOKEN_SOURCE),
    message:
      "The Atelier tokens are retired (F-05-T34): use bg-shell, text-ink-3, border-hair, bg-espresso, text-amber-ink or text-ink-3.",
  },
  {
    selector: textMatching(ARBITRARY_COLOUR_SOURCE),
    message: "No arbitrary colour values: use the design tokens (SPEC-048).",
  },
  {
    selector: textMatching(FONT_WEIGHT_SOURCE),
    message: "Geist is 400 and 500 only: use font-normal or font-medium (SPEC-048, ADR-155).",
  },
  {
    selector: textMatching(SHADOW_SOURCE),
    message: "Use a shadow token (shadow-e1, shadow-pop, …), not a default shadow (SPEC-048).",
  },
  {
    selector: textMatching(LARGE_TYPE_SOURCE),
    message: "Use the type roles, not text-4xl and up (SPEC-048).",
  },
  {
    selector: textMatching(ACCRUAL_SOURCE, { jsx: true }),
    message: "The product is Accrued, not Accrual (AGENTS.md, SPEC-048).",
  },
  {
    selector: textMatching(EMOJI_SOURCE, { jsx: true }),
    message: "No emoji in the product: use the icon registry (SPEC-048).",
  },
];

/** Hex and rgb()/hsl() literals. Allowed only in theme.css, packages/ui tokens/ and brand/. */
export const colourLiteralSyntax = [
  {
    selector: textMatching(HEX_SOURCE),
    message: "No raw hex colours: use the design tokens (SPEC-016, SPEC-048).",
  },
  {
    selector: textMatching(COLOUR_FUNCTION_SOURCE),
    message: "No rgb()/rgba()/hsl() colour literals: use the design tokens (SPEC-048).",
  },
];

// TODO(F-05-T06): switch this on when the text-* codemod has landed. Until then screens and
// components still use Tailwind's text-xs to text-3xl, which theme.css maps onto the plan's roles
// (ADR-155 §1), so banning them now would fail every screen. To switch on: set
// TYPE_SCALE_BAN_ENABLED to true. eslint-rules.test.ts checks the flag against the shipped config.
export const TYPE_SCALE_BAN_ENABLED = true;

/** text-xs … text-3xl (and text-sm/6 and variants). Exported switched off; see the TODO above. */
export const deferredTypeScaleSyntax = [
  {
    selector: textMatching(TYPE_SCALE_SOURCE),
    message: "Use the type role classes, not Tailwind's text-xs … text-3xl (SPEC-048, F-05-T06).",
  },
];

/** The syntax bans a config adds: the colour literals, and the type scale once it is enabled. */
// F-04-T17 (CLOCK-001's frontend half): an argument-less `new Date()` reads the wall clock as
// surely as `Date.now()` (banned in restrictedProperties); both go through clock.tsx.
export const CLOCK_SYNTAX = [
  {
    selector: "NewExpression[callee.name='Date'][arguments.length=0]",
    message:
      "Read the time through clock.tsx (useNow) so tests and fixtures can fix it (F-04-T17, SPEC-048).",
  },
];

export function designSyntaxFor({ colourLiterals = true } = {}) {
  return [
    ...designSyntax,
    ...CLOCK_SYNTAX,
    ...(colourLiterals ? colourLiteralSyntax : []),
    ...(TYPE_SCALE_BAN_ENABLED ? deferredTypeScaleSyntax : []),
  ];
}

const FORMAT_MESSAGE = "Format numbers, money and dates through format.ts (SPEC-048).";

/** `no-restricted-properties` entries: number and date formatting, and the wall clock. */
export function restrictedProperties({ formatting = true, clock = true } = {}) {
  return [
    ...(formatting
      ? [
          "toFixed",
          "toLocaleString",
          "toLocaleDateString",
          "toLocaleTimeString",
          "toLocaleUpperCase",
          "toLocaleLowerCase",
        ].map((property) => ({ property, message: FORMAT_MESSAGE }))
      : []),
    ...(clock
      ? [
          {
            object: "Date",
            property: "now",
            message:
              "Read the time through clock.tsx so tests and fixtures can fix it (SPEC-048).",
          },
        ]
      : []),
  ];
}

/** The `Intl` global is part of the formatting ban. */
export const intlGlobal = { name: "Intl", message: FORMAT_MESSAGE };

/** Files that own the banned calls. */
export const FORMAT_FILES = ["src/**/format.ts"];
export const CLOCK_FILES = ["src/**/clock.tsx"];

// F-05-T39 (INV-4; DEC-59, ADR-163; plan 04 lint L7): portal code never renders the product's
// name. A string, a template chunk or JSX text that contains it fails, in any case. The one place
// the name may appear is the "Secured by" footer the firm turns on, which draws the Wordmark
// component and holds no such string.
export const PRODUCT_NAME_SOURCE = "[Aa][Cc][Cc][Rr][Uu][Ee][Dd]";

export const portalTextSyntax = [
  {
    selector: textMatching(PRODUCT_NAME_SOURCE, { jsx: true }),
    message:
      "Portal code never renders the product's name: draw the firm's brand (DEC-59, ADR-163, INV-4).",
  },
];

/** packages/ui's portal surfaces and their specimens (F-05-T35 to T37). */
export const UI_PORTAL_FILES = [
  "src/brand/portal-brand.tsx",
  "src/layout/portal-toolbar.tsx",
  "src/layout/mobile-tab-bar.tsx",
  "src/templates/portal-layout.tsx",
  "src/templates/auth-card.tsx",
  "src/requests/**/*.{ts,tsx}",
  "src/specimens/portal.tsx",
  "src/specimens/requests.tsx",
  "src/specimens/auth.tsx",
];
