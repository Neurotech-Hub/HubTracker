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
- **Database**: PostgreSQL with timezone support and migration capabilities
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

   HubTracker uses PostgreSQL for all environments. You'll need to set up PostgreSQL locally or use a cloud database.

   **Local PostgreSQL Setup:**
   ```bash
   # Install PostgreSQL first (see PostgreSQL Setup section below)
   # Then run migrations:
   flask db upgrade
   ```

   **Cloud Database (Recommended):**
   - Use Render PostgreSQL service for production
   - Use any PostgreSQL cloud service for development
   - Set DATABASE_URL environment variable
   - Run migrations: flask db upgrade

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

### PostgreSQL Setup

PostgreSQL is required for HubTracker. You can set it up locally or use a cloud service.

#### Prerequisites

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Windows:**
- Download from https://www.postgresql.org/download/windows/
- Install with default settings

#### Manual Setup

1. **Create Database User and Setup Database**
   ```bash
   # Connect to PostgreSQL
   # On macOS:
   psql postgres
   # On Linux:
   sudo -u postgres psql

   # Create user with password (replace 'your_password' with a secure password)
   CREATE USER hubtracker_user WITH PASSWORD 'your_password' CREATEDB;

   # Create database with proper ownership
   CREATE DATABASE hubtracker_dev OWNER hubtracker_user;

   # Grant necessary privileges
   GRANT ALL PRIVILEGES ON DATABASE hubtracker_dev TO hubtracker_user;
   
   # Set default privileges for future tables
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hubtracker_user;

   # Exit
   \q
   ```

   If you need to reset the database at any point:
   ```bash
   psql postgres -c "DROP DATABASE IF EXISTS hubtracker_dev;"
   psql postgres -c "CREATE DATABASE hubtracker_dev OWNER hubtracker_user;"
   psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE hubtracker_dev TO hubtracker_user;"
   psql postgres -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO hubtracker_user;"
   ```

2. **Create Environment File**
   Create a `.env` file in your project root:
   ```env
   FLASK_ENV=development
   SECRET_KEY=dev-secret-key-change-in-production
   DATABASE_URL=postgresql+psycopg://hubtracker_user:your_password@localhost:5432/hubtracker_dev
   ```

3. **Install Dependencies and Initialize Database**
   ```bash
   pip install -r requirements.txt
   flask db upgrade  # This will create all database tables
   python app.py
   ```

Note: On macOS, if you get connection errors, try removing the `-h localhost` flag when connecting with psql. If you get permission errors during migrations, make sure you've granted all the necessary privileges as shown in step 1.

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

5. **Starting Fresh (Clear All Migrations)**
   If you need to completely reset your migration history and database:
   ```bash
   # WARNING: This will delete all data and migration history!
   
   # 1. Stop the Flask application
   # 2. Drop and recreate your PostgreSQL database
   dropdb your_database_name
   createdb your_database_name
   
   # 3. Delete migration history
   rm -rf migrations/versions/*
   
   # 4. Reinitialize migrations (if migrations folder doesn't exist)
   flask db init
   
   # 5. Create initial migration from current models
   flask db migrate -m "Initial migration"
   
   # 6. Apply the migration to create fresh database
   flask db upgrade
   ```

   **When to use this:**
   - During development when migration history becomes messy
   - When you want to consolidate many migrations into one
   - When starting a new development environment
   
   **⚠️ NEVER use this in production** - you will lose all data!

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
   - Set **Start Command**: `python start.py`
   - Set **Environment**: `python`

3. **Environment Variables (in Render Dashboard)**
   ```
   FLASK_ENV=production
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=postgresql+psycopg://username:password@host:port/database
   ```
   
   **Note:** PostgreSQL is required for production deployment. Set up a PostgreSQL service in Render and use the provided connection string.

4. **Database Setup**
   - The `start.py` script automatically:
     - Creates the `instance` directory if it doesn't exist
     - Checks if database migrations are needed
     - Runs migrations only when necessary (safe for existing data)
     - Starts the web server with gunicorn
   - **Your database is completely safe** - the script never destroys existing data
   - Your existing data will be preserved across deployments
   - First user should be created through the web interface (only if no users exist)

5. **Troubleshooting Render Deployment**
   - Make sure gunicorn is in your requirements.txt
   - Check Render logs for detailed error messages
   - Ensure your repository is properly connected and up to date

#### Render Deployment (PostgreSQL Required)

1. **Create PostgreSQL Service in Render**
   - Go to your Render dashboard
   - Click "New" → "PostgreSQL"
   - Choose your plan and region
   - Note the connection details

2. **Update Environment Variables**
   Add the PostgreSQL connection string to your web service:
   ```
   FLASK_ENV=production
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=postgresql+psycopg://username:password@host:port/database
   ```

3. **Deploy**
   - The `start.py` script will automatically detect PostgreSQL and use it
   - Migrations will run automatically on first deployment
   - Your data will be persistent and backed up by Render

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
   export DATABASE_URL=postgresql+psycopg://user:pass@localhost/hubtracker
   ```

2. **Initialize Database**
   ```bash
   flask db upgrade        # Uses migrations to set up PostgreSQL tables
   ```

3. **Run with Gunicorn**
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

### Environment Variables

| Variable       | Description                  | Default       | Required             |
| -------------- | ---------------------------- | ------------- | -------------------- |
| `FLASK_ENV`    | Environment mode             | `development` | No                   |
| `SECRET_KEY`   | Flask secret key             | Random        | **Yes (Production)** |
| `DATABASE_URL` | PostgreSQL connection string | None          | **Yes**              |
| `PORT`         | Server port                  | `5000`        | No                   |

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