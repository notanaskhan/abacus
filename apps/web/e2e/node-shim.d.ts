// The one Node API the journey uses (no @types/node in this workspace).
declare module "node:child_process" {
  export function execFileSync(
    file: string,
    args: readonly string[],
    options: { cwd: string; stdio: "pipe" },
  ): unknown;
}
