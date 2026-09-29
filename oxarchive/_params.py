"""Keyword arguments the SDK no longer sends.

Several methods keep ``**kwargs`` for the deprecated ``coin`` keyword, so a
removed parameter would otherwise be accepted and silently dropped. These
parameters were removed because the API never applied them; raising says so
instead of returning unfiltered data as if the filter had worked.
"""

from __future__ import annotations

from typing import Any, Mapping


def reject_unsupported(
    method: str, kwargs: Mapping[str, Any], unsupported: Mapping[str, str]
) -> None:
    """Raise ``TypeError`` if ``kwargs`` holds a parameter the API does not apply.

    Args:
        method: The method name, for the message.
        kwargs: The keyword arguments the method received beyond its signature.
        unsupported: Parameter name to the reason it is not supported.
    """
    for name, reason in unsupported.items():
        if name in kwargs:
            raise TypeError(f"{method}() does not take '{name}': {reason}")


__all__ = ["reject_unsupported"]
