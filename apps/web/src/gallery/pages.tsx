import {
  AgentMonogram,
  AtomMark,
  EmptyState,
  HANDOFF_IN_KITS,
  HANDOFF_MISSING,
  HalfDisc,
  ICON_NAMES,
  ICON_SUBSTITUTES,
  Icon,
  VENDOR_TONES,
  VendorTile,
  ratio,
} from "@abacus/ui";
import { SPECIMENS } from "@abacus/ui/specimens";
import { Link, Outlet, useParams, useSearch } from "@tanstack/react-router";
import { type JSX, useEffect } from "react";
import {
  type FixtureParams,
  parseFixtureParams,
  screenById,
  useSeedFixtures,
} from "./fixture-mode";
import { SURFACES, colorRows, parseTokens } from "./tokens";
// The built screens register themselves for /components/screens/<ID> (P-01-T02: SHL-01).
import "../screens/gallery";

// The /components subtree (SPEC-048 AC-10, AC-11): one lazy chunk that only gallery builds
// compile. Everything here renders from fixtures; nothing calls the API.

function useFixtureParams(): FixtureParams {
  return parseFixtureParams(useSearch({ strict: false }));
}

/** `?contrast=reference` restores the handoff ladder on <html> for as long as the gallery shows. */
function useContrastLadder(params: FixtureParams): void {
  const reference = params.contrast === "reference";
  useEffect(() => {
    if (!reference) return undefined;
    document.documentElement.dataset.contrast = "reference";
    return () => {
      delete document.documentElement.dataset.contrast;
    };
  }, [reference]);
}

export function GalleryLayout(): JSX.Element {
  const params = useFixtureParams();
  useContrastLadder(params);
  if (params.frame) return <Outlet />;
  return (
    <div className="flex flex-col gap-3">
      <nav aria-label="Components" className="flex items-center gap-4 px-1">
        <h1 className="text-[20px] font-medium tracking-[-0.015em]">Components</h1>
        <Link to={"/components" as never} activeOptions={{ exact: true }} className="underline">
          Index
        </Link>
        <Link to={"/components/tokens" as never} className="underline">
          Tokens
        </Link>
        <Link to={"/components/icons" as never} className="underline">
          Icons
        </Link>
      </nav>
      <Outlet />
    </div>
  );
}

export function GalleryIndex(): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      <ul aria-label="Kits" className="flex flex-wrap gap-3 px-1">
        {SPECIMENS.map((s) => (
          <li key={s.id}>
            <a href={`#${s.id}`} className="underline">
              {`${s.kit} ${s.title}`}
            </a>
          </li>
        ))}
      </ul>
      {SPECIMENS.map((s) => (
        <section key={s.id} id={s.id} aria-label={s.title} className="flex flex-col gap-3">
          <s.Component />
        </section>
      ))}
    </div>
  );
}

const RATIO = (n: number): string => ratio(n);

