"""Public, read-only analytics API for external reporting.

Mirrors the analytics overview and the fiscal-year projection without
client or user records: no names, contact details, emails, individual
salaries, notes, approver names, or ids for people or clients. Project
names, membership titles, bill titles, and equipment names are operational
labels and are included. The projection reports combined salary cost
because that is what the profit-and-loss net uses.

Keep the aggregate definitions aligned with analytics() and finances()
in app.py.
"""

from __future__ import annotations

import hashlib
import json
import time as time_module
from dataclasses import dataclass
from datetime import datetime, timedelta, date, time as time_of_day

from flask import Blueprint, jsonify, make_response, render_template, request, url_for
from sqlalchemy import and_, case, desc, func

from models import (
    GENERAL_PROJECT_NAME,
    TIMEZONE,
    Affiliation,
    Client,
    Equipment,
    EquipmentAppointment,
    FinanceSettings,
    Log,
    Membership,
    MembershipFunding,
    Project,
    Quote,
    User,
    db,
    get_current_time,
)

analytics_public_bp = Blueprint("analytics_public", __name__)

API_VERSION = "1"
RATE_LIMIT = 60
RATE_WINDOW = 60
MAX_SERIES_POINTS = 400
MAX_RANGE_DAYS = 3660
DEFAULT_LIMIT = 5
MAX_LIMIT = 25

SECTIONS = (
    "summary",
    "time",
    "projects",
    "clients",
    "billing",
    "memberships",
    "appointments",
    "projection",
)
PERIODS = (
    "today",
    "this_week",
    "last_week",
    "last_30_days",
    "this_month",
    "last_month",
    "fiscal_year",
    "all_time",
)
PROJECT_STATUSES = ("Active", "Prospective", "Awaiting", "Paused", "Archived")
BILL_TYPES = ("quote", "invoice", "planned")
GRAINS = ("day", "week", "month")
APPOINTMENT_STATUSES = ("pending", "approved", "cancelled")
ALLOWED_PARAMS = {
    "section",
    "period",
    "start",
    "end",
    "project_status",
    "bill_type",
    "limit",
    "series",
    "grain",
}

PRIVACY = {
    "description": (
        "Aggregate operational metrics for reporting. "
        "Client and user records are never returned."
    ),
    "omitted": [
        "User names, email addresses, a person's role, individual salaries, and notes",
        "Client names, contact details, billing addresses, and notes",
        "Log notes, quote approver names, appointment purposes, and appointment notes",
        "User ids and client ids",
    ],
    "included_labels": [
        "Project names and statuses",
        "Membership titles and funding end dates",
        "Bill titles on the fiscal-year projection",
        "Equipment names",
        "Combined salary cost and fixed costs on the fiscal-year projection",
    ],
    "substitution": (
        "The analytics page ranks individual people by hours and by appointments. "
        "This API returns hour totals and equipment rankings instead. "
        "The projection's salary column is one combined monthly cost, not a list of people."
    ),
}

PAGE_MAP = (
    ("Active Memberships", "summary.active_memberships"),
    ("Active Projects", "summary.active_projects"),
    ("Clients", "summary.clients"),
    ("Total hours (all time)", "time.total_hours_all_time"),
    ("Total hours (last 30 days)", "time.total_hours_last_30_days"),
    ("Total logs", "time.total_logs"),
    ("Hours by user", "Omitted. Use time.hours, time.hours_this_week, and time.hours_last_week."),
    ("Top projects by hours (30 days)", "projects.top_by_hours (project, status, hours; no client)"),
    ("Client counts", "clients.total, clients.internal, clients.external"),
    ("Top clients", "Omitted."),
    ("Billing totals", "billing.total_bills, active_quotes, active_invoices, internal_invoices, external_invoices"),
    ("Top clients by billed amount", "Omitted."),
    ("Membership totals and budgets", "memberships.total, currently_active, active_dollar_budget, active_hour_budget"),
    ("Memberships ending soonest", "memberships.ending_soonest (title and funding end date)"),
    ("Equipment, trainees, appointments", "appointments.equipment_count, trainee_count, appointment_count"),
    ("Most scheduled trainees", "Omitted. appointments.top_equipment ranks equipment instead."),
    ("Fiscal-year projection", "projection.months and projection.totals. Client names and individual salaries are omitted."),
)

EFFECTS = (
    (
        "Summary",
        "Active memberships and active projects are always the current organization snapshot. "
        "summary.clients follows the same date-window rule as clients.total.",
    ),
    (
        "Client counts",
        "Unfiltered requests count every client on file. With a date filter, counts are distinct clients "
        "that have at least one effort log in that window (and honor project_status when set).",
    ),
    ("Membership totals, budgets, and ending dates", "Always the current organization snapshot."),
    ("Time totals", "Honor the date window and project_status. Unfiltered totals are all-time."),
    ("Project counts by status", "Honor project_status. Not limited by the date window."),
    ("Projects with time logged", "All-time unless a date window is set, then limited to that window. Honors project_status."),
    ("Project hour ranking", "Last 30 days unless a date window is set. General projects are left out. Honors project_status."),
    ("Billing", "All bills unless a date window is set (compared on issue date). Honors bill_type and project_status."),
    ("Equipment and trainee counts", "Always the current inventory and roster size. Counts only."),
    ("Appointment counts and equipment ranking", "All appointments unless a date window is set. Admin bookings are excluded."),
    (
        "Fiscal-year projection",
        "Current July–June year, including later months. period=fiscal_year and an unfiltered request return all 12 months. "
        "A shorter period, or start and end, keeps months that overlap that range. "
        "bill_type and project_status apply to profited and projected bills only. "
        "Funding, the combined salary cost, and fixed costs ignore those two filters. limit does not apply.",
    ),
)

