"""Sample data for local development and demos. Never runs unless asked to."""

import re
from datetime import timedelta
from decimal import Decimal

from flask import current_app

from stockroom.extensions import db
from stockroom.models import (
    Courier,
    Item,
    Order,
    Project,
    Role,
    ShippingSpeed,
    Status,
    Urgency,
    User,
    utcnow,
)


def _order(project, by, vendor, url, status, days_ago, items, shipping="0", **extra) -> Order:
    return Order(
        project=project,
        created_by=by,
        vendor=vendor,
        vendor_url=url,
        status=status,
        created_at=utcnow() - timedelta(days=days_ago),
        urgency=extra.pop("urgency", Urgency.END_OF_WEEK),
        shipping_speed=extra.pop("speed", ShippingSpeed.GROUND),
        shipping_cost=Decimal(shipping),
        items=[
            Item(
                description=d,
                part_number=p,
                unit_price=Decimal(u),
                quantity=q,
                justification=j,
            )
            for d, p, u, q, j in items
        ],
        **extra,
    )


def seed_demo() -> bool:
    """Add a superuser, an admin and sample projects. Returns False if data already exists."""
    if db.session.scalar(db.select(db.func.count(Project.id))):
        return False

    super_email = current_app.config["SUPERUSER_EMAIL"] or "superuser@example.com"
    if not db.session.scalar(db.select(User).filter_by(email=super_email)):
        local = super_email.partition("@")[0]
        name = " ".join(w.capitalize() for w in re.split(r"[._-]+", local) if w) or "Superuser"
        db.session.add(User(email=super_email, name=name, role=Role.ADMIN, is_superuser=True))

    rover = Project(name="Mars Rover Arm")
    drone = Project(name="Autonomous Drone")
    grid = Project(name="Smart Grid Monitor")
    riley = User(email="pm.rover@example.com", name="Riley Chen", role=Role.PM, project=rover)
    sam = User(email="pm.rover2@example.com", name="Sam Ortiz", role=Role.PM, project=rover)
    jordan = User(email="pm.drone@example.com", name="Jordan Lee", role=Role.PM, project=drone)

    db.session.add_all(
        [
            User(email="admin@example.com", name="Morgan Admin", role=Role.ADMIN),
            rover,
            drone,
            grid,
            riley,
            sam,
            jordan,
            _order(
                rover,
                riley,
                "Digi-Key",
                "https://www.digikey.com",
                Status.DELIVERED,
                21,
                [
                    (
                        "NEMA 17 stepper motor",
                        "1528-1062-ND",
                        "14.95",
                        4,
                        "Joint actuators for the arm",
                    ),
                    ("A4988 stepper driver", "1568-1108-ND", "5.95", 4, "One driver per motor"),
                ],
                shipping="8.99",
                courier=Courier.UPS,
                tracking_url="https://www.ups.com/track",
            ),
            _order(
                rover,
                sam,
                "McMaster-Carr",
                "https://www.mcmaster.com",
                Status.SHIPPED,
                6,
                [
                    ('Aluminum 6061 bar, 1/4" x 1"', "8975K13", "11.42", 3, "Arm links"),
                    ("M3 socket head screws (100)", "91290A115", "9.80", 1, "Assembly hardware"),
                ],
                shipping="12.50",
                courier=Courier.FEDEX,
                tracking_url="https://www.fedex.com/fedextrack",
                speed=ShippingSpeed.TWO_DAY,
            ),
            _order(
                rover,
                riley,
                "Adafruit",
                "https://www.adafruit.com",
                Status.PENDING,
                1,
                [("BNO055 9-DOF IMU", "4646", "34.95", 1, "End-effector orientation sensing")],
                urgency=Urgency.IMMEDIATE,
            ),
            _order(
                drone,
                jordan,
                "Amazon",
                "https://www.amazon.com",
                Status.APPROVED,
                3,
                [
                    ("4S 1500mAh LiPo battery", "B0-LIPO-4S", "32.99", 2, "Flight batteries"),
                    ("Balance charger", "B0-CHARGER", "45.00", 1, "Charging the flight batteries"),
                ],
            ),
            _order(
                drone,
                jordan,
                "GetFPV",
                "https://www.getfpv.com",
                Status.CANCELED,
                10,
                [('5" carbon fiber frame', "GF-5", "59.99", 1, "Replaced by an in-house frame")],
            ),
        ]
    )
    db.session.commit()
    return True
