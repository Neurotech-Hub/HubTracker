# Hub Tracker

A modern, full-stack project management web application designed for teams and businesses to efficiently track projects, manage clients, complete tasks, and log time. Built with a focus on speed, usability, and clean design.

## Key Features

### Core Management
- **Multi-User Workspace**: Collaborative environment with role-based access
- **Client & Membership Tracking**: Comprehensive client relationship management
- **Project Organization**: Hierarchical project structure with status tracking
- **Smart Task System**: Intuitive task creation with tagging and assignment
- **Time & Cost Logging**: Dual-mode logging (quick touch + detailed entries)

### User Experience
- **Real-Time Dashboard**: Activity feeds and progress tracking
- **Advanced Analytics**: Task completion trends and project performance metrics
- **Responsive Interface**: Optimized for desktop and mobile workflows
- **Keyboard-Friendly**: Streamlined data entry with smart autocomplete

### Technical Architecture
- **Backend Framework**: Flask with SQLAlchemy ORM for robust data management
- **Database**: SQLite with timezone support and migration capabilities
- **Frontend Stack**: Bootstrap 5 + Alpine.js for reactive components
- **Design System**: Custom CSS with consistent UI patterns
- **API Layer**: RESTful endpoints for dynamic content and integrations

## Architecture Overview

### Application Structure
```
├── Core Application      # Main Flask app with routing and business logic
├── Data Layer           # SQLAlchemy models with relationship mapping
├── Template System      # Jinja2 templates with component architecture
├── Static Assets        # CSS, JavaScript, and design system
├── API Endpoints        # RESTful services for dynamic functionality
└── Configuration        # Environment-based settings and deployment configs
```

### Data Architecture
- **Relational Design**: Normalized database schema with referential integrity
- **Time-Zone Aware**: Consistent temporal data handling across regions
- **Migration Support**: Version-controlled database schema evolution
- **Performance Optimized**: Efficient queries with proper indexing strategies

## Quick Start

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd HubTracker
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Database Setup**

   HubTracker uses Flask-Migrate for database management. This ensures consistent database schema across all installations.

   ```bash
   # First time setup only:
   flask db upgrade   # This will create hubtracker.db and apply all migrations
   ```

   If you want sample data to explore features:
   ```bash
   python init_db.py  # Creates tables AND adds sample users/projects/tasks
   ```

   ⚠️ **Important**: Only use `init_db.py` for initial exploration. For real usage:
   - Use `flask db upgrade` for first-time setup
   - Use migrations for all schema changes
   - Never use `init_db.py` on a production database

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the application**
   - Open your browser and go to `http://localhost:5000`
   - Create your first user account and start using the app

### Database Migration Workflow

HubTracker uses Flask-Migrate to manage database schema changes. Here's how to handle database changes:

1. **Making Schema Changes**
   - Edit the models in `models.py`
   - Generate a new migration:
     ```bash
     flask db migrate -m "Description of your changes"
     ```
   - Review the generated migration in `migrations/versions/`
   - Apply the migration:
     ```bash
     flask db upgrade
     ```

2. **Common Migration Commands**
   ```bash
   flask db migrate -m "message"  # Create a new migration
   flask db upgrade              # Apply pending migrations
   flask db downgrade           # Rollback last migration
   flask db history            # View migration history
   flask db current           # Show current revision
   ```

3. **Best Practices**
   - Always review generated migrations before applying
   - Commit migrations to version control
   - Test migrations on development before production
   - Back up production database before migrating
   - Never delete migration files once they're in use

4. **Troubleshooting**
   If you encounter migration issues:
   ```bash
   # View current database state
   flask db current

   # Force a specific revision
   flask db stamp <revision_id>

   # Show migration SQL
   flask db upgrade --sql
   ```

## Deployment

### Cloud Deployment (Render, Heroku, etc.)

#### Render Deployment

1. **Fork/Clone to your GitHub**
   ```bash
   git clone <your-repo-url>
   cd HubTracker
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

2. **Create Render Web Service**
   - Connect your GitHub repository
   - Set **Build Command**: `pip install -r requirements.txt`
   - Set **Start Command**: `python app.py`
   - Set **Environment**: `python`

3. **Environment Variables (in Render Dashboard)**
   ```
   FLASK_ENV=production
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=sqlite:///hub_tracker.db  # Or PostgreSQL URL for production
   ```

4. **Database Setup**
   - Render will automatically run migrations on deploy
   - Database will be created fresh (no sample data)
   - First user should be created through the web interface

#### Other Cloud Platforms

**Heroku:**
```bash
git push heroku main
heroku run flask db upgrade  # Initialize database
```

**DigitalOcean App Platform:**
- Set build command: `pip install -r requirements.txt`
- Set run command: `python app.py`
- Add environment variables in dashboard

### Local Production Setup

1. **Production Environment**
   ```bash
   export FLASK_ENV=production
   export SECRET_KEY=your-secret-key-here
   export DATABASE_URL=postgresql://user:pass@localhost/hubtracker  # Optional
   ```

2. **Initialize Database**
   ```bash
   flask db upgrade        # Recommended: Uses migrations
   # OR
   python init_clean_db.py # Alternative: Direct setup
   ```

3. **Run with Gunicorn**
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

### Environment Variables

| Variable       | Description                | Default                    | Required             |
| -------------- | -------------------------- | -------------------------- | -------------------- |
| `FLASK_ENV`    | Environment mode           | `development`              | No                   |
| `SECRET_KEY`   | Flask secret key           | Random                     | **Yes (Production)** |
| `DATABASE_URL` | Database connection string | `sqlite:///hub_tracker.db` | No                   |
| `PORT`         | Server port                | `5000`                     | No                   |

### Database Migration

For existing deployments with schema changes:
```bash
flask db upgrade  # Apply new migrations
```

**Important**: Never use `python init_db.py` in production - it will overwrite your data with sample data!

## Development

### Extensibility
- **Modular Architecture**: Clean separation of concerns for easy feature additions
- **Component System**: Reusable UI components and templates
- **API-First Design**: Backend services designed for integration and extension
- **Configuration Management**: Environment-based settings for different deployment contexts

### Development Workflow
- **Hot Reloading**: Automatic server restart during development
- **Debug Mode**: Comprehensive error reporting and interactive debugging
- **Migration Support**: Database schema versioning and rollback capabilities
- **Testing Framework**: Unit and integration testing infrastructure

## Security & Best Practices

### Built-in Security
- **Session Management**: Secure user authentication and authorization
- **Data Validation**: Input sanitization and validation at multiple layers
- **CSRF Protection**: Cross-site request forgery prevention
- **SQL Injection Prevention**: Parameterized queries via SQLAlchemy ORM

### Production Readiness
- **Environment Configuration**: Secure credential management
- **HTTPS Support**: SSL/TLS encryption for data in transit
- **Error Handling**: Graceful failure modes and user feedback
- **Performance Optimization**: Efficient database queries and caching strategies

## Contributing

We welcome contributions that improve functionality, performance, or user experience. Please ensure all changes include appropriate testing and documentation.

## Support

For technical discussions and feature requests, please use the repository's issue tracking system. 