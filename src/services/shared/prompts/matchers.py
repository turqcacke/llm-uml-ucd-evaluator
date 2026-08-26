USE_CASE_DIAGRAM_MATCHER = """Match the Reference and Candidate use case diagrams.

Return one-to-one Node Matches and Relation Matches only. Each reference or
candidate UID may appear in at most one match of its kind. Exclude note and
unclassified (`other`) nodes. For each Reference Relation, choose at most one
semantically matching Candidate Relation. Do not infer a relation match from
endpoint or relation-type equality alone.
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
