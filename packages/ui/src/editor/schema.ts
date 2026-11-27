// F-08-T28 (DEC-6026): the T20 custom schema (F-08 §5 C1; ADR P-59). A document is sections;
// a section holds statement captions and note headings (heading 1-3), body paragraphs, lists and
// read-only statement tables. No links (no blue on paper), no code, no raw HTML node: parseHTML
// is the schema's own and the paste path never reaches it (paste.ts).
import { Node, ReactNodeViewRenderer, mergeAttributes } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import type { Extensions } from "@tiptap/react";
import { StatementTableView } from "./StatementTable";

export const DocNode = Node.create({
  name: "doc",
  topNode: true,
  content: "section+",
});

export const SectionNode = Node.create({
  name: "section",
  group: "section",
  content: "block+",
  defining: true,
  isolating: true,
  addAttributes() {
    return {
      key: { default: "", renderHTML: () => ({}) },
      label: { default: "", renderHTML: () => ({}) },
    };
  },
  parseHTML() {
    return [{ tag: "section[data-section]" }];
  },
  renderHTML({ HTMLAttributes, node }) {
    return [
      "section",
      mergeAttributes(HTMLAttributes, { "data-section": String(node.attrs["key"]) }),
      0,
    ];
  },
});

export const StatementTableNode = Node.create({
  name: "statementTable",
  group: "block",
  atom: true,
  selectable: false,
  draggable: false,
  addAttributes() {
    return {
      key: { default: "", renderHTML: () => ({}) },
      columns: { default: [], renderHTML: () => ({}) },
      rows: { default: [], renderHTML: () => ({}) },
    };
  },
  parseHTML() {
    return [{ tag: "div[data-statement]" }];
  },
  renderHTML({ node }) {
    return ["div", { "data-statement": String(node.attrs["key"]) }];
  },
  addNodeView() {
    return ReactNodeViewRenderer(StatementTableView, { contentDOMElementTag: "div" });
  },
});

export function documentExtensions(): Extensions {
  return [
    DocNode,
    SectionNode,
    StatementTableNode,
    StarterKit.configure({
      document: false,
      heading: { levels: [1, 2, 3] },
      link: false,
      code: false,
      codeBlock: false,
      blockquote: false,
      horizontalRule: false,
      strike: false,
      dropcursor: false,
      trailingNode: false,
    }),
  ];
}
