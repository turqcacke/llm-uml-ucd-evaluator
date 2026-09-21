const title = (value) => value.replaceAll("_", " ");

export function buildDiagnostics(result) {
  if (!result?.matching || !result?.evaluation) return [];

  const diagnostics = [];
  const add = (side, kind, id, severity, message) =>
    diagnostics.push({ side, kind, id, severity, message });

  for (const id of result.matching.missing_nodes ?? [])
    add("reference", "node", id, "error", "Missing node in candidate");
  for (const id of result.matching.missing_relations ?? [])
    add("reference", "relation", id, "error", "Missing relation in candidate");
  for (const id of result.matching.redundant_nodes ?? [])
    add("candidate", "node", id, "warning", "Redundant node");
  for (const id of result.matching.redundant_relations ?? [])
    add("candidate", "relation", id, "warning", "Redundant relation");

  for (const [kind, elements] of [
    ["node", result.evaluation.syntactic.nodes],
    ["relation", result.evaluation.syntactic.relations],
  ]) {
    for (const element of elements ?? []) {
      for (const [check, passed] of Object.entries(element.checks ?? {})) {
        if (!passed)
          add(
            "candidate",
            kind,
            element.uid,
            "error",
            `Syntax: ${title(check)}`,
          );
      }
    }
  }

  for (const node of result.evaluation.pragmatic.nodes ?? []) {
    if (node.score < 3)
      add(
        "candidate",
        "node",
        node.uid,
        "info",
        `Naming understandability: ${node.score}/3`,
      );
  }

  return diagnostics;
}

export function highlightColor(item) {
  if (item.message.startsWith("Missing ")) return "#dc2626";
  if (item.side === "candidate" && item.message.startsWith("Redundant "))
    return "#f59e0b";
  return null;
}
