import sqlalchemy as sa

user_role_enum = sa.Enum(
    "admin",
    "customer",
    "pharmacist",
    name="user_roles",
)