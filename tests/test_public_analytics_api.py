"""Public analytics API: aggregates only, no client or user records."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta

_fd, _DB_PATH = tempfile.mkstemp(prefix="hub-analytics-", suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = "sqlite:///" + _DB_PATH

import analytics_api  # noqa: E402
from app import app, db  # noqa: E402
from models import (  # noqa: E402
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
    get_current_time,
)

FORBIDDEN_TEXT = (
    "priya",
    "nandakumar",
    "jonah",
    "ellison",
    "northwind",
    "helios",
    "casey",
    "morgan",
    "555-0199",
    "evergreen",
    "salary-secret",
    "tok_secret",
    "2222",
    "99999",
    "purpose-secret",
    "note-secret",
    "priya.nandakumar@example.com",
    "7777",
)
FORBIDDEN_KEYS = {
    "user_id",
    "client_id",
    "email",
    "first_name",
    "last_name",
    "contact_name",
    "contact_email",
    "contact_phone",
    "approved_by",
    "approved_by_name",
    "notes",
    "purpose",
    "salary",
    "annual_salary",
    "password",
    "public_token",
    "name",
}


def _walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


class PublicAnalyticsApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _DB_PATH not in app.config["SQLALCHEMY_DATABASE_URI"]:
            raise RuntimeError("Refusing to run against a non-test database")
        cls.ctx = app.app_context()
        cls.ctx.push()
        db.drop_all()
        db.create_all()
        cls.client = app.test_client()
        cls.now = get_current_time()
        cls._seed()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        cls.ctx.pop()
        if os.path.exists(_DB_PATH):
            os.unlink(_DB_PATH)

    def setUp(self):
        analytics_api.RATE_LIMIT = 60
        analytics_api._rate_hits.clear()

    def tearDown(self):
        analytics_api.RATE_LIMIT = 60
        analytics_api._rate_hits.clear()

    @classmethod
    def _seed(cls):
        now = cls.now
        old = now - timedelta(days=45)
        yesterday = now - timedelta(days=1)

        admin = User(
            first_name="Priya",
            last_name="Nandakumar",
            email="priya.nandakumar@example.com",
            role="admin",
            annual_salary=120000,
            notes="salary-secret",
        )
        trainee = User(
            first_name="Jonah",
            last_name="Ellison",
            email="jonah.ellison@example.com",
            role="trainee",
            notes="note-secret trainee",
        )
        active_membership = Membership(title="Bench Access FY26")
        expired_membership = Membership(title="Storage Locker")
        db.session.add_all([admin, trainee, active_membership, expired_membership])
        db.session.flush()

        fy_year = now.year if now.month >= 7 else now.year - 1
        db.session.add_all([
            MembershipFunding(
                membership_id=active_membership.id,
                amount=5000,
                start_date=now - timedelta(days=10),
                end_date=now + timedelta(days=60),
                time_budget=40,
                dollar_budget=1500,
            ),
            MembershipFunding(
                membership_id=expired_membership.id,
                amount=2222,
                start_date=now - timedelta(days=400),
                end_date=now - timedelta(days=200),
                time_budget=9,
                dollar_budget=2222,
            ),
            MembershipFunding(
                membership_id=active_membership.id,
                amount=100,
                start_date=TIMEZONE.localize(datetime(fy_year, 7, 1, 9, 0)),
                end_date=TIMEZONE.localize(datetime(fy_year, 7, 31, 17, 0)),
                payout="upfront",
                time_budget=0,
                dollar_budget=0,
            ),
            MembershipFunding(
                membership_id=active_membership.id,
                amount=7777,
                start_date=now - timedelta(days=1),
                end_date=now + timedelta(days=30),
                payout="exclude",
                time_budget=0,
                dollar_budget=0,
            ),
        ])
        db.session.add(FinanceSettings(
            fy_start_year=fy_year,
            fixed_costs=[100, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ))

        internal_aff = Affiliation(name="Department of Neuroscience", is_internal=True)
        external_aff = Affiliation(name="Partner Biotech", is_internal=False)
        db.session.add_all([internal_aff, external_aff])
        db.session.flush()

        northwind = Client(
            name="Northwind Biolabs",
            membership_id=active_membership.id,
            affiliation_id=internal_aff.id,
            contact_name="Casey Morgan",
            contact_email="casey.morgan@northwind.test",
            contact_phone="555-0199",
            bill_to_address1="742 Evergreen Terrace",
            notes="note-secret client",
        )
        helios = Client(
            name="Helios Clinical",
            affiliation_id=external_aff.id,
            notes="note-secret other client",
        )
        db.session.add_all([northwind, helios])
        db.session.flush()

        optical = Project(name="Optical Bench Calibration", client_id=northwind.id, status="Active")
        shelf = Project(name="Shelf Inventory", client_id=helios.id, status="Archived")
        general = Project(name="General", client_id=northwind.id, status="Active", is_default=True)
        db.session.add_all([optical, shelf, general])
        db.session.flush()

        db.session.add_all([
            Log(notes="note-secret worked with Priya", is_touch=False, hours=2.0, user_id=admin.id, project_id=optical.id, created_at=now),
            Log(notes="note-secret touch", is_touch=True, hours=1.5, user_id=admin.id, project_id=optical.id, created_at=now),
            Log(notes="note-secret old optical", is_touch=False, hours=5.0, user_id=admin.id, project_id=optical.id, created_at=old),
            Log(notes="note-secret general", is_touch=False, hours=9.0, user_id=admin.id, project_id=general.id, created_at=now),
            Log(notes="note-secret shelf", is_touch=False, hours=4.0, user_id=admin.id, project_id=shelf.id, created_at=old),
        ])
        db.session.add_all([
            Quote(
                quote_id="20261104-01",
                client_id=northwind.id,
                project_id=optical.id,
                bill_type="invoice",
                issue_date=now.date(),
                status="published",
                is_public=True,
                total_amount=250,
                public_token="tok_secret_awaiting",
            ),
            Quote(
                quote_id="20261104-02",
                client_id=northwind.id,
                project_id=optical.id,
                bill_type="invoice",
                issue_date=now.date(),
                status="archived",
                total_amount=100,
                public_token="tok_secret_archived",
            ),
            Quote(
                quote_id="20260901-01",
                client_id=northwind.id,
                project_id=optical.id,
                bill_type="quote",
                issue_date=old.date(),
                status="draft",
                total_amount=80,
                public_token="tok_secret_quote",
            ),
            Quote(
                quote_id="20261104-03",
                client_id=northwind.id,
                project_id=optical.id,
                bill_type="invoice",
                issue_date=now.date(),
                status="paid",
                is_public=True,
                total_amount=40,
                approved_by_name="Casey Morgan",
                approved_at=now,
                public_token="tok_secret_paid",
            ),
            Quote(
                quote_id="20261104-04",
                client_id=northwind.id,
                project_id=optical.id,
                title="Calibration run",
                bill_type="invoice",
                finance_mode="profiting",
                profit_percent=50,
                subtotal=200,
                total_amount=0,
                issue_date=now.date(),
                status="paid",
                paid_at=now,
                public_token="tok_secret_profit",
            ),
            Quote(
                quote_id="20261104-05",
                client_id=helios.id,
                project_id=shelf.id,
                title="Lens kit",
                bill_type="quote",
                finance_mode="profiting",
                profit_percent=25,
                subtotal=80,
                total_amount=0,
                issue_date=now.date(),
                status="draft",
                projected_fy_month=0,
                public_token="tok_secret_projected",
            ),
            Quote(
                quote_id="20261104-06",
                client_id=northwind.id,
                project_id=optical.id,
                title="Spare tray",
                bill_type="quote",
                finance_mode="profiting",
                profit_percent=50,
                subtotal=40,
                total_amount=0,
                issue_date=now.date(),
                status="draft",
                projected_fy_month=None,
                public_token="tok_secret_unassigned",
            ),
        ])

        microscope = Equipment(name="Confocal Microscope")
        db.session.add(microscope)
        db.session.flush()
        start = yesterday.replace(hour=9, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=2)
        db.session.add_all([
            EquipmentAppointment(
                equipment_id=microscope.id,
                user_id=trainee.id,
                start_time=start,
                end_time=end,
                purpose="purpose-secret jonah",
                notes="note-secret appointment",
                status="approved",
            ),
            EquipmentAppointment(
                equipment_id=microscope.id,
                user_id=trainee.id,
                start_time=start + timedelta(hours=3),
                end_time=end + timedelta(hours=3),
                purpose="purpose-secret followup",
                status="cancelled",
            ),
            EquipmentAppointment(
                equipment_id=microscope.id,
                user_id=admin.id,
                start_time=start,
                end_time=end,
                purpose="purpose-secret admin",
                status="approved",
            ),
        ])
        db.session.commit()

    def _get(self, query=""):
        response = self.client.get("/api/public/analytics" + query)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def test_overview_matches_page_and_hides_people(self):
        payload = self._get()
        self.assertEqual(payload["api_version"], "1")
        self.assertEqual(payload["timezone"], "America/Chicago")
        self.assertIn("/api/public/analytics/docs", payload["documentation"]["html"])
        self.assertFalse(payload["filters"]["window"]["applied"])
        self.assertIsNone(payload["filters"]["project_status"])

        self.assertEqual(payload["summary"], {
            "active_memberships": 1,
            "active_projects": 2,
            "clients": 2,
        })
        time_block = payload["time"]
        self.assertEqual(time_block["hours"], 21.5)
        self.assertEqual(time_block["logs"], 5)
        self.assertEqual(time_block["detailed_hours"], 20.0)
        self.assertEqual(time_block["touch_hours"], 1.5)
        self.assertEqual(time_block["total_hours_all_time"], 21.5)
        self.assertEqual(time_block["total_hours_last_30_days"], 12.5)
        self.assertEqual(time_block["hours_this_week"], 12.5)
        self.assertEqual(time_block["hours_last_week"], 0.0)
        self.assertEqual(time_block["total_logs"], 5)
        self.assertIsNone(time_block["series"])

        self.assertEqual(payload["projects"]["total"], 3)
        self.assertEqual(payload["projects"]["by_status"]["Active"], 2)
        self.assertEqual(payload["projects"]["by_status"]["Archived"], 1)
        self.assertEqual(payload["projects"]["with_time_logged"], 3)
        self.assertEqual(payload["projects"]["ranking_window"]["label"], "last_30_days")
        self.assertEqual(payload["projects"]["top_by_hours"], [
            {"project": "Optical Bench Calibration", "status": "Active", "hours": 3.5},
        ])

        self.assertEqual(payload["clients"]["total"], 2)
        self.assertEqual(payload["clients"]["internal"], 1)
        self.assertEqual(payload["clients"]["external"], 1)
        self.assertFalse(payload["clients"]["window"]["applied"])
        billing = payload["billing"]
        self.assertEqual(billing["currency"], "USD")
        self.assertEqual(billing["total_bills"], {"count": 2, "amount": 40.0})
        self.assertEqual(billing["active_quotes"], {"count": 3, "amount": 80.0})
        self.assertEqual(billing["active_invoices"], {"count": 1, "amount": 250.0})
        self.assertEqual(billing["internal_invoices"], {"count": 4, "amount": 390.0})
        self.assertEqual(billing["external_invoices"], {"count": 0, "amount": 0.0})

        self.assertEqual(payload["memberships"]["total"], 2)
        self.assertEqual(payload["memberships"]["currently_active"], 1)
        self.assertEqual(payload["memberships"]["active_dollar_budget"], 1500.0)
        self.assertEqual(payload["memberships"]["active_hour_budget"], 40)
        self.assertEqual(payload["memberships"]["ending_soonest"], [
            {
                "membership": "Bench Access FY26",
                "funding_end": (self.now + timedelta(days=60)).date().isoformat(),
            },
        ])

        appointments = payload["appointments"]
        self.assertEqual(appointments["equipment_count"], 1)
        self.assertEqual(appointments["trainee_count"], 1)
        self.assertEqual(appointments["appointment_count"], 2)
        self.assertEqual(appointments["by_status"]["approved"], 1)
        self.assertEqual(appointments["by_status"]["cancelled"], 1)
        self.assertEqual(appointments["by_status"]["pending"], 0)
        self.assertEqual(appointments["top_equipment"], [
            {"equipment": "Confocal Microscope", "appointments": 2},
        ])

        raw = self.client.get("/api/public/analytics").get_data(as_text=True).lower()
        for secret in FORBIDDEN_TEXT:
            self.assertNotIn(secret, raw)
        self.assertFalse(FORBIDDEN_KEYS & set(_walk_keys(payload)))
        self.assertNotIn('"general"', raw)

    def test_date_period_scopes_time_billing_and_rankings(self):
        payload = self._get("?period=last_30_days")
        self.assertTrue(payload["filters"]["window"]["applied"])
        self.assertEqual(payload["filters"]["window"]["label"], "last_30_days")
        # Helios only has an older log; Northwind has effort in the last 30 days.
        self.assertEqual(payload["summary"]["clients"], 1)
        self.assertEqual(payload["clients"]["total"], 1)
        self.assertEqual(payload["clients"]["internal"], 1)
        self.assertEqual(payload["clients"]["external"], 0)
        self.assertTrue(payload["clients"]["window"]["applied"])
        self.assertEqual(payload["time"]["hours"], 12.5)
        self.assertEqual(payload["time"]["logs"], 3)
        self.assertNotIn("total_hours_all_time", payload["time"])
        self.assertEqual(payload["time"]["detailed_hours"], 11.0)
        self.assertEqual(payload["time"]["touch_hours"], 1.5)
        series = payload["time"]["series"]
        self.assertIsNotNone(series)
        self.assertEqual(series["covers"], "last_30_days")
        self.assertEqual(series["grain"], "day")
        self.assertEqual(round(sum(point["hours"] for point in series["points"]), 1), 12.5)
        self.assertEqual(payload["projects"]["top_by_hours"], [
            {"project": "Optical Bench Calibration", "status": "Active", "hours": 3.5},
        ])
        self.assertEqual(payload["billing"]["total_bills"], {"count": 2, "amount": 40.0})
        self.assertEqual(payload["billing"]["active_quotes"], {"count": 2, "amount": 0.0})
        self.assertEqual(payload["appointments"]["appointment_count"], 2)

        today = self._get("?period=today")
        self.assertEqual(today["time"]["hours"], 12.5)
        self.assertEqual(today["appointments"]["appointment_count"], 0)
        self.assertIsNotNone(today["time"]["series"])

        silenced = self._get("?period=last_30_days&series=0")
        self.assertIsNone(silenced["time"]["series"])
        self.assertFalse(silenced["filters"]["series"])

        explicit = self._get("?series=1&section=time")
        self.assertEqual(explicit["time"]["hours"], 21.5)
        self.assertEqual(explicit["time"]["total_hours_all_time"], 21.5)
        self.assertEqual(explicit["time"]["series"]["covers"], "last_30_days")
        self.assertEqual(
            round(sum(point["hours"] for point in explicit["time"]["series"]["points"]), 1),
            12.5,
        )

        today = get_current_time().date()
        start = (today - timedelta(days=500)).isoformat()
        too_fine = self.client.get(f"/api/public/analytics?start={start}&end={today.isoformat()}&grain=day&section=time")
        self.assertEqual(too_fine.status_code, 400)
        self.assertEqual(too_fine.get_json()["parameter"], "grain")

    def test_custom_range_project_status_and_bill_type(self):
        today = get_current_time().date().isoformat()
        custom = self._get(f"?start={today}&end={today}&section=time,billing")
        self.assertEqual(custom["filters"]["window"]["label"], "custom")
        self.assertEqual(
            set(custom) & {"summary", "time", "projects", "clients", "billing", "memberships", "appointments"},
            {"billing", "time"},
        )
        self.assertEqual(custom["time"]["hours"], 12.5)
        self.assertEqual(custom["billing"]["total_bills"]["amount"], 40.0)

        archived = self._get("?project_status=archived")
        self.assertEqual(archived["filters"]["project_status"], ["Archived"])
        self.assertEqual(archived["summary"]["active_projects"], 2)
        self.assertEqual(archived["projects"]["total"], 1)
        self.assertEqual(archived["projects"]["by_status"]["Archived"], 1)
        self.assertEqual(archived["projects"]["by_status"]["Active"], 0)
        self.assertEqual(archived["time"]["hours"], 4.0)
        self.assertEqual(archived["projects"]["top_by_hours"], [])
        self.assertEqual(archived["billing"]["total_bills"], {"count": 0, "amount": 0.0})
        self.assertNotIn("total_hours_all_time", archived["time"])

        ranked = self._get("?period=all_time&project_status=Archived,Active&limit=1")
        names = [item["project"] for item in ranked["projects"]["top_by_hours"]]
        self.assertEqual(names, ["Optical Bench Calibration"])
        self.assertNotIn("General", names)
        self.assertNotIn("Shelf Inventory", names)

        invoices = self._get("?bill_type=Invoice&section=billing")
        self.assertEqual(invoices["filters"]["bill_type"], "invoice")
        self.assertEqual(invoices["billing"]["active_quotes"], {"count": 0, "amount": 0.0})
        self.assertEqual(invoices["billing"]["total_bills"], {"count": 2, "amount": 40.0})
        self.assertEqual(invoices["billing"]["internal_invoices"], {"count": 4, "amount": 390.0})
        self.assertEqual(invoices["billing"]["external_invoices"], {"count": 0, "amount": 0.0})

    def test_fiscal_year_projection_omits_people_and_respects_filters(self):
        payload = self._get("?section=projection")
        projection = payload["projection"]
        fy_year = self.now.year if self.now.month >= 7 else self.now.year - 1
        self.assertEqual(projection["label"], f"FY{(fy_year + 1) % 100}")
        self.assertEqual(projection["start"], f"{fy_year}-07-01")
        self.assertEqual(projection["end"], f"{fy_year + 1}-06-30")
        self.assertEqual(len(projection["months"]), 12)
        self.assertFalse(projection["fixed_costs_from_prior_year"])
        self.assertEqual(projection["salaried_count"], 1)
        self.assertEqual(projection["salary_monthly"], 10000.0)
        self.assertEqual(projection["unassigned_bills"], {"count": 1, "amount": 20.0})
        self.assertEqual(projection["totals"]["salaries"], 120000.0)
        self.assertEqual(projection["totals"]["fixed_costs"], 100.0)
        self.assertEqual(projection["totals"]["paid_bills"], 100.0)
        self.assertEqual(projection["totals"]["projected"], 20.0)
        self.assertEqual(
            projection["totals"]["net"],
            round(
                projection["totals"]["funding"]
                + projection["totals"]["paid_bills"]
                + projection["totals"]["projected"]
                - projection["totals"]["salaries"]
                - projection["totals"]["fixed_costs"],
                2,
            ),
        )

        july = projection["months"][0]
        self.assertEqual(july["label"], f"Jul {fy_year}")
        self.assertEqual(july["fixed_cost"], 100.0)
        self.assertEqual(july["salaries"], 10000.0)
        self.assertIn(
            {"membership": "Bench Access FY26", "payout": "upfront", "amount": 100.0},
            july["funding_items"],
        )
        self.assertEqual(july["projected_items"], [
            {"bill": "Lens kit", "profit_percent": 25, "amount": 20.0},
        ])

        paid_months = [month for month in projection["months"] if month["paid_bills"]]
        self.assertEqual(len(paid_months), 1)
        self.assertEqual(paid_months[0]["paid_bills_items"], [
            {"bill": "Calibration run", "profit_percent": 50, "amount": 100.0},
        ])
        self.assertNotIn("salary_items", paid_months[0])

        raw = self.client.get("/api/public/analytics?section=projection").get_data(as_text=True).lower()
        for secret in FORBIDDEN_TEXT:
            self.assertNotIn(secret, raw, secret)
        self.assertNotIn("northwind", raw)
        self.assertIn("Lens kit", self.client.get("/api/public/analytics?section=projection").get_data(as_text=True))

        full_year = self._get("?period=fiscal_year&section=projection")
        self.assertEqual(len(full_year["projection"]["months"]), 12)
        self.assertEqual(full_year["projection"]["totals"]["projected"], 20.0)

        this_month = self._get("?period=this_month&section=projection")
        self.assertEqual(len(this_month["projection"]["months"]), 1)
        self.assertEqual(this_month["projection"]["months"][0]["salaries"], 10000.0)
        self.assertEqual(this_month["projection"]["totals"]["salaries"], 10000.0)
        self.assertEqual(this_month["projection"]["unassigned_bills"]["count"], 1)

        invoices = self._get("?section=projection&bill_type=invoice")
        self.assertEqual(invoices["projection"]["totals"]["paid_bills"], 100.0)
        self.assertEqual(invoices["projection"]["totals"]["projected"], 0.0)
        self.assertEqual(invoices["projection"]["unassigned_bills"]["count"], 0)
        self.assertEqual(invoices["projection"]["totals"]["funding"], payload["projection"]["totals"]["funding"])

        archived = self._get("?section=projection&project_status=Archived")
        self.assertEqual(archived["projection"]["totals"]["projected"], 20.0)
        self.assertEqual(archived["projection"]["totals"]["paid_bills"], 0.0)
        self.assertEqual(archived["projection"]["unassigned_bills"]["count"], 0)
        self.assertEqual(archived["projection"]["salary_monthly"], 10000.0)

    def test_periods_and_validation(self):
        fiscal = self._get("?period=fiscal_year&section=summary")
        start = fiscal["filters"]["window"]["start"]
        self.assertTrue(start.endswith("-07-01"))
        self.assertEqual(fiscal["filters"]["window"]["end"], get_current_time().date().isoformat())

        month = self._get("?period=this_month&section=summary")
        self.assertTrue(month["filters"]["window"]["start"].endswith("-01"))

        cases = [
            "?period=yesterday",
            "?period=last_month&start=2026-01-01&end=2026-01-31",
            "?start=2026-02-01",
            "?start=2026-03-02&end=2026-03-01",
            "?start=2026-13-01&end=2026-13-02",
            "?section=users",
            "?section=time,clients,users",
            "?project_status=Deleted",
            "?bill_type=receipt",
            "?limit=0",
            "?limit=26",
            "?limit=many",
            "?client_id=1",
            "?user_id=4",
            "?grain=hour",
            "?series=maybe",
        ]
        for query in cases:
            response = self.client.get("/api/public/analytics" + query)
            self.assertEqual(response.status_code, 400, query + " " + response.get_data(as_text=True))
            body = response.get_json()
            self.assertIn("error", body)
            self.assertIn("parameter", body)
            raw = response.get_data(as_text=True).lower()
            self.assertNotIn("northwind", raw)
            self.assertNotIn("priya", raw)

    def test_docs_openapi_and_rate_limit(self):
        docs = self.client.get("/api/public/analytics/docs")
        self.assertEqual(docs.status_code, 200)
        self.assertIn("text/html", docs.content_type)
        page = docs.get_data(as_text=True)
        self.assertIn("Client and user details are not in this API.", page)
        for name in ("section", "period", "project_status", "bill_type", "series", "grain"):
            self.assertIn(name, page)
        self.assertNotIn("Northwind", page)
        self.assertNotIn("Priya", page)

        spec = self.client.get("/api/public/analytics/openapi.json")
        self.assertEqual(spec.status_code, 200)
        document = spec.get_json()
        self.assertEqual(document["openapi"], "3.0.3")
        operation = document["paths"]["/api/public/analytics"]["get"]
        names = {item["name"] for item in operation["parameters"]}
        self.assertEqual(
            names,
            {"section", "period", "start", "end", "project_status", "bill_type", "limit", "series", "grain"},
        )
        self.assertNotIn("client", " ".join(names))

        preflight = self.client.options("/api/public/analytics")
        self.assertEqual(preflight.status_code, 204)
        self.assertEqual(preflight.headers["Access-Control-Allow-Origin"], "*")

        posted = self.client.post("/api/public/analytics")
        self.assertEqual(posted.status_code, 405)

        analytics_api.RATE_LIMIT = 2
        analytics_api._rate_hits.clear()
        self.assertEqual(self.client.get("/api/public/analytics?section=summary").status_code, 200)
        self.assertEqual(self.client.get("/api/public/analytics?section=summary").status_code, 200)
        limited = self.client.get("/api/public/analytics?section=summary")
        self.assertEqual(limited.status_code, 429)
        self.assertIn("Retry-After", limited.headers)
        self.assertEqual(limited.get_json()["error"], "Rate limit exceeded. Try again shortly.")
        # Documentation stays available when the data endpoint is limited.
        self.assertEqual(self.client.get("/api/public/analytics/docs").status_code, 200)


if __name__ == "__main__":
    unittest.main()
