# Add this to your test script to see exactly what's happening
import pyodbc
from config import settings

def debug_connection():
    print("=" * 60)
    print("🔍 DEBUGGING DATABASE CONNECTION")
    print("=" * 60)
    
    # Show what your settings think
    print(f"\n📋 Configuration Settings:")
    print(f"  Server: {settings.DB_SERVER}")
    print(f"  Database: {settings.DB_NAME}")
    print(f"  Driver: {settings.DB_DRIVER}")
    print(f"  Connection URL: {settings.database_url[:100]}...")
    
    try:
        # Connect using your config
        conn = pyodbc.connect(settings._odbc_connect(settings.DB_NAME))
        cursor = conn.cursor()
        
        # Check what database you're ACTUALLY connected to
        cursor.execute("SELECT DB_NAME()")
        current_db = cursor.fetchone()[0]
        print(f"\n✅ Currently connected to: '{current_db}'")
        
        # Check what databases exist
        cursor.execute("SELECT name FROM sys.databases WHERE name LIKE '%Steg%' OR name LIKE '%steg%'")
        matching_dbs = cursor.fetchall()
        print(f"\n📁 Databases matching 'Steg':")
        for db in matching_dbs:
            print(f"   - {db[0]}")
        
        # Check ALL databases
        cursor.execute("SELECT name FROM sys.databases ORDER BY name")
        all_dbs = cursor.fetchall()
        print(f"\n📁 All databases ({len(all_dbs)}):")
        for db in all_dbs:
            print(f"   - {db[0]}")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        
if __name__ == "__main__":
    debug_connection()