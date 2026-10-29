// The F-06 tier-3 specimens that render seed data (F-06-T04 on): registered for
// /components/screens/<ID> like the built screens. Gallery only.
import { registerScreen } from "../fixture-mode";
import { Tpl16Artboard } from "./TPL-16";
import { Tpl19Artboard } from "./TPL-19";

registerScreen("TPL-16", {
  title: "Signing ceremony · Form 8879, Dev & Mira Kapoor",
  Component: Tpl16Artboard,
});

// F-06-T06: frame 9 only (mobile sign); the other frames are R-01's and R-03's.
registerScreen("TPL-19", {
  title: "Portal mobile · Feld, 390 · frame 9 mobile sign",
  Component: Tpl19Artboard,
});
