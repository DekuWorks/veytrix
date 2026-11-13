# Obsidian assistant

Local plugin for a throwaway vault. It is not part of the Veytrix trading API.

It searches notes you pin, quotes the matching text, and names the note path. Create, edit, and trash go through a confirm dialog, then `Vault.create`, `Vault.modify`, or `Vault.trash`. The plugin does not read every note body and does not open a network port.

Load it only in a vault you can afford to damage. Obsidian's own guide says not to develop plugins in your main vault.

```bash
node --experimental-strip-types --test src/core.test.ts
```

Copy this folder to `<vault>/.obsidian/plugins/veytrix-obsidian-assistant` after you compile `src/main.ts` to `main.js` with a bundler that marks `obsidian` as external. That compile step is not run by the trading checks.
