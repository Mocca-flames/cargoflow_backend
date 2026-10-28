from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.documents.models import DocumentType
from app.features.users.model import User  # noqa: F401

ZA = "ZA"

# (code, name, category, applies_to, issuing_authority, requires_expiry, sort_order)
SEED = [
    # Transporter
    ("cipc_registration", "CIPC company registration", "company_registration", "transporter", "CIPC", False, 10),
    ("sars_tax_clearance", "SARS tax compliance status / clearance", "tax_clearance", "transporter", "SARS", True, 20),
    ("goods_in_transit_insurance", "Goods-in-transit insurance certificate", "insurance", "transporter", None, True, 30),
    ("cross_border_permit", "Cross-border road transport permit", "cross_border_permit", "transporter", None, True, 40),
    ("director_id", "Director ID document", "director_id", "transporter", "Department of Home Affairs", True, 50),
    ("bank_confirmation_letter", "Bank confirmation letter", "bank_confirmation", "transporter", None, False, 60),
    # Broker
    ("cipc_registration", "CIPC company registration", "company_registration", "broker", "CIPC", False, 10),
    ("sars_tax_clearance", "SARS tax compliance status / clearance", "tax_clearance", "broker", "SARS", True, 20),
    ("director_id", "Director ID document", "director_id", "broker", "Department of Home Affairs", True, 30),
    ("bank_confirmation_letter", "Bank confirmation letter", "bank_confirmation", "broker", None, False, 40),
    ("trade_references", "Trade references", "references", "broker", None, False, 50),
    # Truck
    ("vehicle_licence", "Vehicle licence disc / registration", "vehicle_licence", "truck", None, True, 10),
]


def seed_document_types(db: Session) -> int:
    created = 0
    for code, name, category, applies_to, authority, expiry, order in SEED:
        exists = db.scalar(
            select(DocumentType.id).where(
                DocumentType.code == code,
                DocumentType.country_code == ZA,
                DocumentType.applies_to == applies_to,
            )
        )
        if exists:
            continue
        db.add(DocumentType(
            code=code, name=name, category=category, applies_to=applies_to,
            country_code=ZA, issuing_authority=authority,
            is_required=True, requires_expiry=expiry, sort_order=order,
        ))
        created += 1
    db.commit()
    return created


if __name__ == "__main__":
    from app.core.database import SessionLocal  # adjust if your session factory is named differently

    with SessionLocal() as session:
        print(f"seeded {seed_document_types(session)} document types")