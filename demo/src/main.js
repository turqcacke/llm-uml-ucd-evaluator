import {
  ApollonEditor,
  UMLDiagramType,
} from "@tumaet/apollon";

import { emptyV3Model, toApiModel, toEditorModel } from "./apollon-model.js";
import { buildDiagnostics, highlightColor } from "./diagnostics.js";
import { readAssessmentStream } from "./sse.js";
import "@tumaet/apollon/style.css";
import "./style.css";

const API_KEY = import.meta.env.VITE_API_KEY;

const METRICS = [
  ["Completeness", "completeness_rate", "rate"],
  ["Semantic precision", "semantic_precision", "rate"],
  ["Semantic F1", "semantic_f1_score", "rate"],
  ["Redundancy", "redundancy_rate", "rate"],
  ["Syntactic error rate", "syntactic_error_rate", "rate"],
  ["Naming understandability", "naming_understandability_score", "score"],
  ["Reference complexity", "reference_complexity", "number"],
  ["Candidate complexity", "candidate_complexity", "number"],
  ["Complexity difference", "complexity_difference", "number"],
  ["Complexity deviation", "complexity_deviation_rate", "rate"],
];

const escapeHtml = (value) =>
  String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[character]);

const state = {
  description: "",
  candidateSkipped: true,
  result: null,
  diagnostics: [],
  hasReference: false,
  activeInput: "description",
  activeResult: "metrics",
};

document.querySelector("#app").innerHTML = `
  <header class="topbar">
    <div>
      <span class="eyebrow">LLM UML Evaluator</span>
      <h1>Diagram assessment</h1>
    </div>
    <span id="api-status" class="status ${API_KEY ? "ready" : "error"}">
      ${API_KEY ? "API configured" : "VITE_API_KEY missing"}
    </span>
  </header>

  <section class="card setup">
    <div class="tabs" role="tablist" aria-label="Assessment input">
      <button class="tab active" data-input-tab="description">1. Description</button>
      <button class="tab" data-input-tab="candidate">2. Candidate <span class="optional">optional</span></button>
      <button class="tab" data-input-tab="reference">3. Reference <span class="optional">optional</span></button>
    </div>

    <div class="input-panel" data-input-panel="description">
      <label class="dropzone">
        <strong>Choose description file</strong>
        <span>Plain text, 100–5000 non-whitespace characters</span>
        <input id="description-file" type="file" accept=".txt,.md,text/plain,text/markdown" />
      </label>
      <textarea id="description" rows="7" placeholder="Or paste the context description here"></textarea>
      <small id="description-count">0 non-whitespace characters</small>
    </div>

    <div class="input-panel hidden" data-input-panel="candidate">
      <label class="dropzone">
        <strong>Choose Apollon JSON</strong>
        <span>Full export or a raw v3 model</span>
        <input id="candidate-file" type="file" accept=".json,application/json" />
      </label>
      <div class="inline-note">
        <span id="candidate-state">No file selected — an empty candidate will be used.</span>
        <button id="skip-candidate" class="secondary" type="button">Use empty candidate</button>
      </div>
    </div>

    <div class="input-panel hidden" data-input-panel="reference">
      <label class="dropzone">
        <strong>Choose reference Apollon JSON</strong>
        <span>Optional. Without it, reference is generated from the description.</span>
        <input id="reference-file" type="file" accept=".json,application/json" />
      </label>
      <div class="inline-note">
        <span id="reference-state">No file selected — description will be used.</span>
        <button id="clear-reference" class="secondary" type="button">Generate from description instead</button>
      </div>
    </div>

    <div class="actions">
      <div class="activity">
        <p id="message" aria-live="polite"></p>
        <div id="progress" class="progress hidden" aria-label="Assessment progress">
          <div class="progress-track"><span id="progress-bar"></span></div>
          <div class="progress-steps">
            <span data-progress-step="extracting">Extracting</span>
            <span data-progress-step="analyzing">Analyzing</span>
            <span data-progress-step="saving">Saving</span>
            <span data-progress-step="completed">Completed</span>
          </div>
        </div>
      </div>
      <div class="action-buttons">
        <button id="regenerate" class="secondary hidden" type="button">Regenerate from description</button>
        <button id="assess" class="primary" type="button">Generate & assess</button>
      </div>
    </div>
  </section>

  <section class="workspace card">
    <div class="section-heading">
      <div>
        <span class="eyebrow">Workspace</span>
        <h2>Candidate and reference</h2>
      </div>
    </div>
    <div class="diagram-grid">
      <section class="diagram-pane">
        <h3>Candidate</h3>
        <div id="candidate-editor" class="editor"></div>
      </section>
      <section class="diagram-pane">
        <h3>Reference</h3>
        <div id="reference-editor" class="editor"></div>
      </section>
    </div>
  </section>

  <section class="results card">
    <div class="section-heading">
      <div>
        <span class="eyebrow">Assessment</span>
        <h2>Results</h2>
      </div>
      <span id="assessment-id" class="muted">Run an assessment to see results</span>
    </div>
    <div class="tabs compact" role="tablist" aria-label="Assessment results">
      <button class="tab active" data-result-tab="metrics">Metrics</button>
      <button class="tab" data-result-tab="errors">Errors <span id="error-count" class="badge">0</span></button>
      <button class="tab" data-result-tab="matches">Matches</button>
    </div>
    <div id="metrics" class="result-panel empty-state">No assessment yet.</div>
    <div id="errors" class="result-panel hidden empty-state">No assessment yet.</div>
    <div id="matches" class="result-panel hidden empty-state">No assessment yet.</div>
  </section>
`;

