import uuid

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.schemas.custom_tool import (
    CreateCustomToolRequest,
    CustomToolListResponse,
    CustomToolResponse,
    ExecuteCustomToolRequest,
    GenerateToolCodeRequest,
    GenerateToolRequest,
    PublishCustomToolRequest,
)
from app.services.custom_tool_runtime import CustomToolRuntimeError
from app.services.custom_tool_service import CustomToolServiceError, custom_tool_service
from app.services.log_service import log_service

router = APIRouter()
logger = logging.getLogger(__name__)


def require_admin(current_user: User) -> None:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators can manage custom tools")


async def log_custom_tool_action(
    *,
    request: Request,
    current_user: User,
    action_name: str,
    description: str,
    success: bool = True,
    result_message: str | None = None,
    resource_id: str | None = None,
    resource_name: str | None = None,
    extra_info: dict | None = None,
    risk_level: str = "low",
) -> None:
    try:
        await log_service.create_user_action_log(
            user_id=str(current_user.id),
            tenant_id=current_user.tenant_id,
            action_type="custom_tool",
            action_name=action_name,
            description=description,
            resource_type="custom_tool",
            resource_id=resource_id,
            resource_name=resource_name,
            success=success,
            result_message=result_message,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            level="INFO" if success else "ERROR",
            risk_level=risk_level,
            extra_info=extra_info or {},
        )
    except Exception:
        pass


def mask_runtime_config(runtime_config: dict | None) -> dict:
    config = dict(runtime_config or {})
    api_key = config.get("api_key")
    if isinstance(api_key, dict) and api_key.get("value"):
        masked = dict(api_key)
        masked["value"] = "********"
        masked["configured"] = True
        config["api_key"] = masked
    return config


def get_user_display_name(user: User | None, fallback: str | None = None) -> str | None:
    if not user:
        return fallback
    return user.full_name or user.nickname or user.username or user.email or fallback


def serialize_tool(tool, published_by_name: str | None = None) -> CustomToolResponse:
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
        runtime_config=mask_runtime_config(tool.runtime_config),
        safety_policy=tool.safety_policy or {},
        agent_id=tool.agent_id,
        published_by=tool.approved_by,
        published_by_name=published_by_name,
        enabled=tool.enabled,
        created_at=tool.created_at.isoformat(),
        updated_at=tool.updated_at.isoformat(),
    )


@router.post("/generate")
async def generate_custom_tool_spec(
    request_context: Request,
    request: GenerateToolRequest,
    current_user: User = Depends(deps.get_current_user),
):
    require_admin(current_user)
    spec = await custom_tool_service.generate_spec(request)
    await log_custom_tool_action(
        request=request_context,
        current_user=current_user,
        action_name="generate_custom_tool_spec",
        description="生成自定义智能体工具规格",
        resource_name=spec.name,
        extra_info={
            "preferred_kind": request.preferred_kind,
            "agent_id": request.agent_id,
            "generated_name": spec.name,
            "generated_kind": spec.kind,
        },
    )
    return spec.model_dump()


@router.post("/generate-code")
async def generate_custom_tool_code(
    request_context: Request,
    request: GenerateToolCodeRequest,
    current_user: User = Depends(deps.get_current_user),
):
    require_admin(current_user)
    spec = await custom_tool_service.generate_code_draft(request.spec, request.instruction)
    await log_custom_tool_action(
        request=request_context,
        current_user=current_user,
        action_name="generate_custom_tool_code",
        description="生成自定义智能体工具代码草稿",
        resource_name=spec.name,
        extra_info={
            "tool_name": spec.name,
            "kind": spec.kind,
            "code_execution_enabled": False,
            "requires_sandbox_review": True,
        },
        risk_level="medium",
    )
    return spec.model_dump()


@router.post("", response_model=CustomToolResponse)
async def create_custom_tool(
    request_context: Request,
    request: CreateCustomToolRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    require_admin(current_user)
    try:
        tool = await custom_tool_service.create_tool(
            db=db,
            tenant_id=current_user.tenant_id,
            user_id=str(current_user.id),
            spec=request,
        )
        await log_custom_tool_action(
            request=request_context,
            current_user=current_user,
            action_name="create_custom_tool",
            description="创建自定义智能体工具草稿",
            resource_id=str(tool.id),
            resource_name=tool.name,
            extra_info={
                "tool_id": str(tool.id),
                "tool_name": tool.name,
                "kind": tool.kind,
                "status": tool.status,
                "agent_id": tool.agent_id,
                "input_schema": tool.input_schema,
                "output_schema": tool.output_schema,
                "code_execution_enabled": False,
            },
        )
        return serialize_tool(tool)
    except CustomToolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=CustomToolListResponse)
