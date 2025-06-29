from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_migrate import Migrate
from datetime import datetime
import pytz
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///hubtracker.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Import models and db
from models import db, User, Client, Membership, Project, Task, Log

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)

# Time zone configuration
TIMEZONE = pytz.timezone('America/Chicago')

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login')
def login():
    users = User.query.all()
    return render_template('login.html', users=users)

@app.route('/login/<int:user_id>')
def login_user(user_id):
    user = User.query.get_or_404(user_id)
    session['user_id'] = user.id
    session['user_name'] = user.first_name
    flash(f'Welcome, {user.first_name}!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', user=user)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Placeholder routes for navigation
@app.route('/projects')
def projects():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('projects.html')

@app.route('/clients')
def clients():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('clients.html')

@app.route('/memberships')
def memberships():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('memberships.html')

@app.route('/reports')
def reports():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('reports.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 