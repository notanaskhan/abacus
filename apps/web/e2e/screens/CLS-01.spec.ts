// CLS-01 (C-01-T50 screen spec): every built artboard on its live route in fixture mode, axe at
// zero serious or critical findings in light and forced colors (close-boards.ts).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/CLS-01.spec.ts`.
import { walkClose } from "./close-boards";

// e is the designed loading state (`GET /v1/closes` never answers): skeleton tiles and rows.
walkClose("CLS-01", "/closes", ["a", "b", "c", "d", "e", "f"], undefined, ["e"]);
