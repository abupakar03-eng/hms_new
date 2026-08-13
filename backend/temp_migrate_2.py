import sys
import sqlalchemy as sa
sys.path.append('f:\\Hospital Soft\\backend')
from database import engine
with engine.begin() as conn:
  try: conn.execute(sa.text('ALTER TABLE patients ADD COLUMN details JSON DEFAULT ''{}'';'.replace(''{}'',''\'{}\'')))
  except Exception as e: print(e)

