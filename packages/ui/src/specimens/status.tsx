import type { JSX, ReactNode } from "react";
import {
  RegistryStatus,
  StatusDisc,
  StatusPill,
  SubLine,
  SyncChip,
  TallyPill,
  Tick,
  type TickCode,
} from "../components/status";
import {
  DISC_LABEL,
  DISC_STATES,
  type DiscSize,
  type PillSize,
  type PillVariant,
  type RegistryCode,
  type RegistryObject,
} from "../status";
import { STATUS_REGISTRY } from "../status.gen";

// The Status kit's specimens (C-06, F-05-T12): the sheets of the kit handoff, drawn by the shared
// components. Sample words are registry words; a placeholder reads as itself ("Synced {date}"),
// so no sample data is invented.

function Sheet({
  title,
  meta,
  children,
}: {
  title: string;
  meta?: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <section className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2">
      <div className="flex h-[31px] items-center gap-2 border-b-[0.5px] border-hair bg-band-hd px-3">
        <h2 className="flex-1 truncate text-section">{title}</h2>
        {meta !== undefined && <span className="text-meta text-ink-3">{meta}</span>}
      </div>
      <div className="flex flex-col">{children}</div>
    </section>
  );
}

function Row({
  name,
  meaning,
  spec,
  children,
}: {
  name: string;
  meaning?: string;
  spec?: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <div className="flex min-h-11 flex-wrap items-center gap-x-3.5 gap-y-2 border-b-[0.5px] border-hair px-3.5 py-2 last:border-b-0">
      <div className="w-[200px] shrink-0">
        <div className="text-dense font-medium">{name}</div>
        {meaning !== undefined && <div className="text-meta text-ink-3">{meaning}</div>}
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">{children}</div>
      {spec !== undefined && <div className="ml-auto text-right text-meta text-ink-3">{spec}</div>}
    </div>
  );
}

/** A placeholder in a word reads as itself: "Synced {date}". */
function asItself(object: RegistryObject, code: string): Record<string, string> {
  const codes: Record<string, { label: string }> = STATUS_REGISTRY[object];
  const label = codes[code]?.label ?? "";
  return Object.fromEntries(
    [...label.matchAll(/\{(\w+)\}/g)].flatMap((m) => (m[1] === undefined ? [] : [[m[1], m[0]]])),
  );
}

function Registry<O extends RegistryObject>({
  object,
  code,
}: {
  object: O;
  code: RegistryCode<O>;
}): JSX.Element {
  return <RegistryStatus object={object} code={code} vars={asItself(object, code)} />;
}

// ---- Pills ------------------------------------------------------------------------------------

const VARIANTS: { variant: PillVariant; meaning: string; samples: JSX.Element }[] = [
  {
    variant: "amber",
    meaning: "In motion or waiting on someone",
    samples: (
      <>
        <Registry object="return" code="in_review" />
        <Registry object="engagement" code="active" />
      </>
    ),
  },
  {
    variant: "green",
    meaning: "Finished, matched, ties",
    samples: (
      <>
        <Registry object="engagement" code="delivered" />
        <Registry object="proposed_entry" code="approved" />
      </>
    ),
  },
  {
    variant: "green-tint",
    meaning: "Cleared to move to the next step",
    samples: (
      <>
        <Registry object="return" code="approved" />
        <Registry object="document" code="matched" />
      </>
    ),
  },
  {
    variant: "red",
    meaning: "Must be reported. Used sparingly",
    samples: <Registry object="deficiency_severity" code="significant_deficiency" />,
  },
  {
    variant: "red-tint",
    meaning: "Something is wrong and needs a person",
    samples: (
      <>
        <Registry object="return" code="rejected" />
        <Registry object="request" code="overdue" />
      </>
    ),
  },
  {
    variant: "neutral",
    meaning: "Facts without judgment",
    samples: <Registry object="return" code="not_started" />,
  },
  {
    variant: "muted",
    meaning: "Blocked upstream, nothing to do yet",
    samples: (
      <>
        <Registry object="engagement" code="on_hold" />
        <Registry object="tie_out_tally" code="pending" />
      </>
    ),
  },
  {
    variant: "soon",
    meaning: "Feature not yet available",
    samples: <Registry object="integration" code="coming_soon" />,
  },
  {
    variant: "outline",
    meaning: "Can be installed or enabled",
    samples: <Registry object="integration" code="available" />,
  },
  {
    variant: "tag",
    meaning: "Category, never a state",
    samples: (
      <>
        <Registry object="misstatement_type" code="factual" />
        <Registry object="saved_prompt_access" code="firm" />
      </>
    ),
  },
];

