import { syncStatus } from "./catalogue.js";

export function updatePresentation(status) {
  const request = status?.request;
  const active = request && ["queued", "running"].includes(request.state);
  const offline = !status?.runner?.online;
  let label = "Run Update", message = "";
  if (active) {
    label = request.state === "running" ? "Running update" : "Update requested";
    message = offline ? "Discovery PC offline / awaiting runner. Your request is saved."
      : request.state === "queued" && status.runner.busy ? "Waiting for the current discovery run." : label;
  } else if (request?.state === "completed") {
    message = "Update completed";
  } else if (request?.state === "failed") {
    message = "Update failed. " + (request.error_code === "request_expired" ? "The discovery PC did not collect the request in time." : "Please try again; existing jobs remain available.");
  }
  if (request?.summary) {
    const s = request.summary;
    message += ` · ${s.new_jobs} new jobs · ${s.refreshed_jobs} existing jobs refreshed`;
    if (s.source_failures?.length) message += ` · Source checks incomplete: ${s.source_failures.join(", ")}`;
  }
  return { label, message, active: Boolean(active) };
}

export function createUpdateController({ api, onComplete, document, timers = globalThis }) {
  const button = document.getElementById("run-update");
  const output = document.getElementById("update-status");
  let timer, generation = 0, stopped = true, pendingKey, sending = false;
  const completed = new Set();
  function stop() { stopped = true; generation++; timers.clearTimeout(timer); button.disabled = true; output.textContent = ""; pendingKey = undefined; }
  async function poll() {
    const version = generation;
    let active = false;
    try {
      const status = await api("/update-status");
      if (stopped || version !== generation) return;
      if (!status || !("request" in status)) throw new Error("Update status unavailable.");
      const view = updatePresentation(status);
      // The authoritative queue confirms acceptance even if the POST reply was lost.
      if (view.active) pendingKey = undefined;
      active = view.active; button.textContent = view.label; button.disabled = active || sending;
      output.textContent = view.message;
      if (status.last_successful_update) document.getElementById("health").textContent = syncStatus(status.last_successful_update);
      if (["completed", "failed"].includes(status.request?.state) && status.request.summary && !completed.has(status.request.id)) {
        completed.add(status.request.id); await onComplete();
      }
    } catch (error) {
      if (stopped || version !== generation) return;
      button.disabled = true; output.textContent = error.message || "Update status unavailable.";
    } finally {
      if (!stopped && version === generation) timer = timers.setTimeout(poll, active ? 5000 : 30000);
    }
  }
  button.onclick = async () => {
    if (sending || button.disabled) return;
    const version = generation; sending = true; button.disabled = true;
    pendingKey ||= globalThis.crypto.randomUUID();
    try {
      await api("/update-requests", { method: "POST", body: JSON.stringify({ key: pendingKey }) });
      if (stopped || version !== generation) return;
      pendingKey = undefined;
    } catch (error) {
      if (!stopped && version === generation) output.textContent = error.message;
    } finally {
      sending = false;
      if (!stopped && version === generation) { timers.clearTimeout(timer); await poll(); }
    }
  };
  return { stop, start() { stopped = false; generation++; timers.clearTimeout(timer); poll(); } };
}
