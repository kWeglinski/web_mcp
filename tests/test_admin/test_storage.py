"""Unit tests for admin ConfigStorage."""

import json

import pytest

from web_mcp.admin.storage import ConfigStorage


class TestSaveAndLoad:
    """Tests for saving and loading config from disk."""

    def test_save_and_load(self, tmp_path):
        """Test write config, reload from same path, verify."""
        config_file = tmp_path / "config.json"
        storage = ConfigStorage(config_file)

        storage.set_path_config("/search", {"name": "Search", "enabled_tools": ["get_page"]})
        storage.save()

        # Reload from the same path
        storage2 = ConfigStorage(config_file)
        paths = storage2.get_paths()

        assert "/search" in paths
        assert paths["/search"]["name"] == "Search"
        assert paths["/search"]["enabled_tools"] == ["get_page"]

    def test_save_load_multiple_paths(self, tmp_path):
        """Test saving and loading multiple path configurations."""
        config_file = tmp_path / "config.json"
        storage = ConfigStorage(config_file)

        storage.set_path_config("/search", {"name": "Search", "enabled_tools": ["get_page", "search_web"]})
        storage.set_path_config("/research", {"name": "Research", "enabled_tools": ["get_page"]})
        storage.save()

        storage2 = ConfigStorage(config_file)
        paths = storage2.get_paths()

        assert len(paths) == 2
        assert "/search" in paths
        assert "/research" in paths


class TestDefaultEmptyConfig:
    """Tests for default empty configuration."""

    def test_default_empty_config(self, tmp_path):
        """Test that no file exists → empty paths."""
        config_file = tmp_path / "nonexistent.json"
        storage = ConfigStorage(config_file)

        paths = storage.get_paths()
        assert paths == {}

    def test_get_path_config_none(self, tmp_path):
        """Test get_path_config returns None for nonexistent path."""
        config_file = tmp_path / "config.json"
        storage = ConfigStorage(config_file)

        result = storage.get_path_config("/nonexistent")
        assert result is None


class TestCorruptFile:
    """Tests for handling corrupt config files."""

    def test_corrupt_file(self, tmp_path):
        """Test bad JSON → fallback to empty."""
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json {{{")

        storage = ConfigStorage(config_file)
        paths = storage.get_paths()

        assert paths == {}

    def test_empty_file(self, tmp_path):
        """Test empty file → fallback to empty."""
        config_file = tmp_path / "config.json"
        config_file.write_text("")

        storage = ConfigStorage(config_file)
        paths = storage.get_paths()

        assert paths == {}

    def test_partial_json(self, tmp_path):
        """Test partial/invalid JSON structure → fallback to empty."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"version": 1}')

        storage = ConfigStorage(config_file)
        paths = storage.get_paths()

        assert paths == {}


class TestUpsertAndDelete:
    """Tests for upsert and delete operations."""

    def test_upsert_creates_new_path(self, tmp_path):
        """Test set_path_config creates a new path."""
        config_file = tmp_path / "config.json"
        storage = ConfigStorage(config_file)

        storage.set_path_config("/new-path", {"name": "New", "enabled_tools": ["health"]})

        paths = storage.get_paths()
        assert "/new-path" in paths
        assert paths["/new-path"]["name"] == "New"

    def test_upsert_overwrites_existing_path(self, tmp_path):
        """Test set_path_config overwrites an existing path."""
        config_file = tmp_path / "config.json"
        storage = ConfigStorage(config_file)

        storage.set_path_config("/search", {"name": "Search V1", "enabled_tools": ["get_page"]})
        storage.set_path_config("/search", {"name": "Search V2", "enabled_tools": ["get_page", "search_web"]})

        paths = storage.get_paths()
        assert paths["/search"]["name"] == "Search V2"
        assert paths["/search"]["enabled_tools"] == ["get_page", "search_web"]

    def test_delete_existing_path(self, tmp_path):
        """Test delete_path_config removes an existing path."""
        config_file = tmp_path / "config.json"
        storage = ConfigStorage(config_file)

        storage.set_path_config("/search", {"name": "Search", "enabled_tools": ["get_page"]})
        result = storage.delete_path_config("/search")

        assert result is True
        assert storage.get_path_config("/search") is None

    def test_delete_nonexistent_path(self, tmp_path):
        """Test delete_path_config returns False for nonexistent path."""
        config_file = tmp_path / "config.json"
        storage = ConfigStorage(config_file)

        result = storage.delete_path_config("/nonexistent")

        assert result is False

    def test_full_crud_cycle(self, tmp_path):
        """Test full CRUD cycle: create, read, update, delete."""
        config_file = tmp_path / "config.json"
        storage = ConfigStorage(config_file)

        # Create
        storage.set_path_config("/search", {"name": "Search", "enabled_tools": ["get_page"]})
        assert storage.get_path_config("/search") is not None

        # Read
        config = storage.get_path_config("/search")
        assert config["name"] == "Search"

        # Update
        storage.set_path_config("/search", {"name": "Search Updated", "enabled_tools": ["get_page", "search_web"]})
        config = storage.get_path_config("/search")
        assert config["name"] == "Search Updated"

        # Delete
        assert storage.delete_path_config("/search") is True
        assert storage.get_path_config("/search") is None


class TestGetAllToolNames:
    """Tests for get_all_tool_names."""

    def test_get_all_tool_names(self):
        """Test returns 9 tool names from TOOL_REGISTRY."""
        storage = ConfigStorage()
        tool_names = storage.get_all_tool_names()

        assert len(tool_names) == 9
        assert "get_page" in tool_names
        assert "search_web" in tool_names
        assert "brave_search" in tool_names
        assert "run_javascript" in tool_names
