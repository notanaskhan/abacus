import { CommandPalette, type PaletteGroup } from "@abacus/ui";
import { type JSX, useMemo, useState } from "react";
import { type Area, AREAS } from "../../app-core/nav-areas";
import { INTERIM_GO } from "./copy";

// The interim Go… frame (P-01-T02; P-01 §2.2, AC 1.1.8): until SHL-02 ships with P-02, Go… and
// ⌘K open the O5 palette frame over the 13 areas of nav.ts, filtered here in the browser, and the
// shortcut list. It sends no request and searches nothing. Undesigned: composed from the O5 kit
// (DEC-32 pattern), reviewed by AY.

export interface InterimGoProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onArea: (area: Area) => void;
}

function chordHint(area: Area): string | undefined {
  return area.chord === undefined ? undefined : `G ${area.chord.toUpperCase()}`;
}

export function InterimGo({ open, onOpenChange, onArea }: InterimGoProps): JSX.Element {
  const [query, setQuery] = useState("");
  const groups = useMemo<PaletteGroup[]>(() => {
    const q = query.trim().toLowerCase();
    const areas = AREAS.filter((a) => q === "" || a.label.toLowerCase().includes(q));
    const shortcuts = INTERIM_GO.shortcuts.filter(
      (s) => q === "" || s.label.toLowerCase().includes(q),
    );
    return [
      {
        label: INTERIM_GO.areas,
        items: areas.map((area) => {
          const hint = chordHint(area);
          return {
            id: `area-${area.landing}`,
            label: area.label,
            ...(hint === undefined ? {} : { hint }),
            run: () => {
              onArea(area);
            },
          };
        }),
      },
      {
        label: INTERIM_GO.shortcutsTitle,
        items: shortcuts.map((s) => ({
          id: `key-${s.keys}`,
          label: s.label,
          hint: s.keys,
          run: () => {
            const area = AREAS.find((a) => a.label === s.label);
            if (area !== undefined) onArea(area);
          },
        })),
      },
    ];
  }, [query, onArea]);
  return (
    <CommandPalette
      open={open}
      onOpenChange={(next) => {
        if (!next) setQuery("");
        onOpenChange(next);
      }}
      query={query}
      onQueryChange={setQuery}
      groups={groups}
      placeholder={INTERIM_GO.placeholder}
    />
  );
}
