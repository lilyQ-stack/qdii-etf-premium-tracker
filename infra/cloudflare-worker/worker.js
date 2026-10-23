/**
 * Optional external Cloudflare cron -> GitHub workflow_dispatch.
 * Put GITHUB_TOKEN in Worker secrets, never in git. Dispatch can itself queue.
 */
const WORKFLOWS = [
  "capture-1400.yml",
  "tencent-reference-capture.yml",
  "capture-crossmarket.yml",
];
const REPO = "lilyQ-stack/qdii-etf-premium-tracker";

function cstParts(date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", minute: "2-digit",
    hourCycle: "h23", weekday: "short"
  }).formatToParts(date);
  return Object.fromEntries(parts.map(p => [p.type, p.value]));
}

async function dispatch(env, workflow) {
  const url = "https://api.github.com/repos/" + REPO +
              "/actions/workflows/" + workflow + "/dispatches";
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: "Bearer " + env.GITHUB_TOKEN,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "qdii-etf-cron-dispatcher",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ref: "main"})
  });
  return {
    workflow, status: response.status, accepted: response.status === 204,
    error: response.ok ? null : (await response.text()).slice(0, 500)
  };
}
export default {
  async scheduled(event, env, ctx) {
    if (!env.GITHUB_TOKEN) {
      console.error("Missing GITHUB_TOKEN Worker secret");
      return;
    }
    const p = cstParts(new Date(event.scheduledTime));
    const weekday = ["Mon", "Tue", "Wed", "Thu", "Fri"].includes(p.weekday);
    if (!weekday || p.hour !== "14" ||
        !["04", "09", "14"].includes(p.minute)) {
      console.log(JSON.stringify({skipped: true, cst: p}));
      return;
    }
    const results = await Promise.all(WORKFLOWS.map(w => dispatch(env, w)));
    console.log(JSON.stringify({cst: p, results}));
    if (results.some(r => !r.accepted))
      console.error("GitHub workflow_dispatch failed for at least one target");
  }
};
