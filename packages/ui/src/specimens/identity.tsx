import type { JSX } from "react";
import {
  AgentAvatar,
  FirmMark,
  MONOGRAM_SIZES,
  Monogram,
  PERSON_SIZES,
  PERSON_TINTS,
  Person,
  PersonStack,
  Wordmark,
} from "../brand";
import { Row, Sheet } from "./frame";

// The identity primitives' specimens (F-05-T14): the brand of Foundations 01, the Agent's avatar,
// the firm's own mark (C-00) and people (C-28). Names are the handoff's: the demo firm
// Brightwater Hale and the people of the Presence seed.

const PEOPLE = [
  "Hannah Leclerc",
  "Simone Baptiste",
  "Cole Hart",
  "Margaret Okonkwo",
  "Thomas Whitcombe",
] as const;

const WORDMARK_SIZES = [76, 44, 32, 24, 20, 12.5] as const;

export function WordmarkSpecimen(): JSX.Element {
  return (
    <Sheet title="Wordmark" meta="Geist 500 · tracking −0.035em · posted dot · minimum 12">
      {WORDMARK_SIZES.map((size) => (
        <Row
          key={size}
          name={`${String(size)}px`}
          meaning={
            size === 76
              ? "Hero"
              : size === 44
                ? "Clearspace"
                : size === 20
                  ? "Sign-in"
                  : size === 12.5
                    ? "Palette, firm menu, portal footer"
                    : undefined
          }
        >
          <Wordmark size={size} />
        </Row>
      ))}
    </Sheet>
  );
}

export function MonogramSpecimen(): JSX.Element {
  return (
    <Sheet title="Monogram and Agent avatar" meta="Radius 28% · “a” at 0.62 · minimum 16">
      <Row name="Monogram" meaning="Sign-in, favicon, tenant console">
        {MONOGRAM_SIZES.map((size) => (
          <span key={size} className="inline-flex flex-col items-center gap-1">
            <Monogram size={size} label={`Monogram ${String(size)}`} />
            <span className="text-meta text-ink-3">{size}</span>
          </span>
        ))}
      </Row>
      <Row name="Agent avatar" meaning="The Agent is never a person">
        <AgentAvatar label="Accrued Agent" />
      </Row>
      <Row name="Sign-in lockup" meaning="Monogram 28 and wordmark 20, gap 10">
        <span className="inline-flex items-center gap-[10px]">
          <Monogram size={28} />
          <Wordmark size={20} />
        </span>
      </Row>
    </Sheet>
  );
}

export function FirmMarkSpecimen(): JSX.Element {
  return (
    <Sheet title="Firm mark" meta="Radius 5 · hairline ring · the portal's own mark">
      <Row name="Initials" meaning="Default, from the firm's name">
        <FirmMark name="Brightwater Hale" size={20} />
        <FirmMark name="Brightwater Hale" size={34} />
      </Row>
      <Row name="Wave" meaning="The demo firm's mark in the kit">
        <FirmMark name="Brightwater Hale" mark="wave" size={20} />
        <FirmMark name="Brightwater Hale" mark="wave" size={34} />
      </Row>
      <Row name="Portal toolbar slot" meaning="Mark 20, gap 9, name 16">
        <span className="inline-flex items-center gap-[9px]">
          <FirmMark name="Brightwater Hale" mark="wave" />
          <span className="text-brand">Brightwater Hale</span>
        </span>
      </Row>
    </Sheet>
  );
}

export function PersonSpecimen(): JSX.Element {
  return (
    <Sheet title="People" meta="Initials on a tint in join order · no photos · no online dots">
      {PERSON_SIZES.map((size) => (
        <Row key={size} name={`Person ${String(size)}px`} meaning="Avatar, 8px, name 13">
          <Person name="Hannah Leclerc" size={size} />
          <Person name="Margaret Okonkwo" size={size} idle />
          <Person name="Thomas" size={size} />
        </Row>
      ))}
      <Row name="Tints" meaning="Join order; the fifth reuses the first">
        {PERSON_TINTS.map((tint, i) => (
          <Person key={tint} name={PEOPLE[i] ?? "Hannah Leclerc"} tint={tint} showName={false} />
        ))}
        <Person name={PEOPLE[4]} tint={1} showName={false} />
      </Row>
      <Row name="Idle" meaning="No activity for over five minutes">
        <Person name="Hannah Leclerc" tint={1} showName={false} />
        <Person name="Hannah Leclerc" tint={1} idle showName={false} />
        <Person name="Simone Baptiste" showName={false} idle />
      </Row>
      <Row name="Stack" meaning="Overlap −6, ring 1.5, at most 3 then +n">
        <PersonStack people={PEOPLE.slice(0, 2).map((name) => ({ name }))} />
        <PersonStack people={PEOPLE.slice(0, 3).map((name) => ({ name }))} />
        <PersonStack people={PEOPLE.map((name) => ({ name }))} />
        <PersonStack people={PEOPLE.slice(0, 3).map((name, i) => ({ name, idle: i === 2 }))} />
      </Row>
    </Sheet>
  );
}
