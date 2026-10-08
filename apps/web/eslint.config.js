// Flat config: typescript-eslint strict type-checked rules plus import boundaries (ADR-009, ADR-010).
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

const PALETTE =
  "/\\b(bg|text|border|ring|outline|divide|fill|stroke|placeholder|from|to)-(neutral|gray|red|green|amber|blue|slate|zinc|stone|yellow|white|black)\\b/";
const HEX = "/#[0-9a-fA-F]{6}\\b|#[0-9a-fA-F]{3}\\b/";

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
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "Call the backend only through @abacus/api-client (ADR-011)." },
        { name: "XMLHttpRequest", message: "Call the backend only through @abacus/api-client." },
      ],
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/**/*.test.{ts,tsx}"],
    rules: {
      // ADR-065: model output is plain text, rendered only through AgentText.
      "no-restricted-syntax": [
        "error",
        // SPEC-016 AC-1: colours come only from the design tokens (packages/ui/src/theme.css).
        {
          selector: `Literal[value=${PALETTE}], TemplateElement[value.raw=${PALETTE}]`,
          message:
            "Use the design tokens (bg-surface, text-muted, …), not Tailwind's palette (SPEC-016).",
        },
        {
          selector: `Literal[value=${HEX}], TemplateElement[value.raw=${HEX}]`,
          message: "No raw hex colours: use the design tokens (SPEC-016).",
        },
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
  // The OIDC token endpoint is the identity provider, not our API (src/auth/session.ts).
  { files: ["src/auth/session.ts"], rules: { "no-restricted-globals": "off" } },
  { files: ["**/*.js"], extends: [tseslint.configs.disableTypeChecked] },
);
