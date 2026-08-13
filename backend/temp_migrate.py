import sys
import sqlalchemy as sa
sys.path.append('f:\\Hospital Soft\\backend')
from database import engine, Base
import models
Base.metadata.create_all(bind=engine)
print('Tables created/verified.')
commands = [
  'ALTER TABLE lab_samples ADD COLUMN container_type VARCHAR;',
  'ALTER TABLE lab_samples ADD COLUMN remarks VARCHAR;',
  'ALTER TABLE lab_orders ADD COLUMN status VARCHAR DEFAULT ''Pending'';',
  'ALTER TABLE lab_orders ADD COLUMN priority VARCHAR DEFAULT ''Routine'';',
  'ALTER TABLE lab_orders ADD COLUMN remarks VARCHAR;'
]
for cmd in commands:
  with engine.begin() as conn:
    try: conn.execute(sa.text(cmd))
    except Exception as e: print(e)

