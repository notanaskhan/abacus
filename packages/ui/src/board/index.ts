// L2 board kit (F-08 §B; T19): the BoardCanvas engine (F-08-T18). BoardCard C-24, headers, lanes and
// the navigator are F-08-T21; BoardLayout T19 is F-08-T22.
export { BoardCanvas, type BoardCanvasProps } from "./BoardCanvas";
export {
  type BoardCardVM,
  type BoardColumn,
  type MoveIntent,
  type MoveResult,
  SPRING_BACK_MS,
} from "./types";
