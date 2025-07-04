from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_migrate import Migrate
from datetime import datetime
import pytz
import os
import markdown
from sqlalchemy import func, desc, text
import re
from markupsafe import Markup

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///hubtracker.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import models and db
from models import db, User, Client, Membership, Project, Task, Log, UserProjectPin, UserTaskFlag, TIMEZONE, get_current_time, MembershipSupplement

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
    
    return dict(
        get_pinned_projects=get_pinned_projects,
        has_logged_today=has_logged_today()
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

# Add global functions to Jinja2 environment
app.jinja_env.globals.update(min=min)
app.jinja_env.filters['render_tags'] = render_tags

app.jinja_env.filters['render_tags'] = render_tags

@app.route('/')
def index():
    # Public landing page - show general metrics without sensitive data
    from datetime import timedelta
    from sqlalchemy import func
    
    # Get public-friendly metrics
    total_projects = Project.query.filter(Project.status.in_(['Active', 'Awaiting', 'Paused'])).count()
    total_clients = Client.query.count()
    total_active_projects = Project.query.filter_by(status='Active').count()
    
    # Last 30 days activity
    thirty_days_ago = get_current_time() - timedelta(days=30)
    recent_activity = Log.query.filter(Log.created_at >= thirty_days_ago).count()
    
    # Tasks completed in last 30 days (general count)
    tasks_completed_recently = Task.query.filter(
        Task.completed_on >= thirty_days_ago,
        Task.is_complete == True
    ).count()
    
    # Get daily activity for chart (last 30 days, aggregated)
    activity_data = []
    for i in range(30):
        date = thirty_days_ago + timedelta(days=i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        daily_tasks = Task.query.filter(
            Task.completed_on >= date_start,
            Task.completed_on < date_end,
            Task.is_complete == True
        ).count()
        
        daily_logs = Log.query.filter(
            Log.created_at >= date_start,
            Log.created_at < date_end
        ).count()
        
        activity_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'tasks': daily_tasks,
            'activity': daily_logs
        })
    
    # Get some general project types/status distribution
    project_status_results = db.session.query(
        Project.status,
        func.count(Project.id).label('count')
    ).group_by(Project.status).all()
    
    # Convert Row objects to dictionaries for JSON serialization
    project_status_counts = [
        {
            'status': row.status,
            'count': row.count
        }
        for row in project_status_results
    ]
    
    return render_template('landing.html',
                         total_projects=total_projects,
                         total_clients=total_clients,
                         total_active_projects=total_active_projects,
                         recent_activity=recent_activity,
                         tasks_completed_recently=tasks_completed_recently,
                         activity_data=activity_data,
                         project_status_counts=project_status_counts)

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
                is_admin=True
            )
            user.set_last_name(last_name)
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # Log them in
            session['user_id'] = user.id
            session['user_name'] = user.full_name
            flash('Welcome! Your admin account has been created.', 'success')
            return redirect(url_for('dashboard'))
        
        # Show first-time setup form
        return render_template('login.html', first_time_setup=True)
    
    # Normal login flow
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['user_name'] = user.full_name
            session['is_admin'] = user.is_admin
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
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
    
    user = User.query.get(session['user_id'])
    
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
    
    # Recent Activity (last 7 days)
    from datetime import timedelta
    seven_days_ago = get_current_time() - timedelta(days=7)
    
    # Recent tasks completed by me
    recent_my_completions = Task.query.filter(
        Task.completed_by_user_id == session['user_id'],
        Task.completed_on >= seven_days_ago
    ).order_by(Task.completed_on.desc()).limit(5).all()
    
    # Recent tasks assigned to me
    recent_assignments = Task.query.filter(
        Task.assigned_to == session['user_id'],
        Task.created_at >= seven_days_ago,
        Task.is_complete == False
    ).order_by(Task.created_at.desc()).limit(3).all()
    
    # Recent logs I created
    recent_logs = Log.query.filter(
        Log.user_id == session['user_id'],
        Log.created_at >= seven_days_ago
    ).order_by(Log.created_at.desc()).limit(5).all()
    
    # Serialize tasks with related data
    tasks_for_me = [serialize_task(task) for task in tasks_for_me_query]
    tasks_i_created = [serialize_task(task) for task in tasks_i_created_query]
    recent_my_completions_serialized = [serialize_task(task) for task in recent_my_completions]
    recent_assignments_serialized = [serialize_task(task) for task in recent_assignments]
    
    # Get day of week for personalized messages
    import datetime
    day_of_week = datetime.datetime.now().strftime('%A')
    
    # Get Kanban data for projects
    active_projects = Project.query.filter_by(status='Active').order_by(Project.updated_at.desc()).all()
    awaiting_projects = Project.query.filter_by(status='Awaiting').order_by(Project.updated_at.desc()).all()
    paused_projects = Project.query.filter_by(status='Paused').order_by(Project.updated_at.desc()).all()
    archived_projects = Project.query.filter_by(status='Archived').order_by(Project.updated_at.desc()).all()
    
    # If no Awaiting/Paused projects exist yet, also check Prospective projects for Awaiting column
    if not awaiting_projects:
        awaiting_projects = Project.query.filter_by(status='Prospective').order_by(Project.updated_at.desc()).all()
    
    # Get data for action buttons (creating new items)
    clients = Client.query.order_by(Client.name.asc()).all()
    memberships = Membership.query.all()
    users = User.query.order_by(User.first_name.asc()).all()
    
    return render_template('dashboard.html', 
                         user=user,
                         tasks_for_me=tasks_for_me, 
                         tasks_i_created=tasks_i_created,
                         recent_my_completions=recent_my_completions_serialized,
                         recent_assignments=recent_assignments_serialized,
                         recent_logs=recent_logs,
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
    
    projects = Project.query.join(Client).all()
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

@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    description = request.form.get('description', '').strip()  # This contains the full text with tags
    project_id = request.form.get('project_id')
    assigned_to = request.form.get('assigned_to')
    
    if description:
        # If no project specified, use default project
        if not project_id:
            default_project = Project.query.filter_by(is_default=True).first()
            project_id = default_project.id if default_project else None
        
        task = Task(
            description=description,  # Store the full text with tags
            created_by=session['user_id'],
            project_id=int(project_id) if project_id else None,
            assigned_to=int(assigned_to) if assigned_to else None
        )
        db.session.add(task)
        db.session.commit()
    
    # Redirect back to the referring page or dashboard
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/task/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    task = Task.query.get_or_404(task_id)
    task.toggle_complete(session['user_id'])
    db.session.commit()
    
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
            'project_name': None,
            'client_name': None,
            'assigned_to_name': None,
            'assigned_to_id': None,
            'creator_name': None,
            'completed_by_name': None,
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
    
    # Get all tasks for this project
    tasks = project.tasks.order_by(Task.created_at.desc()).all()
    
    # Get recent logs for this project
    recent_logs = project.logs.order_by(Log.created_at.desc()).limit(10).all()
    
    # Check if current user has pinned this project
    is_pinned = UserProjectPin.query.filter_by(
        user_id=session['user_id'], 
        project_id=project_id
    ).first() is not None
    
    # Serialize tasks
    serialized_tasks = [serialize_task(task) for task in tasks]
    
    # Get clients and users for dropdowns
    clients = Client.query.order_by(Client.name.asc()).all()
    users = User.query.order_by(User.first_name.asc()).all()
    
    return render_template('project_detail.html', 
                         project=project, 
                         tasks=serialized_tasks,
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
    
    project = Project.query.get_or_404(project_id)
    
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
    clients = membership.clients.order_by(Client.name.asc()).all()
    
    # Get all projects through these clients
    projects = []
    for client in clients:
        projects.extend(client.projects.all())
    
    # Sort projects by name
    projects.sort(key=lambda p: p.name)
    
    return render_template('membership_detail.html', 
                         membership=membership,
                         clients=clients,
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
    flash('Membership created successfully', 'success')
    return redirect(url_for('memberships'))

@app.route('/edit_membership/<int:membership_id>', methods=['POST'])
def edit_membership(membership_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    membership = Membership.query.get_or_404(membership_id)
    
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
    
    membership.title = title
    membership.start_date = start_date
    membership.is_annual = is_annual
    membership.cost = cost
    membership.time = time
    membership.budget = budget
    membership.notes = notes
    
    db.session.commit()
    flash('Membership updated successfully', 'success')
    return redirect(url_for('memberships'))

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
    
    # Update project status
    project.status = new_status
    project.updated_at = get_current_time()
    
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
    total_members = User.query.count()
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
            Task.is_complete == True
        ).count()
        
        # Current user completions for this day
        my_completions = Task.query.filter(
            Task.completed_on >= date_start,
            Task.completed_on < date_end,
            Task.completed_by_user_id == session['user_id'],
            Task.is_complete == True
        ).count()
        
        completion_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'all_tasks': all_completions,
            'my_tasks': my_completions
        })
    
    # Get most active projects by task completion
    most_active_projects = db.session.query(
        Project.name,
        Client.name.label('client_name'),
        func.count(Task.id).label('completed_tasks')
    ).join(Client).join(Task).filter(
        Task.is_complete == True,
        Task.completed_on >= twenty_nine_days_ago
    ).group_by(Project.id, Project.name, Client.name).order_by(desc('completed_tasks')).limit(10).all()
    
    # LOG ANALYTICS (Last 30 Days)
    
    # Total log metrics
    total_logs_last_30 = Log.query.filter(Log.created_at >= thirty_days_ago).count()
    touch_logs_last_30 = Log.query.filter(Log.created_at >= thirty_days_ago, Log.is_touch == True).count()
    detailed_logs_last_30 = Log.query.filter(Log.created_at >= thirty_days_ago, Log.is_touch == False).count()
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
                Log.is_touch == True
            ).count()
            
            detailed_count = Log.query.filter(
                Log.created_at >= date_start,
                Log.created_at < date_end,
                Log.is_touch == False
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
        func.sum(text('CASE WHEN is_touch = 1 THEN 1 ELSE 0 END')).label('touch_count'),
        func.sum(text('CASE WHEN is_touch = 0 THEN 1 ELSE 0 END')).label('detailed_count')
    ).join(Client).join(Log).filter(
        Log.created_at >= thirty_days_ago
    ).group_by(Project.id, Project.name, Client.name).order_by(desc('log_count')).limit(8).all()
    
    # Most active users by logging (last 30 days)
    most_active_loggers = db.session.query(
        User.first_name,
        User.last_name,
        func.count(Log.id).label('log_count'),
        func.sum(Log.hours).label('total_hours'),
        func.sum(text('CASE WHEN is_touch = 1 THEN 1 ELSE 0 END')).label('touch_count'),
        func.sum(text('CASE WHEN is_touch = 0 THEN 1 ELSE 0 END')).label('detailed_count')
    ).join(Log).filter(
        Log.created_at >= thirty_days_ago
    ).group_by(User.id).order_by(desc('log_count')).limit(8).all()
    
    return render_template('analytics.html',
                         # Top metrics
                         total_members=total_members,
                         total_projects=total_projects,
                         total_clients=total_clients,
                         open_tasks=open_tasks,
                         # Task analytics
                         completion_data=completion_data,
                         most_active_projects=most_active_projects,
                         # Log analytics
                         total_logs_last_30=total_logs_last_30,
                         touch_logs_last_30=touch_logs_last_30,
                         detailed_logs_last_30=detailed_logs_last_30,
                         total_hours_last_30=round(total_hours_last_30, 1),
                         log_activity_data=log_activity_data,
                         most_logged_projects=most_logged_projects,
                         most_active_loggers=most_active_loggers)

