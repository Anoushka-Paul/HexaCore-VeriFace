import sqlite3

conn = sqlite3.connect('veriface_auth.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('tables:', cur.fetchall())
try:
    cur.execute('SELECT id, username, role FROM users')
    rows = cur.fetchall()
    print('users:', rows)
except Exception as e:
    print('users select error:', e)
conn.close()