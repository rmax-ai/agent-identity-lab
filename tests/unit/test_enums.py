from packages.common.enums import AgentStatus, BlueprintStatus, PolicyDecision


class TestAgentStatus:
    def test_active_value(self):
        assert AgentStatus.ACTIVE.value == "active"

    def test_suspended_value(self):
        assert AgentStatus.SUSPENDED.value == "suspended"

    def test_revoked_terminal(self):
        assert AgentStatus.REVOKED.value == "revoked"
        assert AgentStatus.DECOMMISSIONED.value == "decommissioned"


class TestBlueprintStatus:
    def test_draft_default(self):
        assert BlueprintStatus.DRAFT.value == "draft"

    def test_active_deprecated(self):
        assert BlueprintStatus.ACTIVE.value == "active"
        assert BlueprintStatus.DEPRECATED.value == "deprecated"


class TestPolicyDecision:
    def test_decisions(self):
        assert PolicyDecision.ALLOW.value == "allow"
        assert PolicyDecision.DENY.value == "deny"
