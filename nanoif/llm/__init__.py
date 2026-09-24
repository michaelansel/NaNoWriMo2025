"""LLM client package: profiles, structured-output client, pricing, schema, test doubles."""

from nanoif.llm.client import Completer, LLMClient, LLMResult, Usage
from nanoif.llm.errors import (
    LLMBudgetExceeded,
    LLMConfigError,
    LLMError,
    LLMSchemaError,
    LLMTransportError,
    LLMTruncatedError,
)
from nanoif.llm.profiles import Settings

__all__ = [
    "Completer",
    "LLMBudgetExceeded",
    "LLMClient",
    "LLMConfigError",
    "LLMError",
    "LLMResult",
    "LLMSchemaError",
    "LLMTransportError",
    "LLMTruncatedError",
    "Settings",
    "Usage",
]
