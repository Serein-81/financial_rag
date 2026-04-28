from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.schemas.custom_tool import (
    CreateCustomToolRequest,
    CustomToolListResponse,
    CustomToolResponse,
    ExecuteCustomToolRequest,
    GenerateToolRequest,
    PublishCustomToolRequest,
)
from app.services.custom_tool_runtime import CustomToolRuntimeError
from app.services.custom_tool_service import CustomToolServiceError, custom_tool_service

router = APIRouter()


def serialize_tool(tool) -> CustomToolResponse:
    return CustomToolResponse(
        id=str(tool.id),
        name=tool.name,
        display_name=tool.display_name,
        description=tool.description,
        purpose=tool.purpose,
        kind=tool.kind,
        status=tool.status,
        version=tool.version,
        input_schema=tool.input_schema or {},
        output_schema=tool.output_schema or {},
        runtime_config=tool.runtime_config or {},
        safety_policy=tool.safety_policy or {},
        agent_id=tool.agent_id,
        enabled=tool.enabled,
        created_at=tool.created_at.isoformat(),
        updated_at=tool.updated_at.isoformat(),
    )


@router.post("/generate")
async def generate_custom_tool_spec(
    request: GenerateToolRequest,
    current_user: User = Depends(deps.get_current_user),
):
    spec = await custom_tool_service.generate_spec(request)
    return spec.model_dump()


@router.post("", response_model=CustomToolResponse)
async def create_custom_tool(
    request: CreateCustomToolRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    try:
        tool = await custom_tool_service.create_tool(
            db=db,
            tenant_id=current_user.tenant_id,
            user_id=str(current_user.id),
            spec=request,
        )
        return serialize_tool(tool)
    except CustomToolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=CustomToolListResponse)
async def list_custom_tools(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    tools = await custom_tool_service.list_tools(db, current_user.tenant_id)
    return {
        "total": len(tools),
        "tools": [serialize_tool(tool) for tool in tools],
    }


@router.get("/{tool_id}", response_model=CustomToolResponse)
async def get_custom_tool(
    tool_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    try:
        return serialize_tool(await custom_tool_service.get_tool(db, current_user.tenant_id, tool_id))
    except CustomToolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{tool_id}/publish", response_model=CustomToolResponse)
async def publish_custom_tool(
    tool_id: str,
    request: PublishCustomToolRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    try:
        tool = await custom_tool_service.publish_tool(
            db=db,
            tenant_id=current_user.tenant_id,
            tool_id=tool_id,
            agent_id=request.agent_id,
        )
        return serialize_tool(tool)
    except CustomToolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{tool_id}/execute")
async def execute_custom_tool(
    tool_id: str,
    request: ExecuteCustomToolRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    try:
        return await custom_tool_service.execute_tool(
            db=db,
            tenant_id=current_user.tenant_id,
            tool_id=tool_id,
            arguments=request.arguments,
        )
    except CustomToolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CustomToolRuntimeError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
