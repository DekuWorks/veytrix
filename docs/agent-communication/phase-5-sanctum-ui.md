# Phase 5: Sanctum visualisation

Files: `comms/*.ts(x)`, `sanctum/ui/ChatThread.tsx`, `ChatPanel.tsx`, `ConversationMonitor.tsx`, `comms.css`, `SkyFloor.tsx` (props), `SanctumPage.tsx`.

- A bubble is a stored agent message, cut to 150 characters, with its origin tag. Nothing is generated in the browser. Clicking an avatar opens its chat and shows its newest stored message, or says it has none.
- Messages from the API (reply, feed, doorbell) enter a `SpeechScheduler`. Direct replies speak at once. A discussion first walks its members to the boardroom (4 seconds), then speaks in stored order (one speaker every 3.5 seconds), then sends them home. Reduced motion jumps instead of walking.
- Chat panel: transcript with `role="log"`, sources per message, origin and kind tags, typing state, quick questions, retry, Ctrl+Enter, focus on open. Below 760 px it becomes a bottom sheet.
- Conversations rail: a drawer over the floor with search, archive filter, pin, unread badges, start discussion, convene boardroom, open the All desks room, pause, resume, close, replay (play, pause, step, restart, 3x) which makes avatars speak the stored rows tagged as replay.
- Follow on floor centres the camera on a desk.
- The scripted feed lines were removed. The feed shows stored messages, or says none exist.
- Realtime: the page says whether Supabase Realtime is not configured, connected, or polling.

21st.dev: see the completion report.
