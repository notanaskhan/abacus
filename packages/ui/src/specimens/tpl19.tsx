import { type JSX, useState } from "react";
import { PortalBrandProvider } from "../brand";
import { RequestMobile, useRequestBinder } from "../requests";
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

// TPL-19 frames 1, 2 and 7 on T7-M (F-06-T10; Wave 0 - Templates `#tpl19`): Claire Feld's portal
// on a 390 × 844 phone at E0. 1 Home (greeting, the return card with its ring, to-dos, team), 2
// Documents (the DropZone card, the open requests as cards, the rest folded), 7 the More sheet over
// Home, with no Approvals for a household. The open requests are TPL-07's own. Frames 3 to 6 and 8
// (the camera path) and 9 (mobile signing) are later rows. White-labelled: no product mark.

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
} as const;

function Phone({ tab, more = false }: { tab: "Home" | "Documents"; more?: boolean }): JSX.Element {
  const [active, setActive] = useState<string>(tab);
  const binder = useRequestBinder({
    firm: FIRM,
    today: "Sep 14",
    binder: "2025 Binder",
    viewer: { kind: "human", name: CLAIRE },
    requests: TPL07_REQUESTS,
    sections: TPL07_SECTIONS,
    onOpen: () => undefined,
  });
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
      >
        {active === "Documents" ? (
          <RequestMobile binder={binder} dropHint={TPL19_COPY.dropHint} openOnly={{}} />
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

/** TPL-19 frames 1, 2 and 7 (F-06-T10). */
export function Tpl19Specimen(): JSX.Element {
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
      <Artboard
        id="tpl-19-7"
        badge="TPL-19 · 7"
        name="More sheet"
        note="No Approvals for a household"
      >
        <Phone tab="Home" more />
      </Artboard>
    </div>
  );
}
