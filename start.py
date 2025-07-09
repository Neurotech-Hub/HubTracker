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
    
    # Run database migrations
    print("Running database migrations...")
    try:
        subprocess.run(['flask', 'db', 'upgrade'], check=True)
        print("Database migrations completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Migration failed: {e}")
        print(f"Error output: {e.stderr}")
        print("Continuing anyway - database may already be up to date...")
    
    # Start the web server
    print("Starting gunicorn server...")
    os.execvp('gunicorn', ['gunicorn', 'app:app'])

if __name__ == '__main__':
    main() 