#!/usr/bin/env python3
"""
Ensure every client has a "General" project (Archived, unassigned lead).
is_default is never set here — only the user can mark a default project.

Also callable on app startup (see app.py); run manually:

    python ensure_general_projects.py
"""

import sys
from typing import Any, Dict

from models import db, Client, Project, GENERAL_PROJECT_NAME


def ensure_general_projects_for_all_clients() -> Dict[str, Any]:
    """Idempotent backfill. Returns counts for logging."""
    created = 0
    normalized = 0
    clients = Client.query.all()
    for client in clients:
        general = Project.query.filter_by(
            client_id=client.id, name=GENERAL_PROJECT_NAME
        ).first()
        if not general:
            db.session.add(
                Project(
                    name=GENERAL_PROJECT_NAME,
                    client_id=client.id,
                    project_lead_id=None,
                    status="Archived",
                    is_default=False,
                )
            )
            created += 1
        else:
            changed = False
            if general.status != "Archived":
                general.status = "Archived"
                changed = True
            if general.project_lead_id is not None:
                general.project_lead_id = None
                changed = True
            if changed:
                normalized += 1
    db.session.commit()
    return {
        "clients": len(clients),
        "general_created": created,
        "general_normalized": normalized,
    }


def main() -> None:
    from app import app

    with app.app_context():
        stats = ensure_general_projects_for_all_clients()
        print(
            f"Clients: {stats['clients']} | General created: {stats['general_created']} | "
            f"General normalized (status/lead): {stats['general_normalized']}"
        )


if __name__ == "__main__":
    main()
    sys.exit(0)
