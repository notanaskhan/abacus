// HOME-01 R2 bands (I-01-T24): To-dos and Mentions, copy verbatim from the handoff's revision.md
// (CHANGES 3, NEW STATES h and i). Names, titles, quotes and objects are data, never copy.

export const BAND_COPY = {
  todos: { title: "To-dos", empty: "Nothing assigned", from: (name: string) => `from ${name}` },
  mentions: {
    title: "Mentions",
    empty: "No new mentions",
    mentioned: (name: string) => `${name} mentioned you`,
    quoted: (text: string, object: string) => `'${text}' · ${object}`,
    unread: "Unread",
  },
} as const;
