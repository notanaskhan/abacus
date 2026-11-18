// The console shell (G-04-T14; G-04 §5.1, §5.3): the staff sign-in gate around PLT-01. In fixture
// mode (`VITE_FIXTURES=1`, `?st=a…g`) the Rowan Achebe persona is signed in and PLT-01 renders its
// artboards; Library releases (e) shows only there. A production build folds the fixture flag to a
// constant, so the PLT-01 fixture screen (seed-backed until its live hosts land) and the seed are
// dropped from dist/console (scripts/console-dist-check.mjs holds it), and the page is the gate.
import { Skeleton } from "@abacus/ui";
import { type JSX, Suspense, lazy } from "react";
import { StaffAuth } from "./StaffAuth";

const FIXTURES = import.meta.env.VITE_FIXTURES === "1";

const FixtureConsole = FIXTURES
  ? lazy(async () => ({ default: (await import("../screens/PLT-01")).TenantConsole }))
  : null;

export function ConsoleShell({ search }: { search: string }): JSX.Element {
  const st = new URLSearchParams(search).get("st") ?? undefined;
  return (
    <StaffAuth signedIn={FixtureConsole !== null}>
      {FixtureConsole !== null && (
        <Suspense fallback={<Skeleton className="h-[480px]" />}>
          <FixtureConsole st={st} />
        </Suspense>
      )}
    </StaffAuth>
  );
}
