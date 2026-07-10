"""Abstract policy engine adapter."""

from abc import ABC, abstractmethod

from packages.policy_client.models import PolicyInput, PolicyOutput


class PolicyAdapter(ABC):
    """Abstract interface for policy engines."""

    @abstractmethod
    async def evaluate(self, policy_input: PolicyInput) -> PolicyOutput:
        """Evaluate a policy decision for the given input."""

    @abstractmethod
    async def health(self) -> bool:
        """Check if the policy engine is reachable."""


class PolicyError(Exception):
    """Policy evaluation error."""
