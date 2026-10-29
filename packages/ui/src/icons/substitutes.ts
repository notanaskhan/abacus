import type { IconName } from "./names";

export const ICON_SUBSTITUTES: { readonly [N in IconName]?: string } = {
  "align-center": "text-align-center",
  "align-left": "text-align-start",
  "align-right": "text-align-end",
  "book-marked": "book-bookmark",
  "building-2": "building-complex",
  "circle-help": "circle-question-mark",
  filter: "funnel",
  "gantt-chart": "chart-gantt",
  history: "rotate-ccw-clock",
  indent: "list-indent-increase",
  "indent-decrease": "list-indent-decrease",
  "indent-increase": "list-indent-increase",
  text: "text-align-start",
  "trash-2": "trash",
  "wrap-text": "text-wrap",
};