const candidateEditor = new ApollonEditor(
  document.querySelector("#candidate-editor"),
  { type: UMLDiagramType.UseCaseDiagram, model: toEditorModel(emptyV3Model()) },
);
const referenceEditor = new ApollonEditor(
  document.querySelector("#reference-editor"),
  { type: UMLDiagramType.UseCaseDiagram, model: toEditorModel(emptyV3Model()) },
);

function normalizeModel(value) {
  return toEditorModel(value);
}

function modelForApi(editor) {
  return toApiModel(editor.model);
}

async function api(path, body) {
  if (!API_KEY) throw new Error("Set VITE_API_KEY in demo/.env and restart Vite.");
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok || !payload?.ok)
    throw new Error(payload?.error_message ?? `Request failed (${response.status})`);
  return payload.data;
}

async function streamAssessment(body, onProgress) {
  if (!API_KEY) throw new Error("Set VITE_API_KEY in demo/.env and restart Vite.");
  const response = await fetch("/api/v1/assessments/streams", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
    body: JSON.stringify(body),
  });
  return readAssessmentStream(response, onProgress);
}

async function readFile(input, asJson = false) {
  const file = input.files?.[0];
  if (!file) return null;
  const text = await file.text();
  return asJson ? JSON.parse(text) : text;
}

function setMessage(message, kind = "") {
  const element = document.querySelector("#message");
  element.textContent = message;
  element.className = kind;
}

const PROGRESS_STAGES = ["extracting", "analyzing", "saving", "completed"];

function setProgress(stateName) {
  const progress = document.querySelector("#progress");
  progress.classList.remove("hidden", "failed");
  const index = PROGRESS_STAGES.indexOf(stateName);
  document.querySelector("#progress-bar").style.width = `${Math.max(5, ((index + 1) / PROGRESS_STAGES.length) * 100)}%`;
  document.querySelectorAll("[data-progress-step]").forEach((step, stepIndex) => {
    step.classList.toggle("done", stepIndex < index);
    step.classList.toggle("current", stepIndex === index);
  });
}

function failProgress() {
  document.querySelector("#progress").classList.add("failed");
}

function updateAssessmentButton() {
  document.querySelector("#assess").textContent = !state.hasReference
    ? "Generate & assess"
    : state.result
      ? "Re-assess Apollon → Apollon"
      : "Assess Apollon → Apollon";
}

function setTab(group, name) {
  document.querySelectorAll(`[data-${group}-tab]`).forEach((button) =>
    button.classList.toggle("active", button.dataset[`${group}Tab`] === name),
  );
  document.querySelectorAll(`[data-${group}-panel]`).forEach((panel) =>
    panel.classList.toggle("hidden", panel.dataset[`${group}Panel`] !== name),
  );
}

function selectElement(side, kind, id) {
  const editor = side === "reference" ? referenceEditor : candidateEditor;
  editor.revealAssessment(editorIdFor(editor, kind, id));
}

