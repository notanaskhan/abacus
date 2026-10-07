// Flat config: typescript-eslint strict type-checked rules plus import boundaries (ADR-009, ADR-010).
import { defineConfig } from "eslint/config";
import tseslint from "typescript-eslint";

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
