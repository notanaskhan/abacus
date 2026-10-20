// The few Node APIs the DS-06 codemod and its test use (no @types/node in this workspace).
declare module "node:fs" {
  export interface Dirent {
    name: string;
    isDirectory: () => boolean;
    isFile: () => boolean;
  }
  export function readFileSync(path: string, encoding: "utf8"): string;
  export function writeFileSync(path: string, data: string, encoding: "utf8"): void;
  export function readdirSync(path: string, options: { withFileTypes: true }): Dirent[];
  export function mkdtempSync(prefix: string): string;
  export function mkdirSync(path: string, options: { recursive: true }): void;
  export function rmSync(path: string, options: { recursive: true; force: true }): void;
}
declare module "node:path" {
  export function join(...parts: string[]): string;
  export function resolve(...parts: string[]): string;
}
declare module "node:os" {
  export function tmpdir(): string;
}
