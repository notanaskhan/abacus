import { type JSX, useState } from "react";
import { PortalBrandProvider } from "../brand";
import {
  type CapturedPage,
  DeferredFrame,
  RequestMobile,
  ReviewAssignSheet,
  UploadActionSheet,
  applyUpload,
  useRequestBinder,
} from "../requests";
import { PortalLayout, portalNav } from "../templates/portal-layout";
import {
  MobileGreeting,
  MobileTeamCard,
  MobileTodoCard,
  ReturnProgressCard,
} from "../templates/portal-mobile-home";
import { Artboard, BRIGHTWATER_BRAND } from "./portal";
import { TPL07_REQUESTS, TPL07_SECTIONS } from "./requests";
import { FIRM, REQUEST_COUNTS, STAFF } from "./seed-figures";

// TPL-19 on T7-M (F-06-T10, F-06-T11; Wave 0 - Templates `#tpl19`): Claire Feld's portal on a
// 390 × 844 phone at E0. 1 Home (greeting, the return card with its ring, to-dos, team), 2
// Documents (the DropZone card, the open requests as cards, the rest folded), 7 the More sheet over
// Home, with no Approvals for a household. The open requests are TPL-07's own. Frames 5 and 6 are
// the v1 capture path (DEC-45): "Upload…" opens the action sheet (native camera or file), the
// Review & assign sheet, then the UploadRing and the receipt, which takes the pill from "2 to do"
// to "1 to do". Frames 3, 4 and 8 and the permission-off variant are R-03's (DEC-97) and render a
// placeholder. Frames 3 to 6 carry the alternate-path caption: the seeded Sep 14 story is the 9:12
// AM email INB-02 files. Frame 9 (mobile signing) is apps/web's. White-labelled: no product mark.

const CLAIRE = "Claire Feld";
const HOUSEHOLD = portalNav("individual");
const OPEN = TPL07_REQUESTS.filter((r) => r.st === "req").length;

export const TPL19_COPY = {
  greeting: "Good morning, Claire",
  ret: {
    title: "2025 Tax Return",
    status: "We're reviewing your return",
    line: `${String(OPEN)} documents still needed · extended due date Oct 15, 2026`,
  },
  todos: [
    { key: "upload", icon: "file-up", title: `Upload ${String(OPEN)} documents` },
    {
      key: "message",
      icon: "message-circle",
      title: `1 new message from ${STAFF.kevin}`,
      detail: "Could you send the 1095-C when you have a moment?",
    },
  ],
  team: {
    title: `Your ${FIRM} team`,
    people: [
      { name: STAFF.daniel, role: "Partner" },
      { name: STAFF.samuel, role: "Manager" },
      { name: STAFF.kevin, role: "Preparer" },
    ],
  },
  dropHint: "Photos of multi-page documents are combined into one PDF",
  alternate: "Alternate: client uploads by camera instead of email (not the seeded demo day)",
  stitched: {
    fileName: "Claire_Feld_2025_1095-C_MercerHill.pdf",
    size: "3.1 MB",
    sources: ["Claire_Feld_1095C_Camera_P1.jpg", "Claire_Feld_1095C_Camera_P2.jpg"],
  },
  today: "Sep 14",
} as const;

/** The 1095-C request the camera path fulfils (TPL-07's `aca`). */
const ACA = "aca";

/** Where the capture path stands: frame 2, the action sheet, frame 5, frame 6 in flight, done. */
type Capture = "none" | "sheet" | "review" | "uploading" | "uploaded";

