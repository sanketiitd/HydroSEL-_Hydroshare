import sqlite3

conn = sqlite3.connect('hydro_storage.db')
c = conn.cursor()

# Ensure the table exists
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')

# Insert the admin (using a try-except to avoid crashes if it already exists)
try:
    c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
              ('admin', 'password123', 'admin'))
    conn.commit()
    print("✅ Admin user 'admin' with password 'password123' created successfully!")
except sqlite3.IntegrityError:
    print("⚠️ User 'admin' already exists.")

conn.close()