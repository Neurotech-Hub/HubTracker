#!/usr/bin/env python3
"""
Test script to verify database setup
Run this to check if the database is properly configured
"""

import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

def test_database_setup():
    print("Testing database setup...")
    
    try:
        # Import Flask app
        from app import app, db
        
        with app.app_context():
            # Check if we can connect to the database
            print("✓ Flask app imported successfully")
            
            # Check if instance directory exists
            instance_path = app.instance_path
            print(f"✓ Instance path: {instance_path}")
            
            if not os.path.exists(instance_path):
                print(f"Creating instance directory: {instance_path}")
                os.makedirs(instance_path, exist_ok=True)
            
            # Check database URI
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
            print(f"✓ Database URI: {db_uri}")
            
            # Try to create tables
            print("Creating database tables...")
            db.create_all()
            print("✓ Database tables created successfully")
            
            # Test a simple query
            from models import User
            user_count = User.query.count()
            print(f"✓ Database query successful - Users: {user_count}")
            
            print("\n🎉 Database setup test completed successfully!")
            return True
            
    except Exception as e:
        print(f"❌ Database setup test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_database_setup()
    sys.exit(0 if success else 1) 