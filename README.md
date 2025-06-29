# Hub Tracker

A modern project management web application built with Flask, designed for tracking projects, clients, tasks, and time logs. Hub Tracker provides a clean, responsive interface for managing your business operations.

## Features

- **User Management**: Multi-user support with admin privileges
- **Client Management**: Track client information and memberships
- **Project Tracking**: Organize work by projects with detailed notes
- **Task Management**: Create and track tasks with completion status
- **Time Logging**: Log hours worked and fixed costs
- **Dashboard**: Overview of current projects and activities
- **Responsive Design**: Works seamlessly on desktop and mobile devices

## Technology Stack

- **Backend**: Flask 3.0.0 with SQLAlchemy ORM
- **Database**: SQLite (with timezone support)
- **Frontend**: Bootstrap 5.3.0 with custom CSS
- **Icons**: Bootstrap Icons
- **Time Zone**: America/Chicago (configurable)
- **Deployment**: Render-ready with Gunicorn

## Project Structure

```
HubTracker/
├── app.py              # Main Flask application
├── models.py           # Database models
├── init_db.py          # Database initialization script
├── requirements.txt    # Python dependencies
├── .gitignore         # Git ignore rules
├── README.md          # This file
├── static/
│   └── css/
│       └── style.css  # Custom styles
└── templates/
    ├── base.html      # Base template with sidebar
    ├── login.html     # User selection page
    ├── dashboard.html # Main dashboard
    ├── projects.html  # Projects page (placeholder)
    ├── clients.html   # Clients page (placeholder)
    ├── memberships.html # Memberships page (placeholder)
    └── reports.html   # Reports page (placeholder)
```

## Database Models

- **Users**: User accounts with admin privileges
- **Clients**: Client/company information
- **Memberships**: Subscription/membership tracking
- **Projects**: Project information linked to clients
- **Tasks**: Task tracking with completion status
- **Logs**: Time and cost logging for projects

## Quick Start

### Local Development

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

4. **Initialize the database**
   ```bash
   python init_db.py
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the application**
   Open your browser and go to `http://localhost:5000`

### Sample Users

The database initialization script creates several sample users:

- **John Smith** (Admin)
- **Sarah Johnson** (User)
- **Mike Brown** (User)
- **Emily Davis** (User)
- **Alex** (User - no last name)

Click on any user to "log in" and explore the application.

## Deployment on Render

This application is configured for easy deployment on Render's web service.

### Prerequisites

1. Push your code to a GitHub repository
2. Create a Render account

### Deployment Steps

1. **Connect to Render**
   - Go to [Render Dashboard](https://dashboard.render.com/)
   - Click "New" → "Web Service"
   - Connect your GitHub repository

2. **Configure the Service**
   - **Name**: `hub-tracker` (or your preferred name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

3. **Environment Variables** (Optional)
   - `SECRET_KEY`: Your secret key for sessions
   - `DATABASE_URL`: Will use SQLite by default

4. **Deploy**
   - Click "Create Web Service"
   - Render will automatically build and deploy your application

### First Time Setup on Render

After deployment, you'll need to initialize the database:

1. Go to your Render service dashboard
2. Open the "Shell" tab
3. Run: `python init_db.py`

## Configuration

### Environment Variables

- `SECRET_KEY`: Flask secret key (defaults to development key)
- `DATABASE_URL`: Database connection string (defaults to SQLite)
- `PORT`: Port number (defaults to 5000)

### Time Zone

The application is configured for America/Chicago timezone. To change this:

1. Update `TIMEZONE` in `models.py`
2. Update `TIMEZONE` in `app.py`

## Development

### Adding New Features

The application is structured to make adding new features straightforward:

1. **Database Changes**: Update models in `models.py`
2. **Routes**: Add new routes in `app.py`
3. **Templates**: Create new templates in `templates/`
4. **Styles**: Add custom CSS to `static/css/style.css`

### Database Migrations

For production deployments, consider using Flask-Migrate:

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

## Security Notes

- Change the `SECRET_KEY` in production
- Implement proper password hashing for user authentication
- Add CSRF protection for forms
- Configure HTTPS for production deployments

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. Please check the license file for details.

## Support

For issues and questions, please create an issue in the GitHub repository. 