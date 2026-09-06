"""Demo subjects.

These are the records a buyer would already have before anyone picks up the
phone: an order, a contact, and a date somebody typed in at some point that
nobody can defend. `known_values` is exactly that -- what the system believes,
which is what a CONTRADICTED verdict is measured against.
"""

from __future__ import annotations

from dataclasses import dataclass

from .planner import Contact


@dataclass(frozen=True)
class Subject:
    id: str
    schema_name: str
    label: str
    contact: Contact
    known_values: dict[str, str]


SUBJECTS: tuple[Subject, ...] = (
    Subject(
        id="PO-1041",
        schema_name="supplier_delivery",
        label="Housing bracket, 500 units",
        contact=Contact(
            phone="+821000001041", name="Kim Min-su", org="Hanseong Precision", role_hint="sales_rep"
        ),
        known_values={"promised_ship_date": "2026-09-24"},
    ),
    Subject(
        id="PO-1042",
        schema_name="supplier_delivery",
        label="Drive shaft, 300 units",
        contact=Contact(
            phone="+821000001042", name="Lee Su-jin", org="Daeryuk Machinery", role_hint="account_manager"
        ),
        known_values={"promised_ship_date": "2026-09-20"},
    ),
    Subject(
        id="PO-1043",
        schema_name="supplier_delivery",
        label="Sensor module, 120 units",
        contact=Contact(
            phone="+821000001043", name="Park Jung-ho", org="Sinwoo Tech", role_hint="production_manager"
        ),
        known_values={"promised_ship_date": "2026-09-18"},
    ),
    Subject(
        id="PO-1044",
        schema_name="supplier_delivery",
        label="Aluminium plate, 80 units",
        contact=Contact(
            phone="+821000001044", name="Choi Young-han", org="Woojin Materials", role_hint="sales_rep"
        ),
        known_values={"promised_ship_date": "2026-10-01"},
    ),
    Subject(
        id="CAND-2291",
        schema_name="reference_check",
        label="Senior researcher candidate",
        contact=Contact(
            phone="+821000002291", name="Jung Ha-neul", org="Previous employer", role_hint="direct_manager"
        ),
        known_values={
            "employment_end_date": "2026-03-31",
            "final_title": "선임 연구원",
        },
    ),
)


def subject(subject_id: str) -> Subject:
    for entry in SUBJECTS:
        if entry.id == subject_id:
            return entry
    raise KeyError(f"unknown subject {subject_id!r}")


def seed_store(store: "object") -> int:
    """Write the demo subjects into a store. Returns how many were written."""
    for entry in SUBJECTS:
        store.upsert_subject(  # type: ignore[attr-defined]
            entry.id,
            schema_name=entry.schema_name,
            label=entry.label,
            contact_name=entry.contact.name,
            contact_phone=entry.contact.phone,
            contact_org=entry.contact.org,
            known_values=entry.known_values,
        )
    return len(SUBJECTS)
