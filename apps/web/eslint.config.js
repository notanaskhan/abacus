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
  "src/screens/Board.tsx", // elapsed time of a polling window for a screening run
  "src/screens/CheckResults.tsx", // elapsed time of a polling window after an upload
  "src/testing/support.tsx", // test helper: backdates a sign-in
];

export default defineConfig(
  { ignores: ["dist"] },
  tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["**/packages/*/src/**", "@abacus/*/src/**"],
              message: "Import a package through its public entry point, not its src/.",
            },
            {
              group: ["../../*"],
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
              message:
                "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
            },
            {
              name: "marked",
              message:
                "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
            },
            {
              name: "markdown-it",
              message:
                "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
            },
            {
              name: "remark",
              message:
                "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
            },
            {
              name: "rehype-raw",
              message:
                "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
            },
            {
              name: "dompurify",
              message:
                "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
            },
            {
              name: "html-react-parser",
              message:
                "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
            },
            {
              name: "sanitize-html",
              message:
                "OUT-001: model text renders as plain text through AgentText only (ADR-065).",
            },
          ],
        },
      ],
      // ADR-011: the backend is reached only through the generated client.
      "no-restricted-globals": ["error", ...NETWORK_GLOBALS],
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/**/*.test.{ts,tsx}"],
    rules: {
      // ADR-065: model output is plain text, rendered only through AgentText.
      "no-restricted-syntax": [
        "error",
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
  { files: ["**/*.js"], extends: [tseslint.configs.disableTypeChecked] },
);
