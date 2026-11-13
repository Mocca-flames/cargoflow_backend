"""Send a sample "new load" director notification through Brevo (real email)."""
import asyncio
from datetime import date, timedelta
from decimal import Decimal

from app.core.email import BrevoMailer
from app.features.companies.models import Company
from app.features.loads.models import Load
from app.features.loads.service import _load_email_html
from app.features.users.model import User

RECIPIENTS = ["junior@cargoflowafrica.co.za", "juniorflamebet@gmail.com"]


def main() -> None:
    load = Load(
        id=9999,
        origin="Lusaka, Zambia",
        destination="Harare, Zimbabwe",
        commodity="Maize meal",
        truck_type="superlink",
        trucks_needed=2,
        rate=Decimal("12000.00"),
        currency="ZAR",
        payment_terms="7 days",
        pickup_date=date.today() + timedelta(days=3),
        note="Collect at depot, deliver to Harare warehouse. Contact Peter +260 977 000 111.",
        backload_origin="Harare",
        backload_destination="Lusaka",
        backload_commodity="Fertilizer",
        backload_rate=Decimal("9500.00"),
        posted_as="client",
        status="open",
    )
    company = Company(legal_name="Example Logistics (Pty) Ltd", trading_name="Example Logistics")
    user = User(email="client@example.com", full_name="Test Client", password_hash="x")

    subject = f"New load #{load.id}: {load.origin} → {load.destination}"
    html_content = _load_email_html(load, company, user)
    mailer = BrevoMailer()
    for recipient in RECIPIENTS:
        asyncio.run(mailer.send(to_email=recipient, subject=subject, html_content=html_content))
        print(f"sent: {recipient}")


if __name__ == "__main__":
    main()
