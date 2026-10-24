// F-04-T31 (F-04.21; ADR-085): fixture JSON exported from the Python Brightwater Hale scenario at
// E0 through the API (`make fixtures SNAPSHOT=E0`). The backend's equivalence test holds these
// files to `make seed-demo` + the API; `exported.test.ts` holds fixture mode to these files.
// Fixture mode serves them for the reads they cover; the rest of the TS seed is interim until
// each read is exported.

import type { FirmClientOut, RequestItemOut } from "@abacus/api-client";
import engagementsE0 from "./e0.engagements.json";
import firmClientsE0 from "./e0.firm-clients.json";
import northwindRequestsE0 from "./e0.northwind-request-items.json";

export interface ExportedRead<T> {
  scenario: { version: string; hash: string; snapshot: string };
  persona: string;
  request: string;
  body: T;
}

/** The E0 exports, typed with the generated API types (a schema change breaks the build). */
export const EXPORTED_E0 = {
  firmClients: firmClientsE0 as ExportedRead<FirmClientOut[]>,
  engagements: engagementsE0 as ExportedRead<Record<string, unknown>[]>,
  northwindRequestItems: northwindRequestsE0 as ExportedRead<RequestItemOut[]>,
} as const;
