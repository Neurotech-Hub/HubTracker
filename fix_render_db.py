#!/usr/bin/env python3
"""
Script to manually fix Render database by running migrations
Run this on Render to initialize the database tables
"""

import os
import sys
import subprocess

def fix_render_database():
    print("🔧 Fixing Render database...")
    
    # Set Flask environment variables
    os.environ['FLASK_APP'] = 'app.py'
    os.environ['FLASK_ENV'] = 'production'
    
    # Ensure instance directory exists
    instance_path = os.path.join(os.getcwd(), 'instance')
    if not os.path.exists(instance_path):
        print(f"Creating instance directory: {instance_path}")
        os.makedirs(instance_path, exist_ok=True)
    
    print(f"📁 Instance directory: {instance_path}")
    
    # Check database file
    db_path = os.path.join(instance_path, 'hubtracker.db')
    if os.path.exists(db_path):
        print(f"✅ Database file exists: {db_path}")
    else:
        print(f"❌ Database file not found: {db_path}")
        return False
    
    # Run migrations to create tables
    print("\n🔄 Running database migrations...")
    try:
        subprocess.run(['flask', 'db', 'upgrade'], check=True)
        print("✅ Database migrations completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Database migration failed: {e}")
        return False
    
    # Verify tables were created
    print("\n🔍 Verifying database tables...")
    try:
        result = subprocess.run(['flask', 'db', 'current'], 
                              capture_output=True, text=True, check=True)
        current_revision = result.stdout.strip()
        print(f"✅ Current database revision: {current_revision}")
        
        if current_revision and current_revision != "(None)" and "None" not in current_revision:
            print("🎉 Database is properly initialized!")
            return True
        else:
            print("❌ Database still not properly initialized")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Could not verify database: {e}")
        return False

if __name__ == '__main__':
    success = fix_render_database()
    sys.exit(0 if success else 1) 