import os
import json
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.deps import get_redis, get_storage
from app.core.roles import UserRole
from app.core.security import hash_password
from app.db.base import Base
from app.db.enums import CategoryEnum, OrderStatus
from app.db.sessions import get_async_session
from app.main import app
from app.models.inventory import InventoryBatch
from app.models.product import Product
from app.models.user import User
from app.services.notification.notification_service import NotificationService
from app.services.prescription_service import PrescriptionService
from app.core.deps import get_service, get_session_factory



# DISABLE RATE LIMITING GLOBALLY
app.state.limiter_enabled = False


# DATABASE SETUP (SQLite in-memory, SAFE)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingAsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)



# PYTEST CORE FIXTURES
@pytest.fixture(scope="session")
def test_app():
    app.debug = True
    return app



@pytest.fixture(scope="session", autouse=True)
def disable_rate_limiter():
    patcher = patch(
        "slowapi.extension.Limiter.limit",
        side_effect=lambda *args, **kwargs: lambda f: f,
    )
    patcher.start()
    yield
    patcher.stop()

@pytest.fixture(scope="function", autouse=True)
async def setup_db():
    """Create and drop tables per test (NO engine.dispose)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    IMPORTANT:
    - NO rollback
    - NO manual close
    - SQLite tables are recreated anyway
    """
    async with TestingAsyncSessionLocal() as session:
        yield session

@pytest.fixture(scope="session", autouse=True)
async def close_engine():
    yield
    await engine.dispose()



@pytest.fixture(autouse=True)
def block_real_r2_storage(monkeypatch, mock_storage_service):
    monkeypatch.setattr(
        "app.storage.r2_storage.R2Storage",
        lambda *args, **kwargs: mock_storage_service,
    )




# MOCKS
@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    _storage = {}

    async def set_val(key, val, ex=None):
        _storage[key] = val

    async def get_val(key):
        return _storage.get(key)

    async def delete_val(key):
        _storage.pop(key, None)

    redis.set = AsyncMock(side_effect=set_val)
    redis.get = AsyncMock(side_effect=get_val)
    redis.delete = AsyncMock(side_effect=delete_val)
    redis.execute_command = AsyncMock()
    return redis



@pytest.fixture(autouse=True)
def mock_stripe(monkeypatch):
    """Mock PaymentIntent.create to avoid real Stripe calls."""

    def fake_create(**kwargs):
        # Fake PaymentIntent object
        mock_intent = MagicMock()
        mock_intent.id = f"pi_{uuid.uuid4().hex}"
        mock_intent.client_secret = "secret_123"
        mock_intent.metadata = kwargs.get("metadata", {})
        return mock_intent

    # Patch the correct import path of stripe.PaymentIntent.create
    monkeypatch.setattr(
        "app.services.payment_service.stripe.PaymentIntent.create",
        fake_create
    )
    yield

@pytest.fixture(autouse=True)
def mock_stripe_webhook(monkeypatch):
    """Mock Webhook.construct_event to bypass signature verification."""

    class FakeStripePaymentIntent:
        def __init__(self, payload):
            self.id = payload.get("id", f"pi_{uuid.uuid4().hex}")
            self.metadata = payload.get("metadata", {})

    class FakeStripeEvent:
        def __init__(self, payload: dict):
            self.id = payload.get("id", f"evt_{uuid.uuid4().hex}")
            self.type = payload.get("type", "payment_intent.succeeded")
            obj_data = payload.get("data", {}).get("object", {})
            self.data = MagicMock(object=FakeStripePaymentIntent(obj_data))

        def to_dict(self):
            return {
                "id": self.id,
                "type": self.type,
                "data": {"object": self.data.object.__dict__},
            }

    def fake_construct(payload_bytes, sig_header=None, secret=None):
        if isinstance(payload_bytes, bytes):
            payload_dict = json.loads(payload_bytes.decode("utf-8"))
        else:
            payload_dict = payload_bytes
        return FakeStripeEvent(payload_dict)

    monkeypatch.setattr(
        "app.services.payment_service.stripe.Webhook.construct_event",
        fake_construct
    )
    yield



@pytest.fixture
def mock_notification_service(monkeypatch):
    mock = AsyncMock(spec=NotificationService)
    monkeypatch.setattr(
        "app.services.notification.service.NotificationService",
        lambda: mock,
    )
    return mock



