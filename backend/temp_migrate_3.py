import sys
import sqlalchemy as sa
sys.path.append('f:\\Hospital Soft\\backend')
from database import engine
with engine.begin() as conn:
  try: conn.execute(sa.text('ALTER TABLE lab_reports ADD COLUMN results_data JSON DEFAULT ''[]''::json;'.replace(''[]'',''\'[]\''')))
  except Exception as e: print(e)

