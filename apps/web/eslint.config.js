// Flat config: typescript-eslint strict type-checked rules plus import boundaries (ADR-009, ADR-010).
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";
import {
  CLOCK_FILES,
  FORMAT_FILES,
  designSyntaxFor,
  intlGlobal,
  restrictedProperties,
} from "@abacus/ui/eslint-design-rules";
import { scopeTermSyntax } from "@abacus/ui/eslint-scope-rules";

// The design-system rules (SPEC-048 AC-5: palette that admits only Accrued tokens, colour
// literals, banned utilities, formatting and clock, brand strings) are defined once in
// packages/ui/eslint-design-rules.js and shared with packages/ui.
const NETWORK_GLOBALS = [
  { name: "fetch", message: "Call the backend only through @abacus/api-client (ADR-011)." },
  { name: "XMLHttpRequest", message: "Call the backend only through @abacus/api-client." },
];

// Files still allowed to read the wall clock (SPEC-048 AC-5). Formatting has no exceptions any
// more: F-05-T10 moved every call site onto packages/ui/src/format.ts. Each file below measures
// elapsed time or token lifetime, which is not business time (that is useNow, useToday and
// clock.tsx), so it has no fixture clock to read. Recorded in packages/ui/src/tokens/DECISIONS.md.
const LEGACY_CLOCK = [
  "src/auth/session.ts", // token lifetime against the device's clock (OIDC), not business time
  "src/legacy/Board.tsx", // elapsed time of a polling window for a screening run
  "src/legacy/CheckResults.tsx", // elapsed time of a polling window after an upload
  "src/testing/support.tsx", // test helper: backdates a sign-in
];

// Rules for every source file (ADR-065 and the design and scope rules).
const SCREEN_SYNTAX = [
  // SPEC-016 AC-1, SPEC-048 AC-5: design tokens only (packages/ui/eslint-design-rules.js).
  ...designSyntaxFor(),
  ...scopeTermSyntax(), // F-02-T09: banned product terms (scope-guards.yaml)
  {
    selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
    message: "Never render HTML (ADR-065).",
  },
  {
    selector: "Property[key.name='dangerouslySetInnerHTML']",
    message: "Never render HTML (ADR-065).",
  },
  {
    selector:
      "AssignmentExpression > MemberExpression.left[property.name=/^(innerHTML|outerHTML)$/], CallExpression > MemberExpression.callee[property.name=/^(insertAdjacentHTML|createContextualFragment)$/]",
    message: "Never write HTML into the DOM (ADR-065).",
  },
  {
    // Rendered directly, or as the result of `&&` / `?:` inside JSX.
    selector:
      "JSXElement > JSXExpressionContainer > MemberExpression[property.name=/^(rationale|quote)$/], JSXElement > JSXExpressionContainer > LogicalExpression > MemberExpression.right[property.name=/^(rationale|quote)$/], JSXElement > JSXExpressionContainer > ConditionalExpression > MemberExpression[property.name=/^(rationale|quote)$/]",
    message: "Render model text through <AgentText text={…} /> (ADR-065).",
  },
  {
    selector:
      "JSXOpeningElement[name.name!='AgentText'] > JSXAttribute > JSXExpressionContainer MemberExpression[property.name=/^(rationale|quote)$/]",
    message: "Model text goes only to <AgentText text={…} /> (ADR-065).",
  },
];

// F-05-T15 / F-05-T23: no native select and no boxed Input outside the legacy screens, which M2
// replaces screen by screen and M3 deletes with the Atelier `Input` (plan 04, section M2-M3).
const NEW_CODE_SYNTAX = [
  {
    selector: "JSXOpeningElement[name.name='select']",
    message: "Use the design system's Picker, not a native select (F-05-T15).",
  },
  {
    selector:
      "ImportDeclaration[source.value='@abacus/ui'] > ImportSpecifier[imported.name='Input']",
    message: "The boxed Input is legacy: use SearchField, Picker or ValueRow (F-05-T15).",
  },
];

// F-04-T14: no string route in a screen; link with `{...to.<ID>(params)}` instead.
const SCREEN_LINK_SYNTAX = [
  {
    selector:
      "JSXAttribute[name.name='to'] > Literal, JSXAttribute[name.name='to'] > JSXExpressionContainer > :matches(Literal, TemplateLiteral)",
    message: "Link to a screen with {...to.<ID>(params)} from src/routes/to.ts (F-04-T14).",
  },
  {
    selector: "Property[key.name='to'] > :matches(Literal, TemplateLiteral)",
    message: "Navigate to a screen with to.<ID>(params) from src/routes/to.ts (F-04-T14).",
  },
];

// F-03-T32 (ADR-145): screens ask `useCan` / `<Can>` (src/app-core/can.tsx) what the person may
// do; they never compare role codes. Applies outside app-core and the legacy screens, which M2
// replaces (their checks move with P-01's codemod). A membership `kind` ("staff" / "client") is
// not a role and stays comparable.
const ROLE_CODES =
  "firm_admin|practice_leader|quality_partner|security_admin|engagement_partner|manager|senior|" +
  "staff|reviewer|eqr_reviewer|specialist|client_service|client_admin|client_contributor";
const ROLE_LITERAL = `Literal[value=/^(${ROLE_CODES})$/]`;
const ROLE_MESSAGE =
  "Do not compare role codes: ask useCan(action) or <Can action=…> from app-core (F-03-T32).";
