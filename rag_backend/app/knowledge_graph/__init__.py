# Knowledge Graph Module

from .entity_extractor import entity_extractor
from .relation_extractor import relation_extractor
from .neo4j_manager import neo4j_manager
from .coreference_resolver import coreference_resolver
from .kg_types import (
    EntityType,
    RelationType,
    ENTITY_TYPE_DESCRIPTIONS,
    RELATION_TYPE_DESCRIPTIONS,
    get_entity_type_prompt_block,
    get_relation_type_prompt_block,
)

__all__ = [
    'entity_extractor',
    'relation_extractor',
    'neo4j_manager',
    'coreference_resolver',
    'EntityType',
    'RelationType',
    'ENTITY_TYPE_DESCRIPTIONS',
    'RELATION_TYPE_DESCRIPTIONS',
    'get_entity_type_prompt_block',
    'get_relation_type_prompt_block',
]