from packages.identity_models.schemas import BlueprintCreate


class TestBlueprintCreate:
    def test_defaults(self):
        blueprint = BlueprintCreate(slug="test-bp", name="Test Blueprint")
        assert blueprint.slug == "test-bp"
        assert blueprint.approved_models == []
        assert blueprint.max_session_ttl_seconds == 1800

    def test_min_ttl_enforced(self):
        blueprint = BlueprintCreate(slug="t", name="T", max_session_ttl_seconds=60)
        assert blueprint.max_session_ttl_seconds == 60

    def test_slug_validation(self):
        blueprint = BlueprintCreate(slug="valid-slug-123", name="Valid")
        assert blueprint.slug == "valid-slug-123"
