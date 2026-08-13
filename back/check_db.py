from config import settings
import pyodbc

def check_database():
    print("=" * 60)
    print("📊 CHECKING DATABASE CONTENTS")
    print("=" * 60)
    
    try:
        conn = pyodbc.connect(settings._odbc_connect(settings.DB_NAME))
        cursor = conn.cursor()
        
        # 1. Check all tables
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE='BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        tables = cursor.fetchall()
        
        print(f"\n📋 Tables in StegDB ({len(tables)} found):")
        if tables:
            for table in tables:
                # Get row count for each table
                table_name = table[0]
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                    count = cursor.fetchone()[0]
                    print(f"   - {table_name}: {count} rows")
                except:
                    print(f"   - {table_name}: (can't count)")
        else:
            print("   ❌ NO TABLES FOUND!")
            print("\n💡 This means your app hasn't created any tables yet.")
            print("   Check if your models are properly set up.")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    check_database()