# LOGGING ROUTES
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
    
    return {'projects': projects}

@app.route('/add_touch_log', methods=['POST'])
def add_touch_log():
    if 'user_id' not in session:
        return {'success': False, 'error': 'Not logged in'}, 401
    
    project_id = request.json.get('project_id')
    
    if not project_id:
        return {'success': False, 'error': 'Project ID required'}, 400
    
    # Verify project exists and is active
    project = Project.query.filter_by(id=project_id, status='Active').first()
    if not project:
        return {'success': False, 'error': 'Project not found or inactive'}, 404
    
    # Create touch log
    log = Log(
        is_touch=True,
        user_id=session['user_id'],
        project_id=project_id
    )
    
    db.session.add(log)
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
    
    if not project_id:
        flash('Project is required', 'error')
        return redirect(request.referrer or url_for('dashboard'))
    
    if not notes:
        flash('Notes are required for time logs', 'error')
        return redirect(request.referrer or url_for('dashboard'))
    
    # Verify project exists and is active
    project = Project.query.filter_by(id=project_id, status='Active').first()
    if not project:
        flash('Project not found or inactive', 'error')
        return redirect(request.referrer or url_for('dashboard'))
    
    # Create time log
    log = Log(
        is_touch=False,
        hours=float(hours) if hours else None,
        fixed_cost=float(fixed_cost) if fixed_cost else None,
        notes=notes,
        user_id=session['user_id'],
        project_id=project_id
    )
    
    db.session.add(log)
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

