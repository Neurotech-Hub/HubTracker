from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz

# Create db instance that will be initialized in app.py
db = SQLAlchemy()

# Time zone configuration
TIMEZONE = pytz.timezone('America/Chicago')

def get_current_time():
    """Get current time in Chicago timezone"""
    return datetime.now(TIMEZONE)

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    password = db.Column(db.String(255), nullable=True)  # Will implement hashing later
    
    # Relationships
    created_tasks = db.relationship('Task', foreign_keys='Task.created_by', backref='creator', lazy='dynamic')
    completed_tasks = db.relationship('Task', foreign_keys='Task.completed_by_user_id', backref='completer', lazy='dynamic')
    logs = db.relationship('Log', backref='user', lazy='dynamic')
    led_projects = db.relationship('Project', backref='project_leader', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.first_name} {self.last_name or ""}>'
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name or ''}".strip()

class Membership(db.Model):
    __tablename__ = 'memberships'
    
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.DateTime(timezone=True), nullable=True)
    is_annual = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relationships
    clients = db.relationship('Client', backref='membership', lazy='dynamic')
    
    def __repr__(self):
        return f'<Membership {self.id}>'

class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    membership_id = db.Column(db.Integer, db.ForeignKey('memberships.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    projects = db.relationship('Project', backref='client', lazy='dynamic')
    
    def __repr__(self):
        return f'<Client {self.name}>'

class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    project_lead_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)
    
    # Relationships
    tasks = db.relationship('Task', backref='project', lazy='dynamic')
    logs = db.relationship('Log', backref='project', lazy='dynamic')
    
    def __repr__(self):
        return f'<Project {self.name}>'

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    is_complete = db.Column(db.Boolean, default=False, nullable=False)
    completed_on = db.Column(db.DateTime(timezone=True), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    completed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)  # Adding project relationship
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    
    def __repr__(self):
        return f'<Task {self.description[:30]}...>'
    
    def mark_complete(self, user_id):
        """Mark task as complete by a user"""
        self.is_complete = True
        self.completed_by_user_id = user_id
        self.completed_on = get_current_time()

class Log(db.Model):
    __tablename__ = 'logs'
    
    id = db.Column(db.Integer, primary_key=True)
    notes = db.Column(db.Text, nullable=True)
    is_touch = db.Column(db.Boolean, default=False, nullable=False)
    hours = db.Column(db.Float, nullable=True)
    fixed_cost = db.Column(db.Numeric(10, 2), nullable=True)  # Fixed to 2 decimal places
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)  # Adding project relationship
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)
    
    def __repr__(self):
        return f'<Log {self.id} - {self.user.first_name if self.user else "Unknown"}>' 