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
    email = db.Column(db.String(120), nullable=False, unique=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    password = db.Column(db.String(255), nullable=True)  # Will implement hashing later
    
    # Relationships
    created_tasks = db.relationship('Task', foreign_keys='Task.created_by', backref='creator', lazy='dynamic')
    assigned_tasks = db.relationship('Task', foreign_keys='Task.assigned_to', backref='assignee', lazy='dynamic')
    completed_tasks = db.relationship('Task', foreign_keys='Task.completed_by_user_id', backref='completer', lazy='dynamic')
    logs = db.relationship('Log', backref='user', lazy='dynamic')
    led_projects = db.relationship('Project', backref='project_leader', lazy='dynamic')
    pinned_projects = db.relationship('UserProjectPin', backref='user', lazy='dynamic')
    flagged_tasks = db.relationship('UserTaskFlag', backref='user', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.first_name} {self.last_name or ""}>'
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name or ''}".strip()
    
    def set_last_name(self, value):
        """Set last_name, converting empty strings to None"""
        self.last_name = value.strip() if value and value.strip() else None

    def check_password(self, password):
        """Check if provided password matches user's password"""
        # For now, simple plaintext comparison
        # TODO: Implement proper password hashing
        return self.password == password

    def set_password(self, password):
        """Set user's password"""
        # For now, store plaintext
        # TODO: Implement proper password hashing
        self.password = password

class Membership(db.Model):
    __tablename__ = 'memberships'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime(timezone=True), nullable=True)
    is_annual = db.Column(db.Boolean, default=False, nullable=False)
    cost = db.Column(db.Float, nullable=True)  # Monthly or annual cost
    time = db.Column(db.Integer, nullable=True)  # Time budget in hours
    budget = db.Column(db.Float, nullable=True)  # Dollar budget
    notes = db.Column(db.Text, nullable=True)  # Markdown-enabled notes
    status = db.Column(db.String(20), default='Active', server_default='Active', nullable=False)  # Active, Pending, Archived
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)
    
    # Relationships
    clients = db.relationship('Client', backref='membership', lazy='dynamic')
    supplements = db.relationship('MembershipSupplement', backref='membership', lazy='dynamic')
    
    def __repr__(self):
        return f'<Membership {self.title}>'
    
    @property
    def total_budget(self):
        """Get total budget including supplements"""
        base = self.budget or 0
        supplements = sum(s.budget or 0 for s in self.supplements)
        return base + supplements
    
    @property
    def total_time(self):
        """Get total time budget including supplements"""
        base = self.time or 0
        supplements = sum(s.time or 0 for s in self.supplements)
        return base + supplements
    
    @property
    def used_budget(self):
        """Calculate used budget from logs"""
        from sqlalchemy import func
        total = db.session.query(func.sum(Log.fixed_cost)).join(
            Project, Project.id == Log.project_id
        ).join(
            Client, Client.id == Project.client_id
        ).filter(
            Client.membership_id == self.id,
            Log.fixed_cost.isnot(None)
        ).scalar()
        return float(total) if total else 0
    
    @property
    def used_time(self):
        """Calculate used time from logs"""
        from sqlalchemy import func
        total = db.session.query(func.sum(Log.hours)).join(
            Project, Project.id == Log.project_id
        ).join(
            Client, Client.id == Project.client_id
        ).filter(
            Client.membership_id == self.id,
            Log.hours.isnot(None)
        ).scalar()
        return float(total) if total else 0
    
    @property
    def remaining_budget(self):
        """Calculate remaining budget"""
        return self.total_budget - self.used_budget
    
    @property
    def remaining_time(self):
        """Calculate remaining time"""
        return self.total_time - self.used_time

class MembershipSupplement(db.Model):
    __tablename__ = 'membership_supplements'
    
    id = db.Column(db.Integer, primary_key=True)
    membership_id = db.Column(db.Integer, db.ForeignKey('memberships.id', ondelete='CASCADE'), nullable=False)
    budget = db.Column(db.Float, nullable=True)  # Additional dollar budget
    time = db.Column(db.Integer, nullable=True)  # Additional time budget in hours
    notes = db.Column(db.Text, nullable=True)  # Optional notes about the supplement
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)
    
    def __repr__(self):
        return f'<MembershipSupplement {self.id} for Membership {self.membership_id}>'

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
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id', ondelete='CASCADE'), nullable=False)
    project_lead_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(20), default='Active', server_default='Active', nullable=True)  # Active, Prospective, Archived
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)
    
    # Relationships
    tasks = db.relationship('Task', backref='project', lazy='dynamic')
    logs = db.relationship('Log', backref='project', lazy='dynamic')
    pins = db.relationship('UserProjectPin', backref='project', lazy='dynamic')
    
    def __repr__(self):
        return f'<Project {self.name}>'

class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)  # Task description with tags (@[User] and #[Project])
    is_complete = db.Column(db.Boolean, default=False, nullable=False)
    completed_on = db.Column(db.DateTime(timezone=True), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)  # Task assignment
    completed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True)  # Adding project relationship
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    
    # Relationships
    flags = db.relationship('UserTaskFlag', backref='task', lazy='dynamic')
    
    def __repr__(self):
        return f'<Task {self.description[:30]}...>'
    
    def mark_complete(self, user_id):
        """Mark task as complete by a user"""
        self.is_complete = True
        self.completed_by_user_id = user_id
        self.completed_on = get_current_time()
    
    def toggle_complete(self, user_id):
        """Toggle task completion status"""
        if self.is_complete:
            self.is_complete = False
            self.completed_by_user_id = None
            self.completed_on = None
        else:
            self.mark_complete(user_id)

class Log(db.Model):
    __tablename__ = 'logs'
    
    id = db.Column(db.Integer, primary_key=True)
    notes = db.Column(db.Text, nullable=True)
    is_touch = db.Column(db.Boolean, default=False, nullable=False)
    hours = db.Column(db.Float, nullable=True)
    fixed_cost = db.Column(db.Numeric(10, 2), nullable=True)  # Fixed to 2 decimal places
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True)  # Adding project relationship
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)
    
    def __repr__(self):
        return f'<Log {self.id} - {self.user.first_name if self.user else "Unknown"}>'

class UserProjectPin(db.Model):
    __tablename__ = 'user_project_pins'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    
    # Ensure one pin per user-project pair
    __table_args__ = (db.UniqueConstraint('user_id', 'project_id', name='unique_user_project_pin'),)
    
    def __repr__(self):
        return f'<UserProjectPin {self.user_id}:{self.project_id}>'

class UserTaskFlag(db.Model):
    __tablename__ = 'user_task_flags'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    
    # Ensure one flag per user-task pair
    __table_args__ = (db.UniqueConstraint('user_id', 'task_id', name='unique_user_task_flag'),)
    
    def __repr__(self):
        return f'<UserTaskFlag {self.user_id}:{self.task_id}>' 