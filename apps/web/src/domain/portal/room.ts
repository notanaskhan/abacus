// The third-party room's data (R-01 §5.2, L3; docs/screens/POR-14.md): exactly the requests
// delegated to the person (`GET /v1/portal/room`, C5 portal-pbc; DEC-387), the code-only "Which
// request is this for?" pre-selection (`POST /v1/portal/room/suggest`) and the person's writes on
// a delegated request (its own upload, withdraw and shared comment), over the generated client.

import type { PortalFileOut, PortalRoomOut, PortalRoomRowOut } from "@abacus/api-client";
import { suggestRoomRequest } from "@abacus/api-client";
import {
  getPortalRoomOptions,
  getPortalRoomQueryKey,
  itemCommentsQueryKey,
} from "@abacus/api-client/query";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { postComment, uploadFiles, withdrawFile } from "./sheet";

export function useRoom() {
  return useQuery({ ...getPortalRoomOptions(), retry: false });
}

/** Every row of the room, band by band. */
export function roomRows(room: PortalRoomOut): PortalRoomRowOut[] {
  return room.bands.flatMap((b) => b.rows);
}

/** The rows that still take an upload. */
export function openRows(room: PortalRoomOut): PortalRoomRowOut[] {
  return roomRows(room).filter((r) => (r.allowed_actions ?? []).includes("upload"));
}

/** The pre-selection for files dropped on the pill: the one open row the server's code-only
 * scoring names for the first file, if any. */
export async function suggestFor(files: readonly File[]): Promise<string | null> {
  if (files.length === 0) return null;
  const answer = await suggestRoomRequest({
    body: { file_names: files.slice(0, 20).map((f) => f.name) },
  });
  return answer.data?.suggestions[0]?.request_item_id ?? null;
}

/** The person's writes on a delegated request, each followed by a fresh read of the room (and
 * the request's thread). */
export function useRoomActions() {
  const queryClient = useQueryClient();
  const refresh = (row: PortalRoomRowOut): void => {
    void queryClient.invalidateQueries({ queryKey: getPortalRoomQueryKey() });
    void queryClient.invalidateQueries({
      queryKey: itemCommentsQueryKey({
        path: { engagement_id: row.engagement_id, item_id: row.id },
      }),
    });
  };
  return {
    upload: async (row: PortalRoomRowOut, files: readonly File[]): Promise<void> => {
      await uploadFiles(row.engagement_id, row.id, files);
      refresh(row);
    },
    withdraw: async (row: PortalRoomRowOut, file: PortalFileOut): Promise<void> => {
      await withdrawFile(row.engagement_id, file.id);
      refresh(row);
    },
    comment: async (row: PortalRoomRowOut, text: string): Promise<void> => {
      await postComment(row.engagement_id, row.id, text);
      refresh(row);
    },
  };
}
