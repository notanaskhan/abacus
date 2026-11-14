// TPL-17 "Form renderer specimen — Ridgeline 2025 Form 1065" (F-07-T19; TASK-7949; handoff TPL-17
// spec.md, verbatim): the six page faces F-07-T15 rendered through the C11 renderer and their field
// manifest, the five K-1s with their four boxes, the Total = Schedule K tie, and the three
// diagnostics. Figures are the handoff's (and the manifest's): 1,231,600 · 18,400 · 6,200 ·
// 600,000; nothing here sums or computes.
import manifest from "./fixtures/tpl-17/manifest.json";
import page1 from "./fixtures/tpl-17/page-1.png";
import page2 from "./fixtures/tpl-17/page-2.png";
import page3 from "./fixtures/tpl-17/page-3.png";
import page4 from "./fixtures/tpl-17/page-4.png";
import page5 from "./fixtures/tpl-17/page-5.png";
import page6 from "./fixtures/tpl-17/page-6.png";
import type { FormDiagnostic, FormThumb, K1ListRow } from "../templates/form-renderer";
import type { MatchId } from "../tracing/types";
import type { ViewerFile, ViewerRegion } from "../viewer/types";

const IMAGES: readonly string[] = [page1, page2, page3, page4, page5, page6];

interface ManifestField {
  id: string;
  label: string;
  value: string | null;
  page: number;
  rect_pt: readonly [number, number, number, number];
  match_id: string | null;
  diagnostic: string | null;
}

const FIELDS = manifest.fields as unknown as readonly ManifestField[];

/** The rendered form as the viewer reads it: the pages, and each traced field as a region. */
export function tpl17File(pages: readonly number[] = [1, 2, 3, 4, 5, 6]): ViewerFile {
  const wanted = new Set(pages);
  return {
    name: "Ridgeline Property Partners, LP · 2025 Form 1065",
    pages: manifest.pages
      .filter((p) => wanted.has(p.n))
      .map((p) => ({
        n: p.n,
        width_pt: p.width_pt,
        height_pt: p.height_pt,
        rotation: 0 as const,
        src: IMAGES[p.n - 1] ?? "",
      })),
    regions: FIELDS.filter((f) => f.match_id !== null && wanted.has(f.page)).map(
      (f): ViewerRegion => ({
        match: f.match_id as MatchId,
        page: f.page,
        rects: [f.rect_pt],
        label: f.label,
      }),
    ),
  };
}

/** The thumbnails rail: six rendered faces; page 1 and page 6 carry a diagnostic. */
export const TPL17_THUMBS: readonly FormThumb[] = manifest.pages.map((p) => ({
  n: p.n,
  src: IMAGES[p.n - 1] ?? null,
  diagnostics: FIELDS.filter((f) => f.page === p.n && f.diagnostic !== null).length,
}));

const DRAFT = "Draft K-1 · pre-release";

/** The K-1 list (box 2 · box 5 · box 18A · box 19A), the handoff's figures as written. */
export const TPL17_K1S: readonly (K1ListRow & { boxes: readonly string[]; handoff: string })[] = [
  { id: "ridgeline-gp", name: "Ridgeline GP LLC", amount: "24632", status: DRAFT,
    boxes: ["24632", "368", "124", "12000"], handoff: "—" },
  { id: "meera-shah", name: "Meera Shah", amount: "468008", status: DRAFT,
    boxes: ["468008", "6992", "2356", "228000"], handoff: "→ Shah 1040 · draft" },
  { id: "pell-street-ventures", name: "Pell Street Ventures LLC", amount: "400270", status: DRAFT,
    boxes: ["400270", "5980", "2015", "180000"], handoff: "—" },
  { id: "pell-street-ii", name: "Pell Street II LLC (7/1–12/31)", amount: "30790", status: DRAFT,
    boxes: ["30790", "460", "155", "30000"], handoff: "—" },
  { id: "jonah-feld", name: "Jonah Feld", amount: "307900", status: DRAFT,
    boxes: ["307900", "4600", "1550", "150000"], handoff: "→ Feld 1040 · draft" },
];  // fmt: skip

/** Total = Schedule K (the server's tie state; the specimen never sums). */
export const TPL17_TOTAL = { boxes: ["1231600", "18400", "6200", "600000"], state: "tie" as const };

export const TPL17_DIAGNOSTICS: readonly (FormDiagnostic & { title: string })[] = [
  {
    id: "m3",
    severity: "error",
    title: "Schedule M-3 required",
    text: "Total assets at year end are $17,914,500, at or above $10 million. Check box J, attach Schedule M-3 and drop Schedule M-1.",
    page: 1,
    match: null,
  },
  {
    id: "m2",
    severity: "warning",
    title: "Schedule M-2 doesn't tie to Schedule L",
    text: "M-2 line 9 shows $6,860,000; Schedule L line 21 shows $6,866,200 (off 6,200). Tax-exempt interest is missing from 'Other increases'.",
    page: 4,
    match: "m2-9" as MatchId,
  },
  {
    id: "743b",
    severity: "warning",
    title: "§743(b) placeholder on Pell Street II LLC",
    text: "$28,595 placeholder (360,000 − 331,405) pending the §754 decision. Attach the election statement or remove the placeholder before filing.",
    page: 6,
    match: null,
  },
];
