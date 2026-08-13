
from backend.database import SessionLocal
import backend.models as models
from backend.auth import get_password_hash

db = SessionLocal()
db.query(models.User).delete()
db.commit()

admin = models.User(
    username='admin',
    hashed_password=get_password_hash('admin123'),
    role='Admin',
    is_active=True
)
db.add(admin)
db.commit()
print('Users reset and default admin created: admin/admin123')

