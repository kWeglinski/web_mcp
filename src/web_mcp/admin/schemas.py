"""Pydantic models for admin API request/response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PathConfigInput(BaseModel):
    """Input for creating or updating a path configuration."""

    name: str = Field(..., min_length=1, max_length=100, description="Display name for the path")
    description: str = Field("", max_length=500, description="Optional description")
    enabled_tools: list[str] = Field(
        ..., min_length=1, description="List of tool names to enable"
    )
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
