// CLS-04 (C-01-T50 screen spec): every built artboard on its live route in fixture mode, axe at
// zero serious or critical findings in light and forced colors (close-boards.ts).
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/CLS-04.spec.ts`.
import { walkClose } from "./close-boards";

walkClose("CLS-04", "/closes/_closeId_/accounts", ["a", "a2", "b", "cprime", "d", "e", "f"]);
