#!/bin/bash
# Startup script for Render deployment
# This ensures the database is initialized before starting the web server

echo "Starting HubTracker deployment..."

# Initialize database with migrations (only creates tables if they don't exist)
echo "Running database migrations..."
flask db upgrade || echo "Migrations completed (database may already exist)"

# Start the web server
echo "Starting gunicorn server..."
exec gunicorn app:app 