function Phone({
  tab,
  more = false,
  capture: initial = "none",
}: {
  tab: "Home" | "Documents";
  more?: boolean;
  capture?: Capture;
}): JSX.Element {
  const [active, setActive] = useState<string>(tab);
  const [capture, setCapture] = useState<Capture>(initial);
  const [target, setTarget] = useState<string | null>(ACA);
  const [pages, setPages] = useState<readonly CapturedPage[]>([{ n: 1 }, { n: 2 }]);
  const [landed, setLanded] = useState<readonly string[]>(initial === "uploaded" ? [ACA] : []);
  const binder = useRequestBinder({
    firm: FIRM,
    today: TPL19_COPY.today,
    binder: "2025 Binder",
    viewer: { kind: "human", name: CLAIRE },
    requests:
      initial === "uploaded"
        ? TPL07_REQUESTS.map((r) =>
            r.id === ACA ? applyUpload(r, TPL19_COPY.stitched.fileName, TPL19_COPY.today) : r,
          )
        : TPL07_REQUESTS,
    sections: TPL07_SECTIONS,
    onOpen: () => undefined,
  });
  const open = binder.items.filter((r) => r.st === "req").map((r) => ({ id: r.id, title: r.title }));
  const upload = (): void => {
    if (target !== null) {
      binder.update(target, (r) => applyUpload(r, TPL19_COPY.stitched.fileName, TPL19_COPY.today));
      setLanded((ids) => [...ids, target]);
    }
    setCapture("uploaded");
  };
  const overlay =
    capture === "sheet" ? (
      <UploadActionSheet
        request={binder.items.find((r) => r.id === target)?.title ?? null}
        onClose={() => {
          setCapture("none");
        }}
        onFiles={(files) => {
          setPages(files.map((f, i) => ({ n: i + 1, src: URL.createObjectURL(f) })));
          setCapture("review");
        }}
      />
    ) : capture === "review" ? (
      <ReviewAssignSheet
        pages={pages}
        fileName={TPL19_COPY.stitched.fileName}
        size={TPL19_COPY.stitched.size}
        sources={TPL19_COPY.stitched.sources}
        requests={open}
        selected={target}
        onSelect={setTarget}
        onRetake={() => {
          setCapture("sheet");
        }}
        onAddPage={() => {
          setCapture("sheet");
        }}
        onUpload={upload}
      />
    ) : undefined;
  return (
    <PortalBrandProvider brand={BRIGHTWATER_BRAND}>
      <PortalLayout
        variant="mobile"
        user={CLAIRE}
        nav={HOUSEHOLD}
        active={active}
        onNavigate={setActive}
        frame
        {...(more ? { moreForceState: "open" as const } : {})}
        {...(overlay === undefined ? {} : { overlay })}
      >
        {active === "Documents" ? (
          <RequestMobile
            binder={binder}
            dropHint={TPL19_COPY.dropHint}
            openOnly={{ keep: landed }}
            onUpload={(id) => {
              setTarget(id ?? ACA);
              setCapture("sheet");
            }}
            {...(capture === "uploading" ? { progress: { [ACA]: 0.7 } } : {})}
          />
        ) : (
          <>
            <MobileGreeting text={TPL19_COPY.greeting} />
            <ReturnProgressCard
              title={TPL19_COPY.ret.title}
              fraction={REQUEST_COUNTS.feld.received / REQUEST_COUNTS.feld.total}
              status={TPL19_COPY.ret.status}
              line={TPL19_COPY.ret.line}
            />
            <MobileTodoCard label="To do" items={TPL19_COPY.todos} />
            <MobileTeamCard title={TPL19_COPY.team.title} people={TPL19_COPY.team.people} />
          </>
        )}
      </PortalLayout>
    </PortalBrandProvider>
  );
}

/** Frame 5 over the camera: the review sheet on the dark viewfinder ground (no shell). */
function ReviewFrame(): JSX.Element {
  const [target, setTarget] = useState<string | null>(ACA);
  const open = TPL07_REQUESTS.filter((r) => r.st === "req").map((r) => ({
    id: r.id,
    title: r.title,
  }));
  return (
    <PortalBrandProvider brand={BRIGHTWATER_BRAND}>
      <div
        data-shell="app"
        data-variant="portal-camera"
        data-frame="phone"
        style={{ height: 844 }}
        className="relative w-[390px] flex-none overflow-hidden rounded-phone bg-cta-press shadow-e1"
      >
        <ReviewAssignSheet
          pages={[{ n: 1 }, { n: 2 }]}
          fileName={TPL19_COPY.stitched.fileName}
          size={TPL19_COPY.stitched.size}
          sources={TPL19_COPY.stitched.sources}
          requests={open}
          selected={target}
          onSelect={setTarget}
          onRetake={() => undefined}
          onAddPage={() => undefined}
          onUpload={() => undefined}
        />
      </div>
    </PortalBrandProvider>
  );
}

/** TPL-19 frames 1 to 8 and the permission-off variant (F-06-T10, F-06-T11). */
export function Tpl19Specimen(): JSX.Element {
  const alt = (frame: string): string => `${TPL19_COPY.alternate} · ${frame}`;
  return (
    <div className="flex flex-wrap gap-6">
      <Artboard id="tpl-19-1" badge="TPL-19 · 1" name="Home" note="Claire Feld at 390 × 844">
        <Phone tab="Home" />
      </Artboard>
      <Artboard
        id="tpl-19-2"
        badge="TPL-19 · 2"
        name="Documents"
        note="The open requests match TPL-07"
      >
        <Phone tab="Documents" />
      </Artboard>
      <Artboard id="tpl-19-3" badge="TPL-19 · 3" name="Camera, page 1" note={alt("Camera, page 1")}>
        <DeferredFrame />
      </Artboard>
      <Artboard id="tpl-19-4" badge="TPL-19 · 4" name="Camera, page 2" note={alt("Camera, page 2")}>
        <DeferredFrame />
      </Artboard>
      <Artboard id="tpl-19-5" badge="TPL-19 · 5" name="Review & assign" note={alt("Review & assign")}>
        <ReviewFrame />
      </Artboard>
      <Artboard
        id="tpl-19-6-ring"
        badge="TPL-19 · 6"
        name="Uploading"
        note={alt("Uploaded · the UploadRing at 70%")}
      >
        <Phone tab="Documents" capture="uploading" />
      </Artboard>
      <Artboard id="tpl-19-6" badge="TPL-19 · 6" name="Uploaded" note={alt("Uploaded")}>
        <Phone tab="Documents" capture="uploaded" />
      </Artboard>
      <Artboard
        id="tpl-19-7"
        badge="TPL-19 · 7"
        name="More sheet"
        note="No Approvals for a household"
      >
        <Phone tab="Home" more />
      </Artboard>
      <Artboard id="tpl-19-8" badge="TPL-19 · 8" name="Low-quality warning" note="R-03 (DEC-97)">
        <DeferredFrame />
      </Artboard>
      <Artboard
        id="tpl-19-perm"
        badge="TPL-19"
        name="Camera permission off"
        note="R-03 (DEC-97)"
      >
        <DeferredFrame />
      </Artboard>
    </div>
  );
}
