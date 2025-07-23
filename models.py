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

# Association table for User-Equipment relationship
user_equipment = db.Table('user_equipment',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    db.Column('equipment_id', db.Integer, db.ForeignKey('equipment.id', ondelete='CASCADE'), primary_key=True),
    db.Column('created_at', db.DateTime(timezone=True), default=get_current_time, nullable=False)
)

class Equipment(db.Model):
    __tablename__ = 'equipment'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    manual = db.Column(db.String(255), nullable=True)  # URL to manual
    is_schedulable = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)
    
    # Relationships
    users = db.relationship('User', secondary=user_equipment, backref=db.backref('equipment', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Equipment {self.name}>'

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    role = db.Column(db.String(20), nullable=False, default='trainee')  # admin, trainee, finance
    password = db.Column(db.String(255), nullable=True)  # Will implement hashing later
    
    # Relationships
    created_tasks = db.relationship('Task', foreign_keys='Task.created_by', backref='creator', lazy='dynamic')
    assigned_tasks = db.relationship('Task', foreign_keys='Task.assigned_to', backref='assignee', lazy='dynamic')
    completed_tasks = db.relationship('Task', foreign_keys='Task.completed_by_user_id', backref='completer', lazy='dynamic')
    logs = db.relationship('Log', backref='user', lazy='dynamic')
    led_projects = db.relationship('Project', backref='project_leader', lazy='dynamic')
    pinned_projects = db.relationship('UserProjectPin', backref='user', lazy='dynamic')
    flagged_tasks = db.relationship('UserTaskFlag', backref='user', lazy='dynamic')
    preferences = db.relationship('UserPreferences', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
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
        
    @property
    def is_admin(self):
        """Helper property to maintain compatibility"""
        return self.role == 'admin'

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
    
    def update_status(self, new_status, user_id):
        """Update project status and log the change"""
        old_status = self.status
        self.status = new_status
        
        # Log the activity
        ActivityLog.log_activity(
            user_id=user_id,
            activity_type='project_status_change',
            entity_type='project',
            entity_id=self.id,
            old_value={'status': old_status},
            new_value={'status': new_status, 'name': self.name}
        )

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
    flags = db.relationship('UserTaskFlag', backref='task', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Task {self.description[:30]}...>'
    
    def mark_complete(self, user_id):
        """Mark task as complete by a user"""
        self.is_complete = True
        self.completed_by_user_id = user_id
        self.completed_on = get_current_time()
        
        # Log the activity
        ActivityLog.log_activity(
            user_id=user_id,
            activity_type='task_completed',
            entity_type='task',
            entity_id=self.id,
            new_value={
                'description': self.description,
                'project_id': self.project_id,
                'assigned_to': self.assigned_to
            }
        )
    
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

class UserPreferences(db.Model):
    __tablename__ = 'user_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    key = db.Column(db.String(50), nullable=False)  # Name of the preference (e.g., 'task_slider_position')
    value = db.Column(db.String(255), nullable=True)  # Value of the preference
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)
    
    # Ensure one preference key per user
    __table_args__ = (db.UniqueConstraint('user_id', 'key', name='unique_user_preference'),)
    
    def __repr__(self):
        return f'<UserPreferences {self.user_id}:{self.key}={self.value}>'

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)  # Who performed the action
    activity_type = db.Column(db.String(50), nullable=False)  # e.g., 'task_completed', 'project_status_change'
    entity_type = db.Column(db.String(50), nullable=False)  # e.g., 'task', 'project', 'user'
    entity_id = db.Column(db.Integer, nullable=False)  # ID of the affected record
    old_value = db.Column(db.JSON, nullable=True)  # Previous state
    new_value = db.Column(db.JSON, nullable=True)  # New state
    extra_data = db.Column(db.JSON, nullable=True)  # Additional context
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    
    # Relationships
    user = db.relationship('User', backref='activity_logs', lazy='joined')
    
    def __repr__(self):
        return f'<ActivityLog {self.activity_type} on {self.entity_type}:{self.entity_id}>'
    
    @classmethod
    def log_activity(cls, user_id, activity_type, entity_type, entity_id, old_value=None, new_value=None, extra_data=None):
        """Helper method to create activity log entries"""
        log = cls(
            user_id=user_id,
            activity_type=activity_type,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            extra_data=extra_data
        )
        db.session.add(log)
        return log

# Equipment Scheduling Models

class SchedulingSettings(db.Model):
    __tablename__ = 'scheduling_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    max_booking_duration_hours = db.Column(db.Float, default=4.0, nullable=False)
    min_booking_notice_hours = db.Column(db.Float, default=4.0, nullable=False)
    booking_advance_limit_days = db.Column(db.Integer, default=7, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)
    
    def __repr__(self):
        return f'<SchedulingSettings max_duration={self.max_booking_duration_hours}h, min_notice={self.min_booking_notice_hours}h, advance_limit={self.booking_advance_limit_days}d>'

class EquipmentOperatingHours(db.Model):
    __tablename__ = 'equipment_operating_hours'
    
    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)
    
    # Ensure one operating hours record per day
    __table_args__ = (db.UniqueConstraint('day_of_week', name='unique_day_hours'),)
    
    def __repr__(self):
        return f'<EquipmentOperatingHours day={self.day_of_week} {self.start_time}-{self.end_time}>'

class EquipmentBlockedDate(db.Model):
    __tablename__ = 'equipment_blocked_dates'
    
    id = db.Column(db.Integer, primary_key=True)
    blocked_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    is_annual_recurring = db.Column(db.Boolean, default=False, nullable=False)  # For holidays that recur yearly
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)
    
    def __repr__(self):
        return f'<EquipmentBlockedDate {self.blocked_date} - {self.reason}>'

class EquipmentAppointment(db.Model):
    __tablename__ = 'equipment_appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=False)
    purpose = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='approved', nullable=False)  # pending, approved, cancelled
    created_at = db.Column(db.DateTime(timezone=True), default=get_current_time, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=get_current_time, onupdate=get_current_time, nullable=False)
    
    # Relationships
    equipment = db.relationship('Equipment', backref='appointments')
    user = db.relationship('User', backref='equipment_appointments', lazy='joined')
    
    def __repr__(self):
        return f'<EquipmentAppointment {self.equipment.name if self.equipment else "Unknown"} - {self.user.full_name if self.user else "Unknown"} {self.start_time}>'
    
    @property
    def duration_hours(self):
        """Calculate duration in hours"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds() / 3600
        return 0 