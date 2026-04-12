from logging.config import fileConfig
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def get_url():
    return os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/rag_db"
    ).replace("+asyncpg", "").replace("+asyncpg", "")

config.set_main_option("sqlalchemy.url", get_url())

from app.db.base import Base
from app.models.policy import Policy
from app.models.policy_relation import PolicyRelation
from app.models.enterprise_policy_match import EnterprisePolicyMatch
from app.models.user_financial_data import UserFinancialData

target_metadata = Base.metadata

connectable = create_engine(get_url(), pool_pre_ping=True)

with connectable.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=target_metadata
    )

    with context.begin_transaction():
        context.run_migrations()
