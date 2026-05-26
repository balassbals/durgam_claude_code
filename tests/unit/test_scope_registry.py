"""Unit tests for E-006 scope-type registry."""

from unittest.mock import MagicMock

from durgam.scopes.registry import (
    SCOPE_TYPE_REGISTRY,
    ScopeTypeConfig,
    get_scope_type_dropdown_options,
    get_scope_type_keys,
    load_scope_objects,
)


class TestScopeTypeRegistry:
    def test_registry_has_three_entries(self):
        assert set(SCOPE_TYPE_REGISTRY.keys()) == {"campus", "department", "school"}

    def test_all_entries_are_scope_type_config(self):
        for key, cfg in SCOPE_TYPE_REGISTRY.items():
            assert isinstance(cfg, ScopeTypeConfig)
            assert cfg.key == key
            assert cfg.label
            assert callable(cfg.list_options)

    def test_get_scope_type_keys(self):
        keys = get_scope_type_keys()
        assert keys == ["campus", "department", "school"]

    def test_get_scope_type_dropdown_options(self):
        options = get_scope_type_dropdown_options()
        assert len(options) == 3
        values = [o["value"] for o in options]
        labels = [o["label"] for o in options]
        assert "campus" in values
        assert "department" in values
        assert "school" in values
        assert "Campus" in labels
        assert "Department" in labels
        assert "School" in labels

    def test_each_option_has_value_and_label(self):
        for opt in get_scope_type_dropdown_options():
            assert "value" in opt
            assert "label" in opt
            assert opt["value"] == SCOPE_TYPE_REGISTRY[opt["value"]].key

    def test_scope_type_config_is_frozen(self):
        cfg = SCOPE_TYPE_REGISTRY["campus"]
        import pytest
        with pytest.raises(AttributeError):
            cfg.key = "other"  # type: ignore[misc]


class TestLoadScopeObjects:
    def test_unknown_scope_type_returns_empty(self):
        session = MagicMock()
        result = load_scope_objects("nonexistent", session)
        assert result == []

    def test_empty_string_returns_empty(self):
        session = MagicMock()
        result = load_scope_objects("", session)
        assert result == []

    def test_each_registered_type_calls_its_list_function(self):
        """Verify that load_scope_objects dispatches to the correct list_options callable."""
        sentinel = [{"id": "test", "label": "Test"}]
        mock_fn = MagicMock(return_value=sentinel)
        original = dict(SCOPE_TYPE_REGISTRY)
        try:
            SCOPE_TYPE_REGISTRY["test_scope"] = ScopeTypeConfig(
                key="test_scope", label="Test Scope", list_options=mock_fn,
            )
            session = MagicMock()
            result = load_scope_objects("test_scope", session)
            assert result == sentinel
            mock_fn.assert_called_once_with(session)
        finally:
            SCOPE_TYPE_REGISTRY.clear()
            SCOPE_TYPE_REGISTRY.update(original)

    def test_campus_config_callable_exists(self):
        cfg = SCOPE_TYPE_REGISTRY["campus"]
        assert callable(cfg.list_options)

    def test_department_config_callable_exists(self):
        cfg = SCOPE_TYPE_REGISTRY["department"]
        assert callable(cfg.list_options)

    def test_school_config_callable_exists(self):
        cfg = SCOPE_TYPE_REGISTRY["school"]
        assert callable(cfg.list_options)


class TestRegistryExtensibility:
    """Verify that adding a scope type to the registry makes it available everywhere."""

    def test_adding_scope_type_appears_in_keys_and_options(self):
        original = dict(SCOPE_TYPE_REGISTRY)
        try:
            SCOPE_TYPE_REGISTRY["centre"] = ScopeTypeConfig(
                key="centre",
                label="Centre of Excellence",
                list_options=lambda session: [{"id": "x", "label": "Test Centre"}],
            )
            assert "centre" in get_scope_type_keys()
            options = get_scope_type_dropdown_options()
            assert any(o["value"] == "centre" for o in options)

            session = MagicMock()
            result = load_scope_objects("centre", session)
            assert result == [{"id": "x", "label": "Test Centre"}]
        finally:
            SCOPE_TYPE_REGISTRY.clear()
            SCOPE_TYPE_REGISTRY.update(original)

    def test_removing_scope_type_removes_from_keys_and_options(self):
        original = dict(SCOPE_TYPE_REGISTRY)
        try:
            del SCOPE_TYPE_REGISTRY["school"]
            assert "school" not in get_scope_type_keys()
            options = get_scope_type_dropdown_options()
            assert not any(o["value"] == "school" for o in options)
            assert load_scope_objects("school", MagicMock()) == []
        finally:
            SCOPE_TYPE_REGISTRY.clear()
            SCOPE_TYPE_REGISTRY.update(original)
