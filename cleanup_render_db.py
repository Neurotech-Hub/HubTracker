#!/usr/bin/env python3
"""
Script to clean up Render database and start fresh
Run this on Render to remove the old database and let start.py create a new one
"""

import os
import sys

def cleanup_render_database():
    print("🧹 Cleaning up Render database...")
    
    # Check if we're on Render (look for Render-specific environment)
    if not os.environ.get('RENDER'):
        print("⚠️  This script is designed for Render deployment")
        print("   It will delete the existing database file")
        response = input("   Are you sure you want to continue? (y/N): ")
        if response.lower() != 'y':
            print("❌ Aborted")
            return False
    
    # Paths to check
    instance_path = os.path.join(os.getcwd(), 'instance')
    old_db_path = os.path.join(instance_path, 'hub_tracker.db')
    new_db_path = os.path.join(instance_path, 'hubtracker.db')
    
    print(f"📁 Instance directory: {instance_path}")
    
    # Check what database files exist
    files_to_remove = []
    
    if os.path.exists(old_db_path):
        files_to_remove.append(old_db_path)
        print(f"🔍 Found old database: {old_db_path}")
    
    if os.path.exists(new_db_path):
        files_to_remove.append(new_db_path)
        print(f"🔍 Found new database: {new_db_path}")
    
    if not files_to_remove:
        print("✅ No database files found to remove")
        return True
    
    # Remove database files
    print("\n🗑️  Removing database files...")
    for db_file in files_to_remove:
        try:
            os.remove(db_file)
            print(f"✅ Removed: {db_file}")
        except Exception as e:
            print(f"❌ Failed to remove {db_file}: {e}")
            return False
    
    print("\n🎉 Database cleanup completed!")
    print("📝 Next steps:")
    print("   1. Deploy your updated code to Render")
    print("   2. The start.py script will create a fresh hubtracker.db")
    print("   3. Create your first admin user through the web interface")
    
    return True

if __name__ == '__main__':
    success = cleanup_render_database()
    sys.exit(0 if success else 1) 