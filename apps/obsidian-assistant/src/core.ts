/**
 * Local note search and confirmed writes.
 *
 * The vault reader is only asked for the paths the user selected. Nothing in
 * this module opens a server or uploads a note.
 */

export const READS_WHOLE_VAULT = false;
export const EXPOSES_PUBLIC_ENDPOINT = false;
export const UPLOADS_VAULT = false;

export type NoteAction = "create" | "edit" | "delete";

export interface GroundedNote {
  path: string;
  title: string;
  body: string;
}

export interface NoteReader {
  read(path: string): Promise<string | null>;
}

export interface NoteWriter {
  create(path: string, body: string): Promise<void>;
  modify(path: string, body: string): Promise<void>;
  trash(path: string): Promise<void>;
}

export interface Confirmation {
  confirmed: boolean;
  action: NoteAction;
  path: string;
}

export type Mutation =
  | { action: "create"; path: string; body: string }
  | { action: "edit"; path: string; body: string }
  | { action: "delete"; path: string };

export interface SearchHit {
  path: string;
  title: string;
  excerpt: string;
}

export function titleFromPath(path: string): string {
  const name = path.split("/").pop() ?? path;
  return name.replace(/\.md$/i, "");
}

export function excerpt(body: string, query: string): string {
  const needle = query.trim().toLowerCase();
  if (!needle) return "";
  const index = body.toLowerCase().indexOf(needle);
  if (index < 0) return "";
  const start = Math.max(0, index - 24);
  const end = Math.min(body.length, index + needle.length + 24);
  return body.slice(start, end);
}

export async function searchSelected(
  reader: NoteReader,
  selected: readonly string[],
): Promise<{ notes: GroundedNote[]; readPaths: string[] }> {
  const readPaths: string[] = [];
  const notes: GroundedNote[] = [];
  const unique = [...new Set(selected.map((path) => path.trim()).filter(Boolean))];
  for (const path of unique) {
    readPaths.push(path);
    const body = await reader.read(path);
    if (body === null) continue;
    notes.push({ path, title: titleFromPath(path), body });
  }
  return { notes, readPaths };
}

export function answerFromNotes(
  query: string,
  notes: readonly GroundedNote[],
): { text: string; used: SearchHit[] } {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return { text: "No query was provided.", used: [] };
  }
  const used: SearchHit[] = [];
  for (const note of notes) {
    const inBody = note.body.toLowerCase().includes(needle);
    const inTitle = note.title.toLowerCase().includes(needle);
    if (!inBody && !inTitle) continue;
    const slice = inBody ? excerpt(note.body, query) : note.title;
    used.push({ path: note.path, title: note.title, excerpt: slice });
  }
  if (used.length === 0) {
    return { text: "No selected note contains that query.", used: [] };
  }
  const lines = used.map((hit) => `${hit.path}: ${hit.excerpt}`);
  return {
    text: `Notes used: ${used.map((hit) => hit.path).join(", ")}\n${lines.join("\n")}`,
    used,
  };
}

export async function applyMutation(
  writer: NoteWriter,
  mutation: Mutation,
  confirmation: Confirmation | null,
): Promise<{ applied: boolean; reason: string }> {
  const confirmed =
    confirmation !== null &&
    confirmation.confirmed === true &&
    confirmation.action === mutation.action &&
    confirmation.path === mutation.path;
  if (!confirmed) {
    return { applied: false, reason: "confirmation_required" };
  }
  if (mutation.action === "create") {
    await writer.create(mutation.path, mutation.body);
    return { applied: true, reason: "created" };
  }
  if (mutation.action === "edit") {
    await writer.modify(mutation.path, mutation.body);
    return { applied: true, reason: "edited" };
  }
  await writer.trash(mutation.path);
  return { applied: true, reason: "trashed" };
}
