// The design system is linted like the app (ADR-009, ADR-065): strict type-checked rules, and no
// HTML rendering anywhere, since AgentText is the control that keeps model text plain. On top of
// that, SPEC-048 AC-5 (F-05-T07): only Accrued tokens, no colour literals outside tokens/ and
// brand/, no off-system utilities, formatting through format.ts and the clock through clock.tsx.
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";
import {
  CLOCK_FILES,
  FORMAT_FILES,
  designSyntaxFor,
  intlGlobal,
  restrictedProperties,
} from "./eslint-design-rules.js";
import { scopeTermSyntax } from "./eslint-scope-rules.js";

const NETWORK_GLOBALS = [
  { name: "fetch", message: "Components never call the network (ADR-011)." },
];
const HTML_SYNTAX = [
  {
    selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
    message: "Never render HTML (ADR-065).",
  },
  {
    selector:
      "AssignmentExpression > MemberExpression.left[property.name=/^(innerHTML|outerHTML)$/]",
    message: "Never write HTML into the DOM (ADR-065).",
  },
];

export default defineConfig(
  tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      "no-restricted-globals": ["error", ...NETWORK_GLOBALS],
      "no-restricted-syntax": ["error", ...HTML_SYNTAX],
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/**/*.test.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": [
        "error",
        ...HTML_SYNTAX,
        ...designSyntaxFor(),
        ...scopeTermSyntax(),
      ],
      "no-restricted-properties": ["error", ...restrictedProperties()],
      "no-restricted-globals": ["error", ...NETWORK_GLOBALS, intlGlobal],
    },
  },
  {
    // Hex and rgba( are the tokens' own business: allowed here and nowhere else in the package.
    files: ["src/tokens/**", "src/brand/**", "src/tokens.ts"],
    rules: {
      "no-restricted-syntax": [
        "error",
        ...HTML_SYNTAX,
        ...designSyntaxFor({ colourLiterals: false }),
      ],
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
  { files: ["**/*.js"], extends: [tseslint.configs.disableTypeChecked] },
);
