import { Spinner } from "@abacus/ui";
import type { JSX } from "react";

/** The product splash, shown while a signed-out visitor is sent to sign in. */
export function App({ status }: { status?: string }): JSX.Element {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3">
      <h1 className="text-2xl font-semibold">Abacus</h1>
      {status !== undefined && <Spinner label={status} />}
    </main>
  );
}
