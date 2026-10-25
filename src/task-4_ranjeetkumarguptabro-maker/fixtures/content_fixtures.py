"""Standard and edge-case content items for testing and demonstrations."""

from workflow.models import ContentItem

# Valid scenario content items
SAMPLE_PASS_CONTENT = ContentItem(
    id="content-001",
    title="Evidence Synthesis: Enterprise Agent Architecture",
    body=(
        "Recent benchmarks demonstrate that stateful checkpointing significantly reduces "
        "cost and latency in human-in-the-loop agent workflows. All facts verified."
    ),
    metadata={"author": "Atomity Research", "domain": "agentic-systems"},
)

SAMPLE_REVISE_ONCE_CONTENT = ContentItem(
    id="content-002",
    title="Draft: LLM Memory Patterns in Multi-Step Workflows",
    body=(
        "State persistence allows agents to pause safely across process boundaries. "
        "[NEEDS_REVISION] Requires empirical citation comparing SQLite with Redis."
    ),
    metadata={"author": "Workflow Team", "domain": "orchestration"},
)

SAMPLE_REVISE_LIMIT_CONTENT = ContentItem(
    id="content-003",
    title="Analysis: Contested Industry Metrics",
    body=(
        "Performance benchmarks claiming 99.9% autonomous accuracy. "
        "[FAIL_LIMIT] Methodology lacks control groups and reproducible seeds."
    ),
    metadata={"author": "Guest Contributor", "domain": "benchmarks"},
)

# Malformed content test cases to verify strict validation boundaries
INVALID_CONTENT_CASES = [
    {
        "name": "empty_id",
        "data": {"id": "", "title": "Valid Title", "body": "Valid body text."},
        "expected_error": "Content ID cannot be empty",
    },
    {
        "name": "whitespace_only_id",
        "data": {"id": "   ", "title": "Valid Title", "body": "Valid body text."},
        "expected_error": "Content ID cannot be empty",
    },
    {
        "name": "invalid_chars_in_id",
        "data": {"id": "invalid content id /!", "title": "Valid Title", "body": "Valid body text."},
        "expected_error": "contains invalid characters",
    },
    {
        "name": "empty_title",
        "data": {"id": "content-err-1", "title": "", "body": "Valid body text."},
        "expected_error": "Content title cannot be empty",
    },
    {
        "name": "whitespace_only_title",
        "data": {"id": "content-err-2", "title": "   \n\t", "body": "Valid body text."},
        "expected_error": "Content title cannot be empty",
    },
    {
        "name": "empty_body",
        "data": {"id": "content-err-3", "title": "Valid Title", "body": ""},
        "expected_error": "Content body cannot be empty",
    },
    {
        "name": "whitespace_only_body",
        "data": {"id": "content-err-4", "title": "Valid Title", "body": "   "},
        "expected_error": "Content body cannot be empty",
    },
]
