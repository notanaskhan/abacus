// BoardCanvas view models (F-08-T18; F-08 §B1; T19). The board is a read model: a move is an intent
// the host sends to the server, and the result comes back from it (chapter 04 §7.5 "guarded moves").

export interface BoardColumn {
  key: string;
  label: string;
  /** The server's count for the column (the tiles' truth); the preview adds the dragged card. */
  count: number;
  /** A column the dragged card may not enter dims to .5 and refuses the drop. */
  accepts?: boolean;
}

export interface BoardCardVM {
  id: string;
  column: string;
  title: string;
  version: number;
}

export interface MoveIntent {
  cardId: string;
  toColumn: string;
  expectedVersion: number;
  /** Only when the host allows a run on move (its AI policy); never true otherwise. */
  runAgent: boolean;
}

export type MoveResult =
  | { kind: "moved" }
  | { kind: "dispatched"; runId: string; text: string }
  | { kind: "guarded"; requires: "sign_off"; text: string }
  | { kind: "refused"; text: string };

export const SPRING_BACK_MS = 240;
