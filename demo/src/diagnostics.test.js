import assert from "node:assert/strict";
import test from "node:test";

import { buildDiagnostics, highlightColor } from "./diagnostics.js";
import { readFile } from "node:fs/promises";
import { toApiModel, toEditorModel } from "./apollon-model.js";

test("maps reference and candidate problems to clickable diagnostics", () => {
  const diagnostics = buildDiagnostics({
    matching: {
      missing_nodes: ["r-node"],
      redundant_nodes: ["c-extra"],
      redundant_relations: ["c-relation"],
    },
    evaluation: {
      syntactic: {
        nodes: [{ uid: "c-node", checks: { named: false, connected: true } }],
        relations: [],
      },
      pragmatic: { nodes: [{ uid: "c-node", score: 2 }] },
    },
  });

  assert.deepEqual(
    diagnostics.map(({ side, id, severity }) => ({ side, id, severity })),
    [
      { side: "reference", id: "r-node", severity: "error" },
      { side: "candidate", id: "c-extra", severity: "warning" },
      { side: "candidate", id: "c-relation", severity: "warning" },
      { side: "candidate", id: "c-node", severity: "error" },
      { side: "candidate", id: "c-node", severity: "info" },
    ],
  );
  assert.equal(highlightColor(diagnostics[0]), "#dc2626");
  assert.equal(highlightColor(diagnostics[1]), "#f59e0b");
  assert.equal(highlightColor(diagnostics[2]), "#f59e0b");
  assert.equal(highlightColor(diagnostics[4]), null);
});

test("round-trips a v3 use-case system through the maintained editor model", async () => {
  const fixtureUrl = new URL(
    "../../datasets/23_exercises/exercise_1/exercise_1.json",
    import.meta.url,
  );
  const fixture = JSON.parse(await readFile(fixtureUrl, "utf8"));
  const model = toApiModel(toEditorModel(fixture.model));

  assert.equal(Object.keys(model.elements).length, 7);
  assert.equal(Object.keys(model.relationships).length, 4);
  assert.equal(
    model.elements["afbcda63-60f7-44a8-b886-6e51a8f06870"].type,
    "UseCaseSystem",
  );
  assert.deepEqual(
    model.elements["d9e4893d-eae5-4ebe-bcc3-ebd97068f846"].bounds,
    { x: -100, y: -200, width: 180, height: 100 },
  );
});

test("gives a node and relation with the same API id distinct editor ids", () => {
  const source = {
    version: "3.0.0",
    type: "UseCaseDiagram",
    size: { width: 400, height: 300 },
    interactive: { elements: {}, relationships: {} },
    elements: {
      shared: {
        id: "shared",
        name: "Actor",
        type: "UseCaseActor",
        owner: null,
        bounds: { x: 0, y: 0, width: 80, height: 140 },
      },
    },
    relationships: {
      shared: {
        id: "shared",
        name: "",
        type: "UseCaseAssociation",
        owner: null,
        bounds: { x: 0, y: 0, width: 10, height: 10 },
        path: [{ x: 0, y: 0 }, { x: 10, y: 10 }],
        source: { direction: "Right", element: "shared" },
        target: { direction: "Left", element: "shared" },
      },
    },
    assessments: {},
  };

  const editorModel = toEditorModel(source);
  assert.notEqual(editorModel.nodes[0].id, editorModel.edges[0].id);
  const apiModel = toApiModel(editorModel);
  assert.equal(apiModel.elements.shared.id, "shared");
  assert.equal(apiModel.relationships.shared.id, "shared");
});