async def list_custom_tools(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    tools = await custom_tool_service.list_tools(
        db,
        current_user.tenant_id,
        include_unpublished=current_user.is_admin,
    )
    publisher_ids = {tool.approved_by for tool in tools if tool.approved_by}
    publishers = {}
    if publisher_ids:
        from sqlalchemy import select

        user_ids = []
        for publisher_id in publisher_ids:
            try:
                user_ids.append(uuid.UUID(str(publisher_id)))
            except ValueError:
                pass
        result = await db.execute(select(User).where(User.id.in_(user_ids)))
        publishers = {str(user.id): get_user_display_name(user, str(user.id)) for user in result.scalars().all()}

    return {
        "total": len(tools),
        "tools": [
            serialize_tool(tool, published_by_name=publishers.get(str(tool.approved_by)) if tool.approved_by else None)
            for tool in tools
        ],
    }


@router.get("/{tool_id}", response_model=CustomToolResponse)
async def get_custom_tool(
    tool_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    try:
        tool = await custom_tool_service.get_tool(db, current_user.tenant_id, tool_id)
        if not current_user.is_admin and not (tool.enabled and tool.status == "published"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom tool not found")
        return serialize_tool(tool)
    except CustomToolServiceError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{tool_id}/publish", response_model=CustomToolResponse)
async def publish_custom_tool(
    tool_id: str,
    request_context: Request,
    request: PublishCustomToolRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    require_admin(current_user)
    try:
        tool = await custom_tool_service.publish_tool(
            db=db,
            tenant_id=current_user.tenant_id,
            tool_id=tool_id,
            agent_id=request.agent_id,
            published_by=str(current_user.id),
            published_by_name=get_user_display_name(current_user, str(current_user.id)),
        )
        await log_custom_tool_action(
            request=request_context,
            current_user=current_user,
            action_name="publish_custom_tool",
            description="发布并注册自定义智能体工具",
            resource_id=str(tool.id),
            resource_name=tool.name,
            extra_info={
                "tool_id": str(tool.id),
                "tool_name": tool.name,
                "kind": tool.kind,
                "agent_id": tool.agent_id,
                "status": tool.status,
                "enabled": tool.enabled,
                "registered_as_local_tool": True,
            },
            risk_level="medium",
        )
        return serialize_tool(tool, published_by_name=get_user_display_name(current_user, str(current_user.id)))
    except CustomToolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{tool_id}/execute")
async def execute_custom_tool(
    tool_id: str,
    request_context: Request,
    request: ExecuteCustomToolRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    try:
        result = await custom_tool_service.execute_tool(
            db=db,
            tenant_id=current_user.tenant_id,
            tool_id=tool_id,
            arguments=request.arguments,
        )
        output_payload = result.get("output", result.get("data", result))
        result.setdefault("arguments", request.arguments)
        result.setdefault("output", output_payload)
        await log_custom_tool_action(
            request=request_context,
            current_user=current_user,
            action_name="execute_custom_tool",
            description="执行自定义智能体工具测试",
            resource_id=tool_id,
            resource_name=result.get("tool"),
            extra_info={
                "tool_id": tool_id,
                "tool_name": result.get("tool"),
                "arguments_keys": list(request.arguments.keys()),
                "result_status": result.get("status"),
                "http_status": result.get("http_status"),
                "output_keys": list(output_payload.keys()) if isinstance(output_payload, dict) else [],
            },
        )
        return result
    except CustomToolServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CustomToolRuntimeError as e:
        await log_custom_tool_action(
            request=request_context,
            current_user=current_user,
            action_name="execute_custom_tool",
            description="执行自定义智能体工具测试失败",
            success=False,
            result_message=str(e),
            resource_id=tool_id,
            extra_info={
                "tool_id": tool_id,
                "arguments_keys": list(request.arguments.keys()),
                "error": str(e),
            },
            risk_level="medium",
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        error_detail = str(e) or repr(e) or e.__class__.__name__
        logger.exception("Execute custom tool failed: tool_id=%s error=%s", tool_id, error_detail)
        await log_custom_tool_action(
            request=request_context,
            current_user=current_user,
            action_name="execute_custom_tool",
            description="执行自定义智能体工具测试失败",
            success=False,
            result_message=error_detail,
            resource_id=tool_id,
            extra_info={
                "tool_id": tool_id,
                "arguments_keys": list(request.arguments.keys()),
                "error": error_detail,
                "error_type": e.__class__.__name__,
            },
            risk_level="medium",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Custom tool execution failed: {error_detail}",
        )
