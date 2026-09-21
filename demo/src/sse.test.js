import assert from "node:assert/strict";
import test from "node:test";

import { readAssessmentStream } from "./sse.js";

function responseFrom(chunks) {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  }));
}

test("reads split progress events and the final assessment", async () => {
  const states = [];
  const response = responseFrom([
    'event: progress\r\ndata: {"state":"extracting"}\r',
    '\n\r',
    '\nevent: progress\ndata: {"state":"analyzing"}\n\n',
    'event: result\ndata: {"state":"completed","data":{"uid":"a-1"}}\n\n',
  ]);

  const result = await readAssessmentStream(response, (state) => states.push(state));
  assert.deepEqual(states, ["extracting", "analyzing"]);
  assert.deepEqual(result, { uid: "a-1" });
});

test("surfaces an SSE assessment error", async () => {
  const response = responseFrom([
    'event: error\ndata: {"error_message":"Assessment failed"}\n\n',
  ]);
  await assert.rejects(
    readAssessmentStream(response, () => {}),
    /Assessment failed/,
  );
});

test("ignores SSE heartbeat comments", async () => {
  const response = responseFrom([
    ': ping - 2026-09-21T00:00:00Z\n\n',
    'event: result\ndata: {"state":"completed","data":{"uid":"a-2"}}\n\n',
  ]);

  assert.deepEqual(
    await readAssessmentStream(response, () => {}),
    { uid: "a-2" },
  );
});
