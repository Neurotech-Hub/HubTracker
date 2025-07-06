#!/bin/bash
# Startup script for Render deployment
# This ensures the database is initialized before starting the web server

echo "Starting HubTracker deployment..."

# Initialize database with migrations
echo "Running database migrations..."
flask db upgrade

# Start the web server
echo "Starting gunicorn server..."
gunicorn app:app 