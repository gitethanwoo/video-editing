// Capture a page's CDP screencast frames to disk, with timestamps. No live encoding.
//
// Usage: node screencast.mjs <browser-ws-url> <out-dir> [url-substring]
//   browser-ws-url  from `agent-browser --session <name> get cdp-url`
//   url-substring   picks the page to record (default: first page that is not chrome://)
// Stop with SIGINT. Writes <out-dir>/f000000.jpg..., <out-dir>/frames.json ([{file, t}] in
// epoch seconds) and <out-dir>/started once frames are flowing. Encode with frames_to_mp4.py.
//
// Chrome sends a frame only when the page repaints, so a still page produces no frames.
// Frame durations must come from the timestamps, not from a fixed rate.
import fs from "node:fs";
import path from "node:path";

const [wsUrl, outDir, match] = process.argv.slice(2);
if (!wsUrl || !outDir) {
  console.error("usage: node screencast.mjs <browser-ws-url> <out-dir> [url-substring]");
  process.exit(2);
}
fs.mkdirSync(outDir, { recursive: true });
const ws = new WebSocket(wsUrl);
let id = 0;
const pending = new Map();
const send = (method, params = {}, sessionId) =>
  new Promise((resolve, reject) => {
    const msgId = ++id;
    pending.set(msgId, { resolve, reject });
    ws.send(JSON.stringify({ id: msgId, method, params, sessionId }));
  });

const frames = [];
let sessionId;
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const p = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? p.reject(new Error(JSON.stringify(msg.error))) : p.resolve(msg.result);
    return;
  }
  if (msg.method === "Page.screencastFrame") {
    const { data, metadata, sessionId: frameSession } = msg.params;
    const file = `f${String(frames.length).padStart(6, "0")}.jpg`;
    fs.writeFileSync(path.join(outDir, file), Buffer.from(data, "base64"));
    frames.push({ file, t: metadata.timestamp });
    send("Page.screencastFrameAck", { sessionId: frameSession }, sessionId).catch(() => {});
  }
};

ws.onopen = async () => {
  const { targetInfos } = await send("Target.getTargets");
  const pages = targetInfos.filter((t) => t.type === "page");
  console.error("pages:", pages.map((p) => p.url));
  const target = match
    ? pages.find((p) => p.url.includes(match))
    : pages.find((p) => !p.url.startsWith("chrome://"));
  if (!target) {
    console.error(`no page matches ${JSON.stringify(match ?? "non-chrome page")}`);
    process.exit(1);
  }
  ({ sessionId } = await send("Target.attachToTarget", { targetId: target.targetId, flatten: true }));
  await send("Page.enable", {}, sessionId);
  await send("Page.startScreencast", { format: "jpeg", quality: 92, everyNthFrame: 1 }, sessionId);
  console.error("recording", target.url);
  fs.writeFileSync(path.join(outDir, "started"), String(Date.now() / 1000));
};

process.on("SIGINT", async () => {
  try {
    await send("Page.stopScreencast", {}, sessionId);
  } catch {}
  fs.writeFileSync(path.join(outDir, "frames.json"), JSON.stringify(frames));
  console.error("frames:", frames.length);
  process.exit(0);
});
