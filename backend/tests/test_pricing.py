from fastapi.testclient import TestClient
from app.main import app


def test_recommended_price_hits_requested_margin():
    client = TestClient(app)
    response = client.get("/api/pricing/recommendation", params={"cost_xof": 650000, "target_margin_pct": 35})
    assert response.status_code == 200
    body = response.json()
    assert body["suggested_price_xof"] == 1000000
    assert body["estimated_margin_pct"] == 35
