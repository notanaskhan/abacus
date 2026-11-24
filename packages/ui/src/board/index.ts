// L2 board kit (F-08 §B; T19): the BoardCanvas engine (F-08-T18). BoardCard C-24, headers, lanes and
// the navigator are F-08-T21; BoardLayout T19 is F-08-T22.
export { BoardCanvas, type BoardCanvasProps } from "./BoardCanvas";
// F-08-T22 (DEC-5930): BoardLayout T19.
export {
  type BoardFilter,
  BoardLayout,
  type BoardLayoutCard,
  type BoardLayoutColumn,
  type BoardLayoutLane,
  type BoardLayoutProps,
  type BoardVariant,
  type BoardView,
  RUN_ON_MOVE_DENIED,
} from "./BoardLayout";
// F-08-T21 (DEC-5929): C-24 card, header and lane, C-26 AgentProgress, the 280 navigator.
export {
  AgentProgress,
  type AgentProgressProps,
  type AgentProgressState,
  BoardCard,
  type BoardCardLook,
  type BoardCardProps,
  type BoardCardVariant,
  BoardColumnHeader,
  type BoardColumnHeaderProps,
  BoardLane,
  type BoardLaneProps,
  BoardNavigator,
  type BoardNavigatorProps,
  type NavigatorItem,
} from "./BoardCard";
export {
  type BoardCardVM,
  type BoardColumn,
  type MoveIntent,
  type MoveResult,
  SPRING_BACK_MS,
} from "./types";
