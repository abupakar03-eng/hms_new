
import psycopg2

conn = psycopg2.connect('postgresql://postgres@127.0.0.1:5432/postgres')
cur = conn.cursor()
cur.execute('UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;')
conn.commit()
cur.close()
conn.close()
print('Users created_at fixed!')

