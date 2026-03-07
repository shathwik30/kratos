class KratosError(Exception):
    """Base exception for all Kratos errors."""


class ConfigurationError(KratosError):
    """Raised when Kratos is misconfigured (e.g. invalid db_url)."""


class ValidationError(KratosError):
    """Raised when input data fails validation."""


class DatabaseError(KratosError):
    """Raised when a database operation fails."""
