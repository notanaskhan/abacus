// The few Node APIs the dist scan (dist.test.ts) uses; this workspace has no @types/node.
declare module "node:fs" {
  export function mkdtempSync(prefix: string): string;
  export function readFileSync(path: string, encoding: "utf8"): string;
  export function readdirSync(path: string): string[];
  export function rmSync(path: string, options: { recursive: boolean; force: boolean }): void;
  export function statSync(path: string): { isDirectory(): boolean };
}
declare module "node:os" {
  export function tmpdir(): string;
}
declare module "node:path" {
  export function dirname(path: string): string;
  export function join(...parts: string[]): string;
}
declare module "node:url" {
  export function fileURLToPath(url: string): string;
}
declare const process: { env: Record<string, string | undefined> };