FIELD_GROUPS = (
    {
        "id": "summary",
        "title": "summary",
        "fields": (
            ("active_memberships", "Memberships whose funding covers the current moment."),
            ("active_projects", "Projects with status Active."),
            (
                "clients",
                "Unfiltered: how many client records exist. With a date filter: distinct clients with an "
                "effort log in that window. No client is identified.",
            ),
        ),
    },
    {
        "id": "time",
        "title": "time",
        "fields": (
            ("hours", "Hours in the active window. All-time when no date window is requested."),
            ("logs", "Log rows in that same window, including rows with no hours."),
            ("detailed_hours", "Hours on logs that are not touch entries."),
            ("touch_hours", "Hours on touch entries."),
            ("total_hours_all_time", "Unfiltered requests only. Same number as the overview."),
            ("total_hours_last_30_days", "Unfiltered requests only. Rolling 30 days of 24 hours."),
            ("hours_this_week", "Unfiltered requests only. Monday through Sunday, America/Chicago."),
            ("hours_last_week", "Unfiltered requests only. The previous Monday through Sunday."),
            ("total_logs", "Unfiltered requests only. All-time log count."),
            ("series", "Null unless series is on. Bucketed hours and log counts."),
        ),
    },
    {
        "id": "projects",
        "title": "projects",
        "fields": (
            ("total", "Project count after project_status is applied."),
            ("by_status", "Counts for Active, Prospective, Awaiting, Paused, and Archived."),
            ("with_time_logged", "Distinct projects that have at least one log in the time window."),
            ("with_time_logged_window", "Window used for with_time_logged."),
            ("ranking_window", "Window used for top_by_hours. Last 30 days when no date filter is set."),
            ("top_by_hours", "Objects with project, status, and hours. The per-client General project is excluded."),
        ),
    },
    {
        "id": "clients",
        "title": "clients",
        "fields": (
            (
                "total",
                "Unfiltered: client records on file. With a date filter: distinct clients with an effort log "
                "in that window.",
            ),
            (
                "internal",
                "Among the clients in total, those whose affiliation is marked internal.",
            ),
            (
                "external",
                "Among the clients in total, those whose affiliation is marked external.",
            ),
            ("window", "all_time unless a date filter is set. Compared on log created_at."),
        ),
    },
    {
        "id": "billing",
        "title": "billing",
        "fields": (
            ("currency", "Always USD. Amounts are numbers, not formatted strings."),
            ("window", "all_time unless a date filter is set. Bills match on issue date."),
            ("total_bills", "Paid bills only (status paid). Count and amount."),
            ("active_quotes", "Quotes that are neither paid nor archived."),
            ("active_invoices", "Invoices that are neither paid nor archived."),
            ("internal_invoices", "Invoices for clients with an internal affiliation."),
            ("external_invoices", "Invoices for clients with an external affiliation."),
        ),
    },
    {
        "id": "memberships",
        "title": "memberships",
        "fields": (
            ("total", "Membership records."),
            ("currently_active", "Memberships with funding covering now."),
            ("active_dollar_budget", "Sum of dollar budgets on funding that covers now."),
            ("active_hour_budget", "Sum of hour budgets on funding that covers now."),
            ("ending_soonest", "Active memberships, soonest funding end first. Title and funding_end date."),
        ),
    },
    {
        "id": "appointments",
        "title": "appointments",
        "fields": (
            ("equipment_count", "Equipment records. Not affected by the date filter."),
            ("trainee_count", "Users whose role is trainee. A count, not a list."),
            ("appointment_count", "Bookings by non-admin users in the appointment window."),
            ("by_status", "pending, approved, and cancelled counts for that window."),
            ("top_equipment", "Equipment name and booking count. People are not listed."),
            ("window", "all_time unless a date filter is set. Compared on appointment start."),
        ),
    },
    {
        "id": "projection",
        "title": "projection",
        "fields": (
            ("label", "Fiscal-year name, such as FY27. The year runs July 1 through June 30."),
            ("start", "July 1 of the fiscal year, inclusive."),
            ("end", "June 30 of the fiscal year, inclusive."),
            ("fixed_costs_fy", "Fiscal year the saved fixed costs belong to."),
            ("fixed_costs_from_prior_year", "True when those fixed costs were saved for an earlier year."),
            ("salaried_count", "How many people are included in the combined salary cost. No names."),
            ("salary_monthly", "Combined monthly salary cost. The same amount is applied to every month, matching the projection page."),
            ("unassigned_bills", "Open profiting bills with no fiscal-year month. Count and profit amount. Not part of the monthly totals."),
            ("months", "Funding, profited bills, projected bills, salaries, fixed cost, and net for each month in range."),
            ("months.funding_items", "Membership title, payout (upfront or monthly), and amount. No client."),
            ("months.paid_bills_items", "Bill title, profit percent, and profit amount. The profit amount is subtotal times profit percent."),
            ("months.projected_items", "Open profiting bills assigned to that month. Same fields as paid bills, without a client."),
            ("totals", "Sums of the returned months: funding, paid_bills, projected, salaries, fixed_costs, inflow, outflow, and net."),
        ),
    },
)


class APIError(Exception):
    def __init__(self, message, status=400, **details):
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details


@dataclass(frozen=True)
class Bounds:
    label: str
    applied: bool
    start: datetime | None = None
    end: datetime | None = None
    start_date: date | None = None
    end_date: date | None = None


_rate_hits: dict[str, list[float]] = {}


def _parameter_docs():
    return (
        {
            "name": "section",
            "description": (
                "Panels to return. Repeat the parameter or send a comma-separated list. "
                "`all` returns every panel and cannot be combined with other names. "
                f"Defaults to all. Allowed: {', '.join(SECTIONS)}."
            ),
            "example": "time,billing",
        },
        {
            "name": "period",
            "description": (
                "Preset window for time, project rankings, billing issue dates, and appointments. "
                "Do not combine with start or end. "
                f"Allowed: {', '.join(PERIODS)}. "
                "Weeks run Monday through Sunday. The fiscal year starts July 1. "
                "last_30_days is a rolling 30 spans of 24 hours, matching the overview."
            ),
            "example": "last_month",
        },
        {
            "name": "start",
            "description": "Inclusive range start, YYYY-MM-DD, America/Chicago. Required with end.",
            "example": "2026-07-01",
        },
        {
            "name": "end",
            "description": (
                f"Inclusive range end, YYYY-MM-DD, America/Chicago. Required with start. "
                f"The span cannot exceed {MAX_RANGE_DAYS} days."
            ),
            "example": "2026-07-31",
        },
        {
            "name": "project_status",
            "description": (
                "Limit time, project counts, project rankings, and billing to these project statuses. "
                "Repeat or send a comma-separated list. Matching is case-insensitive. "
                f"Allowed: {', '.join(PROJECT_STATUSES)}."
            ),
            "example": "Active",
        },
        {
            "name": "bill_type",
            "description": (
                "Limit every billing metric to one type. "
                f"Allowed: {', '.join(BILL_TYPES)}."
            ),
            "example": "invoice",
        },
        {
            "name": "limit",
            "description": (
                f"Maximum rows in each ranked list (projects, memberships, equipment). "
                f"Default {DEFAULT_LIMIT}. Maximum {MAX_LIMIT}."
            ),
            "example": "10",
        },
        {
            "name": "series",
            "description": (
                "Include time.series. `1`, `true`, `yes`, or `on` turns it on. "
                "`0`, `false`, `no`, or `off` turns it off. "
                "When omitted, a date window includes a series and an unfiltered request does not. "
                "Without a date window, an explicit series covers the last 30 days while time.hours stays all-time."
            ),
            "example": "1",
        },
        {
            "name": "grain",
            "description": (
                "Bucket size for time.series: day, week, or month. "
                "Week buckets start on Monday. Month buckets start on the first. "
                "When omitted: day up to 45 days, week up to 400 days, otherwise month. "
                f"A requested grain that would produce more than {MAX_SERIES_POINTS} points is rejected."
            ),
            "example": "week",
        },
    )


