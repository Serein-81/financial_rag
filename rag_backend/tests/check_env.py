#!/usr/bin/env python3
import os
print('PGBOUNCER_ENABLED:', os.getenv('PGBOUNCER_ENABLED'))
print('PGBOUNCER_HOST:', os.getenv('PGBOUNCER_HOST'))
print('POSTGRES_SERVER:', os.getenv('POSTGRES_SERVER'))
