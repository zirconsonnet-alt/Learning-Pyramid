class PLMError(Exception):
    """Base class for domain errors."""


class NotFound(PLMError):
    pass


class PreconditionFailure(PLMError):
    pass


class ExternalServiceError(PLMError):
    pass


class CommitTimeValidationFailure(PLMError):
    pass


class StructuralInconsistencyError(PLMError):
    pass


class DirectoryStructureCorruptedError(PLMError):
    pass


class ConcurrencyConflictError(PLMError):
    pass


class SessionClosedError(PLMError):
    pass
