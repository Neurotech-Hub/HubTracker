#!/usr/bin/env python3
"""
Production Database Sync Utility for HubTracker

This script safely syncs production data from Render PostgreSQL to your local development database.
It will:
1. Create a backup of the production database
2. Drop and recreate your local database 
3. Restore the production data locally

WARNING: This will completely replace your local database with production data!
"""

import os
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

def get_database_components(database_url):
    """Parse database URL into components"""
    if not database_url or not database_url.strip():
        raise ValueError("Database URL cannot be empty")
    
    parsed = urlparse(database_url.strip())
    
    # Validate required components
    if not parsed.hostname:
        raise ValueError("Invalid database URL: missing hostname")
    if not parsed.username:
        raise ValueError("Invalid database URL: missing username")
    if not parsed.password:
        raise ValueError("Invalid database URL: missing password")
    if not parsed.path or len(parsed.path) <= 1:
        raise ValueError("Invalid database URL: missing database name")
    
    return {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'database': parsed.path[1:],  # Remove leading slash
        'username': parsed.username,
        'password': parsed.password
    }

def run_command(cmd, env=None, capture_output=False):
    """Run a shell command with proper error handling"""
    # Check for None values in command
    if any(arg is None for arg in cmd):
        print(f"Error: Command contains None values: {cmd}")
        return False
    
    print(f"Running: {' '.join(str(arg) for arg in cmd)}")
    try:
        if capture_output:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, env=env, check=True)
            return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        if capture_output and e.stderr:
            print(f"Error output: {e.stderr}")
        return False

def test_connection(db_components, description):
    """Test if we can connect to a database"""
    print(f"\n🔍 Testing connection to {description}...")
    
    env = os.environ.copy()
    env['PGPASSWORD'] = db_components['password']
    
    # Use PostgreSQL 16 tools for compatibility
    psql_path = '/opt/homebrew/opt/postgresql@16/bin/psql'
    if not os.path.exists(psql_path):
        psql_path = 'psql'  # Fallback to system PATH
    
    cmd = [
        psql_path,
        '-h', db_components['host'],
        '-p', str(db_components['port']),
        '-U', db_components['username'],
        '-d', db_components['database'],
        '-c', 'SELECT version();'
    ]
    
    return run_command(cmd, env=env, capture_output=True)

def create_backup(prod_components, backup_file):
    """Create a backup of the production database"""
    print(f"\n📦 Creating backup of production database...")
    
    env = os.environ.copy()
    env['PGPASSWORD'] = prod_components['password']
    
    # Use PostgreSQL 16 tools for compatibility
    pg_dump_path = '/opt/homebrew/opt/postgresql@16/bin/pg_dump'
    if not os.path.exists(pg_dump_path):
        pg_dump_path = 'pg_dump'  # Fallback to system PATH
    
    cmd = [
        pg_dump_path,
        '-h', prod_components['host'],
        '-p', str(prod_components['port']),
        '-U', prod_components['username'],
        '-d', prod_components['database'],
        '--clean',  # Include DROP statements
        '--if-exists',  # Don't error if objects don't exist
        '--no-owner',  # Don't try to set ownership
        '--no-privileges',  # Don't try to set privileges
        '-f', backup_file
    ]
    
    return run_command(cmd, env=env)

def restore_backup(local_components, backup_file):
    """Restore backup to local database"""
    print(f"\n🔄 Restoring backup to local database...")
    
    env = os.environ.copy()
    env['PGPASSWORD'] = local_components['password']
    
    # Use PostgreSQL 16 tools for compatibility
    psql_path = '/opt/homebrew/opt/postgresql@16/bin/psql'
    if not os.path.exists(psql_path):
        psql_path = 'psql'  # Fallback to system PATH
    
    # First, restore the backup
    cmd = [
        psql_path,
        '-h', local_components['host'],
        '-p', str(local_components['port']),
        '-U', local_components['username'],
        '-d', local_components['database'],
        '-f', backup_file
    ]
    
    return run_command(cmd, env=env)

def main():
    print("🚀 HubTracker Production Database Sync Utility")
    print("=" * 50)
    
    # Get production database URL
    print("\n📡 Production Database Connection")
    print("Expected format: postgresql://username:password@hostname:port/database")
    prod_url = input("Enter your Render PostgreSQL URL: ").strip()
    
    if not prod_url:
        print("❌ No database URL provided. Exiting.")
        sys.exit(1)
    
    # Parse URLs
    try:
        prod_components = get_database_components(prod_url)
        print(f"🔍 Debug - Parsed components: {prod_components}")
    except Exception as e:
        print(f"❌ Invalid production database URL: {e}")
        sys.exit(1)
    
    # Local database components (from our setup)
    local_components = {
        'host': 'localhost',
        'port': 5432,
        'database': 'hubtracker_dev',
        'username': 'hubtracker_user',
        'password': 'dev_password_2024'
    }
    
    print(f"\n📋 Configuration:")
    print(f"Production: {prod_components['username']}@{prod_components['host']}:{prod_components['port']}/{prod_components['database']}")
    print(f"Local: {local_components['username']}@{local_components['host']}:{local_components['port']}/{local_components['database']}")
    
    # Test connections
    print(f"\n🔍 Testing connections...")
    
    if not test_connection(prod_components, "production database"):
        print("❌ Cannot connect to production database. Please check your URL and network connection.")
        sys.exit(1)
    print("✅ Production database connection successful")
    
    if not test_connection(local_components, "local database"):
        print("❌ Cannot connect to local database. Please ensure PostgreSQL is running and credentials are correct.")
        sys.exit(1)
    print("✅ Local database connection successful")
    
    # Final confirmation
    print(f"\n⚠️  WARNING: This will completely replace your local database with production data!")
    print(f"Local database '{local_components['database']}' will be overwritten.")
    
    confirm = input("\nAre you sure you want to continue? Type 'yes' to proceed: ").strip().lower()
    if confirm != 'yes':
        print("❌ Operation cancelled.")
        sys.exit(0)
    
    # Create temporary backup file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as temp_file:
        backup_file = temp_file.name
    
    try:
        # Step 1: Create backup
        if not create_backup(prod_components, backup_file):
            print("❌ Failed to create backup of production database")
            sys.exit(1)
        print("✅ Production database backup created")
        
        # Step 2: Restore to local
        if not restore_backup(local_components, backup_file):
            print("❌ Failed to restore backup to local database")
            sys.exit(1)
        print("✅ Production data restored to local database")
        
        print(f"\n🎉 Database sync completed successfully!")
        print(f"Your local database now contains the production data.")
        
    except KeyboardInterrupt:
        print(f"\n❌ Operation cancelled by user")
        sys.exit(1)
    
    finally:
        # Clean up temporary file
        if os.path.exists(backup_file):
            os.unlink(backup_file)
            print(f"🧹 Cleaned up temporary backup file")

if __name__ == '__main__':
    main() 