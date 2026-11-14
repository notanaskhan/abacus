// TPL-17 "Form renderer specimen — Ridgeline 2025 Form 1065" (F-07-T19; TASK-7949; handoff TPL-17
// a–f): six artboards on the T17 FormRendererLayout for Daniel Reyes, Mon Sep 14, 2026 9:24 AM CT.
//   a  Page 1 with the K-1 list        b  Schedule K pages 4–5 with the trace
//   c  Diagnostics                     d  Page 6 Schedule M-2 as drafted
//   e  The Jonah Feld K-1 preview      f  Loading
// Data in (tpl17-data.ts, F-07-T15's rendered faces and manifest); the specimen computes nothing.
// Every K-1 reads "Draft K-1 · pre-release" (DEC-78: final K-1s come from the engine). The
// draft watermark is inside the server-rendered page image; the kit never draws it (tier-4
// decision "Watermark", F-07-T23).
import { type JSX, useState } from "react";
import { FormRendererLayout } from "../templates/form-renderer";
import { MatchScope } from "../tracing/match";
import { Artboard } from "./portal";
import {
  TPL17_DIAGNOSTICS,
  TPL17_K1S,
  TPL17_THUMBS,
  TPL17_TOTAL,
  tpl17File,
} from "./tpl17-data";

export type Tpl17State = "a" | "b" | "c" | "d" | "e" | "f";

interface Board {
  id: Tpl17State;
  name: string;
  note: string;
  page: number;
  loading?: boolean;
}

export const TPL17_BOARDS: readonly Board[] = [
  { id: "a", name: "Page 1 with K-1s", note: "Form 1065 · page 1 of 6; the five K-1s tie to Schedule K", page: 1 },
  { id: "b", name: "Schedule K trace", note: "Pages 4–5: lines 2, 5, 18a, 19a and 20a lit", page: 2 },
  { id: "c", name: "Diagnostics", note: "1 error and 2 warnings, each with Go to", page: 1 },
  { id: "d", name: "M-2 as drafted", note: "Page 6: line 9 6,860,000, off 6,200 vs Schedule L", page: 4 },
  { id: "e", name: "K-1 preview", note: "Jonah Feld, DRAFT · pre-release (in the page image)", page: 5 },
  { id: "f", name: "Loading", note: "Thumbnails and the page as skeletons", page: 1, loading: true },
];  // fmt: skip

/** The diagnostics as the layout lists them: the handoff's title, then its body. */
export const TPL17_LAYOUT_DIAGNOSTICS = TPL17_DIAGNOSTICS.map((d) => ({
  ...d,
  text: `${d.title} — ${d.text}`,
}));

function Tpl17({ board }: { board: Board }): JSX.Element {
  const [page, setPage] = useState(board.page);
  return (
    <Artboard id={`tpl-17${board.id}`} badge={`TPL-17${board.id}`} name={board.name} note={board.note}>
      <MatchScope>
        <div className="relative h-[800px] w-[1400px] bg-shell" data-tpl17={board.id}>
          <FormRendererLayout
            mode="form"
            thumbs={TPL17_THUMBS}
            page={page}
            onPage={setPage}
            file={board.loading === true ? null : tpl17File()}
            k1s={TPL17_K1S}
            total={{ state: TPL17_TOTAL.state }}
            diagnostics={TPL17_LAYOUT_DIAGNOSTICS}
            loading={board.loading === true}
          />
        </div>
      </MatchScope>
    </Artboard>
  );
}

export function Tpl17Specimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-[24px]">
      {TPL17_BOARDS.map((b) => (
        <Tpl17 key={b.id} board={b} />
      ))}
    </div>
  );
}
