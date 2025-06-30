#!/usr/bin/env python3
"""
Clean database initialization script for Hub Tracker
Run this script to create tables without sample data (production-ready)
"""

from app import app
from models import db

def init_clean_database():
    """Initialize database with tables only (no sample data)"""
    
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✅ Database tables created successfully!")
        print("🚀 Your Hub Tracker database is ready for use.")
        print("\nNext steps:")
        print("1. Run the application: python app.py")
        print("2. Navigate to http://localhost:5000")
        print("3. Create your first user account through the web interface")

if __name__ == "__main__":
    init_clean_database() 