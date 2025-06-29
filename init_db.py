#!/usr/bin/env python3
"""
Database initialization script for Hub Tracker
Run this script to create tables and populate with sample data
"""

from app import app
from models import db, User, Client, Membership, Project, Task, Log
from datetime import datetime, timedelta
import pytz

# Time zone configuration
TIMEZONE = pytz.timezone('America/Chicago')

def init_database():
    """Initialize database with tables and sample data"""
    
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        
        # Check if data already exists
        if User.query.first():
            print("Database already contains data. Skipping sample data creation.")
            return
        
        print("Adding sample data...")
        
        # Create sample memberships
        membership1 = Membership(
            start_date=datetime.now(TIMEZONE) - timedelta(days=365),
            is_annual=True
        )
        membership2 = Membership(
            start_date=datetime.now(TIMEZONE) - timedelta(days=90),
            is_annual=False
        )
        
        db.session.add_all([membership1, membership2])
        db.session.commit()
        
        # Create sample users
        users = [
            User(first_name="John", last_name="Smith", is_admin=True),
            User(first_name="Sarah", last_name="Johnson", is_admin=False),
            User(first_name="Mike", last_name="Brown", is_admin=False),
            User(first_name="Emily", last_name="Davis", is_admin=False),
            User(first_name="Alex", last_name="", is_admin=False),  # Test user with no last name
        ]
        
        db.session.add_all(users)
        db.session.commit()
        
        # Create sample clients
        clients = [
            Client(
                name="TechCorp Industries", 
                membership_id=membership1.id,
                notes="Large technology company specializing in software development"
            ),
            Client(
                name="Green Valley Labs", 
                membership_id=membership2.id,
                notes="Research laboratory focused on environmental sustainability"
            ),
            Client(
                name="City Medical Center", 
                membership_id=membership1.id,
                notes="Healthcare facility requiring digital transformation"
            ),
            Client(
                name="StartupX", 
                membership_id=None,
                notes="Early-stage startup in fintech space"
            ),
        ]
        
        db.session.add_all(clients)
        db.session.commit()
        
        # Create sample projects
        projects = [
            Project(
                name="Website Redesign",
                client_id=clients[0].id,
                project_lead_id=users[1].id,
                notes="Complete overhaul of company website with modern design"
            ),
            Project(
                name="Mobile App Development",
                client_id=clients[0].id,
                project_lead_id=users[2].id,
                notes="Native iOS and Android application for customer engagement"
            ),
            Project(
                name="Data Analytics Platform",
                client_id=clients[1].id,
                project_lead_id=users[1].id,
                notes="Custom analytics solution for research data processing"
            ),
            Project(
                name="Patient Portal System",
                client_id=clients[2].id,
                project_lead_id=users[3].id,
                notes="Online portal for patients to access medical records"
            ),
            Project(
                name="MVP Development",
                client_id=clients[3].id,
                project_lead_id=users[2].id,
                notes="Minimum viable product for fintech application"
            ),
        ]
        
        db.session.add_all(projects)
        db.session.commit()
        
        # Create sample tasks
        tasks = [
            Task(
                description="Create wireframes for homepage",
                project_id=projects[0].id,
                created_by=users[1].id,
                is_complete=True,
                completed_by_user_id=users[1].id,
                completed_on=datetime.now(TIMEZONE) - timedelta(days=2)
            ),
            Task(
                description="Implement user authentication",
                project_id=projects[1].id,
                created_by=users[2].id,
                is_complete=False
            ),
            Task(
                description="Set up database schema",
                project_id=projects[2].id,
                created_by=users[1].id,
                is_complete=True,
                completed_by_user_id=users[3].id,
                completed_on=datetime.now(TIMEZONE) - timedelta(hours=6)
            ),
            Task(
                description="Design patient dashboard",
                project_id=projects[3].id,
                created_by=users[3].id,
                is_complete=False
            ),
        ]
        
        db.session.add_all(tasks)
        db.session.commit()
        
        # Create sample logs
        logs = [
            Log(
                notes="Initial project setup and planning meeting",
                hours=2.5,
                user_id=users[1].id,
                project_id=projects[0].id,
                created_at=datetime.now(TIMEZONE) - timedelta(days=3)
            ),
            Log(
                notes="Code review and bug fixes",
                hours=1.5,
                user_id=users[2].id,
                project_id=projects[1].id,
                created_at=datetime.now(TIMEZONE) - timedelta(days=1)
            ),
            Log(
                notes="Client consultation call",
                is_touch=True,
                user_id=users[1].id,
                project_id=projects[2].id,
                created_at=datetime.now(TIMEZONE) - timedelta(hours=4)
            ),
            Log(
                notes="Database optimization work",
                hours=3.0,
                fixed_cost=150.00,
                user_id=users[3].id,
                project_id=projects[3].id,
                created_at=datetime.now(TIMEZONE) - timedelta(hours=8)
            ),
        ]
        
        db.session.add_all(logs)
        db.session.commit()
        
        print("Sample data created successfully!")
        print("\nSample Users:")
        for user in users:
            admin_status = " (Admin)" if user.is_admin else ""
            print(f"  - {user.full_name}{admin_status}")
        
        print(f"\nSample Clients: {len(clients)}")
        print(f"Sample Projects: {len(projects)}")
        print(f"Sample Tasks: {len(tasks)}")
        print(f"Sample Logs: {len(logs)}")

if __name__ == "__main__":
    init_database() 