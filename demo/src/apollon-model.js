import { importDiagram } from "@tumaet/apollon/model";

const NODE_TYPES = {
  useCase: "UseCase",
  useCaseActor: "UseCaseActor",
  useCaseSystem: "UseCaseSystem",
};

const DIRECTIONS = {
  top: "Up",
  right: "Right",
  bottom: "Down",
  left: "Left",
  "right-top": "Upright",
  "left-top": "Upleft",
  "right-bottom": "Downright",
  "left-bottom": "Downleft",
  "top-right": "RightTop",
  "top-left": "LeftTop",
  "bottom-right": "RightBottom",
  "bottom-left": "LeftBottom",
};

export const emptyV3Model = () => ({
  version: "3.0.0",
  type: "UseCaseDiagram",
  size: { width: 1200, height: 700 },
  interactive: { elements: {}, relationships: {} },
  elements: {},
  relationships: {},
  assessments: {},
});

export function toEditorModel(value) {
  const model = value?.model ?? value;
  if (!model || typeof model !== "object")
    throw new Error("The file is not an Apollon model.");
  try {
    const imported = importDiagram(model);
    return {
      ...imported,
      edges: imported.edges.map((edge) => {
        const apiId = edge.data?.apiId ?? edge.id;
        return {
          ...edge,
          id: `relation:${apiId}`,
          data: { ...edge.data, apiId },
        };
      }),
    };
  } catch {
    throw new Error("The file is not a supported Apollon v3/v4 model.");
  }
}

function absolutePosition(node, nodesById, seen = new Set()) {
  if (!node.parentId || seen.has(node.id)) return node.position;
  const parent = nodesById[node.parentId];
  if (!parent) return node.position;
  const parentPosition = absolutePosition(parent, nodesById, new Set([...seen, node.id]));
  return {
    x: node.position.x + parentPosition.x,
    y: node.position.y + parentPosition.y,
  };
}

function nodeBounds(node, nodesById) {
  const position = absolutePosition(node, nodesById);
  return {
    ...position,
    width: node.width ?? node.measured?.width ?? 100,
    height: node.height ?? node.measured?.height ?? 60,
  };
}

function edgeGeometry(edge, nodesById) {
  let points = edge.data?.points ?? [];
  if (points.length < 2) {
    const source = nodeBounds(nodesById[edge.source], nodesById);
    const target = nodeBounds(nodesById[edge.target], nodesById);
    points = [
      { x: source.x + source.width / 2, y: source.y + source.height / 2 },
      { x: target.x + target.width / 2, y: target.y + target.height / 2 },
    ];
  }
  const xs = points.map(({ x }) => x);
  const ys = points.map(({ y }) => y);
  const bounds = {
    x: Math.min(...xs),
    y: Math.min(...ys),
    width: Math.max(...xs) - Math.min(...xs),
    height: Math.max(...ys) - Math.min(...ys),
  };
  return {
    bounds,
    path: points.map(({ x, y }) => ({ x: x - bounds.x, y: y - bounds.y })),
  };
}

export function toApiModel(model) {
  const nodesById = Object.fromEntries(model.nodes.map((node) => [node.id, node]));
  const elements = Object.fromEntries(model.nodes.map((node) => {
    const type = NODE_TYPES[node.type];
    if (!type) throw new Error(`Unsupported Use Case node type: ${node.type}`);
    return [node.id, {
      id: node.id,
      name: String(node.data?.name ?? ""),
      type,
      owner: node.parentId ?? null,
      bounds: nodeBounds(node, nodesById),
    }];
  }));
  const relationships = Object.fromEntries(model.edges.map((edge) => {
    const apiId = edge.data?.apiId ?? edge.id;
    const geometry = edgeGeometry(edge, nodesById);
    return [apiId, {
      id: apiId,
      name: String(edge.data?.label ?? ""),
      type: edge.type,
      owner: null,
      ...geometry,
      source: {
        direction: DIRECTIONS[edge.sourceHandle] ?? edge.sourceHandle,
        element: edge.source,
      },
      target: {
        direction: DIRECTIONS[edge.targetHandle] ?? edge.targetHandle,
        element: edge.target,
      },
      isManuallyLayouted: Boolean(edge.data?.isManuallyLayouted),
    }];
  }));
  return {
    ...emptyV3Model(),
    size: {
      width: Math.max(1200, ...Object.values(elements).map(({ bounds }) => bounds.x + bounds.width)),
      height: Math.max(700, ...Object.values(elements).map(({ bounds }) => bounds.y + bounds.height)),
    },
    interactive: model.interactive ?? { elements: {}, relationships: {} },
    elements,
    relationships,
    assessments: model.assessments ?? {},
  };
}
