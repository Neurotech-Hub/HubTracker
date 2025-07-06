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
    
    # Debug: Check DATABASE_URL
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Mask password for security
        if '@' in database_url:
            parts = database_url.split('@')
            if ':' in parts[0]:
                user_pass = parts[0].split(':')
                if len(user_pass) >= 3:  # postgresql://user:pass@host
                    masked_url = f"{user_pass[0]}:{user_pass[1]}:***@{parts[1]}"
                else:
                    masked_url = f"{parts[0].split(':')[0]}:***@{parts[1]}"
            else:
                masked_url = database_url
        else:
            masked_url = database_url
        print(f"Database URL found: {masked_url}")
    else:
        print("ERROR: No DATABASE_URL found. PostgreSQL is required.")
        sys.exit(1)
    
    # Check if database has been migrated
    print("Checking database migration status...")
    
    try:
        result = subprocess.run(['flask', 'db', 'current'], 
                              capture_output=True, text=True, check=True)
        current_revision = result.stdout.strip()
        print(f"Current database revision: {current_revision}")
        
        # If we get a revision, database is initialized
        if current_revision and current_revision != "(None)" and "None" not in current_revision:
            print("Database is up to date, skipping migrations")
        else:
            print("Database needs migrations, running upgrade...")
            subprocess.run(['flask', 'db', 'upgrade'], check=True)
            print("Database migration completed")
            
    except subprocess.CalledProcessError as e:
        print(f"Migration check failed: {e}")
        print("Running initial database setup...")
        subprocess.run(['flask', 'db', 'upgrade'], check=True)
        print("Database setup completed")
    
    # Start the web server
    print("Starting gunicorn server...")
    os.execvp('gunicorn', ['gunicorn', 'app:app'])

if __name__ == '__main__':
    main() 