export function TokensPage(): JSX.Element {
  const tokens = parseTokens();
  const colors = colorRows(tokens);
  const others = tokens.filter((t) => t.group !== "color");
  return (
    <div className="flex flex-col gap-3">
      <section aria-label="Colour tokens" className="rounded-pane bg-card p-4 shadow-e2">
        <h2 className="pb-2 text-[14.5px] font-medium">Colour</h2>
        <table className="w-full text-left">
          <caption className="sr-only">
            Every colour token, with its contrast on card, shell and nested under the AA ladder and
            the reference ladder
          </caption>
          <thead>
            <tr>
              <th scope="col">Token</th>
              <th scope="col">Swatch</th>
              <th scope="col">Value</th>
              <th scope="col">Solid on card</th>
              {SURFACES.map((s) => (
                <th key={`aa-${s}`} scope="col">{`AA on ${s}`}</th>
              ))}
              <th scope="col">Reference value</th>
              {SURFACES.map((s) => (
                <th key={`ref-${s}`} scope="col">{`Reference on ${s}`}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {colors.map((c) => (
              <tr key={c.name} data-token={`color-${c.name}`}>
                <th scope="row">{c.name}</th>
                <td>
                  <span
                    aria-hidden="true"
                    className="inline-block size-5 rounded-tile shadow-e1"
                    style={{ background: c.value }}
                  />
                </td>
                <td>{c.value}</td>
                <td>{c.solid.aa}</td>
                {SURFACES.map((s) => (
                  <td key={`aa-${s}`}>{RATIO(c.contrast.aa[s])}</td>
                ))}
                <td>{c.referenceValue}</td>
                {SURFACES.map((s) => (
                  <td key={`ref-${s}`}>{RATIO(c.contrast.reference[s])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section aria-label="Other tokens" className="rounded-pane bg-card p-4 shadow-e2">
        <h2 className="pb-2 text-[14.5px] font-medium">Type, radii, elevation and motion</h2>
        <table className="w-full text-left">
          <caption className="sr-only">Every non-colour token</caption>
          <thead>
            <tr>
              <th scope="col">Token</th>
              <th scope="col">Value</th>
            </tr>
          </thead>
          <tbody>
            {others.map((t) => (
              <tr key={`${t.group}-${t.name}`} data-token={`${t.group}-${t.name}`}>
                <th scope="row">{`${t.group}-${t.name}`}</th>
                <td>{t.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

/** Where a registered name came from: the handoff's own set, its missing-icons table, or kit data. */
function iconGroup(name: (typeof ICON_NAMES)[number]): string {
  if ((HANDOFF_MISSING as readonly string[]).includes(name)) return "Missing from accrued-ui.js";
  if ((HANDOFF_IN_KITS as readonly string[]).includes(name)) return "Found in kit data";
  return "accrued-ui.js";
}

// F-05-T13 (SPEC-048 B3): every registered icon name with its glyph, and the custom glyphs.
export function IconsPage(): JSX.Element {
  return (
    <div className="flex flex-col gap-3">
      <section aria-label="Custom glyphs" className="rounded-pane bg-card p-4 shadow-e2">
        <h2 className="pb-2 text-[14.5px] font-medium">Custom glyphs</h2>
        <ul className="flex flex-wrap items-center gap-4">
          <li data-glyph-name="agent-monogram" className="flex items-center gap-2">
            <AgentMonogram size={16} />
            <AgentMonogram size={34} />
            <span>Agent monogram</span>
          </li>
          <li data-glyph-name="atom-mark" className="flex items-center gap-2 text-ink-2">
            <AtomMark size={12} />
            <AtomMark size={22} />
            <span>Atom mark</span>
          </li>
          <li data-glyph-name="half-disc" className="flex items-center gap-2 text-ink">
            <HalfDisc size={15} />
            <HalfDisc size={22} />
            <span>Half disc</span>
          </li>
          <li data-glyph-name="vendor-tile" className="flex items-center gap-2">
            {VENDOR_TONES.map((tone) => (
              <VendorTile key={tone} name="Quick Books" tone={tone} size={32} />
            ))}
            <span>Vendor monogram tiles</span>
          </li>
        </ul>
      </section>
      <section aria-label="Registered icons" className="rounded-pane bg-card p-4 shadow-e2">
        <h2 className="pb-2 text-[14.5px] font-medium">{`Icons (${String(ICON_NAMES.length)})`}</h2>
        <table className="w-full text-left">
          <caption className="sr-only">
            Every registered icon name at 14 and 22, with the lucide name it renders as
          </caption>
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">14</th>
              <th scope="col">22</th>
              <th scope="col">Lucide name</th>
              <th scope="col">Source</th>
            </tr>
          </thead>
          <tbody>
            {ICON_NAMES.map((name) => (
              <tr key={name} data-icon-name={name}>
                <th scope="row">{name}</th>
                <td className="text-ink">
                  <Icon name={name} size={14} />
                </td>
                <td className="text-ink">
                  <Icon name={name} size={22} />
                </td>
                <td>{ICON_SUBSTITUTES[name] ?? name}</td>
                <td>{iconGroup(name)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

export function ScreenPage(): JSX.Element {
  const id =
    useParams({ strict: false, select: (p: Record<string, string | undefined>) => p.id }) ?? "";
  const params = useFixtureParams();
  const seeded = useSeedFixtures(params);
  const entry = screenById(id);
  if (entry === undefined) {
    return <EmptyState title="Not built">{`No screen is registered under ${id}.`}</EmptyState>;
  }
  if (!seeded) return <div data-screen={id} aria-busy="true" />;
  return (
    <div data-screen={id}>
      <entry.Component params={params} />
    </div>
  );
}
