import { describe, expect, it } from "vitest";
import { takeEvents } from "./stream";

describe("sse buffer", () => {
  it("emits a chunk before the stream has finished", () => {
    const first = takeEvents('event: chunk\ndata: {"text":"Hi"}\n\n');
    expect(first.events.map((item) => item.event)).toEqual(["chunk"]);
    expect(first.rest).toBe("");
    const second = takeEvents(`${first.rest}event: done\ndata: {"ok":true}\n\n`);
    expect(second.events.map((item) => item.event)).toEqual(["done"]);
  });
});
