#!/usr/bin/env python3
"""
Startup script for Render deployment
This ensures the database is initialized before starting the web server
"""

import os
import sys
import subprocess

def main():
    print("Starting HubTracker deployment...")
    
    # Ensure instance directory exists
    instance_path = os.path.join(os.getcwd(), 'instance')
    if not os.path.exists(instance_path):
        print(f"Creating instance directory: {instance_path}")
        os.makedirs(instance_path, exist_ok=True)
    
    # Set Flask environment variables
    os.environ['FLASK_APP'] = 'app.py'
    os.environ['FLASK_ENV'] = 'production'
    
    # Check if database already exists and has been migrated
    print("Checking database status...")
    
    # Check if database file exists and has tables
    db_path = os.path.join(instance_path, 'hubtracker.db')
    db_exists = os.path.exists(db_path)
    print(f"Database file exists: {db_exists}")
    
    if db_exists:
        # Check if database has any tables by trying to get migration status
        try:
            result = subprocess.run(['flask', 'db', 'current'], 
                                  capture_output=True, text=True, check=True)
            current_revision = result.stdout.strip()
            print(f"Current database revision: {current_revision}")
            
            # If we get a revision, database is initialized
            if current_revision and current_revision != "(None)" and "None" not in current_revision:
                print("Database is up to date, skipping migrations")
            else:
                print("Database exists but needs migrations, running upgrade...")
                subprocess.run(['flask', 'db', 'upgrade'], check=True)
                print("Database migration completed")
                
        except subprocess.CalledProcessError as e:
            print(f"Migration check failed: {e}")
            print("Database file exists but may be empty, running migrations...")
            subprocess.run(['flask', 'db', 'upgrade'], check=True)
            print("Database migration completed")
    else:
        # Database doesn't exist, create it with migrations
        print("Database doesn't exist, creating with migrations...")
        subprocess.run(['flask', 'db', 'upgrade'], check=True)
        print("Database created and initialized")
    
    # Start the web server
    print("Starting gunicorn server...")
    os.execvp('gunicorn', ['gunicorn', 'app:app'])

if __name__ == '__main__':
    main() 