# USERS ROUTES (Admin only)
@app.route('/users')
def users():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if user is admin
    if not session.get('is_admin', False):
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    users = User.query.order_by(User.first_name.asc()).all()
    
    return render_template('users.html', users=users)

@app.route('/add_user', methods=['POST'])
def add_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if user is admin
    if not session.get('is_admin', False):
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    is_admin = request.form.get('is_admin') == 'on'
    
    if not first_name or not email or not password:
        flash('First name, email, and password are required', 'error')
        return redirect(url_for('users'))
    
    # Check if email already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        flash('Email already exists', 'error')
        return redirect(url_for('users'))
    
    user = User(
        first_name=first_name,
        email=email,
        is_admin=is_admin
    )
    user.set_last_name(last_name)
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    flash('User created successfully', 'success')
    return redirect(url_for('users'))

@app.route('/edit_user/<int:user_id>', methods=['POST'])
def edit_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if user is admin
    if not session.get('is_admin', False):
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    is_admin = request.form.get('is_admin') == 'on'
    
    if not first_name or not email:
        flash('First name and email are required', 'error')
        return redirect(url_for('users'))
    
    # Check if email already exists (excluding current user)
    existing_user = User.query.filter(User.email == email, User.id != user_id).first()
    if existing_user:
        flash('Email already exists', 'error')
        return redirect(url_for('users'))
    
    user.first_name = first_name
    user.set_last_name(last_name)
    user.email = email
    user.is_admin = is_admin
    
    # Only update password if provided
    if password:
        user.set_password(password)
    
    db.session.commit()
    
    # Update session if editing own account
    if user_id == session['user_id']:
        session['user_name'] = user.full_name
        session['is_admin'] = user.is_admin
    
    flash('User updated successfully', 'success')
    return redirect(url_for('users'))

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Check if user is admin
    if not session.get('is_admin', False):
        flash('Access denied. Administrator privileges required.', 'error')
        return redirect(url_for('dashboard'))
    
    # Prevent deleting yourself
    if user_id == session['user_id']:
        flash('Cannot delete your own account', 'error')
        return redirect(url_for('users'))
    
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
        return redirect(url_for('users'))
    
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully', 'success')
    return redirect(url_for('users'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5001))) 