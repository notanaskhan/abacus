import { FlagOffState } from "@abacus/ui";
import { createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { useSession } from "../../app-core/session";
import { appRoute, lazyScreen } from "../root";

// FIL-01 (N-01-T16): `/files` and `/files/$clientId`, with `?node=<folder_ref>&doc=<item id>` deep
// links (`docs/screens/FIL-01.md`), behind `files.browser`. Read-only (DV-10).

const FilesPage = lazyScreen(async () => (await import("../../screens/FIL-01")).FilesPage);

interface FilesSearch {
  node?: string;
  doc?: string;
}

function validateFilesSearch(search: Record<string, unknown>): FilesSearch {
  return {
    ...(typeof search.node === "string" && search.node !== "" ? { node: search.node } : {}),
    ...(typeof search.doc === "string" && search.doc !== "" ? { doc: search.doc } : {}),
  };
}

function gated(children: JSX.Element): JSX.Element {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <FeatureGate
        flag="files.browser"
        fallback={<FlagOffState flag="files.browser" label="Files" />}
      >
        {children}
      </FeatureGate>
    </div>
  );
}

function Files({ clientId }: { clientId?: string }): JSX.Element {
  const viewer = useSession().user?.displayName ?? "";
  // Either files route renders this: read the active match's search, never the client route's
  // alone (on /files that throws "Could not find an active match"; main CI triage, DEC-1865).
  const search: FilesSearch = useSearch({ strict: false });
  const navigate = useNavigate();
  return gated(
    <FilesPage
      {...(clientId === undefined ? {} : { clientId })}
      node={search.node ?? ""}
      doc={search.doc ?? null}
      viewer={viewer}
      onNode={(node) => {
        void navigate({ to: ".", search: { node }, replace: true });
      }}
      onDoc={(doc) => {
        void navigate({
          to: ".",
          search: {
            ...(search.node === undefined ? {} : { node: search.node }),
            ...(doc === null ? {} : { doc }),
          },
          replace: true,
        });
      }}
    />,
  );
}

export const filesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/files",
  validateSearch: validateFilesSearch,
  component: function FilesIndex(): JSX.Element {
    return <Files />;
  },
});

export const filesClientRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/files/$clientId",
  validateSearch: validateFilesSearch,
  component: function FilesOfClient(): JSX.Element {
    const { clientId } = filesClientRoute.useParams();
    return <Files clientId={clientId} />;
  },
});

export const filesRoutes = [filesRoute, filesClientRoute] as const;
