"""Rule violations raised by the pure domain layer.

Services translate these into HTTP-shaped domain errors; nothing here knows
about Django or DRF.
"""
from __future__ import annotations


class RuleViolation(Exception):
    """A leave rule refused the request. `code` is stable for clients."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class InvalidTransition(Exception):
    def __init__(self, status: str, event: str):
        super().__init__(f"Cannot {event} a request that is {status}.")
        self.status = status
        self.event = event
