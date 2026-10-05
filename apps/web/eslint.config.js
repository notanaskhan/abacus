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
        },
      ],
    },
  },
  { files: ["**/*.js"], extends: [tseslint.configs.disableTypeChecked] },
);
