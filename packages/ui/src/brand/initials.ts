// Initials for avatars and tiles (C-28 Presence, C-00 firm logo slot). Two capitals at most, never
// a photo: a person is "SB" for Simone Baptiste, a firm is "BH" for Brightwater Hale.

const SEPARATORS = /[\s\-_/&.,]+/u;

function words(name: string): string[] {
  return name.split(SEPARATORS).filter((w) => w.length > 0);
}

function capital(word: string | undefined): string {
  return word === undefined ? "" : (Array.from(word)[0] ?? "").toUpperCase();
}

/**
 * A person's initials: the first letter of the first word and of the last ("Hannah Leclerc" is
 * "HL", "Cole A. Hart" is "CH"); one word gives one letter. An empty name gives "?".
 */
export function personInitials(name: string): string {
  const parts = words(name);
  const first = parts[0];
  const last = parts.length > 1 ? parts[parts.length - 1] : undefined;
  return `${capital(first)}${capital(last)}` || "?";
}

/**
 * A firm's initials: the first letters of its first two words ("Brightwater Hale LLP" is "BH").
 * An empty name gives "?".
 */
export function firmInitials(name: string): string {
  const [first, second] = words(name);
  return `${capital(first)}${capital(second)}` || "?";
}
