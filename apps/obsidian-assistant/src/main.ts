import { Modal, Notice, Plugin, TFile, type App } from "obsidian";

import {
  answerFromNotes,
  applyMutation,
  searchSelected,
  type Confirmation,
  type Mutation,
  type NoteReader,
  type NoteWriter,
} from "./core";

interface LocalData {
  selectedPaths: string[];
}

/**
 * Desktop plugin. It reads pinned notes through the Obsidian vault API and
 * asks before create, edit, or trash. It does not start a server.
 */
export default class VeytrixObsidianAssistant extends Plugin {
  async onload(): Promise<void> {
    this.addCommand({
      id: "pin-active-note",
      name: "Pin the active note for answers",
      callback: () => void this.pinActive(),
    });
    this.addCommand({
      id: "answer-from-pinned-notes",
      name: "Answer from pinned notes",
      callback: () => this.askQuery(),
    });
    this.addCommand({
      id: "create-note",
      name: "Create a note (asks first)",
      callback: () => this.askCreate(),
    });
    this.addCommand({
      id: "edit-active-note",
      name: "Replace the active note (asks first)",
      callback: () => this.askEdit(),
    });
    this.addCommand({
      id: "trash-active-note",
      name: "Move the active note to trash (asks first)",
      callback: () => void this.askTrash(),
    });
  }

  private reader(): NoteReader {
    return {
      read: async (path: string) => {
        const file = this.app.vault.getAbstractFileByPath(path);
        if (!(file instanceof TFile)) return null;
        return this.app.vault.read(file);
      },
    };
  }

  private writer(): NoteWriter {
    return {
      create: (path, body) => this.app.vault.create(path, body),
      modify: async (path, body) => {
        const file = this.app.vault.getAbstractFileByPath(path);
        if (!(file instanceof TFile)) throw new Error("missing");
        await this.app.vault.modify(file, body);
      },
      trash: async (path) => {
        const file = this.app.vault.getAbstractFileByPath(path);
        if (!(file instanceof TFile)) throw new Error("missing");
        await this.app.vault.trash(file, false);
      },
    };
  }

  private async selectedPaths(): Promise<string[]> {
    const data = (await this.loadData()) as LocalData | null;
    return Array.isArray(data?.selectedPaths) ? data.selectedPaths : [];
  }

  private async pinActive(): Promise<void> {
    const file = this.app.workspace.getActiveFile();
    if (!(file instanceof TFile)) {
      new Notice("Open a note before pinning it.");
      return;
    }
    const selected = await this.selectedPaths();
    if (!selected.includes(file.path)) selected.push(file.path);
    await this.saveData({ selectedPaths: selected });
    new Notice(`Pinned ${file.path}. Answers read pinned notes only.`);
  }

  private askQuery(): void {
    const modal = new QueryModal(this.app, (query) => void this.answer(query));
    modal.open();
  }

  private async answer(query: string): Promise<void> {
    const selected = await this.selectedPaths();
    if (selected.length === 0) {
      new Notice("Pin a note first. The whole vault is not read.");
      return;
    }
    const searched = await searchSelected(this.reader(), selected);
    const answer = answerFromNotes(query, searched.notes);
    new Notice(answer.text);
  }

  private askCreate(): void {
    const modal = new CreateModal(this.app, (path, body) => {
      void this.confirm(
        `Create ${path}?`,
        { action: "create", path, body },
        { confirmed: true, action: "create", path },
      );
    });
    modal.open();
  }

  private askEdit(): void {
    const file = this.app.workspace.getActiveFile();
    if (!(file instanceof TFile)) {
      new Notice("Open the note you want to replace.");
      return;
    }
    const path = file.path;
    const modal = new BodyModal(this.app, (body) => {
      void this.confirm(
        `Replace ${path}?`,
        { action: "edit", path, body },
        { confirmed: true, action: "edit", path },
      );
    });
    modal.open();
  }

  private async askTrash(): Promise<void> {
    const file = this.app.workspace.getActiveFile();
    if (!(file instanceof TFile)) {
      new Notice("Open the note you want to trash.");
      return;
    }
    const path = file.path;
    await this.confirm(
      `Move ${path} to the vault trash?`,
      { action: "delete", path },
      { confirmed: true, action: "delete", path },
    );
  }

  private async confirm(message: string, mutation: Mutation, confirmation: Confirmation): Promise<void> {
    const modal = new ConfirmModal(this.app, message, () => {
      void applyMutation(this.writer(), mutation, confirmation).then((result) => {
        new Notice(result.applied ? result.reason : "No change was made.");
      });
    });
    modal.open();
  }
}

class ConfirmModal extends Modal {
  private readonly message: string;
  private readonly onYes: () => void;

  constructor(app: App, message: string, onYes: () => void) {
    super(app);
    this.message = message;
    this.onYes = onYes;
  }

  onOpen(): void {
    this.contentEl.createEl("p", { text: this.message });
    const yes = this.contentEl.createEl("button", { text: "Confirm" });
    const no = this.contentEl.createEl("button", { text: "Cancel" });
    yes.addEventListener("click", () => {
      this.onYes();
      this.close();
    });
    no.addEventListener("click", () => this.close());
  }

  onClose(): void {
    this.contentEl.empty();
  }
}

class QueryModal extends Modal {
  private readonly onSubmit: (query: string) => void;

  constructor(app: App, onSubmit: (query: string) => void) {
    super(app);
    this.onSubmit = onSubmit;
  }

  onOpen(): void {
    const input = this.contentEl.createEl("input", { type: "text" });
    input.placeholder = "Search pinned notes";
    const yes = this.contentEl.createEl("button", { text: "Search" });
    yes.addEventListener("click", () => {
      const query = input.value;
      this.close();
      this.onSubmit(query);
    });
  }

  onClose(): void {
    this.contentEl.empty();
  }
}

class CreateModal extends Modal {
  private readonly onSubmit: (path: string, body: string) => void;

  constructor(app: App, onSubmit: (path: string, body: string) => void) {
    super(app);
    this.onSubmit = onSubmit;
  }

  onOpen(): void {
    const path = this.contentEl.createEl("input", { type: "text" });
    path.placeholder = "folder/note.md";
    const body = this.contentEl.createEl("textarea");
    const yes = this.contentEl.createEl("button", { text: "Continue" });
    yes.addEventListener("click", () => {
      this.close();
      this.onSubmit(path.value, body.value);
    });
  }

  onClose(): void {
    this.contentEl.empty();
  }
}

class BodyModal extends Modal {
  private readonly onSubmit: (body: string) => void;

  constructor(app: App, onSubmit: (body: string) => void) {
    super(app);
    this.onSubmit = onSubmit;
  }

  onOpen(): void {
    const body = this.contentEl.createEl("textarea");
    const yes = this.contentEl.createEl("button", { text: "Continue" });
    yes.addEventListener("click", () => {
      this.close();
      this.onSubmit(body.value);
    });
  }

  onClose(): void {
    this.contentEl.empty();
  }
}
