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
    
    # Initialize database with migrations
    print("Running database migrations...")
    try:
        result = subprocess.run(['flask', 'db', 'upgrade'], 
                              capture_output=True, text=True, check=True)
        print("Database migrations completed successfully")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error running migrations: {e}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)
    
    # Start the web server
    print("Starting gunicorn server...")
    os.execvp('gunicorn', ['gunicorn', 'app:app'])

if __name__ == '__main__':
    main() 