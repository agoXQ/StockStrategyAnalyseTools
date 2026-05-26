from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app import models
from app.deps import get_db
from app.main import app


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_permissions_sync_and_metrics_flow():
    client = make_client()

    admin = client.post(
        "/api/auth/register",
        json={"username": "admin", "password": "secret", "email": "admin@example.com"},
    )
    assert admin.status_code == 200
    assert admin.json()["role"] == "admin"

    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]

    user = client.post(
        "/api/users/",
        headers=auth_headers(admin_token),
        json={"username": "user1", "password": "secret", "email": "u1@example.com", "role": "user"},
    )
    assert user.status_code == 200

    user_login = client.post("/api/auth/login", json={"username": "user1", "password": "secret"})
    assert user_login.status_code == 200
    user_token = user_login.json()["access_token"]

    forbidden_sync = client.post(
        "/api/data/sync",
        headers=auth_headers(user_token),
        json={"trade_date": "2026-01-02", "stock_codes": ["600519"]},
    )
    assert forbidden_sync.status_code == 403

    strategy = client.post(
        "/api/strategies/",
        headers=auth_headers(user_token),
        json={"name": "成长测试", "description": "demo", "benchmark": "CSI300", "tags": ["成长"]},
    )
    assert strategy.status_code == 200
    strategy_id = strategy.json()["id"]

    strategies = client.get("/api/strategies/?keyword=成长&page=1&pageSize=10", headers=auth_headers(user_token))
    assert strategies.status_code == 200
    assert strategies.json()["total"] == 1
    assert strategies.json()["items"][0]["id"] == strategy_id

    batch = client.post(
        f"/api/strategies/{strategy_id}/batches",
        headers=auth_headers(user_token),
        json={"name": "批次A", "batch_date": "2026-01-01", "description": "first"},
    )
    assert batch.status_code == 200
    batch_id = batch.json()["id"]

    stock = client.post(
        f"/api/batches/{batch_id}/stocks",
        headers=auth_headers(user_token),
        json={"stock_code": "600519", "stock_name": "贵州茅台", "is_held": True},
    )
    assert stock.status_code == 200
    stock_id = stock.json()["id"]

    for trade_date in ["2026-01-01", "2026-01-02"]:
        sync = client.post(
            "/api/data/sync",
            headers=auth_headers(admin_token),
            json={"trade_date": trade_date, "stock_codes": ["600519"]},
        )
        assert sync.status_code == 200
        assert sync.json()["success_count"] == 1
        assert sync.json()["provider"] == "demo"

    metrics = client.get(
        f"/api/batches/{batch_id}/metrics?start=2026-01-01&end=2026-01-02",
        headers=auth_headers(user_token),
    )
    assert metrics.status_code == 200
    assert len(metrics.json()["daily"]) == 2

    stock_without_batch = client.get(
        "/api/stocks/600519/metrics?start=2026-01-01&end=2026-01-02",
        headers=auth_headers(user_token),
    )
    assert stock_without_batch.status_code == 400

    hold = client.get(
        f"/api/metrics/hold-return?n=0&k=1&scope=stock&id={stock_id}",
        headers=auth_headers(user_token),
    )
    assert hold.status_code == 200
    assert hold.json()["status"] == "completed"

    comparison = client.get(
        f"/api/strategies/{strategy_id}/compare-batches",
        headers=auth_headers(user_token),
    )
    assert comparison.status_code == 200
    assert comparison.json()["batch_comparison"][0]["batch_id"] == batch_id