const ROLE_SYNTAX = [
  {
    selector: `BinaryExpression[operator=/^[!=]==?$/]:not([left.property.name='kind']):not([right.property.name='kind']) > ${ROLE_LITERAL}`,
    message: ROLE_MESSAGE,
  },
  { selector: `SwitchCase > ${ROLE_LITERAL}.test`, message: ROLE_MESSAGE },
  {
    selector: `CallExpression[callee.property.name='includes'] > ${ROLE_LITERAL}.arguments`,
    message: ROLE_MESSAGE,
  },
  {
    selector: `CallExpression[callee.property.name='includes'] > MemberExpression.callee > ArrayExpression.object > ${ROLE_LITERAL}`,
    message: ROLE_MESSAGE,
  },
];

// Imports (plan 04 §1.7, F-03-T32). `featureRoots` matches a relative import that reaches across
// feature roots, two or more levels up, outside the roots the importing file may use.
function importRestrictions(featureRoots) {
  return {
    patterns: [
      {
        group: ["**/packages/*/src/**", "@abacus/*/src/**"],
        message: "Import a package through its public entry point, not its src/.",
      },
      {
        // Two or more levels up, except into app-core: shared plumbing every feature may
        // import (plan 04, module boundaries; F-03-T32).
        regex: featureRoots,
        message: "Do not reach across feature roots; import through a public entry point.",
      },
    ],
    paths: [
      {
        name: "axios",
        message: "Call the backend only through @abacus/api-client (ADR-011).",
      },
      {
        name: "react-markdown",
        message: "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
      },
      {
        name: "marked",
        message: "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
      },
      {
        name: "markdown-it",
        message: "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
      },
      {
        name: "remark",
        message: "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
      },
      {
        name: "rehype-raw",
        message: "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
      },
      {
        name: "dompurify",
        message: "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
      },
      {
        name: "html-react-parser",
        message: "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
      },
      {
        name: "sanitize-html",
        message: "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
      },
    ],
  };
}

/** Two or more levels up, except into app-core: shared plumbing every feature may import. */
const FEATURE_ROOTS = "^\\.\\./\\.\\./(?:\\.\\./)*(?!\\.\\./|app-core(?:/|$))";
/** A screen may also import its domain's public index, the typed route builders and the manifest,
 * the firm shell's parts (the SHL screens draw them; P-01 §4 source layout), and the scenario base
 * its scenarios.ts starts from (fixture builds and tests only; the dist test holds it out). */
const SCREEN_ROOTS =
  "^\\.\\./\\.\\./(?:\\.\\./)*(?!\\.\\./|app-core(?:/|$)|domain/[^/]+$|routes/(?:to|manifest)$|shell/firm/[^/]+$|fixtures/scenario$)";

export default defineConfig(
  { ignores: ["dist", "test-results", "playwright-report", "parity-report"] },
  tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      "no-restricted-imports": ["error", importRestrictions(FEATURE_ROOTS)],
      // ADR-011: the backend is reached only through the generated client.
      "no-restricted-globals": ["error", ...NETWORK_GLOBALS],
    },
  },
  {
    // Plan 04 §1.7: screens import domain/*, app-core, the route builders and their shell parts.
    files: ["src/screens/**/*.{ts,tsx}"],
    rules: { "no-restricted-imports": ["error", importRestrictions(SCREEN_ROOTS)] },
  },
  {
    // Tests drive a feature from outside: the router, the seed, the harness (plan 04 §1.7).
    files: ["src/**/*.test.{ts,tsx}"],
    rules: { "no-restricted-imports": ["error", importRestrictions("^$")] },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/**/*.test.{ts,tsx}"],
    rules: {
      // ADR-065: model output is plain text, rendered only through AgentText.
      "no-restricted-syntax": ["error", ...SCREEN_SYNTAX],
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/**/*.test.{ts,tsx}", "src/legacy/**"],
    rules: {
      "no-restricted-syntax": ["error", ...SCREEN_SYNTAX, ...NEW_CODE_SYNTAX],
    },
  },
  {
    // Flat config replaces no-restricted-syntax per block, so this one repeats the lists above.
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/**/*.test.{ts,tsx}", "src/legacy/**", "src/app-core/**"],
    rules: {
      "no-restricted-syntax": ["error", ...SCREEN_SYNTAX, ...NEW_CODE_SYNTAX, ...ROLE_SYNTAX],
    },
  },
  {
    // F-04-T14: a screen links to a screen only through its typed builder (src/routes/to.ts), so
    // link-contract.test.ts sees every designed link.
    files: ["src/screens/**/*.{ts,tsx}"],
    ignores: ["src/**/*.test.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": [
        "error",
        ...SCREEN_SYNTAX,
        ...NEW_CODE_SYNTAX,
        ...ROLE_SYNTAX,
        ...SCREEN_LINK_SYNTAX,
      ],
    },
  },
  {
    // SPEC-048 AC-5: number and date formatting goes through format.ts, the wall clock through
    // clock.tsx. Each of those files keeps the other ban.
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/**/*.test.{ts,tsx}"],
    rules: {
      "no-restricted-properties": ["error", ...restrictedProperties()],
      "no-restricted-globals": ["error", ...NETWORK_GLOBALS, intlGlobal],
    },
  },
  {
    files: FORMAT_FILES,
    rules: {
      "no-restricted-properties": ["error", ...restrictedProperties({ formatting: false })],
      "no-restricted-globals": ["error", ...NETWORK_GLOBALS],
    },
  },
  {
    files: CLOCK_FILES,
    rules: { "no-restricted-properties": ["error", ...restrictedProperties({ clock: false })] },
  },
  {
    files: LEGACY_CLOCK,
    rules: { "no-restricted-properties": ["error", ...restrictedProperties({ clock: false })] },
  },
  // The OIDC token endpoint is the identity provider, not our API (src/auth/session.ts).
  { files: ["src/auth/session.ts"], rules: { "no-restricted-globals": "off" } },
  { files: ["**/*.js", "**/*.mjs"], extends: [tseslint.configs.disableTypeChecked] },
);
