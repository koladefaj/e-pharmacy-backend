import sqlalchemy as sa

user_role_enum = sa.Enum(
    "admin",
    "customer",
    "pharmacist",
    name="user_roles",
)

order_status_enum = sa.Enum(
    "CREATED",
    "CHECKOUT_STARTED",
    "AWAITING_PRESCRIPTION",
    "PRESCRIPTION_REJECTED",
    "READY_FOR_PAYMENT",
    "PAID",
    "CANCELLED",
    "FULFILLED",
    name="order_status_enum",
)