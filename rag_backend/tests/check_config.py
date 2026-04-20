#!/usr/bin/env python3
import sys
sys.path.insert(0, '/app')

from app.core.config import settings

print('DATABASE_URL:', settings.DATABASE_URL)
print('PGBOUNCER_ENABLED:', settings.PGBOUNCER_ENABLED)
print('PGBOUNCER_HOST:', settings.PGBOUNCER_HOST)
print('POSTGRES_SERVER:', settings.POSTGRES_SERVER)
