// AUD-13 (A-08-T37 screen spec): every artboard from the /components gallery on fixtures at
// 1440×900, DPR 2, motion reduced, with axe at zero serious or critical findings in light and
// forced colors, overlays included (gallery-boards.ts).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/AUD-13.spec.ts`.
import { walkGallery } from "./gallery-boards";

walkGallery("AUD-13", ["a", "b", "c", "d", "e"]);
