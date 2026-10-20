// Test helper (SPEC-048): reads the design system's stylesheets and sources from disk. Vitest
// stubs CSS imports (even `?raw`), so the files are read with Node's fs, loaded at run time and
// typed here, without pulling Node's types into the SPA's build.
type Fs = {
  readFileSync: (path: string, encoding: "utf8") => string;
  existsSync: (path: string) => boolean;
  readdirSync: (path: string, options: { recursive: true }) => string[];
};

const cwd = (globalThis as unknown as { process: { cwd: () => string } }).process.cwd();
const modules = { fs: "node:fs" };

async function fs(): Promise<Fs> {
  return (await import(/* @vite-ignore */ modules.fs)) as Fs;
}

/** The apps/web directory (where Vitest runs). */
export const WEB = cwd;
/** packages/ui/src, the design system. */
export const UI = `${cwd}/../../packages/ui/src`;

export async function read(path: string): Promise<string> {
  return (await fs()).readFileSync(path, "utf8");
}

export async function exists(path: string): Promise<boolean> {
  return (await fs()).existsSync(path);
}

/** Every file under `dir` (relative paths), recursively. */
export async function list(dir: string): Promise<string[]> {
  return (await fs()).readdirSync(dir, { recursive: true });
}
