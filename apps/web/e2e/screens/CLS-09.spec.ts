// CLS-09 (C-01-T50 screen spec): every built artboard on its live route in fixture mode, axe at
// zero serious or critical findings in light and forced colors (close-boards.ts).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/CLS-09.spec.ts`.
import { walkClose } from "./close-boards";

walkClose("CLS-09", "/close-plans/_clientId_", ["a", "a2", "a3", "b", "b2", "c", "d", "e", "f"]);
