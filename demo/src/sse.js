function parseEvent(block) {
  let event = "message";
  const data = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return null;
  return { event, payload: JSON.parse(data.join("\n")) };
}

export async function readAssessmentStream(response, onProgress) {
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.error_message ?? `Request failed (${response.status})`);
  }
  if (!response.body) throw new Error("The assessment stream is unavailable.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    buffer = (buffer + decoder.decode(value, { stream: !done })).replaceAll("\r\n", "\n");
    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      if (!block.trim()) continue;
      const parsed = parseEvent(block);
      if (!parsed) continue;
      const { event, payload } = parsed;
      if (event === "progress") onProgress(payload.state);
      if (event === "result") return payload.data;
      if (event === "error") throw new Error(payload.error_message ?? "Assessment failed.");
    }
    if (done) break;
  }
  throw new Error("The assessment stream ended without a result.");
}
