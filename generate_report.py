#!/usr/bin/env python3
"""
Generate a plain-text leadership snapshot from the Hub Tracker database.

Run locally after syncing production data:

    python generate_report.py
    python generate_report.py --output path/to/report.txt

Requires DATABASE_URL in the environment or .env (see app.py).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import and_, case, desc, func, or_

from models import (
    GENERAL_PROJECT_NAME,
    Client,
    Equipment,
    EquipmentAppointment,
    Log,
    Membership,
    MembershipFunding,
    Project,
    Quote,
    Task,
    User,
    db,
    get_current_time,
)


def fmt_currency(value) -> str:
    amount = Decimal(value or 0)
    return f"${amount:,.2f}"


def fmt_number(value, decimals: int = 0) -> str:
    number = float(value or 0)
    if decimals:
        return f"{number:,.{decimals}f}"
    return f"{int(round(number)):,}"


def section(title: str) -> list[str]:
    bar = "=" * len(title)
    return ["", title, bar]


def _log_hours_expr():
    """Sum hours from detailed logs plus touch logs that record hours."""
    detailed = func.coalesce(
        func.sum(case((Log.is_touch.is_(False), Log.hours), else_=0)),
        0,
    )
    touch = func.coalesce(
        func.sum(
            case(
                (and_(Log.is_touch.is_(True), Log.hours.isnot(None)), Log.hours),
                else_=0,
            )
        ),
        0,
    )
    return detailed + touch


def _log_cost_expr():
    return func.coalesce(
        func.sum(case((Log.is_touch.is_(False), Log.fixed_cost), else_=0)),
        0,
    )


def _quote_totals(bill_type: str | None = None, extra_filters=None):
    query = db.session.query(
        func.count(Quote.id),
        func.coalesce(func.sum(Quote.total_amount), 0),
    )
    if bill_type:
        query = query.filter(Quote.bill_type == bill_type)
    if extra_filters is not None:
        query = query.filter(extra_filters)
    return query.one()


def _issued_since(days: int):
    cutoff = get_current_time().date() - timedelta(days=days)
    return _quote_totals(extra_filters=Quote.issue_date >= cutoff)


def collect_overview(now) -> list[str]:
    thirty_days_ago = now - timedelta(days=29)

    total_clients = Client.query.count()
    clients_with_membership = Client.query.filter(Client.membership_id.isnot(None)).count()

    project_status_rows = (
        db.session.query(Project.status, func.count(Project.id))
        .group_by(Project.status)
        .all()
    )
    status_counts = {status or "Unknown": count for status, count in project_status_rows}

    active_non_general = Project.query.filter(
        Project.status == "Active",
        Project.name != GENERAL_PROJECT_NAME,
    ).count()

    role_rows = (
        db.session.query(User.role, func.count(User.id)).group_by(User.role).all()
    )
    role_counts = {role: count for role, count in role_rows}

    open_tasks = Task.query.filter_by(is_complete=False).count()
    completed_tasks = Task.query.filter_by(is_complete=True).count()
    tasks_completed_30d = Task.query.filter(
        Task.is_complete.is_(True),
        Task.completed_on >= thirty_days_ago,
    ).count()

    lines = section("Scale & Engagement")
    lines.extend(
        [
            f"Clients (total)                    {fmt_number(total_clients)}",
            f"Clients (with membership)          {fmt_number(clients_with_membership)}",
            f"Projects (Active)                  {fmt_number(status_counts.get('Active', 0))}",
            f"Projects (Prospective)             {fmt_number(status_counts.get('Prospective', 0))}",
            f"Projects (Archived)                {fmt_number(status_counts.get('Archived', 0))}",
            f"Active projects (excl. General)    {fmt_number(active_non_general)}",
            f"Users (admin)                      {fmt_number(role_counts.get('admin', 0))}",
            f"Users (trainee)                    {fmt_number(role_counts.get('trainee', 0))}",
            f"Users (finance)                    {fmt_number(role_counts.get('finance', 0))}",
            f"Tasks (open)                       {fmt_number(open_tasks)}",
            f"Tasks (completed, all-time)        {fmt_number(completed_tasks)}",
            f"Tasks completed (last 30 days)      {fmt_number(tasks_completed_30d)}",
        ]
    )
    return lines


def collect_billing() -> list[str]:
    approved_filter = and_(
        Quote.bill_type == "quote",
        or_(Quote.approved_by_name.isnot(None), Quote.approved_at.isnot(None)),
    )
    awaiting_filter = and_(
        Quote.bill_type == "quote",
        Quote.is_public.is_(True),
        Quote.approved_by_name.is_(None),
        Quote.approved_at.is_(None),
    )

    all_count, all_total = _quote_totals()
    quote_count, quote_total = _quote_totals("quote")
    invoice_count, invoice_total = _quote_totals("invoice")
    approved_count, approved_total = _quote_totals(extra_filters=approved_filter)
    awaiting_count, awaiting_total = _quote_totals(extra_filters=awaiting_filter)
    issued_30_count, issued_30_total = _issued_since(30)
    issued_90_count, issued_90_total = _issued_since(90)

    top_clients = (
        db.session.query(
            Client.name,
            func.coalesce(func.sum(Quote.total_amount), 0).label("billed"),
        )
        .join(Quote, Quote.client_id == Client.id)
        .group_by(Client.id, Client.name)
        .order_by(desc("billed"))
        .limit(10)
        .all()
    )

    lines = section("Billing Snapshot")
    lines.extend(
        [
            f"Bills (total)                      {fmt_number(all_count)}  ({fmt_currency(all_total)})",
            f"Quotes                             {fmt_number(quote_count)}  ({fmt_currency(quote_total)})",
            f"Invoices                           {fmt_number(invoice_count)}  ({fmt_currency(invoice_total)})",
            f"Client-approved quotes             {fmt_number(approved_count)}  ({fmt_currency(approved_total)})",
            f"Quotes awaiting client approval    {fmt_number(awaiting_count)}  ({fmt_currency(awaiting_total)})",
            f"Issued last 30 days                {fmt_number(issued_30_count)}  ({fmt_currency(issued_30_total)})",
            f"Issued last 90 days                {fmt_number(issued_90_count)}  ({fmt_currency(issued_90_total)})",
            "",
            "Top 10 clients by billed amount:",
        ]
    )
    if top_clients:
        for rank, (name, billed) in enumerate(top_clients, start=1):
            lines.append(f"  {rank:2}. {name:<40} {fmt_currency(billed)}")
    else:
        lines.append("  (none)")
    return lines


def collect_memberships(now) -> list[str]:
    total_memberships = Membership.query.count()
    active_memberships = (
        db.session.query(Membership.id)
        .join(MembershipFunding, MembershipFunding.membership_id == Membership.id)
        .filter(
            MembershipFunding.start_date <= now,
            MembershipFunding.end_date >= now,
        )
        .distinct()
        .count()
    )

    funding_totals = db.session.query(
        func.coalesce(func.sum(MembershipFunding.amount), 0),
        func.coalesce(func.sum(MembershipFunding.dollar_budget), 0),
        func.coalesce(func.sum(MembershipFunding.time_budget), 0),
    ).one()

    logged_consumable = db.session.query(_log_cost_expr()).scalar() or 0

    top_memberships = (
        db.session.query(
            Membership.title,
            func.count(Client.id).label("client_count"),
        )
        .outerjoin(Client, Client.membership_id == Membership.id)
        .group_by(Membership.id, Membership.title)
        .order_by(desc("client_count"))
        .limit(5)
        .all()
    )

    lines = section("Memberships & Funding")
    lines.extend(
        [
            f"Memberships (total)                {fmt_number(total_memberships)}",
            f"Memberships (currently active)     {fmt_number(active_memberships)}",
            f"All-time funding revenue           {fmt_currency(funding_totals[0])}",
            f"All-time dollar budgets            {fmt_currency(funding_totals[1])}",
            f"All-time hour budgets              {fmt_number(funding_totals[2])} hrs",
            f"Logged consumable spend (all-time) {fmt_currency(logged_consumable)}",
            "",
            "Top 5 memberships by client count:",
        ]
    )
    if top_memberships:
        for rank, (title, client_count) in enumerate(top_memberships, start=1):
            lines.append(f"  {rank}. {title:<45} {fmt_number(client_count)} clients")
    else:
        lines.append("  (none)")
    return lines


def collect_logs(now) -> list[str]:
    thirty_days_ago = now - timedelta(days=29)

    all_hours = db.session.query(_log_hours_expr()).scalar() or 0
    all_cost = db.session.query(_log_cost_expr()).scalar() or 0
    log_entries = Log.query.count()

    recent_hours = (
        db.session.query(_log_hours_expr())
        .filter(Log.created_at >= thirty_days_ago)
        .scalar()
        or 0
    )
    recent_cost = (
        db.session.query(_log_cost_expr())
        .filter(Log.created_at >= thirty_days_ago)
        .scalar()
        or 0
    )
    recent_log_entries = Log.query.filter(Log.created_at >= thirty_days_ago).count()
    projects_touched_30d = (
        db.session.query(func.count(func.distinct(Log.project_id)))
        .filter(
            Log.created_at >= thirty_days_ago,
            Log.project_id.isnot(None),
        )
        .scalar()
        or 0
    )

    top_projects = (
        db.session.query(
            Project.name,
            Client.name,
            _log_hours_expr().label("hours"),
        )
        .join(Client, Client.id == Project.client_id)
        .join(Log, Log.project_id == Project.id)
        .filter(Project.name != GENERAL_PROJECT_NAME)
        .group_by(Project.id, Project.name, Client.name)
        .order_by(desc("hours"))
        .limit(5)
        .all()
    )

    lines = section("Delivery & Utilization")
    lines.extend(
        [
            f"Log entries (all-time)             {fmt_number(log_entries)}",
            f"Hours logged (all-time)            {fmt_number(all_hours, 1)}",
            f"Consumable cost logged (all-time) {fmt_currency(all_cost)}",
            f"Log entries (last 30 days)         {fmt_number(recent_log_entries)}",
            f"Hours logged (last 30 days)        {fmt_number(recent_hours, 1)}",
            f"Consumable cost (last 30 days)     {fmt_currency(recent_cost)}",
            f"Projects with log activity (30d)   {fmt_number(projects_touched_30d)}",
            "",
            "Top 5 projects by hours logged (all-time, excl. General):",
        ]
    )
    if top_projects:
        for rank, (project_name, client_name, hours) in enumerate(top_projects, start=1):
            lines.append(
                f"  {rank}. {project_name} ({client_name}) — {fmt_number(hours, 1)} hrs"
            )
    else:
        lines.append("  (none)")
    return lines


def collect_equipment(now) -> list[str]:
    thirty_days_ago = now - timedelta(days=29)

    equipment_total = Equipment.query.count()
    schedulable = Equipment.query.filter_by(is_schedulable=True).count()

    status_rows = (
        db.session.query(EquipmentAppointment.status, func.count(EquipmentAppointment.id))
        .group_by(EquipmentAppointment.status)
        .all()
    )
    status_counts = {status: count for status, count in status_rows}

    booking_seconds = (
        db.session.query(
            func.coalesce(
                func.sum(
                    func.extract(
                        "epoch",
                        EquipmentAppointment.end_time - EquipmentAppointment.start_time,
                    )
                ),
                0,
            )
        )
        .filter(
            EquipmentAppointment.status == "approved",
            EquipmentAppointment.start_time >= thirty_days_ago,
        )
        .scalar()
        or 0
    )
    booking_hours_30d = float(booking_seconds) / 3600.0

    lines = section("Equipment & Scheduling")
    lines.extend(
        [
            f"Equipment (total)                  {fmt_number(equipment_total)}",
            f"Equipment (schedulable)            {fmt_number(schedulable)}",
            f"Appointments (approved)              {fmt_number(status_counts.get('approved', 0))}",
            f"Appointments (pending)               {fmt_number(status_counts.get('pending', 0))}",
            f"Appointments (cancelled)             {fmt_number(status_counts.get('cancelled', 0))}",
            f"Approved booking hours (last 30d)    {fmt_number(booking_hours_30d, 1)}",
        ]
    )
    return lines


def build_report() -> str:
    now = get_current_time()
    header = now.strftime("Generated: %A, %b %d, %Y %I:%M %p America/Chicago")

    body_lines = [
        header,
        "",
        "HUB TRACKER — LEADERSHIP SNAPSHOT",
        "Point-in-time snapshot from local database.",
    ]
    body_lines.extend(collect_overview(now))
    body_lines.extend(collect_billing())
    body_lines.extend(collect_memberships(now))
    body_lines.extend(collect_logs(now))
    body_lines.extend(collect_equipment(now))
    body_lines.extend(
        [
            "",
            "Note: Billing totals use stored Quote.total_amount values.",
            "Utilization metrics are derived from logged hours and fixed costs.",
        ]
    )
    return "\n".join(body_lines) + "\n"


def default_output_path() -> str:
    now = get_current_time()
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    filename = f"hubtracker_snapshot_{now.strftime('%Y%m%d_%H%M%S')}.txt"
    return os.path.join(reports_dir, filename)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Hub Tracker leadership snapshot report.")
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: reports/hubtracker_snapshot_<timestamp>.txt)",
    )
    args = parser.parse_args()

    from app import app

    with app.app_context():
        report_text = build_report()

    output_path = args.output or default_output_path()
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(report_text)

    print(f"Report written to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
