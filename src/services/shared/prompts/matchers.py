USE_CASE_DIAGRAM_MATCHER = """\
Find Node Match and Relation Match between Reference Diagram and Candidate
Diagram. Match meaning, not label similarity.

# Input

- `nodes` got `uid`, `name`, `type`, maybe `parent` node UID.
- `relations` got `uid`, `type`, `source`, `target` node UIDs.
- Resolve parent and endpoint UIDs in own diagram. UID identifies element;
  same UID across diagram = no evidence of match.
- Node-group list = derived index, not extra node.

# Node matching

- Compare every Reference node with eligible Candidate node. Throw out
  `note` and `other` node from Node Match.
- `usecase` vs `usecase`: same behavior, action, object, intended outcome.
  Same topic alone insufficient; create object and delete object = different
  behavior.
- `actor` and `external_system` = actor-like node, match across these two
  type OK. Same interaction role toward modeled subject, not just same
  person, organization, or service name.
- `system` vs `system`: same modeled subject and scope. System boundary and
  external participant not interchangeable.
- No match across other type combination.
- Synonym, paraphrase, translation, abbreviation OK when same meaning. Same
  name alone no make match.
- Use parent meaning plus connected node and relation to resolve ambiguity.
  Different or missing parent or relation structure alone does not
  invalidate clear Node Match. Never equate raw parent UID.
- Keep behavioral scope: broad use case not same as one step of it. No
  merge, no split node to force match.

# Relation matching

- Compare each Reference relation with Candidate relation by relation type
  and semantic role of both endpoint. Get endpoint meaning from node and
  diagram context; no compare endpoint UID across diagram.
- `association`: same participant take part in same use case. Source/target
  flip no change meaning.
- `include`: same including behavior (source) include same included behavior
  (target). Keep direction.
- `extend`: same extending behavior (source) extend same extended behavior
  (target). Keep direction.
- `generalization`: same specific element (source) specialize same general
  element (target). Keep direction.
- Different relation type = different meaning; no swap association, include,
  extend, generalization. Type match alone insufficient, endpoint match
  alone insufficient.
- Relation Match must agree with chosen Node Match wherever endpoint
  matched. No invent endpoint, no infer missing or transitive edge. Leave
  relation unmatched if endpoint meaning cannot be established.

# Pair selection

- One-to-one: each UID at most once per diagram per match kind. Pick
  best-supported pairing over whole diagram.
- Distinguish uncertain meaning from interchangeable semantic equivalents.
  Leave element unmatched when semantic equivalence cannot be established.
  No force match from similar label alone or to grow count.
- When many node or relation are established semantic equivalents, pick
  globally consistent one-to-one pairing that keep largest number of
  established Node Matches and Relation Matches. No leave equal duplicate
  unmatched just because several pairing valid. Match duplicate up to
  smaller count; leave surplus unmatched.
- Break tie only after semantic equivalence and graph consistency
  established: sort Reference UID lexicographically and take smallest
  Candidate UID that keep globally consistent best pairing. Do node pairing
  before relation tie. UID order only tie-break, never evidence of meaning.
  Input array order must no change match count.
"""

USE_CASE_DIAGRAM_MATCHER_REQUEST = """
# Reference:
<reference>
{reference}
</reference>

Candidate:
<candidate>
{candidate}
</candidate>
"""
