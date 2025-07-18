from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_migrate import Migrate
from datetime import datetime
import pytz
import os
import markdown
from sqlalchemy import func, desc, text
import re
from markupsafe import Markup
import json

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, continue without it

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
# Configure database URI - use instance directory for SQLite
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # Convert postgres:// to postgresql:// for newer SQLAlchemy versions
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    # Convert to use psycopg driver for psycopg3
    if DATABASE_URL.startswith('postgresql://'):
        DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # For local development and Render with SQLite
    instance_path = os.path.join(app.instance_path, 'hubtracker.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{instance_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import models and db
from models import db, User, Client, Membership, Project, Task, Log, UserProjectPin, UserTaskFlag, TIMEZONE, get_current_time, MembershipSupplement, Equipment, UserPreferences, ActivityLog

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)

# Template context processors
@app.context_processor
def inject_pinned_projects():
    def get_pinned_projects():
        if 'user_id' not in session:
            return []
        
        # Get pinned projects for current user
        pinned_project_ids = UserProjectPin.query.filter_by(
            user_id=session['user_id']
        ).all()
        
        project_ids = [pin.project_id for pin in pinned_project_ids]
        
        if not project_ids:
            return []
        
        # Get the actual projects with client info
        pinned_projects = Project.query.join(Client).filter(
            Project.id.in_(project_ids)
        ).order_by(Project.name.asc()).all()
        
        # Add open tasks count to each pinned project
        for project in pinned_projects:
            project.open_tasks_count = project.tasks.filter_by(is_complete=False).count()
        
        return pinned_projects
    
    def has_logged_today():
        if 'user_id' not in session:
            return True  # Don't show animation if not logged in
        
        today_start = get_current_time().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = get_current_time().replace(hour=23, minute=59, second=59, microsecond=999999)
        
        has_logs = Log.query.filter(
            Log.user_id == session['user_id'],
            Log.created_at.between(today_start, today_end)
        ).first() is not None
        
        return has_logs
    
    def should_show_log_reminder():
        if 'user_id' not in session:
            return False  # Don't show reminder if not logged in
        
        current_time = get_current_time()
        
        # Only show reminder after 12PM (noon) Chicago time
        if current_time.hour < 12:
            return False
        
        # Check if user has logged today
        today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = current_time.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        has_logs = Log.query.filter(
            Log.user_id == session['user_id'],
            Log.created_at.between(today_start, today_end)
        ).first() is not None
        
        return not has_logs
    
    return dict(
        get_pinned_projects=get_pinned_projects,
        has_logged_today=has_logged_today(),
        should_show_log_reminder=should_show_log_reminder()
    )

# Template filters
@app.template_filter('markdown')
def markdown_filter(text):
    """Convert markdown text to HTML"""
    if not text:
        return ''
    return markdown.markdown(text, extensions=['nl2br', 'fenced_code'])

@app.template_filter('render_tags')
def render_tags(value):
    value = re.sub(r'@\[(.*?)\]', r'<span class="task-tag task-tag-user">@\1</span>', value)
    value = re.sub(r'#\[(.*?)\]', r'<span class="task-tag task-tag-project">#\1</span>', value)
    return Markup(value)

@app.template_filter('time_ago')
def time_ago(datetime_obj):
    """Convert datetime to 'time ago' format"""
    if not datetime_obj:
        return ''
    
    from datetime import datetime
    now = get_current_time()
    diff = now - datetime_obj
    
    if diff.days > 0:
        if diff.days == 1:
            return '1 day ago'
        else:
            return f'{diff.days} days ago'
    elif diff.seconds >= 3600:
        hours = diff.seconds // 3600
        if hours == 1:
            return '1 hour ago'
        else:
            return f'{hours} hours ago'
    elif diff.seconds >= 60:
        minutes = diff.seconds // 60
        if minutes == 1:
            return '1 minute ago'
        else:
            return f'{minutes} minutes ago'
    else:
        return 'just now'

@app.template_filter('currency')
def currency_filter(value):
    """Format number as currency with commas and 2 decimal places"""
    if value is None:
        return '$0.00'
    
    try:
        # Convert to float and format with commas and 2 decimal places
        formatted = "${:,.2f}".format(float(value))
        return formatted
    except (ValueError, TypeError):
        return '$0.00'

# Add global functions to Jinja2 environment
app.jinja_env.globals.update(min=min)
app.jinja_env.filters['markdown'] = markdown_filter
app.jinja_env.filters['render_tags'] = render_tags
app.jinja_env.filters['time_ago'] = time_ago
app.jinja_env.filters['currency'] = currency_filter

