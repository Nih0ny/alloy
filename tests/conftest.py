import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from alloy.main import app
from alloy.dependencies import get_database  

@pytest.fixture
def mock_db():
    mock_client = AsyncMongoMockClient()
    db = mock_client["test_mock_database"]
    
    return db

@pytest.fixture
def client(mock_db):
    def override_get_db():
        yield mock_db
        
    app.dependency_overrides[get_database] = override_get_db
    
    with TestClient(app) as c:
        yield c
        
    app.dependency_overrides.clear()
