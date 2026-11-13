import assert from "node:assert/strict";
import test from "node:test";

import {
  EXPOSES_PUBLIC_ENDPOINT,
  READS_WHOLE_VAULT,
  UPLOADS_VAULT,
  answerFromNotes,
  applyMutation,
  searchSelected,
  type NoteReader,
  type NoteWriter,
} from "./core.ts";

function memory(initial: Record<string, string>) {
  const notes = { ...initial };
  const reads: string[] = [];
  const writes: string[] = [];
  const reader: NoteReader = {
    async read(path: string) {
      reads.push(path);
      return Object.hasOwn(notes, path) ? notes[path] : null;
    },
  };
  const writer: NoteWriter = {
    async create(path: string, body: string) {
      writes.push(`create:${path}`);
      notes[path] = body;
    },
    async modify(path: string, body: string) {
      writes.push(`edit:${path}`);
      notes[path] = body;
    },
    async trash(path: string) {
      writes.push(`delete:${path}`);
      delete notes[path];
    },
  };
  return { notes, reads, writes, reader, writer };
}

test("search reads only the selected notes", async () => {
  const vault = memory({
    "picked.md": "The kiln needs a new shelf.",
    "other.md": "The kiln is also mentioned here.",
  });

  const searched = await searchSelected(vault.reader, ["picked.md"]);
  const answer = answerFromNotes("kiln", searched.notes);

  assert.deepEqual(searched.readPaths, ["picked.md"]);
  assert.deepEqual(vault.reads, ["picked.md"]);
  assert.equal(vault.writes.length, 0);
  assert.equal(answer.used.length, 1);
  assert.equal(answer.used[0].path, "picked.md");
  assert.ok(searched.notes[0].body.includes(answer.used[0].excerpt));
  assert.match(answer.text, /picked\.md/);
  assert.equal(READS_WHOLE_VAULT, false);
  assert.equal(EXPOSES_PUBLIC_ENDPOINT, false);
  assert.equal(UPLOADS_VAULT, false);
});

test("an empty selection reads nothing and the answer names no note", async () => {
  const vault = memory({ "picked.md": "The kiln needs a new shelf." });
  const searched = await searchSelected(vault.reader, []);
  const answer = answerFromNotes("kiln", searched.notes);

  assert.deepEqual(vault.reads, []);
  assert.deepEqual(answer.used, []);
  assert.match(answer.text, /No selected note/);
});

test("a query that misses the selected note does not invent an answer", async () => {
  const vault = memory({ "picked.md": "The kiln needs a new shelf." });
  const searched = await searchSelected(vault.reader, ["picked.md"]);
  const answer = answerFromNotes("copper", searched.notes);

  assert.deepEqual(answer.used, []);
  assert.match(answer.text, /No selected note/);
});

test("create, edit, and delete wait for a matching confirmation", async () => {
  const vault = memory({ "picked.md": "Old shelf note." });

  const unconfirmed = await applyMutation(
    vault.writer,
    { action: "create", path: "new.md", body: "Draft" },
    null,
  );
  const wrongAction = await applyMutation(
    vault.writer,
    { action: "edit", path: "picked.md", body: "Updated shelf note." },
    { confirmed: true, action: "create", path: "picked.md" },
  );
  const declined = await applyMutation(
    vault.writer,
    { action: "delete", path: "picked.md" },
    { confirmed: false, action: "delete", path: "picked.md" },
  );

  assert.equal(unconfirmed.applied, false);
  assert.equal(unconfirmed.reason, "confirmation_required");
  assert.equal(wrongAction.applied, false);
  assert.equal(declined.applied, false);
  assert.deepEqual(vault.writes, []);
  assert.equal(vault.notes["picked.md"], "Old shelf note.");

  const created = await applyMutation(
    vault.writer,
    { action: "create", path: "new.md", body: "Draft" },
    { confirmed: true, action: "create", path: "new.md" },
  );
  const edited = await applyMutation(
    vault.writer,
    { action: "edit", path: "picked.md", body: "Updated shelf note." },
    { confirmed: true, action: "edit", path: "picked.md" },
  );
  const removed = await applyMutation(
    vault.writer,
    { action: "delete", path: "picked.md" },
    { confirmed: true, action: "delete", path: "picked.md" },
  );

  assert.equal(created.applied, true);
  assert.equal(edited.applied, true);
  assert.equal(removed.reason, "trashed");
  assert.deepEqual(vault.writes, ["create:new.md", "edit:picked.md", "delete:picked.md"]);
  assert.equal(vault.notes["new.md"], "Draft");
  assert.equal(Object.hasOwn(vault.notes, "picked.md"), false);
});