function editorIdFor(editor, kind, apiId) {
  if (kind === "node") return apiId;
  return editor.model.edges.find(
    (edge) => (edge.data?.apiId ?? edge.id) === apiId,
  )?.id ?? apiId;
}

function applyHighlights() {
  for (const [side, editor] of [
    ["candidate", candidateEditor],
    ["reference", referenceEditor],
  ]) {
    const highlights = Object.fromEntries(
      state.diagnostics
        .filter((item) => item.side === side && highlightColor(item))
        .map((item) => [editorIdFor(editor, item.kind, item.id), highlightColor(item)]),
    );
    editor.setElementHighlights(highlights);
  }
}

function formatMetric(value, type) {
  if (value === "Infinity") return "∞";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value ?? "—");
  if (type === "rate") return `${(number * 100).toFixed(1)}%`;
  if (type === "score") return `${number.toFixed(2)} / 3`;
  return number.toFixed(Number.isInteger(number) ? 0 : 2);
}

function elementName(side, kind, id) {
  const model = side === "reference" ? referenceEditor.model : candidateEditor.model;
  const element = kind === "node"
    ? model.nodes.find((node) => node.id === id)
    : model.edges.find((edge) => (edge.data?.apiId ?? edge.id) === id);
  const name = kind === "node" ? element?.data?.name : element?.data?.label;
  return String(name ?? "").trim() || id;
}

function renderResults() {
  const result = state.result;
  document.querySelector("#assessment-id").textContent = result ? `Assessment ${result.uid}` : "No assessment";
  document.querySelector("#error-count").textContent = state.diagnostics.length;

  if (!result?.candidate_is_allowed) {
    document.querySelector("#metrics").innerHTML = `<div class="notice">Reference generated. Add a Candidate Diagram to calculate meaningful metrics.</div>`;
  } else {
    document.querySelector("#metrics").innerHTML = `<div class="metric-grid">${METRICS.map(
      ([label, key, type]) => `<article class="metric"><span>${label}</span><strong>${formatMetric(result[key], type)}</strong></article>`,
    ).join("")}</div>`;
  }

  document.querySelector("#errors").innerHTML = state.diagnostics.length
    ? `<div class="list">${state.diagnostics.map((item, index) => `
        <button class="list-item ${item.severity}" data-diagnostic="${index}">
          <span class="severity ${item.severity}"></span>
          <span><strong>${escapeHtml(item.message)}</strong><small>${item.side} · ${item.kind} · ${escapeHtml(elementName(item.side, item.kind, item.id))}</small></span>
        </button>`).join("")}</div>`
    : `<div class="notice success">No element-level errors found.</div>`;

  const matching = result?.matching;
  const rows = [
    ...(matching?.node_matches ?? []).map((match) => ({ kind: "node", ...match })),
    ...(matching?.relation_matches ?? []).map((match) => ({ kind: "relation", ...match })),
  ];
  document.querySelector("#matches").innerHTML = rows.length
    ? `<div class="list">${rows.map((row, index) => `
        <div class="match-row">
          <span>${row.kind}</span>
          <button data-match="${index}" data-side="reference">${escapeHtml(elementName("reference", row.kind, row.reference_uid))}</button>
          <span>↔</span>
          <button data-match="${index}" data-side="candidate">${escapeHtml(elementName("candidate", row.kind, row.candidate_uid))}</button>
        </div>`).join("")}</div>`
    : `<div class="notice">No semantic matches available.</div>`;

  document.querySelectorAll("[data-diagnostic]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = state.diagnostics[Number(button.dataset.diagnostic)];
      selectElement(item.side, item.kind, item.id);
    });
  });
  document.querySelectorAll("[data-match]").forEach((button) => {
    button.addEventListener("click", () => {
      const row = rows[Number(button.dataset.match)];
      const side = button.dataset.side;
      selectElement(side, row.kind, row[`${side}_uid`]);
    });
  });
}