def _hours_value(value):
    return round(float(value or 0), 1)


def _money(value):
    return round(float(value or 0), 2)


def _as_chicago(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return TIMEZONE.localize(dt)
    return dt.astimezone(TIMEZONE)


def _start_of_day(day):
    return TIMEZONE.localize(datetime.combine(day, time_of_day.min))


def _calendar_bounds(label, start_date, end_date, applied=True):
    return Bounds(
        label=label,
        applied=applied,
        start=_start_of_day(start_date),
        end=_start_of_day(end_date + timedelta(days=1)),
        start_date=start_date,
        end_date=end_date,
    )


def _rolling_last_30(now):
    start = now - timedelta(days=30)
    local_now = _as_chicago(now)
    local_start = _as_chicago(start)
    return Bounds(
        label="last_30_days",
        applied=True,
        start=local_start,
        end=None,
        start_date=local_start.date(),
        end_date=local_now.date(),
    )


def _period_bounds(period, now):
    local = _as_chicago(now)
    today = local.date()
    if period == "today":
        return _calendar_bounds("today", today, today)
    if period == "this_week":
        monday = today - timedelta(days=today.weekday())
        return _calendar_bounds("this_week", monday, monday + timedelta(days=6))
    if period == "last_week":
        this_monday = today - timedelta(days=today.weekday())
        last_monday = this_monday - timedelta(days=7)
        return _calendar_bounds("last_week", last_monday, this_monday - timedelta(days=1))
    if period == "last_30_days":
        return _rolling_last_30(local)
    if period == "this_month":
        return _calendar_bounds("this_month", today.replace(day=1), today)
    if period == "last_month":
        first_this_month = today.replace(day=1)
        last_day = first_this_month - timedelta(days=1)
        return _calendar_bounds("last_month", last_day.replace(day=1), last_day)
    if period == "fiscal_year":
        year = today.year if today.month >= 7 else today.year - 1
        start = date(year, 7, 1)
        end = today if today >= start else start
        return _calendar_bounds("fiscal_year", start, end)
    return Bounds(label="all_time", applied=True)


def _window_payload(bounds):
    if bounds is None:
        return {
            "applied": False,
            "label": "all_time",
            "start": None,
            "end": None,
            "start_at": None,
            "end_at": None,
        }
    return {
        "applied": bool(bounds.applied),
        "label": bounds.label,
        "start": bounds.start_date.isoformat() if bounds.start_date else None,
        "end": bounds.end_date.isoformat() if bounds.end_date else None,
        "start_at": bounds.start.isoformat() if bounds.start else None,
        "end_at": bounds.end.isoformat() if bounds.end else None,
    }


def _in_bounds(dt, bounds):
    local = _as_chicago(dt)
    if local is None:
        return False
    if bounds.start is not None and local < bounds.start:
        return False
    if bounds.end is not None and local >= bounds.end:
        return False
    return True


def _parse_bool(value, name):
    if value is None or value.strip() == "":
        return None
    token = value.strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    raise APIError(
        "Expected a boolean.",
        parameter=name,
        allowed=["1", "0", "true", "false", "yes", "no", "on", "off"],
    )


def _parse_date(value, name):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise APIError("Dates must use YYYY-MM-DD.", parameter=name)


def _split_args(name):
    parts = []
    for raw in request.args.getlist(name):
        for piece in raw.split(","):
            item = piece.strip()
            if item:
                parts.append(item)
    return parts


def _parse_request():
    unknown = sorted(set(request.args.keys()) - ALLOWED_PARAMS)
    if unknown:
        raise APIError(
            "Unknown query parameter.",
            parameter=unknown[0],
            unknown=unknown,
            allowed=sorted(ALLOWED_PARAMS),
        )

    section_parts = [part.lower() for part in _split_args("section")]
    if not section_parts or section_parts == ["all"]:
        sections = list(SECTIONS)
    elif "all" in section_parts:
        raise APIError(
            "section=all cannot be combined with other sections.",
            parameter="section",
            allowed=list(SECTIONS),
        )
    else:
        bad = [part for part in section_parts if part not in SECTIONS]
        if bad:
            raise APIError("Unknown section.", parameter="section", value=bad[0], allowed=list(SECTIONS))
        sections = [name for name in SECTIONS if name in section_parts]

    period = (request.args.get("period") or "").strip().lower() or None
    if period and period not in PERIODS:
        raise APIError("Unknown period.", parameter="period", allowed=list(PERIODS))

    start_raw = (request.args.get("start") or "").strip()
    end_raw = (request.args.get("end") or "").strip()
    start = _parse_date(start_raw, "start") if start_raw else None
    end = _parse_date(end_raw, "end") if end_raw else None
    if period and (start or end):
        raise APIError("Pass either period or start and end, not both.", parameter="period")
    if (start is None) ^ (end is None):
        missing = "start" if start is None else "end"
        raise APIError("start and end must be provided together.", parameter=missing)
    if start and end and start > end:
        raise APIError("start must be on or before end.", parameter="start")
    if start and end and (end - start).days > MAX_RANGE_DAYS:
        raise APIError(
            f"Date range cannot exceed {MAX_RANGE_DAYS} days.",
            parameter="end",
        )

    now = get_current_time()
    if period:
        window = _period_bounds(period, now)
    elif start and end:
        window = _calendar_bounds("custom", start, end)
    else:
        window = Bounds(label="page_default", applied=False)

    status_map = {name.lower(): name for name in PROJECT_STATUSES}
    project_statuses = []
    for raw in _split_args("project_status"):
        canonical = status_map.get(raw.lower())
        if not canonical:
            raise APIError(
                "Unknown project_status.",
                parameter="project_status",
                value=raw,
                allowed=list(PROJECT_STATUSES),
            )
        if canonical not in project_statuses:
            project_statuses.append(canonical)

    bill_type = (request.args.get("bill_type") or "").strip().lower() or None
    if bill_type and bill_type not in BILL_TYPES:
        raise APIError("Unknown bill_type.", parameter="bill_type", allowed=list(BILL_TYPES))

    limit_raw = (request.args.get("limit") or "").strip()
    if not limit_raw:
        limit = DEFAULT_LIMIT
    else:
        try:
            limit = int(limit_raw)
        except ValueError:
            raise APIError(
                f"limit must be an integer from 1 to {MAX_LIMIT}.",
                parameter="limit",
            )
        if limit < 1 or limit > MAX_LIMIT:
            raise APIError(
                f"limit must be an integer from 1 to {MAX_LIMIT}.",
                parameter="limit",
            )

    series_flag = _parse_bool(request.args.get("series"), "series")
    if series_flag is None:
        include_series = window.applied
    else:
        include_series = series_flag

    grain = (request.args.get("grain") or "").strip().lower() or None
    if grain and grain not in GRAINS:
        raise APIError("Unknown grain.", parameter="grain", allowed=list(GRAINS))

    return {
        "sections": sections,
        "period": period,
        "start": start,
        "end": end,
        "window": window,
        "project_statuses": project_statuses or None,
        "bill_type": bill_type,
        "limit": limit,
        "include_series": include_series,
        "grain": grain,
        "now": now,
    }


def _client_key():
    raw = (request.remote_addr or "unknown").encode()
    return hashlib.sha256(b"analytics-public:" + raw).hexdigest()[:16]


def _rate_status(key, limit, window):
    now = time_module.time()
    hits = [stamp for stamp in _rate_hits.get(key, []) if now - stamp < window]
    if len(hits) >= limit:
        _rate_hits[key] = hits
        retry = max(1, int(window - (now - hits[0])) + 1)
        return False, 0, retry
    hits.append(now)
    _rate_hits[key] = hits
    if len(_rate_hits) > 5000:
        stale = [name for name, stamps in _rate_hits.items() if not stamps or now - stamps[-1] >= window]
        for name in stale:
            _rate_hits.pop(name, None)
    return True, limit - len(hits), 0


def _enforce_rate_limit():
    allowed, remaining, retry = _rate_status(_client_key(), RATE_LIMIT, RATE_WINDOW)
    if not allowed:
        raise APIError(
            "Rate limit exceeded. Try again shortly.",
            status=429,
            limit=RATE_LIMIT,
            window_seconds=RATE_WINDOW,
            retry_after_seconds=retry,
        )
    return remaining


def _apply_log_scope(query, bounds, project_statuses, created_column=Log.created_at):
    if project_statuses:
        query = query.join(Project, Project.id == Log.project_id).filter(Project.status.in_(project_statuses))
    if bounds is not None and bounds.start is not None:
        query = query.filter(created_column >= bounds.start)
    if bounds is not None and bounds.end is not None:
        query = query.filter(created_column < bounds.end)
    return query


def _scan_logs(bounds, project_statuses):
    query = _apply_log_scope(
        db.session.query(Log.created_at, Log.hours, Log.is_touch),
        bounds,
        project_statuses,
    )
    total_hours = 0.0
    detailed = 0.0
    touch = 0.0
    logs = 0
    per_day = {}
    for created_at, log_hours, is_touch in query.all():
        logs += 1
        value = float(log_hours or 0)
        total_hours += value
        if is_touch:
            touch += value
        else:
            detailed += value
        day = _as_chicago(created_at)
        if day is None:
            continue
        slot = per_day.setdefault(day.date(), [0.0, 0])
        slot[0] += value
        slot[1] += 1
    return {
        "hours": _hours_value(total_hours),
        "logs": logs,
        "detailed_hours": _hours_value(detailed),
        "touch_hours": _hours_value(touch),
        "per_day": per_day,
    }


def _bucket_start(day, grain):
    if grain == "week":
        return day - timedelta(days=day.weekday())
    if grain == "month":
        return day.replace(day=1)
    return day


def _next_bucket(day, grain):
    if grain == "day":
        return day + timedelta(days=1)
    if grain == "week":
        return day + timedelta(days=7)
    year = day.year + (1 if day.month == 12 else 0)
    month = 1 if day.month == 12 else day.month + 1
    return date(year, month, 1)


def _auto_grain(start_date, end_date):
    span = (end_date - start_date).days + 1
    if span <= 45:
        return "day"
    if span <= 400:
        return "week"
    return "month"


def _series_from_days(per_day, bounds, grain, covers):
    today = _as_chicago(get_current_time()).date()
    if bounds.start_date:
        start_date = bounds.start_date
    elif per_day:
        start_date = min(per_day)
    else:
        start_date = None
    if bounds.end_date:
        end_date = bounds.end_date
    elif per_day:
        end_date = max(per_day)
    else:
        end_date = today

    if start_date is None or end_date is None or end_date < start_date:
        return {
            "grain": grain or "day",
            "covers": covers,
            "start": None,
            "end": None,
            "points": [],
        }

    chosen = grain or _auto_grain(start_date, end_date)
    cursor = _bucket_start(start_date, chosen)
    last = _bucket_start(end_date, chosen)
    points = []
    totals = {}
    while cursor <= last:
        points.append(cursor)
        if len(points) > MAX_SERIES_POINTS:
            raise APIError(
                f"Series would exceed {MAX_SERIES_POINTS} points. Use a coarser grain.",
                parameter="grain",
                allowed=list(GRAINS),
            )
        cursor = _next_bucket(cursor, chosen)

    for day, (day_hours, day_logs) in per_day.items():
        if day < start_date or day > end_date:
            continue
        key = _bucket_start(day, chosen)
        slot = totals.setdefault(key, [0.0, 0])
        slot[0] += day_hours
        slot[1] += day_logs

    return {
        "grain": chosen,
        "covers": covers,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "points": [
            {
                "date": point.isoformat(),
                "hours": _hours_value(totals.get(point, (0.0, 0))[0]),
                "logs": totals.get(point, (0.0, 0))[1],
            }
            for point in points
        ],
    }


def _ranked_hours_expr():
    detailed = func.coalesce(func.sum(case((Log.is_touch.is_(False), Log.hours), else_=0)), 0)
    touch = func.coalesce(
        func.sum(case((and_(Log.is_touch.is_(True), Log.hours.isnot(None)), Log.hours), else_=0)),
        0,
    )
    return detailed + touch


def _top_projects(bounds, project_statuses, limit):
    hours_expr = _ranked_hours_expr()
    query = (
        db.session.query(
            Project.name.label("name"),
            Project.status.label("status"),
            hours_expr.label("hours"),
        )
        .join(Log, Log.project_id == Project.id)
        .filter(Project.name != GENERAL_PROJECT_NAME)
    )
    if project_statuses:
        query = query.filter(Project.status.in_(project_statuses))
    if bounds is not None and bounds.start is not None:
        query = query.filter(Log.created_at >= bounds.start)
    if bounds is not None and bounds.end is not None:
        query = query.filter(Log.created_at < bounds.end)
    rows = (
        query.group_by(Project.id, Project.name, Project.status)
        .having(hours_expr > 0)
        .order_by(desc("hours"), Project.name.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "project": row.name,
            "status": row.status or "Unknown",
            "hours": _hours_value(row.hours),
        }
        for row in rows
    ]


def _projects_with_time(bounds, project_statuses):
    query = db.session.query(func.count(func.distinct(Log.project_id))).filter(Log.project_id.isnot(None))
    if project_statuses:
        query = query.join(Project, Project.id == Log.project_id).filter(Project.status.in_(project_statuses))
    if bounds is not None and bounds.start is not None:
        query = query.filter(Log.created_at >= bounds.start)
    if bounds is not None and bounds.end is not None:
        query = query.filter(Log.created_at < bounds.end)
    return int(query.scalar() or 0)


def _project_counts(project_statuses):
    query = db.session.query(Project.status, func.count(Project.id))
    if project_statuses:
        query = query.filter(Project.status.in_(project_statuses))
    counts = {status: 0 for status in PROJECT_STATUSES}
    for status, count in query.group_by(Project.status).all():
        counts[status or "Unknown"] = int(count)
    total = sum(counts.values())
    return total, counts


def _quote_totals(
    bounds,
    project_statuses,
    bill_type,
    type_required=None,
    paid=None,
    active=None,
    affiliation_internal=None,
):
    if bill_type and type_required and bill_type != type_required:
        return {"count": 0, "amount": 0.0}
    if affiliation_internal is not None and bill_type and bill_type != "invoice":
        return {"count": 0, "amount": 0.0}

    query = db.session.query(
        func.count(Quote.id),
        func.coalesce(func.sum(Quote.total_amount), 0),
    )
    if project_statuses:
        query = query.join(Project, Project.id == Quote.project_id).filter(Project.status.in_(project_statuses))
    use_type = bill_type or type_required
    if use_type:
        query = query.filter(Quote.bill_type == use_type)
    if paid is True:
        query = query.filter(Quote.status == "paid")
    if active is True:
        query = query.filter(Quote.status.notin_(("paid", "archived")))
    if affiliation_internal is not None:
        query = query.join(Client, Client.id == Quote.client_id).join(
            Affiliation, Affiliation.id == Client.affiliation_id
        ).filter(Affiliation.is_internal.is_(bool(affiliation_internal)))
    if bounds is not None and bounds.start_date is not None:
        query = query.filter(Quote.issue_date >= bounds.start_date)
    if bounds is not None and bounds.end_date is not None:
        query = query.filter(Quote.issue_date <= bounds.end_date)
    count, amount = query.one()
    return {"count": int(count or 0), "amount": _money(amount)}


def _appointment_filters(bounds):
    filters = [User.role != "admin"]
    if bounds is not None and bounds.start is not None:
        filters.append(EquipmentAppointment.start_time >= bounds.start)
    if bounds is not None and bounds.end is not None:
        filters.append(EquipmentAppointment.start_time < bounds.end)
    return filters


def _build_scope(parsed):
    window = parsed["window"]
    project_statuses = parsed["project_statuses"]
    bill_type = parsed["bill_type"]
    if window.label == "page_default" and not project_statuses and not bill_type:
        return (
            "Organization snapshot matching the analytics overview. "
            "Time totals are all-time. Project hour rankings use the last 30 days. "
            "The projection is the full current fiscal year, July through June."
        )
    sentences = []
    if window.applied and window.label == "all_time":
        sentences.append("Date filter is all time.")
    elif window.applied and window.start_date and window.end_date:
        sentences.append(
            f"Date filter is {window.start_date.isoformat()} through {window.end_date.isoformat()} ({window.label})."
        )
    elif window.applied:
        sentences.append(f"Date filter is {window.label}.")
    if project_statuses:
        joined = ", ".join(project_statuses)
        sentences.append(
            "Project status filter: "
            f"{joined}. It applies to time, client counts with a date filter, project counts, "
            "project rankings, billing, and profited or projected bills."
        )
    if bill_type:
        sentences.append(
            f"Billing is limited to {bill_type} records. Profited and projected bills follow that limit."
        )
    if window.applied:
        sentences.append(
            "Client counts are distinct clients with an effort log in the date window. "
            "Membership figures and active membership or project summary cards stay current."
        )
    else:
        sentences.append(
            "Summary, client counts, and membership figures stay current and ignore these filters."
        )
    if "projection" in parsed["sections"]:
        if window.applied and window.label not in {"fiscal_year", "all_time"}:
            sentences.append(
                "The projection keeps fiscal-year months that overlap the date filter. "
                "Funding, combined salary cost, and fixed costs are not limited by bill type or project status."
            )
        else:
            sentences.append(
                "The projection is the full current fiscal year, July through June. "
                "Funding, combined salary cost, and fixed costs are not limited by bill type or project status."
            )
    if "appointments" in parsed["sections"]:
        sentences.append("Equipment and trainee counts stay current. Appointment counts honor the date filter only.")
    return " ".join(sentences)


def _active_membership_count(now):
    return int(
        db.session.query(func.count(func.distinct(MembershipFunding.membership_id)))
        .filter(MembershipFunding.start_date <= now, MembershipFunding.end_date >= now)
        .scalar()
        or 0
    )


def _clients_with_effort_query(bounds, project_statuses, affiliation_internal=None):
    """Distinct clients that have at least one effort log in scope."""
    query = (
        db.session.query(func.count(func.distinct(Client.id)))
        .select_from(Client)
        .join(Project, Project.client_id == Client.id)
        .join(Log, Log.project_id == Project.id)
    )
    if affiliation_internal is not None:
        query = query.join(Affiliation, Affiliation.id == Client.affiliation_id).filter(
            Affiliation.is_internal.is_(bool(affiliation_internal))
        )
    if project_statuses:
        query = query.filter(Project.status.in_(project_statuses))
    if bounds is not None and bounds.start is not None:
        query = query.filter(Log.created_at >= bounds.start)
    if bounds is not None and bounds.end is not None:
        query = query.filter(Log.created_at < bounds.end)
    return int(query.scalar() or 0)


def _build_summary(parsed, bounds):
    if bounds is not None:
        client_count = _clients_with_effort_query(bounds, parsed["project_statuses"])
    else:
        client_count = int(Client.query.count())
    return {
        "active_memberships": _active_membership_count(get_current_time()),
        "active_projects": int(Project.query.filter_by(status="Active").count()),
        "clients": client_count,
    }


def _build_time(parsed, time_bounds):
    scanned = _scan_logs(time_bounds, parsed["project_statuses"])
    payload = {
        "hours": scanned["hours"],
        "logs": scanned["logs"],
        "detailed_hours": scanned["detailed_hours"],
        "touch_hours": scanned["touch_hours"],
        "series": None,
    }
    overview = (
        not parsed["window"].applied
        and not parsed["project_statuses"]
        and not parsed["bill_type"]
    )
    if overview:
        now = parsed["now"]
        last_30 = _rolling_last_30(now)
        this_week = _period_bounds("this_week", now)
        last_week = _period_bounds("last_week", now)
        last_30_hours = 0.0
        this_week_hours = 0.0
        last_week_hours = 0.0
        rows = _apply_log_scope(
            db.session.query(Log.created_at, Log.hours),
            None,
            None,
        ).all()
        for created_at, log_hours in rows:
            value = float(log_hours or 0)
            if _in_bounds(created_at, last_30):
                last_30_hours += value
            if _in_bounds(created_at, this_week):
                this_week_hours += value
            if _in_bounds(created_at, last_week):
                last_week_hours += value
        payload.update(
            {
                "total_hours_all_time": scanned["hours"],
                "total_hours_last_30_days": _hours_value(last_30_hours),
                "hours_this_week": _hours_value(this_week_hours),
                "hours_last_week": _hours_value(last_week_hours),
                "total_logs": scanned["logs"],
            }
        )
    if parsed["include_series"]:
        if parsed["window"].applied:
            series_bounds = parsed["window"]
            covers = parsed["window"].label
        else:
            series_bounds = _rolling_last_30(parsed["now"])
            covers = "last_30_days"
        payload["series"] = _series_from_days(
            scanned["per_day"],
            series_bounds,
            parsed["grain"],
            covers,
        )
    return payload


def _build_projects(parsed, ranking_bounds, logged_bounds):
    total, by_status = _project_counts(parsed["project_statuses"])
    return {
        "total": total,
        "by_status": by_status,
        "with_time_logged": _projects_with_time(logged_bounds, parsed["project_statuses"]),
        "with_time_logged_window": _window_payload(logged_bounds),
        "ranking_window": _window_payload(ranking_bounds),
        "top_by_hours": _top_projects(ranking_bounds, parsed["project_statuses"], parsed["limit"]),
    }


def _build_clients(parsed, bounds):
    statuses = parsed["project_statuses"]
    if bounds is not None:
        total = _clients_with_effort_query(bounds, statuses)
        internal = _clients_with_effort_query(bounds, statuses, affiliation_internal=True)
        external = _clients_with_effort_query(bounds, statuses, affiliation_internal=False)
    else:
        total = int(Client.query.count())
        internal = int(
            Client.query.join(Affiliation, Affiliation.id == Client.affiliation_id)
            .filter(Affiliation.is_internal.is_(True))
            .count()
        )
        external = int(
            Client.query.join(Affiliation, Affiliation.id == Client.affiliation_id)
            .filter(Affiliation.is_internal.is_(False))
            .count()
        )
    return {
        "total": total,
        "internal": internal,
        "external": external,
        "window": _window_payload(bounds if bounds is not None else Bounds(label="all_time", applied=False)),
    }


def _build_billing(parsed, bounds):
    statuses = parsed["project_statuses"]
    bill_type = parsed["bill_type"]
    return {
        "currency": "USD",
        "window": _window_payload(bounds),
        "total_bills": _quote_totals(bounds, statuses, bill_type, paid=True),
        "active_quotes": _quote_totals(bounds, statuses, bill_type, type_required="quote", active=True),
        "active_invoices": _quote_totals(bounds, statuses, bill_type, type_required="invoice", active=True),
        "internal_invoices": _quote_totals(
            bounds, statuses, bill_type, type_required="invoice", affiliation_internal=True
        ),
        "external_invoices": _quote_totals(
            bounds, statuses, bill_type, type_required="invoice", affiliation_internal=False
        ),
    }


def _build_memberships(limit):
    now = get_current_time()
    total = int(Membership.query.count())
    active_dollar, active_hours = (
        db.session.query(
            func.coalesce(func.sum(MembershipFunding.dollar_budget), 0),
            func.coalesce(func.sum(MembershipFunding.time_budget), 0),
        )
        .filter(MembershipFunding.start_date <= now, MembershipFunding.end_date >= now)
        .one()
    )
    active_ids = (
        db.session.query(MembershipFunding.membership_id)
        .filter(MembershipFunding.start_date <= now, MembershipFunding.end_date >= now)
        .distinct()
    )
    currently_active = _active_membership_count(now)
    upcoming = (
        db.session.query(
            Membership.title,
            func.max(MembershipFunding.end_date).label("funding_end_date"),
        )
        .join(MembershipFunding, MembershipFunding.membership_id == Membership.id)
        .filter(Membership.id.in_(active_ids))
        .group_by(Membership.id, Membership.title)
        .order_by("funding_end_date", Membership.title.asc())
        .limit(limit)
        .all()
    )
    ending = []
    for row in upcoming:
        funding_end = _as_chicago(row.funding_end_date)
        ending.append(
            {
                "membership": row.title,
                "funding_end": funding_end.date().isoformat() if funding_end else None,
            }
        )
    return {
        "total": total,
        "currently_active": currently_active,
        "active_dollar_budget": _money(active_dollar),
        "active_hour_budget": int(active_hours or 0),
        "ending_soonest": ending,
    }


def _build_appointments(limit, bounds):
    filters = _appointment_filters(bounds)
    by_status = {status: 0 for status in APPOINTMENT_STATUSES}
    rows = (
        db.session.query(EquipmentAppointment.status, func.count(EquipmentAppointment.id))
        .join(User, User.id == EquipmentAppointment.user_id)
        .filter(*filters)
        .group_by(EquipmentAppointment.status)
        .all()
    )
    for status, count in rows:
        by_status[status or "unknown"] = int(count)
    top_rows = (
        db.session.query(
            Equipment.name.label("name"),
            func.count(EquipmentAppointment.id).label("appointment_count"),
        )
        .join(EquipmentAppointment, EquipmentAppointment.equipment_id == Equipment.id)
        .join(User, User.id == EquipmentAppointment.user_id)
        .filter(*filters)
        .group_by(Equipment.id, Equipment.name)
        .order_by(desc("appointment_count"), Equipment.name.asc())
        .limit(limit)
        .all()
    )
    return {
        "equipment_count": int(Equipment.query.count()),
        "trainee_count": int(User.query.filter_by(role="trainee").count()),
        "appointment_count": int(sum(by_status.values())),
        "by_status": by_status,
        "top_equipment": [
            {"equipment": row.name, "appointments": int(row.appointment_count)}
            for row in top_rows
        ],
        "window": _window_payload(bounds if bounds is not None else Bounds(label="all_time", applied=False)),
    }


FY_MONTH_LABELS = ("Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun")


def _fy_start_year(now):
    local = _as_chicago(now)
    return local.year if local.month >= 7 else local.year - 1


def _fy_label(fy_start_year):
    return f"FY{(fy_start_year + 1) % 100}"


def _fy_month_index(year, month, fy_start_year):
    index = (year - fy_start_year) * 12 + (month - 7)
    return index if 0 <= index < 12 else None


def _months_between(start, end):
    return max(1, (end.year - start.year) * 12 + (end.month - start.month) + 1)


def _month_calendar(index, fy_start_year):
    month_number = (6 + index) % 12 + 1
    year = fy_start_year + (1 if month_number < 7 else 0)
    return year, month_number


def _profit_amount(quote):
    """Subtotal × profit% for a profiting bill. Matches quote_finance_profit_amount."""
    if quote is None or (quote.finance_mode or "payback") != "profiting":
        return None
    percent = quote.profit_percent if quote.profit_percent is not None else 50
    base = float(quote.subtotal or 0)
    if base < 0:
        base = 0.0
    return base * (percent / 100.0)


def _fixed_cost_values(settings):
    raw = []
    if settings is not None and settings.fixed_costs:
        raw = settings.fixed_costs
        if isinstance(raw, str):
            raw = json.loads(raw)
    values = [float(value or 0) for value in list(raw)[:12]]
    return values + [0.0] * (12 - len(values))


def _projection_indexes(window, fy_start_year):
    """Full fiscal year, unless a shorter date filter overlaps part of it."""
    if (not window.applied) or window.label in {"fiscal_year", "all_time"}:
        return list(range(12))
    if window.start_date is None and window.end_date is None:
        return list(range(12))
    start = window.start_date
    end = window.end_date or start
    indexes = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        index = _fy_month_index(year, month, fy_start_year)
        if index is not None and index not in indexes:
            indexes.append(index)
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return indexes


def _bill_in_projection_scope(quote, parsed):
    if parsed["bill_type"] and (quote.bill_type or "") != parsed["bill_type"]:
        return False
    statuses = parsed["project_statuses"]
    if statuses:
        project = quote.project
        if project is None or (project.status or "") not in statuses:
            return False
    return True


def _build_projection(parsed):
    now = parsed["now"]
    fy_start_year = _fy_start_year(now)
    settings = FinanceSettings.query.first()
    settings_year = settings.fy_start_year if settings is not None else fy_start_year
    fixed_costs = _fixed_cost_values(settings)
    selected = _projection_indexes(parsed["window"], fy_start_year)

    funding_amounts = [0.0] * 12
    paid_amounts = [0.0] * 12
    projected_amounts = [0.0] * 12
    funding_items = [[] for _ in range(12)]
    paid_items = [[] for _ in range(12)]
    projected_items = [[] for _ in range(12)]

    for funding in MembershipFunding.query.all():
        if (funding.payout or "monthly") == "exclude":
            continue
        amount = float(funding.amount or 0)
        if amount == 0 or not funding.start_date:
            continue
        title = funding.membership.title if funding.membership and funding.membership.title else "Membership"
        payout = funding.payout or "monthly"
        start_local = _as_chicago(funding.start_date)
        if payout == "upfront":
            index = _fy_month_index(start_local.year, start_local.month, fy_start_year)
            if index is not None:
                funding_amounts[index] += amount
                funding_items[index].append({
                    "membership": title,
                    "payout": "upfront",
                    "amount": _money(amount),
                })
        else:
            end_local = _as_chicago(funding.end_date or funding.start_date)
            month_count = _months_between(start_local, end_local)
            share = amount / month_count
            for step in range(month_count):
                total_month = start_local.month - 1 + step
                year = start_local.year + total_month // 12
                month = total_month % 12 + 1
                index = _fy_month_index(year, month, fy_start_year)
                if index is None:
                    continue
                funding_amounts[index] += share
                funding_items[index].append({
                    "membership": title,
                    "payout": "monthly",
                    "months": month_count,
                    "amount": _money(share),
                })

    paid_quotes = Quote.query.filter(Quote.status == "paid").all()
    for quote in paid_quotes:
        if not _bill_in_projection_scope(quote, parsed):
            continue
        amount = _profit_amount(quote)
        if amount is None:
            continue
        if quote.paid_at:
            paid_local = _as_chicago(quote.paid_at)
            year, month = paid_local.year, paid_local.month
        elif quote.issue_date:
            year, month = quote.issue_date.year, quote.issue_date.month
        else:
            continue
        index = _fy_month_index(year, month, fy_start_year)
        if index is None:
            continue
        paid_amounts[index] += amount
        paid_items[index].append({
            "bill": quote.title or "Untitled bill",
            "profit_percent": int(quote.profit_percent if quote.profit_percent is not None else 50),
            "amount": _money(amount),
        })

    open_bills = Quote.query.filter(
        Quote.status.notin_(("paid", "archived")),
        Quote.finance_mode == "profiting",
    ).all()
    unassigned_count = 0
    unassigned_amount = 0.0
    for quote in open_bills:
        if not _bill_in_projection_scope(quote, parsed):
            continue
        amount = _profit_amount(quote)
        if amount is None:
            continue
        index = quote.projected_fy_month
        if index is None or not (0 <= index < 12):
            unassigned_count += 1
            unassigned_amount += amount
            continue
        projected_amounts[index] += amount
        projected_items[index].append({
            "bill": quote.title or "Untitled bill",
            "profit_percent": int(quote.profit_percent if quote.profit_percent is not None else 50),
            "amount": _money(amount),
        })

    salaried = User.query.filter(
        User.role == "admin",
        User.annual_salary.isnot(None),
        User.annual_salary > 0,
    ).all()
    salary_monthly = sum(float(user.annual_salary or 0) / 12 for user in salaried)
    salary_month = _money(salary_monthly)

    months = []
    for index in selected:
        year, month_number = _month_calendar(index, fy_start_year)
        funding = _money(funding_amounts[index])
        paid = _money(paid_amounts[index])
        projected = _money(projected_amounts[index])
        fixed = _money(fixed_costs[index])
        net = _money(funding + paid + projected - salary_month - fixed)
        months.append({
            "month": f"{year:04d}-{month_number:02d}",
            "label": f"{FY_MONTH_LABELS[index]} {year}",
            "funding": funding,
            "paid_bills": paid,
            "projected": projected,
            "salaries": salary_month,
            "fixed_cost": fixed,
            "net": net,
            "funding_items": funding_items[index],
            "paid_bills_items": paid_items[index],
            "projected_items": projected_items[index],
        })

    totals = {
        "funding": _money(sum(month["funding"] for month in months)),
        "paid_bills": _money(sum(month["paid_bills"] for month in months)),
        "projected": _money(sum(month["projected"] for month in months)),
        "salaries": _money(sum(month["salaries"] for month in months)),
        "fixed_costs": _money(sum(month["fixed_cost"] for month in months)),
    }
    totals["inflow"] = _money(totals["funding"] + totals["paid_bills"] + totals["projected"])
    totals["outflow"] = _money(totals["salaries"] + totals["fixed_costs"])
    totals["net"] = _money(totals["inflow"] - totals["outflow"])

    return {
        "currency": "USD",
        "label": _fy_label(fy_start_year),
        "start": date(fy_start_year, 7, 1).isoformat(),
        "end": date(fy_start_year + 1, 6, 30).isoformat(),
        "fixed_costs_fy": _fy_label(settings_year),
        "fixed_costs_from_prior_year": bool(settings is not None and settings.fy_start_year < fy_start_year),
        "salaried_count": len(salaried),
        "salary_monthly": salary_month,
        "unassigned_bills": {"count": unassigned_count, "amount": _money(unassigned_amount)},
        "months": months,
        "totals": totals,
    }


def _build_payload(parsed):
    window = parsed["window"]
    if window.applied:
        time_bounds = window
        ranking_bounds = window
        logged_bounds = window
        billing_bounds = window
        appointment_bounds = window
    else:
        time_bounds = None
        ranking_bounds = _rolling_last_30(parsed["now"])
        logged_bounds = None
        billing_bounds = None
        appointment_bounds = None

    payload = {
        "api_version": API_VERSION,
        "generated_at": _as_chicago(parsed["now"]).isoformat(),
        "timezone": "America/Chicago",
        "documentation": {
            "html": url_for("analytics_public.public_analytics_docs", _external=True),
            "openapi": url_for("analytics_public.public_analytics_openapi", _external=True),
        },
        "privacy": PRIVACY,
        "scope": _build_scope(parsed),
        "filters": {
            "sections": parsed["sections"],
            "period": parsed["period"],
            "start": parsed["start"].isoformat() if parsed["start"] else None,
            "end": parsed["end"].isoformat() if parsed["end"] else None,
            "project_status": parsed["project_statuses"],
            "bill_type": parsed["bill_type"],
            "limit": parsed["limit"],
            "series": parsed["include_series"],
            "grain": parsed["grain"],
            "window": _window_payload(window),
        },
    }
    sections = set(parsed["sections"])
    if "summary" in sections:
        payload["summary"] = _build_summary(parsed, time_bounds)
    if "time" in sections:
        payload["time"] = _build_time(parsed, time_bounds)
    if "projects" in sections:
        payload["projects"] = _build_projects(parsed, ranking_bounds, logged_bounds)
    if "clients" in sections:
        payload["clients"] = _build_clients(parsed, time_bounds)
    if "billing" in sections:
        payload["billing"] = _build_billing(parsed, billing_bounds)
    if "memberships" in sections:
        payload["memberships"] = _build_memberships(parsed["limit"])
    if "appointments" in sections:
        payload["appointments"] = _build_appointments(parsed["limit"], appointment_bounds)
    if "projection" in sections:
        payload["projection"] = _build_projection(parsed)
    return payload


def _json(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    if status >= 400:
        response.headers["Cache-Control"] = "no-store"
    else:
        response.headers["Cache-Control"] = "public, max-age=30"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


def _openapi_spec():
    parameters = []
    for item in _parameter_docs():
        parameters.append(
            {
                "name": item["name"],
                "in": "query",
                "required": False,
                "description": item["description"],
                "schema": {"type": "string"},
                "example": item["example"],
            }
        )
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Hub Tracker Public Analytics API",
            "version": API_VERSION,
            "description": (
                "Read-only aggregate metrics from the analytics overview and the fiscal-year projection "
                "for an external reporting bot. "
                "No authentication. Client and user records are not returned. "
                + PRIVACY["substitution"]
            ),
        },
        "servers": [{"url": "/"}],
        "paths": {
            "/api/public/analytics": {
                "get": {
                    "operationId": "getPublicAnalytics",
                    "summary": "Analytics overview aggregates",
                    "description": (
                        "Returns the same operational picture as the analytics overview, "
                        "with optional date, project status, and billing filters. "
                        "An unfiltered request matches the overview: time totals are all-time and "
                        "project rankings cover the last 30 days. "
                        "The projection section is the current fiscal-year profit and loss, July through June."
                    ),
                    "parameters": parameters,
                    "responses": {
                        "200": {
                            "description": "Aggregate analytics. Ranked lists never include clients or users.",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        },
                        "400": {
                            "description": "A query parameter is missing, unknown, or invalid.",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "error": {"type": "string"},
                                            "parameter": {"type": "string"},
                                            "allowed": {"type": "array", "items": {"type": "string"}},
                                        },
                                        "required": ["error"],
                                    }
                                }
                            },
                        },
                        "429": {"description": "Rate limit exceeded. See Retry-After."},
                    },
                }
            },
            "/api/public/analytics/docs": {
                "get": {
                    "operationId": "getPublicAnalyticsDocs",
                    "summary": "HTML documentation",
                    "responses": {"200": {"description": "Documentation page."}},
                }
            },
            "/api/public/analytics/openapi.json": {
                "get": {
                    "operationId": "getPublicAnalyticsOpenAPI",
                    "summary": "OpenAPI document",
                    "responses": {"200": {"description": "This document."}},
                }
            },
        },
    }


