import assert from "node:assert/strict";
import test from "node:test";
import { editNote, searchNotes } from "./vault.mjs";

const notes = [
  { path: "trading.md", title: "Desk", body: "Private trading notes stay here." },
  { path: "garden.md", title: "Garden", body: "Tomatoes." },
];

test("search names the notes that matched", () => {
  const found = searchNotes(notes, "tomatoes");
  assert.deepEqual(found, [{ path: "garden.md", title: "Garden" }]);
});

test("an edit without confirmation does not change the note", () => {
  const result = editNote(notes, "garden.md", "Changed.", false);
  assert.equal(result.applied, false);
  assert.equal(result.reason, "confirmation_required");
  assert.equal(result.notes[1].body, "Tomatoes.");
});

test("a confirmed edit changes only the selected note", () => {
  const result = editNote(notes, "garden.md", "Changed.", true);
  assert.equal(result.applied, true);
  assert.equal(result.notes.find((note) => note.path === "garden.md").body, "Changed.");
  assert.equal(result.notes.find((note) => note.path === "trading.md").body, notes[0].body);
});
