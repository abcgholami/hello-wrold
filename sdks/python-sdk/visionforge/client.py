"""
VisionForge Python SDK — API client for platform interactions.

Usage:
    from visionforge import VisionForgeClient

    client = VisionForgeClient(base_url="https://your-platform.com", api_key="vf_...")
    project = client.get_project("project-id")
    client.upload_images("dataset-id", ["img1.jpg", "img2.jpg"])
"""
import hashlib
import os
from pathlib import Path
from typing import Iterator, List, Optional, Union
import io
import requests


class VisionForgeClient:
    """Client for the VisionForge Platform API."""

    def __init__(
        self,
        base_url: str = "http://localhost",
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        timeout: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.access_token = access_token
        self.timeout = timeout
        self._session = requests.Session()

    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _get(self, path: str, **kwargs) -> dict:
        res = self._session.get(
            f"{self.base_url}/api/core{path}",
            headers=self._headers(),
            timeout=self.timeout,
            **kwargs,
        )
        res.raise_for_status()
        return res.json()

    def _post(self, path: str, json: Optional[dict] = None, **kwargs) -> dict:
        res = self._session.post(
            f"{self.base_url}/api/core{path}",
            headers=self._headers(),
            json=json,
            timeout=self.timeout,
            **kwargs,
        )
        res.raise_for_status()
        return res.json()

    # ── Auth ──────────────────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> dict:
        """Authenticate and store access token."""
        res = requests.post(
            f"{self.base_url}/api/core/auth/login",
            json={"email": email, "password": password},
            timeout=self.timeout,
        )
        res.raise_for_status()
        data = res.json()
        self.access_token = data["access_token"]
        return data

    # ── Projects ──────────────────────────────────────────────────────────────

    def list_projects(self, org_id: str = "default") -> list:
        return self._get("/projects", params={"org_id": org_id})

    def get_project(self, project_id: str) -> dict:
        return self._get(f"/projects/{project_id}")

    def create_project(self, name: str, task_type: str, org_id: str = "default", description: str = "") -> dict:
        return self._post("/projects", json={
            "name": name,
            "task_type": task_type,
            "org_id": org_id,
            "description": description,
        })

    # ── Datasets ──────────────────────────────────────────────────────────────

    def list_datasets(self, project_id: str) -> list:
        return self._get("/datasets", params={"project_id": project_id})

    def create_dataset(self, project_id: str, name: str) -> dict:
        return self._post("/datasets", json={"project_id": project_id, "name": name})

    # ── Images ────────────────────────────────────────────────────────────────

    def upload_images(
        self,
        dataset_id: str,
        images: List[Union[str, Path, bytes]],
        show_progress: bool = True,
    ) -> dict:
        """Upload images to a dataset."""
        files = []
        for img in images:
            if isinstance(img, (str, Path)):
                path = Path(img)
                files.append(("files", (path.name, path.read_bytes(), "image/jpeg")))
            elif isinstance(img, bytes):
                files.append(("files", ("image.jpg", img, "image/jpeg")))

        res = self._session.post(
            f"{self.base_url}/api/core/images/{dataset_id}/upload",
            headers=self._headers(),
            files=files,
            timeout=300,
        )
        res.raise_for_status()
        return res.json()

    def upload_folder(
        self,
        dataset_id: str,
        folder_path: Union[str, Path],
        extensions: tuple = (".jpg", ".jpeg", ".png", ".bmp", ".webp"),
        recursive: bool = True,
    ) -> dict:
        """Upload all images from a folder."""
        folder = Path(folder_path)
        glob_method = folder.rglob if recursive else folder.glob

        image_paths = []
        for ext in extensions:
            image_paths.extend(glob_method(f"*{ext}"))
            image_paths.extend(glob_method(f"*{ext.upper()}"))

        print(f"Found {len(image_paths)} images in {folder}")

        # Upload in batches of 20
        batch_size = 20
        total_uploaded = 0
        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i:i + batch_size]
            result = self.upload_images(dataset_id, batch)
            total_uploaded += result.get("uploaded", 0)
            if show_progress:
                print(f"Uploaded {total_uploaded}/{len(image_paths)} images")

        return {"uploaded": total_uploaded, "total": len(image_paths)}

    def list_images(self, dataset_id: str, page: int = 1, per_page: int = 50) -> dict:
        return self._get(f"/images/{dataset_id}/images", params={"page": page, "per_page": per_page})

    # ── Annotations ──────────────────────────────────────────────────────────

    def get_annotations(self, image_id: str) -> list:
        return self._get(f"/annotations/images/{image_id}/annotations")

    def create_annotation(self, image_id: str, annotation: dict) -> dict:
        return self._post(f"/annotations/images/{image_id}/annotations", json=annotation)

    # ── Label Classes ─────────────────────────────────────────────────────────

    def list_label_classes(self, project_id: str) -> list:
        return self._get("/label-classes", params={"project_id": project_id})

    def create_label_class(self, project_id: str, name: str, color: str = "#FF0000") -> dict:
        return self._post("/label-classes", json={
            "project_id": project_id, "name": name, "color": color
        })

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict(
        self,
        endpoint_id: str,
        image: Union[str, Path, bytes],
        confidence_threshold: float = 0.25,
        iou_threshold: float = 0.45,
    ) -> dict:
        """Run inference on an image using a deployed endpoint."""
        if isinstance(image, (str, Path)):
            image_bytes = Path(image).read_bytes()
            filename = Path(image).name
        else:
            image_bytes = image
            filename = "image.jpg"

        res = self._session.post(
            f"{self.base_url}/api/infer/predict/{endpoint_id}",
            headers=self._headers(),
            files={"file": (filename, image_bytes, "image/jpeg")},
            params={"confidence_threshold": confidence_threshold, "iou_threshold": iou_threshold},
            timeout=self.timeout,
        )
        res.raise_for_status()
        return res.json()

    def predict_folder(
        self,
        endpoint_id: str,
        folder_path: Union[str, Path],
        extensions: tuple = (".jpg", ".jpeg", ".png"),
    ) -> Iterator[dict]:
        """Run inference on all images in a folder. Yields prediction results."""
        folder = Path(folder_path)
        for ext in extensions:
            for img_path in folder.glob(f"*{ext}"):
                result = self.predict(endpoint_id, img_path)
                yield {"path": str(img_path), **result}
