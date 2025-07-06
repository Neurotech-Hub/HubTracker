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
    
    # Check if database already exists and has been migrated
    print("Checking database status...")
    try:
        # Check current migration status
        result = subprocess.run(['flask', 'db', 'current'], 
                              capture_output=True, text=True, check=True)
        current_revision = result.stdout.strip()
        print(f"Current database revision: {current_revision}")
        
        # Only run migrations if we're not at the latest revision
        if current_revision == "(None)" or "None" in current_revision:
            print("Database needs initialization, running migrations...")
            subprocess.run(['flask', 'db', 'upgrade'], check=True)
            print("Database initialization completed")
        else:
            print("Database is up to date, skipping migrations")
            
    except subprocess.CalledProcessError as e:
        print(f"Database check failed: {e}")
        print("Attempting to initialize database...")
        try:
            subprocess.run(['flask', 'db', 'upgrade'], check=True)
            print("Database initialization completed")
        except subprocess.CalledProcessError as e2:
            print(f"Database initialization failed: {e2}")
            print("Continuing with startup anyway...")
    
    # Start the web server
    print("Starting gunicorn server...")
    os.execvp('gunicorn', ['gunicorn', 'app:app'])

if __name__ == '__main__':
    main() 