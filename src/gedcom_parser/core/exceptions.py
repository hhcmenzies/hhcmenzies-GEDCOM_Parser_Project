class PipelineError(Exception):
    """Base exception for pipeline failures."""


class ValidationError(PipelineError):
    """Raised when validation fails."""


class ParseExecutionError(PipelineError):
    """Raised when parsing fails."""
