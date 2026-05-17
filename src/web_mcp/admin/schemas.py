"""Pydantic models for admin API request/response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PathConfigInput(BaseModel):
    """Input for creating or updating a path configuration."""

    name: str = Field(..., min_length=1, max_length=100, description="Display name for the path")
    description: str = Field("", max_length=500, description="Optional description")
    enabled_tools: list[str] = Field(..., min_length=1, description="List of tool names to enable")
    requires_auth: bool = Field(True, description="Whether MCP clients need auth for this path")


class PathConfigOutput(BaseModel):
    """Output for a path configuration."""

    name: str
    description: str = ""
    enabled_tools: list[str]
    requires_auth: bool = True


class ConfigOutput(BaseModel):
    """Full admin config output."""

    version: int = 1
    paths: dict[str, PathConfigOutput]


class ToolInfo(BaseModel):
    """Information about a single tool."""

    name: str
    description: str
    is_read_only: bool
    destructive: bool = False


class ToolsListOutput(BaseModel):
    """Output listing all available tools."""

    tools: list[ToolInfo]


class HealthOutput(BaseModel):
    """Health check output."""

    status: str
    version: str
    admin_enabled: bool


class ApiKeyInfo(BaseModel):
    """Information about an API key (key masked for security)."""

    name: str
    uid: int
    key_prefix: str = Field(..., description="First 8 chars of the key for identification")
    is_bootstrap: bool = Field(False, description="True if this is the WEB_MCP_AUTH_TOKEN")


class ApiKeyCreateInput(BaseModel):
    """Input for creating a new API key."""

    name: str = Field(..., min_length=1, max_length=100, description="Display name for the token")


class ApiKeyCreateOutput(BaseModel):
    """Output after creating an API key (includes full key)."""

    name: str
    uid: int
    key: str = Field(..., description="Full API key — show only once")


class ApiKeyUpdateInput(BaseModel):
    """Input for updating an API key name."""

    name: str = Field(..., min_length=1, max_length=100)
