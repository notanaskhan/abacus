// Written by scripts/seed-manifest.mjs from the module files in this folder; do not edit.
import { admScreens } from "./adm";
import { attScreens } from "./att";
import { audScreens } from "./aud";
import { bndScreens } from "./bnd";
import { cliScreens } from "./cli";
import { clsScreens } from "./cls";
import { ebpScreens } from "./ebp";
import { engScreens } from "./eng";
import { filScreens } from "./fil";
import { fspScreens } from "./fsp";
import { homeScreens } from "./home";
import { iauScreens } from "./iau";
import { inbScreens } from "./inb";
import { insScreens } from "./ins";
import { knwScreens } from "./knw";
import { notScreens } from "./not";
import { pltScreens } from "./plt";
import { porScreens } from "./por";
import { prjScreens } from "./prj";
import { shlScreens } from "./shl";
import { shtScreens } from "./sht";
import { sigScreens } from "./sig";
import { taxScreens } from "./tax";
import { tplScreens } from "./tpl";
import { txiScreens } from "./txi";
import { txpScreens } from "./txp";
import { txtScreens } from "./txt";
import { wbScreens } from "./wb";
import { xlaScreens } from "./xla";

/** Every screen of the design handoff, by screen ID (F-04-T14). */
export const MANIFEST = {
  ...admScreens,
  ...attScreens,
  ...audScreens,
  ...bndScreens,
  ...cliScreens,
  ...clsScreens,
  ...ebpScreens,
  ...engScreens,
  ...filScreens,
  ...fspScreens,
  ...homeScreens,
  ...iauScreens,
  ...inbScreens,
  ...insScreens,
  ...knwScreens,
  ...notScreens,
  ...pltScreens,
  ...porScreens,
  ...prjScreens,
  ...shlScreens,
  ...shtScreens,
  ...sigScreens,
  ...taxScreens,
  ...tplScreens,
  ...txiScreens,
  ...txpScreens,
  ...txtScreens,
  ...wbScreens,
  ...xlaScreens,
} as const;

export type { Manifest, ScreenEntry, ScreenStatus } from "./types";
