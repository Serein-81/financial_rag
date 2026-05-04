"""
Skills API Router

Provides CRUD and discovery endpoints for the skills system.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_current_user_from_token, validate_read_access
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["skills"])


@router.get("/skills")
async def list_skills(
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_read_access),
):
    """List all available skills"""
    from app.skills.skill_registry import skill_registry
    return skill_registry.list_skills()


@router.get("/skills/{skill_name}")
async def get_skill(
    skill_name: str,
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_read_access),
):
    """Get skill details by name"""
    from app.skills.skill_registry import skill_registry
    skill = skill_registry.get_skill(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill {skill_name} not found")
    return skill


@router.post("/skills/{skill_name}/execute")
async def execute_skill(
    skill_name: str,
    current_user: User = Depends(get_current_user_from_token),
    tenant_id: str = Depends(validate_read_access),
):
    """Execute a skill"""
    from app.skills.skill_executor import SkillExecutor
    executor = SkillExecutor()
    result = await executor.execute(skill_name, {})
    return {"skill": skill_name, "result": result}