@app.route('/')
def index():
    # Public landing page - show general metrics without sensitive data
    from datetime import timedelta
    from sqlalchemy import func
    
    # Get public-friendly metrics
    total_projects = Project.query.filter_by(status='Active').count()  # Only active projects
    total_clients = Client.query.count()
    total_active_projects = Project.query.filter_by(status='Active').count()
    total_users = User.query.count()
    total_memberships = Membership.query.filter_by(status='Active').count()
    open_tasks = Task.query.filter_by(is_complete=False).count()
    total_equipment = Equipment.query.count()
    
    # Last 30 days activity (including today)
    thirty_days_ago = get_current_time() - timedelta(days=29)  # Changed from 30 to 29
    
    # Tasks completed in last 30 days (general count)
    tasks_completed_recently = Task.query.filter(
        Task.completed_on >= thirty_days_ago,
        Task.is_complete == True
    ).count()
    
    # Get daily task completion for chart (last 30 days, including today)
    activity_data = []
    for i in range(30):  # Back to 30 days
        date = thirty_days_ago + timedelta(days=i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        daily_tasks = Task.query.filter(
            Task.completed_on >= date_start,
            Task.completed_on < date_end,
            Task.is_complete == True
        ).count()
        
        activity_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'tasks': daily_tasks
        })
    
    # Get trends data for chart (last 30 days) - Hours Logged and Projects Touched
    trends_data = []
    for i in range(30):
        date = thirty_days_ago + timedelta(days=i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        # Calculate total hours logged for this day (including touch logs as 0.5 hours each)
        detailed_hours = db.session.query(func.sum(Log.hours)).filter(
            Log.created_at >= date_start,
            Log.created_at < date_end,
            Log.is_touch.is_(False),
            Log.hours.isnot(None)
        ).scalar() or 0
        
        touch_count = db.session.query(func.count(Log.id)).filter(
            Log.created_at >= date_start,
            Log.created_at < date_end,
            Log.is_touch.is_(True)
        ).scalar() or 0
        
        # Convert touch logs to hours (30 minutes each)
        touch_hours = touch_count * 0.5
        total_hours = detailed_hours + touch_hours
        
        # Calculate projects touched based on activity logs
        projects_touched = set()
        
        try:
            # Get activity logs for this day
            daily_activities = ActivityLog.query.filter(
                ActivityLog.created_at >= date_start,
                ActivityLog.created_at < date_end
            ).all()
            
            for activity in daily_activities:
                project_id = None
                
                if activity.activity_type == 'task_completed':
                    # Get project from task
                    if activity.new_value and 'project_id' in activity.new_value:
                        project_id = activity.new_value['project_id']
                
                elif activity.activity_type == 'project_status_change':
                    # Entity_id is the project_id
                    project_id = activity.entity_id
                
                elif activity.activity_type in ['time_logged', 'touch_logged']:
                    # Get project from log entry
                    if activity.entity_type == 'log':
                        log_entry = db.session.get(Log, activity.entity_id)
                        if log_entry:
                            project_id = log_entry.project_id
                
                if project_id:
                    projects_touched.add(project_id)
        
        except Exception as e:
            # If ActivityLog table doesn't exist or there's an error, default to 0
            projects_touched = set()
        
        trends_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'hours': round(total_hours, 1),
            'projects_touched': len(projects_touched)
        })
    
    # Get task velocity data (tasks completed per day, last 30 days)
    task_velocity_data = []
    for i in range(30):
        date = thirty_days_ago + timedelta(days=i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        daily_tasks = Task.query.filter(
            Task.completed_on >= date_start,
            Task.completed_on < date_end,
            Task.is_complete == True
        ).count()
        
        task_velocity_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'tasks_completed': daily_tasks
        })
    
    # Project Status Data for pie chart (exclude default project)
    project_status_data = {
        'Active': Project.query.filter(Project.status == 'Active', Project.is_default == False).count(),
        'Awaiting': Project.query.filter(Project.status == 'Awaiting', Project.is_default == False).count(),
        'Paused': Project.query.filter(Project.status == 'Paused', Project.is_default == False).count(),
        'Archived': Project.query.filter(Project.status == 'Archived', Project.is_default == False).count()
    }
    
    # Recent Activity for public display (limit 10 items, sanitized)
    public_activities = []
    try:
        recent_activities = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()
        
        for activity in recent_activities:
            activity_item = None
            
            if activity.activity_type == 'task_completed':
                activity_item = {
                    'type': 'task_completed',
                    'description': 'Task completed for a project',
                    'created_at': activity.created_at
                }
            elif activity.activity_type == 'project_status_change':
                old_status = activity.old_value.get('status') if activity.old_value else 'Unknown'
                new_status = activity.new_value.get('status') if activity.new_value else 'Unknown'
                activity_item = {
                    'type': 'project_status_change',
                    'description': f'A project status changed from {old_status} to {new_status}',
                    'created_at': activity.created_at
                }
            elif activity.activity_type == 'time_logged':
                activity_item = {
                    'type': 'time_logged',
                    'description': 'Time logged for a project',
                    'created_at': activity.created_at
                }
            elif activity.activity_type == 'touch_logged':
                activity_item = {
                    'type': 'touch_logged',
                    'description': 'Quick touch logged for a project',
                    'created_at': activity.created_at
                }
            elif activity.activity_type == 'project_created':
                activity_item = {
                    'type': 'project_created',
                    'description': 'New project created',
                    'created_at': activity.created_at
                }
            elif activity.activity_type == 'client_created':
                activity_item = {
                    'type': 'client_created',
                    'description': 'New client added',
                    'created_at': activity.created_at
                }
            elif activity.activity_type == 'membership_created':
                activity_item = {
                    'type': 'membership_created',
                    'description': 'New membership created',
                    'created_at': activity.created_at
                }
            elif activity.activity_type == 'user_created':
                activity_item = {
                    'type': 'user_created',
                    'description': 'New team member added',
                    'created_at': activity.created_at
                }
            
            if activity_item:
                public_activities.append(activity_item)
    
    except Exception as e:
        print(f"Warning: Error processing activities for landing page: {e}")
        public_activities = []
    
    # Update variable names for metrics partial compatibility
    total_members = total_memberships  # Rename for partial compatibility
    
    return render_template('landing.html',
                         total_members=total_members,
                         total_projects=total_projects,
                         total_clients=total_clients,
                         open_tasks=open_tasks,
                         activity_data=activity_data,
                         trends_data=trends_data,
                         task_velocity_data=task_velocity_data,
                         project_status_data=project_status_data,
                         public_activities=public_activities)

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to dashboard
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    # Check if this is first-time setup (no users exist)
    user_count = User.query.count()
    
    if user_count == 0:
        if request.method == 'POST':
            # Create first admin user
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            
            if not first_name or not email or not password:
                flash('First name, email, and password are required', 'error')
                return render_template('login.html', first_time_setup=True)
            
            # Check if email already exists (shouldn't happen in first-time setup)
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email already exists', 'error')
                return render_template('login.html', first_time_setup=True)
            
            # Create admin user
            user = User(
                first_name=first_name,
                email=email,
                role='admin'
            )
            user.set_last_name(last_name)
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # Log them in
            session['user_id'] = user.id
            session['user_name'] = user.full_name
            session['role'] = user.role
            flash('Welcome! Your admin account has been created.', 'success')
            return redirect(url_for('dashboard'))
        
        # Show first-time setup form
        return render_template('login.html', first_time_setup=True)
    
    # Normal login flow
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email:
            flash('Email is required', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Invalid email or password', 'error')
            return render_template('login.html')
        
        # Only check password for admin users
        if user.role == 'admin':
            if not password:
                flash('Password is required for admin users', 'error')
                return render_template('login.html')
            if not user.check_password(password):
                flash('Invalid email or password', 'error')
                return render_template('login.html')
        
        # Only allow admin users to login for now
        if user.role != 'admin':
            flash('Only administrators can login at this time', 'error')
            return render_template('login.html')
        
        session['user_id'] = user.id
        session['user_name'] = user.full_name
        session['role'] = user.role
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/login/<int:user_id>')
def login_user(user_id):
    # This route is deprecated but kept for backward compatibility
    # Redirect to main login page
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    
    # Get tasks assigned to current user - filter out completed (for dashboard widget)
    tasks_for_me_query = Task.query.filter(
        (Task.assigned_to == session['user_id']) &
        (Task.is_complete == False)
    ).order_by(Task.created_at.desc()).all()
    
    # Get tasks created by current user - filter out completed (for dashboard widget)
    tasks_i_created_query = Task.query.filter(
        (Task.created_by == session['user_id']) &
        (Task.is_complete == False)
    ).order_by(Task.created_at.desc()).all()
    
    # Recent Activity (limit 10 items)
    from datetime import timedelta
    
    # Get recent activity from ActivityLog
    recent_activities = []
    try:
        # Check if ActivityLog table exists by trying to query it
        recent_activities = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()
    except Exception as e:
        print(f"Warning: ActivityLog table not available: {e}")
        # Set empty list to prevent further errors
        recent_activities = []
    

    
    # Process activities for display - combine all into single list for proper ordering
    all_activities = []
    
    try:
        for activity in recent_activities:
            if activity.activity_type == 'task_completed':
                # Get the task details
                task = db.session.get(Task, activity.entity_id)
                if task:
                    all_activities.append({
                        'type': 'task_completed',
                        'data': serialize_task(task),
                        'created_at': activity.created_at
                    })
            elif activity.activity_type == 'task_created' and activity.entity_id:
                # Get the task details for assignments
                task = db.session.get(Task, activity.entity_id)
                if task:
                    all_activities.append({
                        'type': 'task_created',
                        'data': serialize_task(task),
                        'created_at': activity.created_at
                    })
            elif activity.activity_type == 'time_logged':
                # Get the log details
                log = db.session.get(Log, activity.entity_id)
                if log:
                    all_activities.append({
                        'type': 'time_logged',
                        'data': log,
                        'created_at': activity.created_at
                    })
            elif activity.activity_type == 'project_status_change':
                all_activities.append({
                    'type': 'project_status_change',
                    'data': activity,
                    'created_at': activity.created_at
                })
            elif activity.activity_type == 'client_created':
                all_activities.append({
                    'type': 'client_created',
                    'data': activity,
                    'created_at': activity.created_at
                })
            elif activity.activity_type == 'membership_supplement_added':
                all_activities.append({
                    'type': 'membership_supplement_added',
                    'data': activity,
                    'created_at': activity.created_at
                })
            elif activity.activity_type == 'user_created':
                all_activities.append({
                    'type': 'user_created',
                    'data': activity,
                    'created_at': activity.created_at
                })
            elif activity.activity_type == 'project_created':
                all_activities.append({
                    'type': 'project_created',
                    'data': activity,
                    'created_at': activity.created_at
                })
            elif activity.activity_type == 'membership_created':
                all_activities.append({
                    'type': 'membership_created',
                    'data': activity,
                    'created_at': activity.created_at
                })
        
        # Sort by creation time (most recent first) and limit to 10
        all_activities.sort(key=lambda x: x['created_at'], reverse=True)
        all_activities = all_activities[:10]
    except Exception as e:
        print(f"Warning: Error processing activities: {e}")
        all_activities = []
    

    
    # Serialize tasks with related data
    tasks_for_me = [serialize_task(task) for task in tasks_for_me_query]
    tasks_i_created = [serialize_task(task) for task in tasks_i_created_query]
    
    # Get day of week for personalized messages
    import datetime
    day_of_week = datetime.datetime.now().strftime('%A')
    
    # Get Kanban data for projects (exclude default project)
    active_projects = Project.query.filter(
        Project.status == 'Active',
        Project.is_default == False
    ).order_by(Project.updated_at.desc()).all()
    
    awaiting_projects = Project.query.filter(
        Project.status == 'Awaiting',
        Project.is_default == False
    ).order_by(Project.updated_at.desc()).all()
    
    paused_projects = Project.query.filter(
        Project.status == 'Paused',
        Project.is_default == False
    ).order_by(Project.updated_at.desc()).all()
    
    archived_projects = Project.query.filter(
        Project.status == 'Archived',
        Project.is_default == False
    ).order_by(Project.updated_at.desc()).all()
    
    # If no Awaiting/Paused projects exist yet, also check Prospective projects for Awaiting column
    if not awaiting_projects:
        awaiting_projects = Project.query.filter(
            Project.status == 'Prospective',
            Project.is_default == False
        ).order_by(Project.updated_at.desc()).all()
    
    # Get data for action buttons (creating new items)
    clients = Client.query.order_by(Client.name.asc()).all()
    memberships = Membership.query.all()
    users = User.query.order_by(User.first_name.asc()).all()
    
    return render_template('dashboard.html', 
                         user=user,
                         tasks_for_me=tasks_for_me, 
                         tasks_i_created=tasks_i_created,
                         all_activities=all_activities,
                         day_of_week=day_of_week,
                         # Kanban data
                         active_projects=active_projects,
                         awaiting_projects=awaiting_projects,
                         paused_projects=paused_projects,
                         archived_projects=archived_projects,
                         # Modal data
                         clients=clients,
                         memberships=memberships,
                         users=users)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/projects')
def get_projects():
    if 'user_id' not in session:
        return {'projects': []}, 401
    
    # Order projects: default project first, then by most recently updated
    projects = Project.query.join(Client).filter(
        Project.status != 'Archived'
    ).order_by(
        Project.is_default.desc(),  # Default project first
        Project.updated_at.desc()   # Then most recently updated
    ).all()
    
    return {
        'projects': [
            {
                'id': p.id,
                'name': p.name,
                'client_name': p.client.name,
                'display_name': f"{p.name} ({p.client.name})",
                'is_default': p.is_default
            }
            for p in projects
        ]
    }

@app.route('/api/users')
def get_users():
    if 'user_id' not in session:
        return {'users': []}, 401
    
    users = User.query.all()
    return {
        'users': [
            {
                'id': u.id,
                'name': u.full_name,
                'first_name': u.first_name
            }
            for u in users
        ]
    }

@app.route('/api/memberships')
def get_memberships():
    if 'user_id' not in session:
        return {'memberships': []}, 401
    
    memberships = Membership.query.all()
    return {
        'memberships': [
            {
                'id': m.id,
                'title': m.title
            }
            for m in memberships
        ]
    }

@app.route('/api/clients')
def get_clients():
    if 'user_id' not in session:
        return {'clients': []}, 401
    
    clients = Client.query.all()
    return {
        'clients': [
            {
                'id': c.id,
                'name': c.name
            }
            for c in clients
        ]
    }

@app.route('/api/export-report', methods=['POST'])
def export_report():
    if 'user_id' not in session:
        return {'error': 'Not logged in'}, 401
    
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        from datetime import datetime, timedelta
        import io
        
        # Get form data
        start_date_str = request.json.get('start_date')
        end_date_str = request.json.get('end_date')
        filter_type = request.json.get('filter_type', 'all')
        filter_value = request.json.get('filter_value', '')
        
        # Parse dates
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Create workbook
        wb = Workbook()
        
        # Remove default sheet
        wb.remove(wb.active)
        
        # Create header sheet
        header_ws = wb.create_sheet("Report Info")
        
        # Add header information
        header_ws['A1'] = "Hub Tracker Report"
        header_ws['A1'].font = Font(size=16, bold=True)
        
        header_ws['A3'] = "Date Range:"
        header_ws['B3'] = f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}"
        
        header_ws['A4'] = "Filter:"
        if filter_type == 'all':
            header_ws['B4'] = "All Memberships and Clients"
        elif filter_type == 'membership':
            membership = db.session.get(Membership, filter_value)
            header_ws['B4'] = f"Membership: {membership.title if membership else 'Unknown'}"
        elif filter_type == 'client':
            client = db.session.get(Client, filter_value)
            header_ws['B4'] = f"Client: {client.name if client else 'Unknown'}"
        
        header_ws['A6'] = "Generated:"
        header_ws['B6'] = datetime.now().strftime('%B %d, %Y at %I:%M %p')
        
        # Auto-adjust column widths
        for column in header_ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            header_ws.column_dimensions[column_letter].width = adjusted_width
        
        # Create data sheet
        data_ws = wb.create_sheet("Project Data")
        
        # Define styles
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        membership_font = Font(bold=True, size=12)
        membership_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        client_font = Font(bold=True)
        client_fill = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Add headers
        headers = [
            "Membership", "Client", "Project", "Log Type", "User", "Date/Time", "Hours", "Cost", "Notes", "Status"
        ]
        for col, header in enumerate(headers, 1):
            cell = data_ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = Alignment(horizontal="center")
        
        # Helper function to calculate project totals
        def calculate_project_totals(project_id, start_date, end_date):
            """Calculate total hours and cost for a project within date range"""
            from sqlalchemy import func
            from datetime import timedelta
            
            # Get detailed logs with actual hours and costs
            detailed_logs = db.session.query(
                func.sum(Log.hours).label('total_hours'),
                func.sum(Log.fixed_cost).label('total_cost')
            ).filter(
                Log.project_id == project_id,
                Log.created_at >= start_date,
                Log.created_at < end_date + timedelta(days=1),
                Log.is_touch.is_(False)
            ).first()
            
            # Get touch logs count (30 minutes each)
            touch_count = db.session.query(func.count(Log.id)).filter(
                Log.project_id == project_id,
                Log.created_at >= start_date,
                Log.created_at < end_date + timedelta(days=1),
                Log.is_touch.is_(True)
            ).scalar() or 0
            touch_hours = touch_count * 0.5
            
            total_hours = float(detailed_logs.total_hours or 0) + touch_hours
            total_cost = float(detailed_logs.total_cost or 0)
            
            return total_hours, total_cost
        
        # Helper function to calculate membership remaining
        def calculate_membership_remaining(membership_id):
            """Calculate remaining budget and time for a membership, using supplement-aware totals"""
            membership = db.session.get(Membership, membership_id)
            if not membership:
                return 0, 0
            # Use the supplement-aware properties directly
            total_budget = float(membership.total_budget or 0)
            total_time = float(membership.total_time or 0)
            # Calculate used cost and time for this membership (all clients/projects)
            clients = Client.query.filter_by(membership_id=membership_id).all()
            client_ids = [c.id for c in clients]
            projects = Project.query.filter(Project.client_id.in_(client_ids)).all()
            used_cost = 0
            used_time = 0
            for project in projects:
                hours, cost = calculate_project_totals(project.id, membership.start_date or datetime(2020, 1, 1), datetime.now())
                used_time += hours
                used_cost += cost
            remaining_budget = total_budget - used_cost
            remaining_time = total_time - used_time
            return remaining_budget, remaining_time
        
        # Get memberships based on filter
        if filter_type == 'membership':
            memberships = [db.session.get(Membership, filter_value)] if filter_value else []
        elif filter_type == 'client':
            client = db.session.get(Client, filter_value)
            memberships = [client.membership] if client and client.membership else []
        else:  # all
            memberships = Membership.query.all()
        
        # Build report data
        row = 2
        membership_summaries = []
        
        for membership in memberships:
            if not membership:
                continue
                
            # Add membership header (merged row for clarity)
            membership_cell = data_ws.cell(row=row, column=1, value=membership.title)
            membership_cell.font = membership_font
            membership_cell.fill = membership_fill
            membership_cell.border = border
            row += 1

            clients = Client.query.filter_by(membership_id=membership.id).all()
            membership_total_hours = 0
            membership_total_cost = 0

            for client in clients:
                projects = Project.query.filter_by(client_id=client.id).all()
                
                # Check if this client has any projects with activity in the date range
                client_has_activity = False
                for project in projects:
                    logs = Log.query.filter(
                        Log.project_id == project.id,
                        Log.created_at >= start_date,
                        Log.created_at < end_date + timedelta(days=1)
                    ).first()
                    if logs:
                        client_has_activity = True
                        break
                
                # Skip clients with no activity in the date range
                if not client_has_activity:
                    continue

                # Add client header (merged row for clarity)
                client_cell = data_ws.cell(row=row, column=2, value=client.name)
                client_cell.font = client_font
                client_cell.fill = client_fill
                client_cell.border = border
                row += 1

                client_total_hours = 0
                client_total_cost = 0

                for project in projects:
                    # Fetch all logs for this project in the date range first
                    logs = Log.query.filter(
                        Log.project_id == project.id,
                        Log.created_at >= start_date,
                        Log.created_at < end_date + timedelta(days=1)
                    ).order_by(Log.created_at).all()

                    # Skip projects with no activity in the date range
                    if not logs:
                        continue

                    # Add project header (merged row for clarity)
                    project_cell = data_ws.cell(row=row, column=3, value=project.name)
                    project_cell.font = Font(italic=True)
                    project_cell.border = border
                    row += 1

                    project_hours = 0
                    project_cost = 0

                    for log in logs:
                        log_type = "Project Touched" if log.is_touch else "Time/Cost Log"
                        user_name = log.user.full_name if log.user else "Unknown"
                        dt_str = log.created_at.strftime('%Y-%m-%d %I:%M %p') if log.created_at else ""
                        hours = float(log.hours or 0)
                        cost = float(log.fixed_cost or 0)
                        notes = log.notes or ""
                        status = project.status

                        # Write log row
                        data_ws.cell(row=row, column=1, value=membership.title).border = border
                        data_ws.cell(row=row, column=2, value=client.name).border = border
                        data_ws.cell(row=row, column=3, value=project.name).border = border
                        data_ws.cell(row=row, column=4, value=log_type).border = border
                        data_ws.cell(row=row, column=5, value=user_name).border = border
                        data_ws.cell(row=row, column=6, value=dt_str).border = border
                        data_ws.cell(row=row, column=7, value=hours).border = border
                        data_ws.cell(row=row, column=8, value=cost).border = border
                        data_ws.cell(row=row, column=9, value=notes).border = border
                        data_ws.cell(row=row, column=10, value=status).border = border

                        project_hours += hours if not log.is_touch else 0.5
                        project_cost += cost
                        client_total_hours += hours if not log.is_touch else 0.5
                        client_total_cost += cost
                        membership_total_hours += hours if not log.is_touch else 0.5
                        membership_total_cost += cost
                        row += 1

                    # Project summary row
                    if logs:
                        data_ws.cell(row=row, column=3, value=f"{project.name} - TOTAL")
                        data_ws.cell(row=row, column=7, value=round(project_hours, 2))
                        data_ws.cell(row=row, column=8, value=round(project_cost, 2))
                        data_ws.cell(row=row, column=10, value="PROJECT TOTAL")
                        for col in range(1, 11):
                            cell = data_ws.cell(row=row, column=col)
                            cell.font = Font(bold=True)
                            cell.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
                            cell.border = border
                        row += 1

                # Client summary row
                if projects:
                    data_ws.cell(row=row, column=2, value=f"{client.name} - TOTAL")
                    data_ws.cell(row=row, column=7, value=round(client_total_hours, 2))
                    data_ws.cell(row=row, column=8, value=round(client_total_cost, 2))
                    data_ws.cell(row=row, column=10, value="CLIENT TOTAL")
                    for col in range(1, 11):
                        cell = data_ws.cell(row=row, column=col)
                        cell.font = Font(bold=True)
                        cell.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
                        cell.border = border
                    row += 1

            # Membership summary row
            if clients:
                data_ws.cell(row=row, column=1, value=f"{membership.title} - TOTAL")
                data_ws.cell(row=row, column=7, value=round(membership_total_hours, 2))
                data_ws.cell(row=row, column=8, value=round(membership_total_cost, 2))
                data_ws.cell(row=row, column=10, value="MEMBERSHIP TOTAL")
                for col in range(1, 11):
                    cell = data_ws.cell(row=row, column=col)
                    cell.font = Font(bold=True, size=12)
                    cell.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
                    cell.border = border
                row += 1
                
                # Calculate and store membership remaining
                remaining_budget, remaining_time = calculate_membership_remaining(membership.id)
                membership_summaries.append({
                    'name': membership.title,
                    'total_hours': membership_total_hours,
                    'total_cost': membership_total_cost,
                    'remaining_budget': remaining_budget,
                    'remaining_time': remaining_time
                })
        
        # Unassociated Projects Section
        unassoc_clients = Client.query.filter(Client.membership_id.is_(None)).all()
        if unassoc_clients:
            # Section header
            data_ws.cell(row=row, column=1, value="Unassociated Projects").font = Font(bold=True, size=12)
            data_ws.cell(row=row, column=1).fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
            row += 1
            
            for client in unassoc_clients:
                projects = Project.query.filter_by(client_id=client.id).all()
                
                # Check if this client has any projects with activity in the date range
                client_has_activity = False
                for project in projects:
                    logs = Log.query.filter(
                        Log.project_id == project.id,
                        Log.created_at >= start_date,
                        Log.created_at < end_date + timedelta(days=1)
                    ).first()
                    if logs:
                        client_has_activity = True
                        break
                
                # Skip clients with no activity in the date range
                if not client_has_activity:
                    continue
                
                # Client header
                client_cell = data_ws.cell(row=row, column=2, value=client.name)
                client_cell.font = client_font
                client_cell.fill = client_fill
                client_cell.border = border
                row += 1
                
                client_total_hours = 0
                client_total_cost = 0
                
                for project in projects:
                    # Fetch all logs for this project in the date range first
                    logs = Log.query.filter(
                        Log.project_id == project.id,
                        Log.created_at >= start_date,
                        Log.created_at < end_date + timedelta(days=1)
                    ).order_by(Log.created_at).all()
                    
                    # Skip projects with no activity in the date range
                    if not logs:
                        continue
                    
                    # Project header
                    project_cell = data_ws.cell(row=row, column=3, value=project.name)
                    project_cell.font = Font(italic=True)
                    project_cell.border = border
                    row += 1
                    
                    project_hours = 0
                    project_cost = 0
                    
                    for log in logs:
                        log_type = "Project Touched" if log.is_touch else "Time/Cost Log"
                        user_name = log.user.full_name if log.user else "Unknown"
                        dt_str = log.created_at.strftime('%Y-%m-%d %I:%M %p') if log.created_at else ""
                        hours = float(log.hours or 0)
                        cost = float(log.fixed_cost or 0)
                        notes = log.notes or ""
                        status = project.status
                        
                        # Write log row
                        data_ws.cell(row=row, column=1, value="Unassociated").border = border
                        data_ws.cell(row=row, column=2, value=client.name).border = border
                        data_ws.cell(row=row, column=3, value=project.name).border = border
                        data_ws.cell(row=row, column=4, value=log_type).border = border
                        data_ws.cell(row=row, column=5, value=user_name).border = border
                        data_ws.cell(row=row, column=6, value=dt_str).border = border
                        data_ws.cell(row=row, column=7, value=hours).border = border
                        data_ws.cell(row=row, column=8, value=cost).border = border
                        data_ws.cell(row=row, column=9, value=notes).border = border
                        data_ws.cell(row=row, column=10, value=status).border = border
                        
                        project_hours += hours if not log.is_touch else 0.5
                        project_cost += cost
                        client_total_hours += hours if not log.is_touch else 0.5
                        client_total_cost += cost
                        row += 1
                    
                    # Project summary row
                    if logs:
                        data_ws.cell(row=row, column=3, value=f"{project.name} - TOTAL")
                        data_ws.cell(row=row, column=7, value=round(project_hours, 2))
                        data_ws.cell(row=row, column=8, value=round(project_cost, 2))
                        data_ws.cell(row=row, column=10, value="PROJECT TOTAL")
                        for col in range(1, 11):
                            cell = data_ws.cell(row=row, column=col)
                            cell.font = Font(bold=True)
                            cell.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
                            cell.border = border
                        row += 1
                
                # Client summary row
                if projects:
                    data_ws.cell(row=row, column=2, value=f"{client.name} - TOTAL")
                    data_ws.cell(row=row, column=7, value=round(client_total_hours, 2))
                    data_ws.cell(row=row, column=8, value=round(client_total_cost, 2))
                    data_ws.cell(row=row, column=10, value="CLIENT TOTAL")
                    for col in range(1, 11):
                        cell = data_ws.cell(row=row, column=col)
                        cell.font = Font(bold=True)
                        cell.fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
                        cell.border = border
                    row += 1
        
        # Create summary sheet
        summary_ws = wb.create_sheet("Membership Summary")
        
        # Add summary headers
        summary_headers = ["Membership", "Total Hours (Period)", "Total Cost (Period)", "Remaining Budget", "Remaining Time"]
        for col, header in enumerate(summary_headers, 1):
            cell = summary_ws.cell(row=1, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = Alignment(horizontal="center")
        
        # Add summary data
        for i, summary in enumerate(membership_summaries, 2):
            summary_ws.cell(row=i, column=1, value=summary['name']).border = border
            summary_ws.cell(row=i, column=2, value=round(summary['total_hours'], 2)).border = border
            summary_ws.cell(row=i, column=3, value=round(summary['total_cost'], 2)).border = border
            summary_ws.cell(row=i, column=4, value=round(summary['remaining_budget'], 2)).border = border
            summary_ws.cell(row=i, column=5, value=round(summary['remaining_time'], 2)).border = border
        
        # Auto-adjust column widths for data sheet
        for column in data_ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            data_ws.column_dimensions[column_letter].width = adjusted_width
        
        # Auto-adjust column widths for summary sheet
        for column in summary_ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            summary_ws.column_dimensions[column_letter].width = adjusted_width
        
        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        # Generate filename
        filename = f"hub_tracker_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"Export error: {str(e)}")
        return {'error': f'Export failed: {str(e)}'}, 500

@app.route('/api/tasks')
def get_tasks():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    # Get all tasks with their related data
    tasks = Task.query.filter(
        Task.is_complete == False  # Only get incomplete tasks for main list
    ).join(
        User, User.id == Task.created_by, aliased=True
    ).outerjoin(
        Project, Project.id == Task.project_id
    ).outerjoin(
        Client, Client.id == Project.client_id
    ).outerjoin(
        User, User.id == Task.assigned_to, aliased=True
    ).outerjoin(
        User, User.id == Task.completed_by_user_id, aliased=True
    ).all()
    
    # Convert tasks to dictionary
    tasks_data = []
    for task in tasks:
        task_dict = {
            'id': task.id,
            'description': task.description,
            'is_complete': task.is_complete,
            'completed_on': task.completed_on.isoformat() if task.completed_on else None,
            'created_at': task.created_at.isoformat(),
            'project_id': task.project_id,
            'project_name': task.project.name if task.project else None,
            'client_name': task.project.client.name if task.project and task.project.client else None,
            'assigned_to_id': task.assigned_to,
            'assigned_to_name': task.assignee.full_name if task.assignee else None,
            'created_by_id': task.created_by,
            'created_by_name': task.creator.full_name if task.creator else None,
            'completed_by_id': task.completed_by_user_id,
            'completed_by_name': task.completer.full_name if task.completer else None,
            'is_flagged': bool(task.flags.filter_by(user_id=session['user_id']).first())
        }
        tasks_data.append(task_dict)
    
    return jsonify({'tasks': tasks_data})

@app.route('/api/completed-tasks')
def get_completed_tasks():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    # Get the 10 most recently completed tasks
    tasks = Task.query.filter(
        Task.is_complete == True
    ).outerjoin(
        Project, Project.id == Task.project_id
    ).outerjoin(
        Client, Client.id == Project.client_id
    ).order_by(Task.completed_on.desc()).limit(10).all()
    
    # Convert tasks to dictionary
    tasks_data = []
    for task in tasks:
        task_dict = {
            'id': task.id,
            'description': task.description,
            'is_complete': task.is_complete,
            'completed_on': task.completed_on.isoformat() if task.completed_on else None,
            'created_at': task.created_at.isoformat(),
            'project_id': task.project_id,
            'project_name': task.project.name if task.project else None,
            'client_name': task.project.client.name if task.project and task.project.client else None,
            'assigned_to_id': task.assigned_to,
            'assigned_to_name': task.assignee.full_name if task.assignee else None,
            'created_by_id': task.created_by,
            'created_by_name': task.creator.full_name if task.creator else None,
            'completed_by_id': task.completed_by_user_id,
            'completed_by_name': task.completer.full_name if task.completer else None,
            'is_flagged': bool(task.flags.filter_by(user_id=session['user_id']).first())
        }
        tasks_data.append(task_dict)
    
    return jsonify({'tasks': tasks_data})

@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    description = request.form.get('description', '').strip()  # This contains the full text with tags
    project_id = request.form.get('project_id')
    assigned_to = request.form.get('assigned_to')
    
    # Debug: Print form data
    print(f"DEBUG add_task: description='{description}', project_id='{project_id}', assigned_to='{assigned_to}'")
    print(f"DEBUG add_task: All form data: {dict(request.form)}")
    
    if description:
        # If no project specified, use the most recently updated project
        if not project_id:
            default_project = Project.query.filter(
                Project.status != 'Archived'
            ).order_by(Project.updated_at.desc()).first()
            project_id = default_project.id if default_project else None
        
        task = Task(
            description=description,  # Store the full text with tags
            created_by=session['user_id'],
            project_id=int(project_id) if project_id else None,
            assigned_to=int(assigned_to) if assigned_to else None
        )
        db.session.add(task)
        db.session.commit()
        
        # Log task creation activity
        ActivityLog.log_activity(
            user_id=session['user_id'],
            activity_type='task_created',
            entity_type='task',
            entity_id=task.id,
            new_value={
                'description': task.description,
                'project_id': task.project_id,
                'assigned_to': task.assigned_to
            }
        )
    
    # Redirect back to the referring page or dashboard
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/task/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    task = Task.query.get_or_404(task_id)
    was_complete = task.is_complete
    task.toggle_complete(session['user_id'])
    db.session.commit()
    
    # Log task completion activity (only if it was completed, not uncompleted)
    if not was_complete and task.is_complete:
        ActivityLog.log_activity(
            user_id=session['user_id'],
            activity_type='task_completed',
            entity_type='task',
            entity_id=task.id,
            new_value={
                'description': task.description,
                'project_id': task.project_id,
                'assigned_to': task.assigned_to
            }
        )
    
    return redirect(request.referrer or url_for('tasks'))

@app.route('/task/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    
    return redirect(request.referrer or url_for('tasks'))

@app.route('/task/<int:task_id>/edit', methods=['POST'])
def edit_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    task = Task.query.get_or_404(task_id)
    description = request.form.get('description', '').strip()
    project_id = request.form.get('project_id')
    assigned_to = request.form.get('assigned_to')
    
    if description:
        task.description = description  # Store the full text with tags
        task.project_id = int(project_id) if project_id else None
        task.assigned_to = int(assigned_to) if assigned_to else None
        db.session.commit()
    
    return redirect(request.referrer or url_for('tasks'))

@app.route('/task/<int:task_id>')
def task_detail(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    task = Task.query.get_or_404(task_id)
    
    # Get logs for this task's project
    project_logs = []
    if task.project:
        project_logs = task.project.logs.order_by(Log.created_at.desc()).limit(5).all()
    
    # Check if current user has flagged this task
    is_flagged = UserTaskFlag.query.filter_by(
        user_id=session['user_id'], 
        task_id=task_id
    ).first() is not None
    
    # Get projects and users for edit form
    projects = Project.query.join(Client).order_by(Project.name.asc()).all()
    users = User.query.order_by(User.first_name.asc()).all()
    
    return render_template('task_detail.html', 
                         task=task,
                         project_logs=project_logs,
                         is_flagged=is_flagged,
                         projects=projects,
                         users=users)

@app.route('/debug/tasks')
def debug_tasks():
    """Debug route to check all tasks in database"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    tasks = Task.query.all()
    result = f"<h2>Debug: All Tasks in Database</h2>"
    result += f"<p>Total tasks: {len(tasks)}</p>"
    result += f"<p>Current user_id: {session['user_id']}</p>"
    
    for task in tasks:
        result += f"<div style='border: 1px solid #ccc; margin: 10px; padding: 10px;'>"
        result += f"<strong>Task {task.id}:</strong> {task.description}<br>"
        result += f"Created by: {task.created_by}<br>"
        result += f"Assigned to: {task.assigned_to}<br>"
        result += f"Project ID: {task.project_id}<br>"
        result += f"Complete: {task.is_complete}<br>"
        result += f"Created: {task.created_at}<br>"
        if task.creator:
            result += f"Creator name: {task.creator.full_name}<br>"
        if task.assignee:
            result += f"Assignee name: {task.assignee.full_name}<br>"
        result += f"</div>"
    
    return result

# Placeholder routes for navigation
def serialize_task(task):
    """Convert task object to dictionary with related data"""
    try:
        # Safely access project and client info
        project_name = None
        client_name = None
        if task.project:
            project_name = task.project.name
            if task.project.client:
                client_name = task.project.client.name
        
        # Safely access user relationships
        assigned_to_name = None
        if task.assignee:
            assigned_to_name = task.assignee.full_name
            
        creator_name = None
        if task.creator:
            creator_name = task.creator.full_name
            
        completed_by_name = None
        if task.completer:
            completed_by_name = task.completer.full_name
        
        # Check if task is flagged by current user
        is_flagged = False
        if 'user_id' in session:
            is_flagged = UserTaskFlag.query.filter_by(
                user_id=session['user_id'], 
                task_id=task.id
            ).first() is not None
        
        # Apply tag formatting to description for frontend display
        formatted_description = render_tags(task.description)
        
        return {
            'id': task.id,
            'description': task.description,
            'formatted_description': formatted_description,
            'original_input': task.description,  # Use description as original_input since it contains the full tagged text
            'is_complete': task.is_complete,
            'completed_on': task.completed_on.isoformat() if task.completed_on else None,
            'created_at': task.created_at.isoformat(),
            'project_id': task.project_id,
            'project_name': project_name,
            'client_name': client_name,
            'assigned_to_name': assigned_to_name,
            'assigned_to_id': task.assigned_to,
            'creator_name': creator_name,
            'completed_by_name': completed_by_name,
            'is_flagged': is_flagged,
        }
    except Exception as e:
        print(f"Error serializing task {task.id}: {e}")
        return {
            'id': task.id,
            'description': task.description,
            'formatted_description': task.description,
            'original_input': task.description,
            'is_complete': task.is_complete,
            'completed_on': None,
            'created_at': task.created_at.isoformat() if task.created_at else '',
            'project_id': task.project_id,
            'project_name': None,
            'client_name': None,
            'assigned_to_name': None,
            'assigned_to_id': None,
            'creator_name': None,
            'completed_by_name': None,
            'is_flagged': False,
        }

@app.route('/tasks')
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    print(f"DEBUG: Current user_id: {session['user_id']}")
    
    # Get tasks assigned to current user - filter out completed
    tasks_for_me_query = Task.query.filter(
        (Task.assigned_to == session['user_id']) &
        (Task.is_complete == False)
    ).order_by(Task.created_at.desc()).all()
    
    # Get tasks created by current user - filter out completed
    tasks_i_created_query = Task.query.filter(
        (Task.created_by == session['user_id']) &
        (Task.is_complete == False)
    ).order_by(Task.created_at.desc()).all()
    
    print(f"DEBUG: Found {len(tasks_for_me_query)} tasks for me, {len(tasks_i_created_query)} tasks I created")
    
    # Get all active tasks ordered by project name
    all_tasks_query = Task.query.join(Project, Task.project_id == Project.id, isouter=True).filter(
        Task.is_complete == False
    ).order_by(Project.name.asc(), Task.created_at.desc()).all()
    print(f"DEBUG: Found {len(all_tasks_query)} total active tasks")
    
    # Get all completed tasks
    completed_tasks_query = Task.query.filter(
        Task.is_complete == True
    ).order_by(Task.completed_on.desc()).all()
    print(f"DEBUG: Found {len(completed_tasks_query)} completed tasks")
    
    # Serialize tasks with related data
    tasks_for_me = [serialize_task(task) for task in tasks_for_me_query]
    tasks_i_created = [serialize_task(task) for task in tasks_i_created_query]
    all_tasks = [serialize_task(task) for task in all_tasks_query]
    completed_tasks = [serialize_task(task) for task in completed_tasks_query]
    
    print(f"DEBUG: Serialized {len(tasks_for_me)} tasks for me, {len(tasks_i_created)} tasks I created, {len(all_tasks)} all_tasks, {len(completed_tasks)} completed_tasks")
    
    return render_template('tasks.html', 
                         tasks_for_me=tasks_for_me, 
                         tasks_i_created=tasks_i_created, 
                         all_tasks=all_tasks, 
                         completed_tasks=completed_tasks)

# PROJECTS ROUTES
@app.route('/projects')
def projects():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    from sqlalchemy import func
    
    # Get all projects and separate by status
    all_projects = Project.query.join(Client).order_by(Project.name.asc()).all()
    
    # Separate active/prospective from archived projects
    active_projects = []
    archived_projects = []
    
    for project in all_projects:
        # Add open tasks count and pinned status to each project
        project.open_tasks_count = project.tasks.filter_by(is_complete=False).count()
        project.is_pinned = UserProjectPin.query.filter_by(
            user_id=session['user_id'], 
            project_id=project.id
        ).first() is not None
        
        # Calculate used hours and budget from logs
        logs_summary = db.session.query(
            func.sum(Log.hours).label('total_hours'),
            func.sum(Log.fixed_cost).label('total_cost')
        ).filter_by(project_id=project.id).first()
        
        project.used_hours = float(logs_summary.total_hours) if logs_summary.total_hours else 0
        project.used_budget = float(logs_summary.total_cost) if logs_summary.total_cost else 0
        
        # Get membership budget info through client
        project.membership_time = None
        project.membership_budget = None
        project.hours_remaining = None
        project.budget_remaining = None
        
        if project.client and project.client.membership:
            membership = project.client.membership
            if membership.time:
                project.membership_time = membership.time
                project.hours_remaining = max(0, membership.time - project.used_hours)
            if membership.budget:
                project.membership_budget = membership.budget
                project.budget_remaining = max(0, membership.budget - project.used_budget)
        
        if project.status == 'Archived':
            archived_projects.append(project)
        else:
            active_projects.append(project)
    
    clients = Client.query.order_by(Client.name.asc()).all()
    users = User.query.order_by(User.first_name.asc()).all()
    
    return render_template('projects.html', 
                         active_projects=active_projects,
                         archived_projects=archived_projects,
                         clients=clients, 
                         users=users)

@app.route('/project/<int:project_id>')
def project_detail(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    from sqlalchemy import func
    
    project = Project.query.get_or_404(project_id)
    
    # Calculate used hours and budget from logs
    logs_summary = db.session.query(
        func.sum(Log.hours).label('total_hours'),
        func.sum(Log.fixed_cost).label('total_cost')
    ).filter_by(project_id=project.id).first()
    
    project.used_hours = float(logs_summary.total_hours) if logs_summary.total_hours else 0
    project.used_budget = float(logs_summary.total_cost) if logs_summary.total_cost else 0
    
    # Get membership budget info through client
    project.membership_time = None
    project.membership_budget = None
    project.hours_remaining = None
    project.budget_remaining = None
    
    if project.client and project.client.membership:
        membership = project.client.membership
        if membership.time:
            project.membership_time = membership.time
            project.hours_remaining = max(0, membership.time - project.used_hours)
        if membership.budget:
            project.membership_budget = membership.budget
            project.budget_remaining = max(0, membership.budget - project.used_budget)
    
    # Get open tasks for this project
    open_tasks = project.tasks.filter_by(is_complete=False).order_by(Task.created_at.desc()).all()
    
    # Get completed tasks for this project
    completed_tasks = project.tasks.filter_by(is_complete=True).order_by(Task.completed_on.desc()).all()
    
    # Get recent logs for this project
    recent_logs = project.logs.order_by(Log.created_at.desc()).limit(10).all()
    
    # Check if current user has pinned this project
    is_pinned = UserProjectPin.query.filter_by(
        user_id=session['user_id'], 
        project_id=project_id
    ).first() is not None
    
    # Serialize tasks
    serialized_open_tasks = [serialize_task(task) for task in open_tasks]
    serialized_completed_tasks = [serialize_task(task) for task in completed_tasks]
    
    # Get clients and users for dropdowns
    clients = Client.query.order_by(Client.name.asc()).all()
    users = User.query.order_by(User.first_name.asc()).all()
    
    return render_template('project_detail.html', 
                         project=project, 
                         tasks=serialized_open_tasks,
                         completed_tasks=serialized_completed_tasks,
                         recent_logs=recent_logs,
                         is_pinned=is_pinned,
                         clients=clients,
                         users=users)

@app.route('/add_project', methods=['POST'])
def add_project():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    name = request.form.get('name', '').strip()
    client_id = request.form.get('client_id')
    project_lead_id = request.form.get('project_lead_id')
    notes = request.form.get('notes', '').strip()
    status = request.form.get('status', 'Active')
    is_default = request.form.get('is_default') == 'on'
    
    if not name:
        flash('Project name is required', 'error')
        return redirect(url_for('projects'))
    
    if not client_id:
        flash('Client is required', 'error')
        return redirect(url_for('projects'))
    
    # If setting as default, remove default from other projects
    if is_default:
        Project.query.filter_by(is_default=True).update({'is_default': False})
    
    project = Project(
        name=name,
        client_id=int(client_id),
        project_lead_id=int(project_lead_id) if project_lead_id else None,
        notes=notes,
        status=status,
        is_default=is_default
    )
    
    db.session.add(project)
    db.session.commit()
    
    # Log project creation activity
    ActivityLog.log_activity(
        user_id=session['user_id'],
        activity_type='project_created',
        entity_type='project',
        entity_id=project.id,
        new_value={
            'name': project.name,
            'client_id': project.client_id,
            'status': project.status,
            'project_lead_id': project.project_lead_id
        }
    )
    
    flash('Project created successfully', 'success')
    return redirect(url_for('projects'))

@app.route('/edit_project/<int:project_id>', methods=['POST'])
def edit_project(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    project = Project.query.get_or_404(project_id)
    
    name = request.form.get('name', '').strip()
    client_id = request.form.get('client_id')
    project_lead_id = request.form.get('project_lead_id')
    notes = request.form.get('notes', '').strip()
    status = request.form.get('status', 'Active')
    is_default = request.form.get('is_default') == 'on'
    
    if not name:
        flash('Project name is required', 'error')
        return redirect(url_for('projects'))
    
    if not client_id:
        flash('Client is required', 'error')
        return redirect(url_for('projects'))
    
    # If setting as default, remove default from other projects
    if is_default and not project.is_default:
        Project.query.filter_by(is_default=True).update({'is_default': False})
    
    project.name = name
    project.client_id = int(client_id)
    project.project_lead_id = int(project_lead_id) if project_lead_id else None
    project.notes = notes
    project.status = status
    project.is_default = is_default
    
    db.session.commit()
    flash('Project updated successfully', 'success')
    return redirect(url_for('projects'))

@app.route('/delete_project/<int:project_id>', methods=['POST'])
def delete_project(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if project exists
    project = db.session.get(Project, project_id)
    if not project:
        flash(f'Project with ID {project_id} not found', 'error')
        return redirect(url_for('projects'))
    
    # Check if project has tasks
    if project.tasks.count() > 0:
        flash('Cannot delete project with existing tasks', 'error')
        return redirect(url_for('projects'))
    
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted successfully', 'success')
    return redirect(url_for('projects'))

# CLIENTS ROUTES
@app.route('/clients')
def clients():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    clients = Client.query.order_by(Client.name.asc()).all()
    memberships = Membership.query.all()
    users = User.query.order_by(User.first_name.asc()).all()
    
    return render_template('clients.html', clients=clients, memberships=memberships, users=users)

@app.route('/client/<int:client_id>')
def client_detail(client_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    client = Client.query.get_or_404(client_id)
    
    # Get all projects for this client
    projects = client.projects.order_by(Project.name.asc()).all()
    
    # Get all tasks for this client's projects
    tasks = Task.query.join(Project).filter(
        Project.client_id == client_id
    ).order_by(Task.created_at.desc()).all()
    
    # Serialize tasks
    serialized_tasks = [serialize_task(task) for task in tasks]
    
    # Get memberships for dropdown
    memberships = Membership.query.all()
    users = User.query.order_by(User.first_name.asc()).all()
    
    return render_template('client_detail.html', 
                         client=client, 
                         projects=projects, 
                         tasks=serialized_tasks,
                         memberships=memberships,
                         users=users)

@app.route('/add_client', methods=['POST'])
def add_client():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    name = request.form.get('name', '').strip()
    membership_id = request.form.get('membership_id')
    notes = request.form.get('notes', '').strip()
    
    if not name:
        flash('Client name is required', 'error')
        return redirect(url_for('clients'))
    
    client = Client(
        name=name,
        membership_id=int(membership_id) if membership_id else None,
        notes=notes
    )
    
    db.session.add(client)
    db.session.commit()
    
    # Log client creation activity
    ActivityLog.log_activity(
        user_id=session['user_id'],
        activity_type='client_created',
        entity_type='client',
        entity_id=client.id,
        new_value={
            'name': client.name,
            'membership_id': client.membership_id
        }
    )
    
    flash('Client created successfully', 'success')
    return redirect(url_for('clients'))

@app.route('/edit_client/<int:client_id>', methods=['POST'])
def edit_client(client_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    client = Client.query.get_or_404(client_id)
    
    name = request.form.get('name', '').strip()
    membership_id = request.form.get('membership_id')
    notes = request.form.get('notes', '').strip()
    
    if not name:
        flash('Client name is required', 'error')
        return redirect(url_for('clients'))
    
    client.name = name
    client.membership_id = int(membership_id) if membership_id else None
    client.notes = notes
    
    db.session.commit()
    flash('Client updated successfully', 'success')
    return redirect(url_for('clients'))

@app.route('/delete_client/<int:client_id>', methods=['POST'])
def delete_client(client_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    client = Client.query.get_or_404(client_id)
    
    # Check if client has projects
    if client.projects.count() > 0:
        flash('Cannot delete client with existing projects', 'error')
        return redirect(url_for('clients'))
    
    db.session.delete(client)
    db.session.commit()
    flash('Client deleted successfully', 'success')
    return redirect(url_for('clients'))

# MEMBERSHIPS ROUTES
@app.route('/memberships')
def memberships():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    memberships = Membership.query.all()
    
    return render_template('memberships.html', memberships=memberships)

@app.route('/membership/<int:membership_id>')
def membership_detail(membership_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    membership = Membership.query.get_or_404(membership_id)
    
    # Get all clients for this membership
    associated_clients = membership.clients.order_by(Client.name.asc()).all()
    
    # Get all available clients for the form
    all_clients = Client.query.order_by(Client.name.asc()).all()
    
    # Get all projects through associated clients
    projects = []
    for client in associated_clients:
        projects.extend(client.projects.all())
    
    # Sort projects by name
    projects.sort(key=lambda p: p.name)
    
    return render_template('membership_detail.html', 
                         membership=membership,
                         clients=associated_clients,
                         all_clients=all_clients,
                         projects=projects,
                         MembershipSupplement=MembershipSupplement)

@app.route('/add_membership', methods=['POST'])
def add_membership():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    title = request.form.get('title', '').strip()
    start_date_str = request.form.get('start_date')
    is_annual = request.form.get('is_annual') == 'on'
    cost_str = request.form.get('cost', '').strip()
    time_str = request.form.get('time', '').strip()
    budget_str = request.form.get('budget', '').strip()
    notes = request.form.get('notes', '').strip()
    
    if not title:
        flash('Title is required', 'error')
        return redirect(url_for('memberships'))
    
    start_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            start_date = TIMEZONE.localize(start_date)
        except ValueError:
            flash('Invalid start date format', 'error')
            return redirect(url_for('memberships'))
    
    cost = None
    if cost_str:
        try:
            cost = float(cost_str)
        except ValueError:
            flash('Invalid cost format', 'error')
            return redirect(url_for('memberships'))
    
    time = None
    if time_str:
        try:
            time = int(time_str)
        except ValueError:
            flash('Invalid time format', 'error')
            return redirect(url_for('memberships'))
    
    budget = None
    if budget_str:
        try:
            budget = float(budget_str)
        except ValueError:
            flash('Invalid budget format', 'error')
            return redirect(url_for('memberships'))
    
    membership = Membership(
        title=title,
        start_date=start_date,
        is_annual=is_annual,
        cost=cost,
        time=time,
        budget=budget,
        notes=notes
    )
    
    db.session.add(membership)
    db.session.commit()
    
    # Log membership creation activity
    ActivityLog.log_activity(
        user_id=session['user_id'],
        activity_type='membership_created',
        entity_type='membership',
        entity_id=membership.id,
        new_value={
            'title': membership.title,
            'cost': membership.cost,
            'time': membership.time,
            'budget': membership.budget,
            'is_annual': membership.is_annual
        }
    )
    
    flash('Membership created successfully', 'success')
    return redirect(url_for('memberships'))

@app.route('/edit_membership/<int:membership_id>', methods=['POST'])
def edit_membership(membership_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    membership = Membership.query.get_or_404(membership_id)
    
    title = request.form.get('title', '').strip()
    start_date_str = request.form.get('start_date')
    status = request.form.get('status', 'Active')
    is_annual = request.form.get('is_annual') == 'on'
    cost_str = request.form.get('cost', '').strip()
    time_str = request.form.get('time', '').strip()
    budget_str = request.form.get('budget', '').strip()
    notes = request.form.get('notes', '').strip()
    
    if not title:
        flash('Title is required', 'error')
        return redirect(url_for('memberships'))
    
    start_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            start_date = TIMEZONE.localize(start_date)
        except ValueError:
            flash('Invalid start date format', 'error')
            return redirect(url_for('memberships'))
    
    cost = None
    if cost_str:
        try:
            cost = float(cost_str)
        except ValueError:
            flash('Invalid cost format', 'error')
            return redirect(url_for('memberships'))
    
    time = None
    if time_str:
        try:
            time = int(time_str)
        except ValueError:
            flash('Invalid time format', 'error')
            return redirect(url_for('memberships'))
    
    budget = None
    if budget_str:
        try:
            budget = float(budget_str)
        except ValueError:
            flash('Invalid budget format', 'error')
            return redirect(url_for('memberships'))
    
    membership.title = title
    membership.start_date = start_date
    membership.status = status
    membership.is_annual = is_annual
    membership.cost = cost
    membership.time = time
    membership.budget = budget
    membership.notes = notes
    
    db.session.commit()
    flash('Membership updated successfully', 'success')
    
    # Redirect back to the membership detail page if we came from there
    referrer = request.headers.get('Referer', '')
    if f'/membership/{membership_id}' in referrer:
        return redirect(url_for('membership_detail', membership_id=membership_id))
    else:
        return redirect(url_for('memberships'))

@app.route('/membership/<int:membership_id>/update_clients', methods=['POST'])
def update_membership_clients(membership_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    membership = Membership.query.get_or_404(membership_id)
    
    # Get the list of client IDs that should be associated
    selected_client_ids = request.form.getlist('client_ids')
    
    # Convert to integers
    try:
        selected_client_ids = [int(cid) for cid in selected_client_ids]
    except ValueError:
        flash('Invalid client ID format', 'error')
        return redirect(url_for('membership_detail', membership_id=membership_id))
    
    # Get all clients that should be associated
    clients_to_associate = Client.query.filter(Client.id.in_(selected_client_ids)).all()
    
    # Get current associated clients
    current_clients = membership.clients.all()
    
    # Remove clients that are no longer selected
    for client in current_clients:
        if client.id not in selected_client_ids:
            client.membership_id = None
    
    # Add newly selected clients
    for client in clients_to_associate:
        if client not in current_clients:
            client.membership_id = membership.id
    
    db.session.commit()
    flash('Client associations updated successfully', 'success')
    return redirect(url_for('membership_detail', membership_id=membership_id))

@app.route('/delete_membership/<int:membership_id>', methods=['POST'])
def delete_membership(membership_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    membership = Membership.query.get_or_404(membership_id)
    
    # Check if membership has clients
    if membership.clients.count() > 0:
        flash('Cannot delete membership with existing clients', 'error')
        return redirect(url_for('memberships'))
    
    db.session.delete(membership)
    db.session.commit()
    flash('Membership deleted successfully', 'success')
    return redirect(url_for('memberships'))

@app.route('/kanban')
def kanban():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get all projects grouped by status
    active_projects = Project.query.filter_by(status='Active').order_by(Project.updated_at.desc()).all()
    awaiting_projects = Project.query.filter_by(status='Awaiting').order_by(Project.updated_at.desc()).all()
    paused_projects = Project.query.filter_by(status='Paused').order_by(Project.updated_at.desc()).all()
    archived_projects = Project.query.filter_by(status='Archived').order_by(Project.updated_at.desc()).all()
    
    # If no Awaiting/Paused projects exist yet, also check Prospective projects for Awaiting column
    if not awaiting_projects:
        awaiting_projects = Project.query.filter_by(status='Prospective').order_by(Project.updated_at.desc()).all()
    
    # Get clients and users for the add project modal
    clients = Client.query.order_by(Client.name.asc()).all()
    users = User.query.order_by(User.first_name.asc()).all()
    
    return render_template('kanban.html',
                         active_projects=active_projects,
                         awaiting_projects=awaiting_projects,
                         paused_projects=paused_projects,
                         archived_projects=archived_projects,
                         clients=clients,
                         users=users)

@app.route('/api/project/<int:project_id>/status', methods=['POST'])
def update_project_status(project_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    project = Project.query.get_or_404(project_id)
    data = request.get_json()
    new_status = data.get('status')
    
    # Validate status
    valid_statuses = ['Active', 'Awaiting', 'Paused', 'Archived']
    if new_status not in valid_statuses:
        return jsonify({'success': False, 'error': 'Invalid status'}), 400
    
    # Use the new update_status method that logs activity
    print(f"DEBUG: Updating project {project_id} status to {new_status}")
    project.update_status(new_status, session['user_id'])
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'message': f'Project moved to {new_status}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/analytics')
def analytics():
    """Analytics page (formerly reports)"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    from datetime import timedelta
    from sqlalchemy import func, desc
    
    # Last 30 days filter
    thirty_days_ago = get_current_time() - timedelta(days=30)
    
    # Get basic stats for the top metrics
    total_members = Membership.query.filter_by(status='Active').count()
    total_projects = Project.query.count()
    total_clients = Client.query.count()
    open_tasks = Task.query.filter_by(is_complete=False).count()

    
    # Get task completion data for last 30 days (including today)
    twenty_nine_days_ago = get_current_time() - timedelta(days=29)
    
    # Generate date series for last 30 days (including today)
    completion_data = []
    for i in range(30):
        date = twenty_nine_days_ago + timedelta(days=i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        # All users completions for this day
        all_completions = Task.query.filter(
            Task.completed_on >= date_start,
            Task.completed_on < date_end,
            Task.is_complete.is_(True)
        ).count()
        
        # Current user completions for this day
        my_completions = Task.query.filter(
            Task.completed_on >= date_start,
            Task.completed_on < date_end,
            Task.completed_by_user_id == session['user_id'],
            Task.is_complete.is_(True)
        ).count()
        
        completion_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'all_tasks': all_completions,
            'my_tasks': my_completions
        })
    
    # Helper function to calculate total logged time for a project
    def calculate_project_logged_time(project_id, start_date):
        """Calculate total logged time for a project including touch logs (30 min each)"""
        from sqlalchemy import func, case
        
        # Get detailed logs with actual hours
        detailed_hours = db.session.query(func.sum(Log.hours)).filter(
            Log.project_id == project_id,
            Log.created_at >= start_date,
            Log.is_touch.is_(False)
        ).scalar() or 0
        
        # Get touch logs count (30 minutes each)
        touch_count = db.session.query(func.count(Log.id)).filter(
            Log.project_id == project_id,
            Log.created_at >= start_date,
            Log.is_touch.is_(True)
        ).scalar() or 0
        
        # Convert touch logs to hours (30 minutes each)
        touch_hours = touch_count * 0.5
        
        return float(detailed_hours) + touch_hours
    
    # Get most active projects by task completion (last 30 days)
    most_active_projects_raw = db.session.query(
        Project.name,
        Client.name.label('client_name'),
        func.count(Task.id).label('completed_tasks')
    ).join(Client).join(Task).filter(
        Task.is_complete.is_(True),
        Task.completed_on >= twenty_nine_days_ago
    ).group_by(Project.id, Project.name, Client.name).order_by(desc('completed_tasks')).limit(8).all()
    
    # Convert to dictionaries for JSON serialization
    most_active_projects = []
    for project in most_active_projects_raw:
        most_active_projects.append({
            'name': project.name,
            'client_name': project.client_name,
            'completed_tasks': project.completed_tasks
        })
    
    # Get most active projects by logged time (last 30 days)
    most_logged_time_projects = []
    projects_with_logs = db.session.query(
        Project.id,
        Project.name,
        Client.name.label('client_name')
    ).join(Client).join(Log).filter(
        Log.created_at >= thirty_days_ago
    ).group_by(Project.id, Project.name, Client.name).all()
    
    for project in projects_with_logs:
        total_hours = calculate_project_logged_time(project.id, thirty_days_ago)
        if total_hours > 0:  # Only include projects with actual logged time
            most_logged_time_projects.append({
                'name': project.name,
                'client_name': project.client_name,
                'total_hours': total_hours
            })
    
    # Sort by total hours and limit to top 8
    most_logged_time_projects.sort(key=lambda x: x['total_hours'], reverse=True)
    most_logged_time_projects = most_logged_time_projects[:8]
    
    # LOG ANALYTICS (Last 30 Days)
    
    # Total log metrics
    total_logs_last_30 = Log.query.filter(Log.created_at >= thirty_days_ago).count()
    touch_logs_last_30 = Log.query.filter(Log.created_at >= thirty_days_ago, Log.is_touch.is_(True)).count()
    detailed_logs_last_30 = Log.query.filter(Log.created_at >= thirty_days_ago, Log.is_touch.is_(False)).count()
    total_hours_last_30 = db.session.query(func.sum(Log.hours)).filter(Log.created_at >= thirty_days_ago).scalar() or 0
    
    # Daily log activity for chart
    log_activity_data = []
    
    # If there are no logs at all, just return empty data for today
    if total_logs_last_30 == 0:
        today = get_current_time()
        log_activity_data.append({
            'date': today.strftime('%Y-%m-%d'),
            'touch_logs': 0,
            'detailed_logs': 0,
            'total_logs': 0
        })
    else:
        for i in range(30):
            date = thirty_days_ago + timedelta(days=i)
            date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            date_end = date_start + timedelta(days=1)
            
            touch_count = Log.query.filter(
                Log.created_at >= date_start,
                Log.created_at < date_end,
                Log.is_touch.is_(True)
            ).count()
            
            detailed_count = Log.query.filter(
                Log.created_at >= date_start,
                Log.created_at < date_end,
                Log.is_touch.is_(False)
            ).count()
            
            log_activity_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'touch_logs': touch_count,
                'detailed_logs': detailed_count,
                'total_logs': touch_count + detailed_count
            })
    
    # Most logged projects (last 30 days)
    most_logged_projects = db.session.query(
        Project.name,
        Client.name.label('client_name'),
        func.count(Log.id).label('log_count'),
        func.sum(Log.hours).label('total_hours'),
        func.sum(text('CASE WHEN is_touch IS TRUE THEN 1 ELSE 0 END')).label('touch_count'),
        func.sum(text('CASE WHEN is_touch IS FALSE THEN 1 ELSE 0 END')).label('detailed_count')
    ).join(Client).join(Log).filter(
        Log.created_at >= thirty_days_ago
    ).group_by(Project.id, Project.name, Client.name).order_by(desc('log_count')).limit(8).all()
    

    
    return render_template('analytics.html',
                         # Top metrics
                         total_members=total_members,
                         total_projects=total_projects,
                         total_clients=total_clients,
                         open_tasks=open_tasks,

                         # Task analytics
                         completion_data=completion_data,
                         most_active_projects=most_active_projects,
                         most_logged_time_projects=most_logged_time_projects,
                         # Log analytics
                         total_logs_last_30=total_logs_last_30,
                         touch_logs_last_30=touch_logs_last_30,
                         detailed_logs_last_30=detailed_logs_last_30,
                         total_hours_last_30=round(total_hours_last_30, 1),
                         log_activity_data=log_activity_data)

