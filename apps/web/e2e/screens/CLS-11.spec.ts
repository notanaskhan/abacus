// CLS-11 (C-02-T35 screen spec): a, a2, c, d and d2 on the live route in fixture mode, axe at zero
// serious or critical findings in light and forced colors (close-boards.ts); d2 holds the
// reconnect confirm with the POR-20 email preview open.
// Run: `ABACUS_VISUAL=1 pnpm exec playwright test --project=chromium e2e/screens/CLS-11.spec.ts`.
import { walkClose } from "./close-boards";

walkClose(
  "CLS-11",
  "/clients/_clientId_/entities/_entityId_/ledger",
  ["a", "a2", "c", "d", "d2"],
  ["closes.engine", "closes.gl_console"],
);
