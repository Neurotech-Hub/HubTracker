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
    
    # Initialize database with migrations (only creates tables if they don't exist)
    print("Running database migrations...")
    try:
        result = subprocess.run(['flask', 'db', 'upgrade'], 
                              capture_output=True, text=True, check=True)
        print("Database migrations completed successfully")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running migrations: {e}")
        print(f"stderr: {e.stderr}")
        # Don't exit on migration errors - database might already exist
        print("Continuing with startup...")
    
    # Start the web server
    print("Starting gunicorn server...")
    os.execvp('gunicorn', ['gunicorn', 'app:app'])

if __name__ == '__main__':
    main() 