# LOGS ROUTES
@app.route('/logs')
def logs():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get all logs with their related data, ordered by most recent first
    logs = Log.query.join(
        User, User.id == Log.user_id
    ).outerjoin(
        Project, Project.id == Log.project_id
    ).outerjoin(
        Client, Client.id == Project.client_id
    ).order_by(Log.created_at.desc()).all()
    
    # Get projects and users for the edit form
    projects = Project.query.join(Client).filter(
        Project.status != 'Archived'
    ).order_by(Project.name.asc()).all()
    
    users = User.query.order_by(User.first_name.asc()).all()
    
    return render_template('logs.html', 
                         logs=logs,
                         projects=projects,
                         users=users)

@app.route('/edit_log/<int:log_id>', methods=['POST'])
def edit_log(log_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    log = Log.query.get_or_404(log_id)
    
    notes = request.form.get('notes', '').strip()
    hours = request.form.get('hours')
    fixed_cost = request.form.get('fixed_cost')
    project_id = request.form.get('project_id')
    log_datetime_str = request.form.get('log_datetime', '').strip()
    
    # Update log fields
    log.notes = notes if notes else None
    log.hours = float(hours) if hours else None
    log.fixed_cost = float(fixed_cost) if fixed_cost else None
    log.project_id = int(project_id) if project_id else None
    
    # Parse custom datetime if provided
    if log_datetime_str:
        try:
            from datetime import datetime
            log_datetime = datetime.strptime(log_datetime_str, '%Y-%m-%dT%H:%M')
            log_datetime = TIMEZONE.localize(log_datetime)
            log.created_at = log_datetime
        except ValueError:
            flash('Invalid date/time format', 'error')
            return redirect(url_for('logs'))
    
    db.session.commit()
    flash('Log entry updated successfully', 'success')
    return redirect(url_for('logs'))

@app.route('/delete_log/<int:log_id>', methods=['POST'])
def delete_log(log_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    log = Log.query.get_or_404(log_id)
    
    db.session.delete(log)
    db.session.commit()
    flash('Log entry deleted successfully', 'success')
    return redirect(url_for('logs'))

# LOGGING ROUTES
@app.route('/add_touch_log', methods=['POST'])
def add_touch_log():
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401
    
    project_id = request.json.get('project_id')
    
    if not project_id:
        return {'success': False, 'error': 'Project ID required'}, 400
    
    # Verify project exists (allow any non-archived project)
    project = Project.query.filter(Project.id == int(project_id), Project.status != 'Archived').first()
    if not project:
        return {'success': False, 'error': 'Project not found or archived'}, 404
    
    # Create touch log
    log = Log(
        is_touch=True,
        user_id=session['user_id'],
        project_id=int(project_id)
    )
    
    db.session.add(log)
    db.session.commit()
    
    # Log touch activity
    ActivityLog.log_activity(
        user_id=session['user_id'],
        activity_type='time_logged',
        entity_type='log',
        entity_id=log.id,
        new_value={
            'is_touch': log.is_touch,
            'project_id': log.project_id
        }
    )
    
    db.session.commit()
    
    return {'success': True, 'message': f'Touch logged for {project.name}'}

@app.route('/add_time_log', methods=['POST'])
def add_time_log():
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401
    
    project_id = request.form.get('project_id')
    hours = request.form.get('hours')
    fixed_cost = request.form.get('fixed_cost')
    notes = request.form.get('notes', '').strip()
    log_datetime_str = request.form.get('log_datetime', '').strip()
    
    if not project_id:
        flash('Project is required', 'error')
        return redirect(request.referrer or url_for('dashboard'))
    
    if not notes:
        flash('Notes are required for time logs', 'error')
        return redirect(request.referrer or url_for('dashboard'))
    
    # Verify project exists (allow any non-archived project)
    project = Project.query.filter(Project.id == int(project_id), Project.status != 'Archived').first()
    if not project:
        flash('Project not found or archived', 'error')
        return redirect(request.referrer or url_for('dashboard'))
    
    # Parse custom datetime if provided
    log_datetime = None
    if log_datetime_str:
        try:
            # Parse the datetime-local format (YYYY-MM-DDTHH:MM)
            from datetime import datetime
            log_datetime = datetime.strptime(log_datetime_str, '%Y-%m-%dT%H:%M')
            # Localize to the application timezone
            log_datetime = TIMEZONE.localize(log_datetime)
        except ValueError:
            flash('Invalid date/time format', 'error')
            return redirect(request.referrer or url_for('dashboard'))
    
    # Create time log
    log = Log(
        is_touch=False,
        hours=float(hours) if hours else None,
        fixed_cost=float(fixed_cost) if fixed_cost else None,
        notes=notes,
        user_id=session['user_id'],
        project_id=int(project_id)
    )
    
    # Override created_at if custom datetime provided
    if log_datetime:
        log.created_at = log_datetime
    
    db.session.add(log)
    db.session.commit()
    
    # Log time logging activity with the same datetime
    activity_log = ActivityLog.log_activity(
        user_id=session['user_id'],
        activity_type='time_logged',
        entity_type='log',
        entity_id=log.id,
        new_value={
            'is_touch': log.is_touch,
            'hours': log.hours,
            'fixed_cost': float(log.fixed_cost) if log.fixed_cost else None,
            'project_id': log.project_id
        }
    )
    
    # Override ActivityLog created_at to match the log entry
    if log_datetime:
        activity_log.created_at = log_datetime
    
    db.session.commit()
    
    flash(f'Time logged for {project.name}', 'success')
    return redirect(request.referrer or url_for('dashboard'))

# PINNING AND FLAGGING ROUTES
@app.route('/project/<int:project_id>/pin', methods=['POST'])
def pin_project(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if already pinned
    existing_pin = UserProjectPin.query.filter_by(
        user_id=session['user_id'], 
        project_id=project_id
    ).first()
    
    if not existing_pin:
        pin = UserProjectPin(user_id=session['user_id'], project_id=project_id)
        db.session.add(pin)
        db.session.commit()
    
    return redirect(request.referrer or url_for('project_detail', project_id=project_id))

@app.route('/project/<int:project_id>/unpin', methods=['POST'])
def unpin_project(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    pin = UserProjectPin.query.filter_by(
        user_id=session['user_id'], 
        project_id=project_id
    ).first()
    
    if pin:
        db.session.delete(pin)
        db.session.commit()
    
    return redirect(request.referrer or url_for('project_detail', project_id=project_id))

@app.route('/task/<int:task_id>/flag', methods=['POST'])
def flag_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if already flagged
    existing_flag = UserTaskFlag.query.filter_by(
        user_id=session['user_id'], 
        task_id=task_id
    ).first()
    
    if not existing_flag:
        flag = UserTaskFlag(user_id=session['user_id'], task_id=task_id)
        db.session.add(flag)
        db.session.commit()
    
    return redirect(request.referrer or url_for('task_detail', task_id=task_id))

@app.route('/task/<int:task_id>/unflag', methods=['POST'])
def unflag_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    flag = UserTaskFlag.query.filter_by(
        user_id=session['user_id'], 
        task_id=task_id
    ).first()
    
    if flag:
        db.session.delete(flag)
        db.session.commit()
    
    return redirect(request.referrer or url_for('task_detail', task_id=task_id))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get_or_404(session['user_id'])
    return render_template('profile.html', user=user)

@app.route('/edit_profile', methods=['POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get_or_404(session['user_id'])
    
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    
    # Validation: first name is required
    if not first_name:
        flash('First name is required', 'error')
        return redirect(url_for('profile'))
    
    user.first_name = first_name
    user.set_last_name(last_name)
    
    db.session.commit()
    
    # Update session with new full name
    session['user_name'] = user.full_name
    
    flash('Profile updated successfully', 'success')
    return redirect(url_for('profile'))

@app.route('/supplement/<int:membership_id>/add', methods=['POST'])
def add_supplement(membership_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    membership = Membership.query.get_or_404(membership_id)
    
    time = request.form.get('time', type=int)
    budget = request.form.get('budget', type=float)
    notes = request.form.get('notes', '').strip()
    
    if not time and not budget:
        flash('Please specify either time or budget for the supplement.', 'warning')
        return redirect(url_for('membership_detail', membership_id=membership_id))
    
    supplement = MembershipSupplement(
        membership_id=membership_id,
        time=time,
        budget=budget,
        notes=notes
    )
    db.session.add(supplement)
    db.session.commit()
    
    # Log membership supplement activity
    ActivityLog.log_activity(
        user_id=session['user_id'],
        activity_type='membership_supplement_added',
        entity_type='membership_supplement',
        entity_id=supplement.id,
        new_value={
            'membership_id': supplement.membership_id,
            'time': supplement.time,
            'budget': supplement.budget
        }
    )
    
    db.session.commit()
    
    flash('Supplement added successfully.', 'success')
    return redirect(url_for('membership_detail', membership_id=membership_id))

@app.route('/supplement/<int:supplement_id>/edit', methods=['POST'])
def edit_supplement(supplement_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    supplement = MembershipSupplement.query.get_or_404(supplement_id)
    
    time = request.form.get('time', type=int)
    budget = request.form.get('budget', type=float)
    notes = request.form.get('notes', '').strip()
    
    if not time and not budget:
        flash('Please specify either time or budget for the supplement.', 'warning')
        return redirect(url_for('membership_detail', membership_id=supplement.membership_id))
    
    supplement.time = time
    supplement.budget = budget
    supplement.notes = notes
    db.session.commit()
    
    flash('Supplement updated successfully.', 'success')
    return redirect(url_for('membership_detail', membership_id=supplement.membership_id))

@app.route('/supplement/<int:supplement_id>/delete', methods=['POST'])
def delete_supplement(supplement_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    supplement = MembershipSupplement.query.get_or_404(supplement_id)
    membership_id = supplement.membership_id
    
    db.session.delete(supplement)
    db.session.commit()
    
    flash('Supplement deleted successfully.', 'success')
    return redirect(url_for('membership_detail', membership_id=membership_id))

@app.route('/api/supplement/<int:supplement_id>')
def get_supplement(supplement_id):
    if 'user_id' not in session:
        return {'error': 'Not authenticated'}, 401
    
    supplement = MembershipSupplement.query.get_or_404(supplement_id)
    return {
        'id': supplement.id,
        'time': supplement.time,
        'budget': supplement.budget,
        'notes': supplement.notes
    }

# ADMIN ROUTES (Admin only)
@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if user is admin
    if session.get('role') != 'admin':
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    users = User.query.order_by(User.first_name.asc()).all()
    equipment_list = Equipment.query.order_by(Equipment.name.asc()).all()
    
    return render_template('admin.html', users=users, equipment_list=equipment_list)

@app.route('/import_labs_projects', methods=['POST'])
def import_labs_projects():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    if 'import_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('admin'))
    
    file = request.files['import_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('admin'))
    
    if not file.filename.endswith(('.json', '.txt')):
        flash('Invalid file type. Please upload a JSON or TXT file.', 'error')
        return redirect(url_for('admin'))
    
    try:
        content = file.read()
        data = json.loads(content)
        
        for client_data in data.get('Clients', []):
            # Check if client already exists
            client = Client.query.filter_by(name=client_data['Name']).first()
            if not client:
                client = Client(name=client_data['Name'])
                db.session.add(client)
                db.session.commit()
            
            # Add projects
            for project_name in client_data.get('Projects', []):
                # Check if project already exists for this client
                project = Project.query.filter_by(name=project_name, client_id=client.id).first()
                if not project:
                    project = Project(
                        name=project_name,
                        client_id=client.id,
                        status='Archived',
                        project_lead_id=1
                    )
                    db.session.add(project)
            
        db.session.commit()
        flash('Import completed successfully', 'success')
        
    except json.JSONDecodeError:
        flash('Invalid JSON format in uploaded file', 'error')
    except Exception as e:
        flash(f'Error during import: {str(e)}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/run_import_script', methods=['POST'])
def run_import_script():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        import import_labs
        flash('Import script executed successfully', 'success')
    except Exception as e:
        flash(f'Error running import script: {str(e)}', 'error')
    
    return redirect(url_for('admin'))

@app.route('/add_equipment', methods=['POST'])
def add_equipment():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    manual = request.form.get('manual', '').strip()
    
    if not name:
        flash('Equipment name is required', 'error')
        return redirect(url_for('admin'))
    
    equipment = Equipment(
        name=name,
        description=description if description else None,
        manual=manual if manual else None
    )
    
    db.session.add(equipment)
    db.session.commit()
    flash('Equipment added successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/edit_equipment/<int:equipment_id>', methods=['POST'])
def edit_equipment(equipment_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    equipment = Equipment.query.get_or_404(equipment_id)
    
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    manual = request.form.get('manual', '').strip()
    
    if not name:
        flash('Equipment name is required', 'error')
        return redirect(url_for('admin'))
    
    equipment.name = name
    equipment.description = description if description else None
    equipment.manual = manual if manual else None
    
    db.session.commit()
    flash('Equipment updated successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/delete_equipment/<int:equipment_id>', methods=['POST'])
def delete_equipment(equipment_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    equipment = Equipment.query.get_or_404(equipment_id)
    
    db.session.delete(equipment)
    db.session.commit()
    flash('Equipment deleted successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/add_user', methods=['POST'])
def add_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if user is admin
    if session.get('role') != 'admin':
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'trainee')  # Default to trainee if not specified
    equipment_ids = request.form.getlist('equipment[]')
    
    if not first_name or not email:
        flash('First name and email are required', 'error')
        return redirect(url_for('admin'))
    
    # Check if email already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        flash('Email already exists', 'error')
        return redirect(url_for('admin'))
    
    # Validate role
    if role not in ['admin', 'trainee', 'finance']:
        flash('Invalid role specified', 'error')
        return redirect(url_for('admin'))
    
    # Only require password for admin users
    if role == 'admin' and not password:
        flash('Password is required for admin users', 'error')
        return redirect(url_for('admin'))
    
    user = User(
        first_name=first_name,
        email=email,
        role=role
    )
    user.set_last_name(last_name)
    if password:  # Only set password if provided
        user.set_password(password)
    
    # Add equipment associations
    if equipment_ids:
        # Convert string IDs to integers
        equipment_int_ids = [int(id) for id in equipment_ids if id.isdigit()]
        equipment_list = Equipment.query.filter(Equipment.id.in_(equipment_int_ids)).all()
        user.equipment.extend(equipment_list)
    
    db.session.add(user)
    db.session.commit()
    
    # Log user creation activity
    ActivityLog.log_activity(
        user_id=session['user_id'],
        activity_type='user_created',
        entity_type='user',
        entity_id=user.id,
        new_value={
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'role': user.role
        }
    )
    
    flash('User created successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/edit_user/<int:user_id>', methods=['POST'])
def edit_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if user is admin
    if session.get('role') != 'admin':
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'trainee')  # Default to trainee if not specified
    equipment_ids = request.form.getlist('equipment[]')
    
    if not first_name or not email:
        flash('First name and email are required', 'error')
        return redirect(url_for('admin'))
    
    # Check if email already exists (excluding current user)
    existing_user = User.query.filter(User.email == email, User.id != user_id).first()
    if existing_user:
        flash('Email already exists', 'error')
        return redirect(url_for('admin'))
    
    # Validate role
    if role not in ['admin', 'trainee', 'finance']:
        flash('Invalid role specified', 'error')
        return redirect(url_for('admin'))
    
    # Only require password for admin users if changing to admin role
    if role == 'admin' and user.role != 'admin' and not password:
        flash('Password is required when promoting to admin', 'error')
        return redirect(url_for('admin'))
    
    user.first_name = first_name
    user.set_last_name(last_name)
    user.email = email
    user.role = role
    
    # Only update password if provided
    if password:
        user.set_password(password)
    
    # Update equipment associations
    user.equipment = []  # Clear existing associations
    if equipment_ids:
        # Convert string IDs to integers
        equipment_int_ids = [int(id) for id in equipment_ids if id.isdigit()]
        equipment_list = Equipment.query.filter(Equipment.id.in_(equipment_int_ids)).all()
        user.equipment.extend(equipment_list)
    
    db.session.commit()
    
    # Update session if editing own account
    if user_id == session['user_id']:
        session['user_name'] = user.full_name
        session['role'] = user.role
    
    flash('User updated successfully', 'success')
    return redirect(url_for('admin'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if user is admin
    if session.get('role') != 'admin':
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    # Prevent deleting yourself
    if user_id == session['user_id']:
        flash('Cannot delete your own account', 'error')
        return redirect(url_for('admin'))
    
    user = User.query.get_or_404(user_id)
    
    # Check if user has created tasks, logs, or leads projects
    has_data = (
        user.created_tasks.count() > 0 or
        user.assigned_tasks.count() > 0 or
        user.completed_tasks.count() > 0 or
        user.logs.count() > 0 or
        user.led_projects.count() > 0
    )
    
    if has_data:
        flash('Cannot delete user with existing data (tasks, logs, or led projects)', 'error')
        return redirect(url_for('admin'))
    
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully', 'success')
    return redirect(url_for('admin'))



@app.route('/test-tasks')
def test_tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get just a few tasks for testing
    test_tasks = Task.query.limit(3).all()
    
    # Serialize with minimal data
    tasks_data = []
    for task in test_tasks:
        tasks_data.append({
            'id': task.id,
            'description': task.description,
            'is_complete': task.is_complete,
            'project_name': task.project.name if task.project else None,
            'client_name': task.project.client.name if task.project and task.project.client else None,
            'creator_name': task.creator.full_name if task.creator else None,
            'assigned_to_id': task.assigned_to,
            'created_at': task.created_at.isoformat() if task.created_at else None
        })
    
    return render_template('test_tasks.html', tasks=tasks_data, current_user_id=session['user_id'])

@app.route('/api/preferences', methods=['GET'])
def get_preferences():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    preferences = UserPreferences.query.filter_by(user_id=session['user_id']).all()
    prefs_dict = {pref.key: pref.value for pref in preferences}
    
    return jsonify(prefs_dict)

@app.route('/api/preferences', methods=['POST'])
def save_preferences():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'Invalid data'}), 400
    
    # Update or create each preference
    for key, value in data.items():
        # Find existing preference
        pref = UserPreferences.query.filter_by(
            user_id=session['user_id'],
            key=key
        ).first()
        
        if pref:
            # Update existing
            pref.value = value
        else:
            # Create new
            pref = UserPreferences(
                user_id=session['user_id'],
                key=key,
                value=value
            )
            db.session.add(pref)
    
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/task-form-data')
def get_task_form_data():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    # Get all active projects
    projects = Project.query.join(
        Client, Client.id == Project.client_id
    ).filter(
        Project.status == 'Active'
    ).order_by(Project.name).all()
    
    # Get all users
    users = User.query.order_by(User.first_name).all()
    
    # Convert to dictionaries
    projects_data = [{
        'id': p.id,
        'name': p.name,
        'display_name': f"{p.name} ({p.client.name})" if p.client else p.name,
        'client_name': p.client.name if p.client else None,
        'is_default': p.is_default
    } for p in projects]
    
    users_data = [{
        'id': u.id,
        'name': u.full_name
    } for u in users]
    
    return jsonify({
        'projects': projects_data,
        'users': users_data
    })

@app.route('/api/projects_for_logging')
def get_projects_for_logging():
    if 'user_id' not in session:
        return {'projects': []}, 401
    
    # Get all non-archived projects, ordered by most recent activity
    projects_query = db.session.query(
        Project,
        Client.name.label('client_name')
    ).join(Client).filter(
        Project.status != 'Archived'
    ).order_by(Project.updated_at.desc())
    
    projects = []
    for project, client_name in projects_query:
        projects.append({
            'id': project.id,
            'name': project.name,
            'client_name': client_name,
            'display_name': f"{project.name} ({client_name})"
        })
    
    # The first project (most recently updated) will be the default
    return {'projects': projects}

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5001))) 