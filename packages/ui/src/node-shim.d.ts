// The few Node APIs the file-reading tests use (icons, motion, F-07-T25); no @types/node here.
declare module "node:fs" {
  export function readFileSync(path: string, encoding: "utf8"): string;
  export function readdirSync(path: string): string[];
  export function existsSync(path: string): boolean;
  export function statSync(path: string): { isDirectory(): boolean };
}
declare module "node:path" {
  export function dirname(path: string): string;
  export function join(...parts: string[]): string;
}
declare module "node:url" {
  export function fileURLToPath(url: string): string;
}

// F-07-T19: a specimen's page image, imported as its URL (Vite and Vitest resolve the asset).
declare module "*.png" {
  const src: string;
  export default src;
}