const SIZES: { size: PillSize; use: string; sample: JSX.Element }[] = [
  {
    size: "state",
    use: "Record state in lists and headers",
    sample: <Registry object="return" code="in_review" />,
  },
  {
    size: "card-state",
    use: "Overview card",
    sample: <Registry object="audit_engagement" code="planning" />,
  },
  { size: "sm", use: "Row second line", sample: <Registry object="document" code="matched" /> },
  { size: "micro", use: "Tickmarks", sample: <Tick code="MS" /> },
  { size: "status", use: "Status picker", sample: <Registry object="close" code="not_started" /> },
  {
    size: "outline",
    use: "Availability",
    sample: <Registry object="integration" code="available" />,
  },
  { size: "tally", use: "Tally strip", sample: <TallyPill code="tie" /> },
  { size: "tag", use: "Category", sample: <Registry object="misstatement_type" code="factual" /> },
];

export function StatusPillSpecimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      <Sheet title="Pill variants" meta="Purple is source tracing and never a status">
        {VARIANTS.map(({ variant, meaning, samples }) => (
          <Row key={variant} name={variant} meaning={meaning}>
            {samples}
          </Row>
        ))}
      </Sheet>
      <Sheet title="Pill sizes" meta="Radius 999, weight 500, never uppercase">
        {SIZES.map(({ size, use, sample }) => (
          <Row key={size} name={size} meaning={use}>
            {sample}
          </Row>
        ))}
      </Sheet>
      <Sheet title="Check, spinner and chevron" meta="The only things inside a pill besides words">
        <Row name="check" meaning="A finished state">
          <StatusPill variant="green" check>
            Complete
          </StatusPill>
        </Row>
        <Row name="spin" meaning="Work in flight">
          <StatusPill variant="amber" spin>
            Working
          </StatusPill>
        </Row>
        <Row name="chevron" meaning="A picker">
          <StatusPill variant="neutral" size="status">
            Not started
          </StatusPill>
        </Row>
      </Sheet>
    </div>
  );
}

// ---- Discs ------------------------------------------------------------------------------------

const DISC_SIZES: readonly DiscSize[] = [13, 15, 17];
const DISC_DRAWING: Record<(typeof DISC_STATES)[number], string> = {
  done: "Olive fill, white check",
  prepared: "Ink-4 ring, ink-3 check",
  todo: "Empty ink-4 ring",
  half: "Left half ink, ink-2 ring",
  run: "Chip track, ink-2 arc, 820ms",
  warn: "Amber triangle, no circle",
  fail: "Brick fill, white x",
  off: "Ink-4 fill, white x",
  wait: "Solid amber dot",
};

export function StatusDiscSpecimen(): JSX.Element {
  return (
    <Sheet title="StatusDisc" meta="13 in issue rows, 15 in rows and rails, 17 in task rows">
      {DISC_STATES.map((state) => (
        <Row key={state} name={state} meaning={DISC_LABEL[state]} spec={DISC_DRAWING[state]}>
          {DISC_SIZES.map((size) => (
            <StatusDisc key={size} state={state} size={size} />
          ))}
        </Row>
      ))}
    </Sheet>
  );
}

// ---- Lines ------------------------------------------------------------------------------------

