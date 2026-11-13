/** Local vault search. Nothing here opens a network socket or a public port. */

export function searchNotes(notes, query) {
  const needle = String(query ?? "").trim().toLowerCase();
  if (!needle) {
    return [];
  }
  return notes
    .filter((note) => {
      const title = String(note.title ?? "").toLowerCase();
      const body = String(note.body ?? "").toLowerCase();
      return title.includes(needle) || body.includes(needle);
    })
    .map((note) => ({ path: note.path, title: note.title }));
}

export function editNote(notes, path, nextBody, confirmed) {
  const current = notes.find((note) => note.path === path);
  if (!current) {
    return { applied: false, reason: "missing_note", notes };
  }
  if (!confirmed) {
    return { applied: false, reason: "confirmation_required", notes };
  }
  const updated = notes.map((note) =>
    note.path === path ? { ...note, body: nextBody } : note,
  );
  return { applied: true, reason: "confirmed", notes: updated };
}