# DATA FIXTURES
@pytest.fixture
async def sample_product(db_session):
    product = Product(
        name="Paracetamol 500mg",
        slug="paracetamol-500mg",
        category=CategoryEnum.OTC,
        active_ingredients="Paracetamol",
        age_restriction=0,
        storage_condition="cool dry place",
        prescription_required=False,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest.fixture
async def test_admin(db_session):
    admin = User(
        full_name="Admin User",
        email="admin@test.com",
        hashed_password=hash_password("adminpass123"),
        role=UserRole.ADMIN,
        is_active=True,
        phone_number="+2340000000000",
        date_of_birth=date(2004, 1, 1),
        address="Store Head Office",
    )
    db_session.add(admin)
    await db_session.commit()
    return admin


@pytest.fixture
async def admin_token(client, test_admin):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.com", "password": "adminpass123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def test_pharmacist(db_session):
    user = User(
        full_name="Test Pharmacist",
        email="pharma@test.com",
        phone_number="+234800000002",
        date_of_birth=date(1999, 1, 1),
        role="pharmacist",
        is_active=True,
        license_verified=True,
        address="example street 333",
        hashed_password=hash_password("strongpassword123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def pharmacist_token(client, test_pharmacist):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "pharma@test.com", "password": "strongpassword123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def test_customer(db_session):
    user = User(
        full_name="test user",
        email="test@example.com",
        phone_number="+1230000000000",
        address="example street 123",
        date_of_birth=date(1999, 1, 1),
        hashed_password=hash_password("strongpassword123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def customer_token(client, test_customer):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "strongpassword123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def sample_product_otc(db_session):
    product = Product(
        name="Vitamin C 1000mg",
        slug=f"vit-c-{uuid.uuid4().hex[:4]}",
        category=CategoryEnum.SUPPLEMENT,
        active_ingredients="Ascorbic Acid",
        prescription_required=False,
        age_restriction=0,
        storage_condition="cool dry place",
        is_active=True,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest.fixture
async def sample_product_rx(db_session):
    product = Product(
        name="Amoxicillin 500mg",
        slug=f"amox-{uuid.uuid4().hex[:4]}",
        category=CategoryEnum.PRESCRIPTION,
        active_ingredients="Amoxicillin",
        prescription_required=True,
        age_restriction=0,
        storage_condition="cool dry place",
        is_active=True,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest.fixture
async def storefront_data(db_session, sample_product_otc, sample_product_rx):
    batch = InventoryBatch(
        product_id=sample_product_otc.id,
        batch_number="B1",
        initial_quantity=50,
        current_quantity=50,
        price=10.0,
        expiry_date=datetime.now(timezone.utc) + timedelta(days=100),
    )
    db_session.add(batch)
    await db_session.commit()
    return {"otc": sample_product_otc, "rx": sample_product_rx}


@pytest.fixture
async def sample_order(db_session, test_customer):
    from app.models.order import Order

    order = Order(
        customer_id=test_customer.id,
        total_amount=100.0,
        status=OrderStatus.AWAITING_PRESCRIPTION,
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)
    return order



# MOCK STORAGE
class MockR2Storage:
    def __init__(self):
        self.uploaded_files = {}
        self.bucket = "test-bucket"
        self.client = MagicMock()

    def generate_presigned_url(self, key: str, expires_in: int = 300) -> str:
        return f"https://mock-storage/{key}"

    async def upload(self, file_id, file_name, file_bytes, content_type):
        self.uploaded_files[file_id] = file_bytes
        return file_id

    async def get_file_path(self, file_id):
        path = os.path.join(tempfile.gettempdir(), file_id)
        with open(path, "wb") as f:
            f.write(self.uploaded_files[file_id])
        return path

    def clear(self):
        self.uploaded_files.clear()


@pytest.fixture
def mock_storage_service():
    storage = MockR2Storage()
    yield storage
    storage.clear()



# DEPENDENCY OVERRIDES
@pytest.fixture(autouse=True)
def override_dependencies(test_app, db_session, mock_storage_service, mock_redis):

    async def _get_test_session():
        yield db_session


    def _get_test_db_factory():
        class AsyncSessionContextManager:
            async def __aenter__(self):
                return db_session 
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass 
        return AsyncSessionContextManager
    

    def _get_prescription_service(session: AsyncSession = None):
        return PrescriptionService(
            session=session or db_session,
            storage=mock_storage_service,
        )

    from app.storage.r2_storage import R2Storage

    test_app.dependency_overrides[get_session_factory] = _get_test_db_factory
    test_app.dependency_overrides[get_async_session] = _get_test_session
    test_app.dependency_overrides[get_storage] = lambda: mock_storage_service
    test_app.dependency_overrides[R2Storage] = lambda: mock_storage_service
    test_app.dependency_overrides[get_service(PrescriptionService)] = _get_prescription_service
    test_app.dependency_overrides[get_redis] = lambda: mock_redis

    yield

    test_app.dependency_overrides.clear()



# HTTP CLIENT
@pytest.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://localhost",
    ) as ac:
        yield ac