export function SubLineSpecimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      <Sheet title="SubLine" meta="A disc and an 11.5px line, not a pill">
        <Row name="text" meaning="Ink-3">
          <SubLine disc="todo">Queued</SubLine>
          <SubLine disc="run">Running</SubLine>
        </Row>
        <Row name="text-amber" meaning="Amber ink, for a line that wants a person">
          <SubLine tone="text-amber" disc="half">
            Blocked on a Partner decision
          </SubLine>
        </Row>
      </Sheet>
      <Sheet title="Lines from the registry" meta="Close task and inbox item">
        {(Object.keys(STATUS_REGISTRY.close_task) as RegistryCode<"close_task">[]).map((code) => (
          <Row key={code} name={`close_task · ${code}`}>
            <Registry object="close_task" code={code} />
          </Row>
        ))}
        {(Object.keys(STATUS_REGISTRY.inbox_item) as RegistryCode<"inbox_item">[]).map((code) => (
          <Row key={code} name={`inbox_item · ${code}`}>
            <Registry object="inbox_item" code={code} />
          </Row>
        ))}
      </Sheet>
    </div>
  );
}

// ---- Sync chip --------------------------------------------------------------------------------

export function SyncChipSpecimen(): JSX.Element {
  return (
    <Sheet
      title="SyncChip"
      meta="The record header's chip: white, 29 high, the glyph is the state"
    >
      {(Object.keys(STATUS_REGISTRY.return_sync_chip) as RegistryCode<"return_sync_chip">[]).map(
        (code) => (
          <Row key={code} name={code}>
            <SyncChip
              code={code}
              vars={asItself("return_sync_chip", code)}
              onClick={() => undefined}
              aria-haspopup="menu"
            />
          </Row>
        ),
      )}
    </Sheet>
  );
}

// ---- Marks ------------------------------------------------------------------------------------

const TICKS: { code: TickCode; meaning: string }[] = [
  { code: "MS", meaning: "Agreed to source: micro green" },
  { code: "Received", meaning: "Received: micro green" },
  { code: "check", meaning: "Agreed: bare ink-3 check" },
  { code: "F", meaning: "Micro neutral" },
  { code: "CF", meaning: "Micro neutral" },
  { code: "PY", meaning: "Micro neutral" },
];

export function TickSpecimen(): JSX.Element {
  return (
    <Sheet title="Tick" meta="Tickmarks in workpaper cells">
      {TICKS.map(({ code, meaning }) => (
        <Row key={code} name={code} meaning={meaning}>
          <Tick code={code} />
        </Row>
      ))}
    </Sheet>
  );
}

export function TallyPillSpecimen(): JSX.Element {
  return (
    <Sheet title="TallyPill" meta="The tally strip's words come from the registry">
      {(Object.keys(STATUS_REGISTRY.tie_out_tally) as RegistryCode<"tie_out_tally">[]).map(
        (code) => (
          <Row key={code} name={code}>
            <TallyPill code={code} vars={asItself("tie_out_tally", code)} />
          </Row>
        ),
      )}
    </Sheet>
  );
}

// ---- The matrix -------------------------------------------------------------------------------

/** Every word of the registry, grouped by object: the blueprint's 3.3.1 and the addendum's 3.2. */
export function StatusMapSpecimen(): JSX.Element {
  const objects = Object.keys(STATUS_REGISTRY) as RegistryObject[];
  return (
    <Sheet title="Status map by object" meta={`${String(objects.length)} objects, every word`}>
      {objects.map((object) => {
        const codes = Object.keys(STATUS_REGISTRY[object]);
        return (
          <Row key={object} name={object} meaning={`${String(codes.length)} words`}>
            <ul aria-label={object} className="flex flex-wrap items-center gap-x-4 gap-y-2">
              {codes.map((code) => (
                <li key={code} data-code={`${object}.${code}`}>
                  <RegistryStatus
                    object={object}
                    code={code as never}
                    vars={asItself(object, code)}
                  />
                </li>
              ))}
            </ul>
          </Row>
        );
      })}
    </Sheet>
  );
}
