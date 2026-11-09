# Agent communication, Phase 5 report

Shipped: chat panel, conversation monitor with replay, follow mode, speech scheduler, SkyFloor props (speech, gather, follow, onAvatar), bottom-sheet layout, feed from stored messages, doc `docs/agent-communication/phase-5-sanctum-ui.md`.

Preserved: the sky floor, desks, avatars, nameplates, wandering, camera presets and controls, boardroom button, zones, footer. `sanctum.css` was not changed by this work.

Changed on purpose: the canned bubbles and the scripted feed lines were removed. `SanctumPage.test.tsx` asserted those scripted lines; the assertion was replaced with one that checks they are gone and that a stored message appears. No other existing assertion was changed.

Visual check: made once in a browser against a scratch database (chat panel, bubble with origin tag, activity feed). The discussion walk and replay were checked in jsdom only; the browser tool kept routing clicks to the user's own tab, so that check was stopped.

Not done: command palette, activity timeline, decision inspector, an in-browser run of every desk.