async function assess(mode) {
  const assessButton = document.querySelector("#assess");
  const regenerateButton = document.querySelector("#regenerate");
  const compactLength = state.description.replace(/\s/g, "").length;
  if (mode === "description" && (compactLength < 100 || compactLength > 5000)) {
    setMessage("Description must contain 100–5000 non-whitespace characters.", "error-text");
    return;
  }

  assessButton.disabled = true;
  regenerateButton.disabled = true;
  const activeButton = mode === "description" && state.result
    ? regenerateButton
    : assessButton;
  activeButton.textContent = mode === "description" ? "Regenerating…" : "Re-assessing…";
  setMessage(mode === "description"
    ? "The model is generating and evaluating a new reference…"
    : "The edited diagrams are being evaluated…");
  setProgress(null);
  try {
    const candidate = { model: modelForApi(candidateEditor) };
    const body = mode === "apollon"
      ? {
          type: "apollon",
          reference: { model: modelForApi(referenceEditor) },
          candidate,
          description: state.description || null,
        }
      : { type: "description", reference: state.description, candidate };
    const result = await streamAssessment(body, setProgress);
    if (mode === "description") {
      const layout = await api("/api/v1/converters/apollon", result.reference);
      referenceEditor.model = normalizeModel(layout);
      state.hasReference = true;
    }
    state.result = result;
    state.diagnostics = buildDiagnostics(result);
    regenerateButton.classList.remove("hidden");
    setProgress("completed");
    setMessage("Assessment completed.", "success-text");
    renderResults();
    requestAnimationFrame(applyHighlights);
  } catch (error) {
    failProgress();
    setMessage(error.message, "error-text");
  } finally {
    assessButton.disabled = false;
    regenerateButton.disabled = false;
    updateAssessmentButton();
    regenerateButton.textContent = "Regenerate from description";
  }
}

document.querySelectorAll("[data-input-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    state.activeInput = button.dataset.inputTab;
    setTab("input", state.activeInput);
  });
});
document.querySelectorAll("[data-result-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    state.activeResult = button.dataset.resultTab;
    document.querySelectorAll("[data-result-tab]").forEach((tab) =>
      tab.classList.toggle("active", tab.dataset.resultTab === state.activeResult),
    );
    document.querySelectorAll(".result-panel").forEach((panel) =>
      panel.classList.toggle("hidden", panel.id !== state.activeResult),
    );
  });
});

document.querySelector("#description").addEventListener("input", (event) => {
  state.description = event.target.value;
  document.querySelector("#description-count").textContent = `${state.description.replace(/\s/g, "").length} non-whitespace characters`;
});
document.querySelector("#description-file").addEventListener("change", async (event) => {
  try {
    const text = await readFile(event.target);
    if (text == null) return;
    state.description = text;
    document.querySelector("#description").value = text;
    document.querySelector("#description").dispatchEvent(new Event("input"));
    setMessage(`Loaded ${event.target.files[0].name}.`, "success-text");
  } catch (error) {
    setMessage(error.message, "error-text");
  }
});
document.querySelector("#candidate-file").addEventListener("change", async (event) => {
  try {
    const value = await readFile(event.target, true);
    if (value == null) return;
    candidateEditor.model = normalizeModel(value);
    state.candidateSkipped = false;
    document.querySelector("#candidate-state").textContent = `Loaded ${event.target.files[0].name}.`;
    setMessage("Candidate loaded.", "success-text");
  } catch (error) {
    setMessage(error.message, "error-text");
  }
});
document.querySelector("#reference-file").addEventListener("change", async (event) => {
  try {
    const value = await readFile(event.target, true);
    if (value == null) return;
    referenceEditor.model = normalizeModel(value);
    referenceEditor.setElementHighlights(null);
    state.hasReference = true;
    document.querySelector("#reference-state").textContent = `Loaded ${event.target.files[0].name}.`;
    updateAssessmentButton();
    setMessage("Reference loaded.", "success-text");
  } catch (error) {
    setMessage(error.message, "error-text");
  }
});
document.querySelector("#clear-reference").addEventListener("click", () => {
  referenceEditor.model = toEditorModel(emptyV3Model());
  referenceEditor.setElementHighlights(null);
  state.hasReference = false;
  document.querySelector("#reference-file").value = "";
  document.querySelector("#reference-state").textContent = "No file selected — description will be used.";
  updateAssessmentButton();
});
document.querySelector("#skip-candidate").addEventListener("click", () => {
  candidateEditor.model = toEditorModel(emptyV3Model());
  state.candidateSkipped = true;
  document.querySelector("#candidate-file").value = "";
  document.querySelector("#candidate-state").textContent = "Empty candidate selected.";
});
document.querySelector("#assess").addEventListener("click", () =>
  assess(state.hasReference ? "apollon" : "description"),
);
document.querySelector("#regenerate").addEventListener("click", () => assess("description"));