@analytics_public_bp.after_request
def _cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Accept, Content-Type"
    response.headers["Access-Control-Max-Age"] = "86400"
    return response


@analytics_public_bp.errorhandler(APIError)
def _handle_api_error(err):
    body = {"error": err.message}
    body.update(err.details)
    response = _json(body, err.status)
    if err.status == 429:
        response.headers["Retry-After"] = str(err.details.get("retry_after_seconds", RATE_WINDOW))
    return response


@analytics_public_bp.route("/api/public/analytics", methods=["GET", "OPTIONS"])
def public_analytics():
    if request.method == "OPTIONS":
        return make_response("", 204)
    remaining = _enforce_rate_limit()
    parsed = _parse_request()
    payload = _build_payload(parsed)
    response = _json(payload)
    response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["Link"] = (
        f'<{url_for("analytics_public.public_analytics_docs")}>; rel="describedby"'
    )
    return response


@analytics_public_bp.route("/api/public/analytics/docs", methods=["GET"])
def public_analytics_docs():
    example_base = url_for("analytics_public.public_analytics", _external=True)
    response = make_response(
        render_template(
            "public_analytics_docs.html",
            parameters=_parameter_docs(),
            effects=EFFECTS,
            field_groups=FIELD_GROUPS,
            page_map=PAGE_MAP,
            privacy=PRIVACY,
            sections=SECTIONS,
            periods=PERIODS,
            project_statuses=PROJECT_STATUSES,
            bill_types=BILL_TYPES,
            rate_limit=RATE_LIMIT,
            rate_window=RATE_WINDOW,
            default_limit=DEFAULT_LIMIT,
            max_limit=MAX_LIMIT,
            max_series_points=MAX_SERIES_POINTS,
            example_overview=example_base,
            example_filtered=example_base + "?period=last_month&section=time,billing",
            example_range=example_base + "?start=2026-07-01&end=2026-09-30&project_status=Active&limit=10&grain=week",
            openapi_url=url_for("analytics_public.public_analytics_openapi"),
        )
    )
    response.headers["Cache-Control"] = "public, max-age=300"
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response


@analytics_public_bp.route("/api/public/analytics/openapi.json", methods=["GET"])
def public_analytics_openapi():
    return _json(_openapi_spec())
