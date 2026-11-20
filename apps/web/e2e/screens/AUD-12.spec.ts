// AUD-12 (A-08-T37 screen spec): every artboard from the /components gallery on fixtures at
// 1440×900, DPR 2, motion reduced, with axe at zero serious or critical findings in light and
// forced colors, overlays included (gallery-boards.ts).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/AUD-12.spec.ts`.
import { walkGallery } from "./gallery-boards";

// d is the agent run in flight: the viewer skeleton is busy by design (C6 v2).
walkGallery("AUD-12", ["a", "b", "c", "d", "e", "f", "g", "h"], { loading: ["d"] });
