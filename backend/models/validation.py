from dataclasses import dataclass

from .enums import ValidationCode


@dataclass(frozen=True, slots=True)
class ValidationResult:
    code: ValidationCode
    message: str

    @staticmethod
    def ok(message: str = "OK") -> "ValidationResult":
        return ValidationResult(code=ValidationCode.OK, message=message)

    @staticmethod
    def not_found(message: str) -> "ValidationResult":
        return ValidationResult(code=ValidationCode.NOT_FOUND, message=message)

    @staticmethod
    def unreachable(message: str) -> "ValidationResult":
        return ValidationResult(code=ValidationCode.UNREACHABLE, message=message)

    @staticmethod
    def invalid_input(message: str) -> "ValidationResult":
        return ValidationResult(code=ValidationCode.INVALID_INPUT, message=message)
