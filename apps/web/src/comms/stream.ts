export type SseEvent = { event: string; data: string };

/** Pull complete SSE blocks out of a growing buffer. Incomplete bytes stay in `rest`. */
export function takeEvents(buffer: string): { rest: string; events: SseEvent[] } {
  const events: SseEvent[] = [];
  let rest = buffer.replace(/\r\n/g, "\n");
  while (true) {
    const split = rest.indexOf("\n\n");
    if (split < 0) {
      break;
    }
    const block = rest.slice(0, split);
    rest = rest.slice(split + 2);
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        data.push(line.slice(5).trim());
      }
    }
    if (data.length > 0) {
      events.push({ event, data: data.join("\n") });
    }
  }
  return { rest, events };
}
