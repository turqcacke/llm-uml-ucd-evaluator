API_DESCRIPTION = """
This API evaluates a Candidate Use Case Diagram against a Reference Diagram
or a Context Description. An assessment can be returned as a single response
or streamed as progress, result, and error events.

### Error codes

All JSON error responses follow the `FailResponse` schema.

- `UNAUTHORIZED`: the API key is missing or invalid.
- `VALIDATION_ERROR`: the request did not pass schema validation.
- `CONVERSION_ERROR`: the provided diagram could not be read.
- `REFERENCE_NOT_ALLOWED`: the Reference Diagram does not contain any actors
  or use cases.
- `LLM_REQUEST_ERROR`: the request to the LLM provider could not be completed.
- `LLM_RESPONSE_ERROR`: the LLM response did not pass schema validation.
- `LLM_RATE_LIMIT_ERROR`: the LLM provider rejected the request because its
  rate limit or quota was exceeded.
- `CONFIG_ERROR`: the LLM provider, model, or credentials are configured
  incorrectly.
- `USE_CASE_ERROR`: the assessment could not be completed.
- `INTERNAL_ERROR`: the server encountered an unexpected error.
"""

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

ASSESSMENT_STREAM_DESCRIPTION = ASSESSMENT_DESCRIPTION + """

### Streaming error delivery

After the stream has started, assessment failures are returned with HTTP 200
as an `error` SSE event. Its data follows `FailResponse`. The assessment must
be started again after an error.
"""
