import { StrictMode } from "react";
import { bootWithRuntimeConfig } from "../app-core/boot";
import { ConsoleShell } from "../console/ConsoleShell";
import "../index.css";

// The Accrued staff console's entry (G-04-T14; G-04 §5.3; chapter 04 §1.1): console.html on the
// console origin, built with `vite build --mode console` into dist/console. It imports nothing of
// the firm app or the portal (scripts/console-dist-check.mjs). Same-origin /v1 under the console CSP
// (vite.config.ts); staff sign in on the staff issuer through the console BFF (console/StaffAuth.tsx,
// DEC-5528).

const root = document.getElementById("root");
if (root === null) throw new Error("Missing #root element");

// Q-01-T23: the console starts only with a valid runtime config; otherwise the plain error state.
void bootWithRuntimeConfig(root, () => (
  <StrictMode>
    <ConsoleShell search={window.location.search} />
  </StrictMode>
));
