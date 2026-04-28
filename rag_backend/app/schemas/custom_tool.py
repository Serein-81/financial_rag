from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ToolFieldSpec(BaseModel):
    type: str = Field(default="string", description="JSON schema type")
    description: str = ""
    required: bool = True
    default: Any = None


class CustomToolSpec(BaseModel):
    name: str = Field(min_length=3, max_length=80, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    display_name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1)
    purpose: Optional[str] = None
    kind: str = Field(default="echo")
    version: str = Field(default="1.0.0", max_length=32)
    input_schema: Dict[str, ToolFieldSpec] = Field(default_factory=dict)
    output_schema: Dict[str, ToolFieldSpec] = Field(default_factory=dict)
    runtime_config: Dict[str, Any] = Field(default_factory=dict)
    safety_policy: Dict[str, Any] = Field(default_factory=dict)
    generated_code: Optional[str] = None
    agent_id: Optional[str] = None

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        allowed = {"echo", "http", "rag_query", "python_code"}
        if value not in allowed:
            raise ValueError(f"kind must be one of {sorted(allowed)}")
        return value


class GenerateToolRequest(BaseModel):
    natural_language: str = Field(min_length=8)
    purpose: Optional[str] = None
    inputs: Optional[str] = None
    outputs: Optional[str] = None
    preferred_kind: Optional[str] = Field(default=None, description="echo/http/rag_query/python_code")
    agent_id: Optional[str] = None


class GenerateToolCodeRequest(BaseModel):
    spec: CustomToolSpec
    instruction: Optional[str] = Field(
        default=None,
        description="Additional implementation notes for the generated code draft",
    )


class CreateCustomToolRequest(CustomToolSpec):
    pass


class UpdateCustomToolRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = None
    purpose: Optional[str] = None
    input_schema: Optional[Dict[str, ToolFieldSpec]] = None
    output_schema: Optional[Dict[str, ToolFieldSpec]] = None
    runtime_config: Optional[Dict[str, Any]] = None
    safety_policy: Optional[Dict[str, Any]] = None
    generated_code: Optional[str] = None
    agent_id: Optional[str] = None


class ExecuteCustomToolRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)


class PublishCustomToolRequest(BaseModel):
    agent_id: Optional[str] = None


class CustomToolResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str
    purpose: Optional[str]
    kind: str
    status: str
    version: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    runtime_config: Dict[str, Any]
    safety_policy: Dict[str, Any]
    agent_id: Optional[str]
    enabled: bool
    created_at: str
    updated_at: str


class CustomToolListResponse(BaseModel):
    total: int
    tools: List[CustomToolResponse]
