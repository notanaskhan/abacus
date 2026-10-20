// The one Node API the journey uses (no @types/node in this workspace).
declare module "node:child_process" {
  export function execFileSync(
    file: string,
    args: readonly string[],
    options: { cwd: string; stdio: "pipe" },
  ): unknown;
}

// The font spec reads vite.config.ts to prove the CSP meta is unchanged.
declare module "node:fs" {
  export function readFileSync(path: string, encoding: "utf8"): string;
}
