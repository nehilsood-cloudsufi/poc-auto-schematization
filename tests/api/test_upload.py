"""Tests for file upload endpoint."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(output_dir=tmp_path)
    return TestClient(app)


class TestUpload:
    def test_upload_csv(self, client, tmp_path):
        csv_content = b"col1,col2\nval1,val2\n"
        response = client.post(
            "/api/upload",
            files={"input_csv": ("test_data.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert data["dataset_name"] == "test_data"
        assert data["rows"] == 1
        assert data["columns"] == 2

    def test_upload_csv_with_metadata(self, client, tmp_path):
        csv_content = b"col1,col2\nval1,val2\n"
        meta_content = b"key,value\nname,test\n"
        response = client.post(
            "/api/upload",
            files={
                "input_csv": ("data.csv", csv_content, "text/csv"),
                "metadata_csv": ("meta.csv", meta_content, "text/csv"),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["metadata_path"] is not None

    def test_upload_no_file(self, client):
        response = client.post("/api/upload")
        assert response.status_code == 422

    def test_upload_empty_csv(self, client):
        csv_content = b"col1,col2\n"
        response = client.post(
            "/api/upload",
            files={"input_csv": ("empty.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 400
        assert "no data rows" in response.json()["detail"].lower()

    def test_upload_custom_dataset_name(self, client):
        csv_content = b"a,b\n1,2\n"
        response = client.post(
            "/api/upload",
            data={"dataset_name": "custom_name"},
            files={"input_csv": ("data.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 200
        assert response.json()["dataset_name"] == "custom_name"
