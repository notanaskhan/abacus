import { type ClassValue, clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";
import { textRoles } from "./tokens/tokens";

// The type roles (`--text-body`, `--text-meta`, `--text-pill` ...) are the only font sizes
// (theme.css resets `--text-*`). tailwind-merge does not read the theme, so without this it takes
// `text-meta` for a colour and drops either that or a real `text-ink-2` from the same list:
// cn("text-meta", "text-ink-2") lost one. Registering the roles as `text` theme values makes them
// font sizes, which conflict with each other and with nothing else. The list is the typed mirror
// of theme.css (tokens.ts, proven equal to it by apps/web/src/lint/tokens-mirror.test.ts).
const twMerge = extendTailwindMerge({
  extend: { theme: { text: Object.keys(textRoles) } },
});

/** Merge class names, letting later Tailwind utilities override earlier ones. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
