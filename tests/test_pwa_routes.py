import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from starlette.testclient import TestClient
from main import app

def test_service_worker_route():
    client = TestClient(app)
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache, no-store, must-revalidate"
    assert "self.skipWaiting()" in response.text

def test_manifest_routes():
    client = TestClient(app)
    for path in ["/manifest.json", "/static/manifest.json"]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache, no-store, must-revalidate"
