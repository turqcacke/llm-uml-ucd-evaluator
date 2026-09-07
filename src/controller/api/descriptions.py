ASSESSMENT_DESCRIPTION = """
### Syntactic checks

Each entry in `evaluation.syntactic.nodes` or
`evaluation.syntactic.relations` contains a `checks` object. `true` means the
check passed, `false` identifies a syntactic violation, and an absent key means
the check was not applicable or its prerequisites were unavailable.

- `name_present`: the node name contains at least one non-whitespace character.
- `parent_exists`: the node has no parent or its parent UID exists in the
  Candidate Diagram.
- `endpoints_exist`: both relation endpoint UIDs exist in the Candidate Diagram.
- `endpoint_types_valid`: the relation connects compatible node types.
  Associations connect an actor with a use case; include and
  extend relations connect two use cases; generalizations connect two use cases
  or two actors.
- `include_acyclic`: the include relation does not participate in an include
  cycle.
- `generalization_acyclic`: the generalization relation does not participate in
  a generalization cycle.
"""
