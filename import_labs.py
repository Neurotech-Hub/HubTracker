from flask import Flask
from models import db, Client, Project
import os
import json

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///hubtracker.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

def import_labs():
    app = create_app()
    
    with app.app_context():
        # Read and parse the JSON file
        with open('output.txt', 'r') as f:
            data = json.load(f)
        
        # Create clients and their projects
        for client_data in data['Clients']:
            # Create or get client
            client_name = client_data['Name']
            client = Client.query.filter_by(name=client_name).first()
            
            if not client:
                client = Client(name=client_name)
                db.session.add(client)
                print(f"Created client: {client_name}")
            else:
                print(f"Found existing client: {client_name}")
            
            # Ensure client is saved to get its ID
            db.session.flush()
            
            # Create projects for this client
            for project_name in client_data['Projects']:
                # Check if project exists
                project = Project.query.filter_by(
                    name=project_name,
                    client_id=client.id
                ).first()
                
                if not project:
                    project = Project(
                        name=project_name,
                        client_id=client.id,
                        status='Archived',
                        project_lead_id=1
                    )
                    db.session.add(project)
                    print(f"  Created project: {project_name}")
                else:
                    # Update existing project
                    project.status = 'Archived'
                    project.project_lead_id = 1
                    print(f"  Updated existing project: {project_name}")
        
        # Commit all changes
        try:
            db.session.commit()
            print("\nSuccessfully imported all labs and projects!")
        except Exception as e:
            db.session.rollback()
            print(f"\nError during import: {str(e)}")

if __name__ == '__main__':
    import_labs() 