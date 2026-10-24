import { type JSX, useState } from "react";
import { ScheduleBar, SectionBand } from "../workpaper/bands";
import { SourceDocGroup, SourceDocRow } from "../workpaper/source-docs";
import type { SourceDoc } from "../workpaper/types";
import { WorkpaperPane } from "../workpaper/workpaper";
import { Held, Row, Sheet } from "./frame";
import { SOC_TABS, pbcGroups } from "./workpaper-data";

// The C-02 Workpaper kit and the C-15 source-document rows (F-05-T50): every band state, the
// schedule bar, the pane with its tabs, markers and footer chips, and the source-document groups
// and rows in both sizes. The workpaper is the T2 handoff's Service Organizations & SOC 1 (on the
// seed's organisations, workpaper-data.ts); the documents are Northwind's PBC list (seed-figures).

export function SectionBandSpecimen(): JSX.Element {
  return (
    <Sheet title="SectionBand and ScheduleBar" meta="30 · espresso · 12 / 500 +.04em uppercase">
      <Row name="Collapsible, open" meaning="One native button; chevron down">
        <div className="w-[560px]">
          <SectionBand number={1} title="Service organizations" />
        </div>
      </Row>
      <Row name="Collapsed" meaning="The chevron turns −90° in 220ms">
        <div className="w-[560px]">
          <SectionBand number={3} title="Complementary user entity controls" collapsed />
        </div>
      </Row>
      <Row name="Signed off" meaning="Check 11 and the sign-off at 72% white, one weight">
        <div className="w-[560px]">
          <SectionBand number={1} title="Service organizations" sign="Prepared · Accrued Agent" />
        </div>
      </Row>
      <Row name="Static" meaning="collapsible={false}: a plain bar, no chevron">
        <div className="w-[560px]">
          <SectionBand number={2} title="SOC 1 reports" collapsible={false} />
        </div>
      </Row>
      <Row name="Long title" meaning="Truncates before the sign-off, never wraps">
        <div className="w-[360px]">
          <SectionBand
            number={3}
            title="Complementary user entity controls"
            sign="Prepared · Accrued Agent"
          />
        </div>
      </Row>
      <Row name="Forced" meaning="hover and focus">
        <Held name="hover">
          <div className="w-[300px]">
            <SectionBand number={2} title="SOC 1 reports" forceState="hover" />
          </div>
        </Held>
        <Held name="focus">
          <div className="w-[300px]">
            <SectionBand number={2} title="SOC 1 reports" forceState="focus" />
          </div>
        </Held>
      </Row>
      <Row name="ScheduleBar" meaning="28 · on-dark 11.5 / 500 · ellipsis">
        <div className="w-[560px]">
          <ScheduleBar title="Schedule 1100.04-A · SOC 1 report coverage" />
        </div>
      </Row>
    </Sheet>
  );
}

export function WorkpaperPaneSpecimen(): JSX.Element {
  return (
    <div className="flex flex-wrap items-start gap-6">
      <div data-artboard="c-02-pane" className="w-[696px]">
        <WorkpaperPane title="Service Organizations & SOC 1" tabs={SOC_TABS} />
      </div>
      <div
        data-artboard="c-02-bare"
        className="flex h-[520px] w-[696px] flex-col overflow-hidden rounded-pane bg-card shadow-e2"
      >
        <p className="flex h-[46px] flex-none items-center px-[14px] text-pane font-medium hairline-b">
          chrome=&#123;false&#125; in a host pane
        </p>
        <WorkpaperPane tabs={SOC_TABS} chrome={false} />
      </div>
    </div>
  );
}

export function SourceDocsSpecimen(): JSX.Element {
  const [opened, setOpened] = useState<SourceDoc | null>(null);
  const groups = pbcGroups();
  const [plan, trust] = groups;
  const sample = (status: SourceDoc["status"]): SourceDoc =>
    groups.flatMap((g) => g.docs).find((d) => d.status === status) as SourceDoc;
  return (
    <div className="flex flex-col gap-6">
      <Sheet title="SourceDocGroup and SourceDocRow" meta="cockpit: band 31 · rows 52">
        <div data-artboard="c-15-cockpit" className="flex w-[696px] flex-col">
          {[plan, trust].map(
            (g) =>
              g !== undefined && (
                <SourceDocGroup
                  key={g.title}
                  title={g.title}
                  received={g.received}
                  total={g.total}
                >
                  {g.docs.map((doc) => (
                    <SourceDocRow
                      key={doc.id}
                      doc={doc}
                      selected={opened?.id === doc.id}
                      onOpen={setOpened}
                    />
                  ))}
                </SourceDocGroup>
              ),
          )}
          <SourceDocGroup title="Cash" received={0} total={1} defaultOpen={false}>
            <SourceDocRow doc={sample("requested")} />
          </SourceDocGroup>
        </div>
        <Row name="Opened" meaning="A row opens the viewer through onOpen">
          <span data-source-docs="opened" className="text-dense text-ink-2">
            {opened === null ? "No document open" : `Viewer: ${opened.title}`}
          </span>
        </Row>
      </Sheet>
      <Sheet title="Row states" meta="words, never colour alone">
        <Row name="Received" meaning="Green pill with a check, then the path">
          <div className="w-[560px]">
            <ul>
              <SourceDocRow doc={sample("received")} />
            </ul>
          </div>
        </Row>
        <Row name="Uploaded – needs review" meaning="Amber pill; no path until accepted">
          <div className="w-[560px]">
            <ul>
              <SourceDocRow doc={sample("review")} />
            </ul>
          </div>
        </Row>
        <Row name="Requested" meaning="ink-3 word and an empty 15 ring; never red">
          <div className="w-[560px]">
            <ul>
              <SourceDocRow doc={sample("requested")} />
            </ul>
          </div>
        </Row>
        <Row name="Selected" meaning="Open in the viewer">
          <div className="w-[560px]">
            <ul>
              <SourceDocRow doc={sample("received")} selected />
            </ul>
          </div>
        </Row>
        <Row name="Forced" meaning="hover and focus">
          <Held name="hover">
            <div className="w-[360px]">
              <ul>
                <SourceDocRow doc={sample("received")} forceState="hover" />
              </ul>
            </div>
          </Held>
          <Held name="focus">
            <div className="w-[360px]">
              <ul>
                <SourceDocRow doc={sample("received")} forceState="focus" />
              </ul>
            </div>
          </Held>
        </Row>
      </Sheet>
      <Sheet title="Compact" meta="C-15: band 32 on nested · rows 40 · padding 6 12 6 34">
        <div data-artboard="c-15-compact" className="flex w-[440px] flex-col">
          {plan !== undefined && (
            <SourceDocGroup
              size="compact"
              title={plan.title}
              received={plan.received}
              total={plan.total}
            >
              {plan.docs.map((doc) => (
                <SourceDocRow key={doc.id} size="compact" doc={doc} />
              ))}
            </SourceDocGroup>
          )}
          {trust !== undefined && (
            <SourceDocGroup
              size="compact"
              title={trust.title}
              received={trust.received}
              total={trust.total}
              defaultOpen={false}
            >
              {trust.docs.map((doc) => (
                <SourceDocRow key={doc.id} size="compact" doc={doc} />
              ))}
            </SourceDocGroup>
          )}
        </div>
      </Sheet>
    </div>
  );
}
