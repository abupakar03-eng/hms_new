
import psycopg2
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

conn = psycopg2.connect('postgresql://postgres@127.0.0.1:5432/postgres')
cur = conn.cursor()
cur.execute('DELETE FROM users;')
conn.commit()

pw = pwd_context.hash('admin123')
cur.execute('INSERT INTO users (username, hashed_password, role, is_active) VALUES (%s, %s, %s, %s);', ('admin', pw, 'Admin', True))
conn.commit()
cur.close()
conn.close()
print('Users reset and default admin created!')

