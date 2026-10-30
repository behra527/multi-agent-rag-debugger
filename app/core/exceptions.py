"""Structured application errors with stable error codes."""

from __future__ import annotations


class AppError(Exception):
    """Base class for expected, user-visible application failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "app_error",
        status_code: int = 400,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ConfigurationError(AppError, ValueError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(
            message,
            code="configuration_error",
            status_code=503,
            details=details,
        )


class ProviderError(AppError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(
            message,
            code="provider_error",
            status_code=502,
            details=details,
        )


class NotFoundError(AppError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(
            message,
            code="not_found",
            status_code=404,
            details=details,
        )


class AuthorizationError(AppError):
    def __init__(self, message: str = "Not authorized.", details: dict | None = None) -> None:
        super().__init__(
            message,
            code="unauthorized",
            status_code=401,
            details=details,
        )


class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied.", details: dict | None = None) -> None:
        super().__init__(
            message,
            code="forbidden",
            status_code=403,
            details=details,
        )


class ValidationFailed(AppError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(
            message,
            code="validation_error",
            status_code=422,
            details=details,
        )


class BudgetExceeded(AppError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(
            message,
            code="budget_exceeded",
            status_code=429,
            details=details,
        )


class IngestionError(AppError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(
            message,
            code="ingestion_error",
            status_code=400,
            details=details,
        )
