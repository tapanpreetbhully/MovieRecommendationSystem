from database.db import get_connection

try:
    connection = get_connection()

    print("✅ MySQL connection successful!")

    connection.close()

except Exception as e:
    print("❌ MySQL connection failed!")
    print("Error:", e)