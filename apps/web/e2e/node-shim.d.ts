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

// Playwright's screenshots are Buffers; the workspace has no @types/node to say so.
declare class Buffer extends Uint8Array {}

// The visual harness (F-05-T16): baseline checks and the parity report.
declare module "node:fs" {
  export function existsSync(path: string): boolean;
  export function mkdirSync(path: string, options: { recursive: true }): void;
  export function writeFileSync(path: string, data: string, encoding: "utf8"): void;
}
