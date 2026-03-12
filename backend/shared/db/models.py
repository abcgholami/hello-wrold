"""
SQLAlchemy ORM models for VisionForge.
All tables use UUID primary keys and timestamptz for audit fields.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, BigInteger, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


def _uuid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ── Users & Auth ──────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)  # null for OAuth-only users
    full_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    memberships = relationship("OrgMembership", back_populates="user")
    api_keys = relationship("ApiKey", back_populates="created_by_user")


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    plan = Column(String, default="free")  # free, pro, enterprise
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    memberships = relationship("OrgMembership", back_populates="org")
    projects = relationship("Project", back_populates="org")


class OrgMembership(Base):
    __tablename__ = "org_memberships"

    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role = Column(String, nullable=False, default="viewer")  # owner, admin, annotator, viewer

    org = relationship("Organization", back_populates="memberships")
    user = relationship("User", back_populates="memberships")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=False)
    key_hash = Column(String, unique=True, nullable=False)
    key_prefix = Column(String, nullable=False)  # first 8 chars for display
    scopes = Column(ARRAY(String), default=["infer"])
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    created_by_user = relationship("User", back_populates="api_keys")


# ── Projects & Datasets ───────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String, nullable=False)
    # classification, detection, instance_seg, semantic_seg
    task_type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    org = relationship("Organization", back_populates="projects")
    datasets = relationship("Dataset", back_populates="project")
    label_classes = relationship("LabelClass", back_populates="project")
    training_jobs = relationship("TrainingJob", back_populates="project")
    model_versions = relationship("ModelVersion", back_populates="project")
    inference_endpoints = relationship("InferenceEndpoint", back_populates="project")
    workflows = relationship("WorkflowDefinition", back_populates="project")


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="datasets")
    images = relationship("Image", back_populates="dataset")
    versions = relationship("DatasetVersion", back_populates="dataset")


class LabelClass(Base):
    __tablename__ = "label_classes"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    color = Column(String, nullable=False, default="#FF0000")
    parent_id = Column(UUID(as_uuid=False), ForeignKey("label_classes.id"), nullable=True)
    supercategory = Column(String, nullable=True)
    coco_id = Column(Integer, nullable=True)  # COCO category id for export
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="label_classes")
    annotations = relationship("Annotation", back_populates="label_class")

    __table_args__ = (
        Index("idx_label_classes_project", "project_id"),
    )


# ── Images & Annotations ──────────────────────────────────────────────────────

class Image(Base):
    __tablename__ = "images"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    dataset_id = Column(UUID(as_uuid=False), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    storage_key = Column(String, nullable=False)        # MinIO object key
    thumb_key = Column(String, nullable=True)           # 256px thumbnail
    medium_key = Column(String, nullable=True)          # 800px medium
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    phash = Column(String, nullable=True, index=True)   # perceptual hash for dedup
    source_video_id = Column(UUID(as_uuid=False), nullable=True)
    frame_number = Column(Integer, nullable=True)
    # train, val, test, unassigned
    split = Column(String, default="unassigned", index=True)
    # unannotated, in_progress, annotated, reviewed
    annotation_status = Column(String, default="unannotated", index=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    dataset = relationship("Dataset", back_populates="images")
    annotations = relationship("Annotation", back_populates="image", cascade="all, delete-orphan")
    assignments = relationship("AnnotationAssignment", back_populates="image")

    __table_args__ = (
        Index("idx_images_dataset", "dataset_id"),
        Index("idx_images_split", "split"),
        Index("idx_images_status", "annotation_status"),
    )


class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    image_id = Column(UUID(as_uuid=False), ForeignKey("images.id", ondelete="CASCADE"), nullable=False, index=True)
    label_class_id = Column(UUID(as_uuid=False), ForeignKey("label_classes.id", ondelete="SET NULL"), nullable=True, index=True)
    # bbox, polygon, mask, classification, keypoints
    annotation_type = Column(String, nullable=False)
    # Bounding box (normalized 0-1)
    bbox_x = Column(Float, nullable=True)
    bbox_y = Column(Float, nullable=True)
    bbox_w = Column(Float, nullable=True)
    bbox_h = Column(Float, nullable=True)
    # Polygon/mask: COCO format [[x1,y1,x2,y2,...]]
    segmentation = Column(JSONB, nullable=True)
    # Keypoints: [[x,y,v], ...] COCO format
    keypoints = Column(JSONB, nullable=True)
    confidence = Column(Float, default=1.0)
    is_ai_generated = Column(Boolean, default=False)
    # pending, approved, rejected
    review_status = Column(String, default="pending")
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    image = relationship("Image", back_populates="annotations")
    label_class = relationship("LabelClass", back_populates="annotations")

    __table_args__ = (
        Index("idx_annotations_image", "image_id"),
        Index("idx_annotations_label", "label_class_id"),
    )


class AnnotationAssignment(Base):
    __tablename__ = "annotation_assignments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    image_id = Column(UUID(as_uuid=False), ForeignKey("images.id", ondelete="CASCADE"), nullable=False)
    assigned_to = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    assigned_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="pending")  # pending, in_progress, done
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    image = relationship("Image", back_populates="assignments")


# ── Dataset Versioning ────────────────────────────────────────────────────────

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    dataset_id = Column(UUID(as_uuid=False), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    name = Column(String, nullable=True)
    split_config = Column(JSONB, nullable=True)          # {"train":0.7,"val":0.2,"test":0.1}
    augmentation_config = Column(JSONB, nullable=True)   # Albumentations pipeline JSON
    filters = Column(JSONB, nullable=True)               # class filters, size filters
    image_count = Column(Integer, nullable=True)
    annotation_count = Column(Integer, nullable=True)
    class_distribution = Column(JSONB, nullable=True)
    export_cache = Column(JSONB, nullable=True)          # cached export download keys
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dataset = relationship("Dataset", back_populates="versions")
    version_images = relationship("DatasetVersionImage", back_populates="version")
    training_jobs = relationship("TrainingJob", back_populates="dataset_version")


class DatasetVersionImage(Base):
    __tablename__ = "dataset_version_images"

    version_id = Column(UUID(as_uuid=False), ForeignKey("dataset_versions.id", ondelete="CASCADE"), primary_key=True)
    image_id = Column(UUID(as_uuid=False), ForeignKey("images.id", ondelete="CASCADE"), primary_key=True)
    split = Column(String, nullable=False)        # train, val, test
    augmented = Column(Boolean, default=False)

    version = relationship("DatasetVersion", back_populates="version_images")
    image = relationship("Image")


# ── Training ──────────────────────────────────────────────────────────────────

class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False, index=True)
    dataset_version_id = Column(UUID(as_uuid=False), ForeignKey("dataset_versions.id"), nullable=False)
    task_type = Column(String, nullable=False)         # classification, detection, instance_seg, semantic_seg
    framework = Column(String, nullable=False)         # ultralytics, mmseg, timm
    architecture = Column(String, nullable=False)      # yolov8n, segformer-b2, etc.
    hyperparameters = Column(JSONB, nullable=False)
    preset = Column(String, nullable=True)             # fast, balanced, accuracy
    # queued, running, completed, failed, cancelled
    status = Column(String, default="queued", index=True)
    celery_task_id = Column(String, nullable=True)
    gpu_count = Column(Integer, default=1)
    current_epoch = Column(Integer, default=0)
    total_epochs = Column(Integer, nullable=True)
    best_metric = Column(Float, nullable=True)
    best_metric_name = Column(String, nullable=True)   # mAP50, top1_acc, mIoU
    mlflow_run_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    project = relationship("Project", back_populates="training_jobs")
    dataset_version = relationship("DatasetVersion", back_populates="training_jobs")
    epoch_metrics = relationship("TrainingEpochMetric", back_populates="job", cascade="all, delete-orphan")
    model_versions = relationship("ModelVersion", back_populates="training_job")


class TrainingEpochMetric(Base):
    __tablename__ = "training_epoch_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(UUID(as_uuid=False), ForeignKey("training_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    epoch = Column(Integer, nullable=False)
    metrics = Column(JSONB, nullable=False)   # {"loss": 0.32, "mAP50": 0.76, ...}
    logged_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("TrainingJob", back_populates="epoch_metrics")


# ── Model Registry ────────────────────────────────────────────────────────────

class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False, index=True)
    training_job_id = Column(UUID(as_uuid=False), ForeignKey("training_jobs.id"), nullable=True)
    dataset_version_id = Column(UUID(as_uuid=False), ForeignKey("dataset_versions.id"), nullable=True)
    version_number = Column(Integer, nullable=False)
    name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    architecture = Column(String, nullable=False)
    task_type = Column(String, nullable=False)
    hyperparameters = Column(JSONB, nullable=True)
    metrics = Column(JSONB, nullable=True)               # final eval metrics
    artifact_storage_key = Column(String, nullable=False) # MinIO key for .pt
    export_artifacts = Column(JSONB, nullable=True)       # {"onnx": "key", "tflite": "key"}
    # development, staging, production, archived
    stage = Column(String, default="development", index=True)
    is_champion = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)

    project = relationship("Project", back_populates="model_versions")
    training_job = relationship("TrainingJob", back_populates="model_versions")
    inference_endpoints = relationship("InferenceEndpoint", back_populates="model_version")


# ── Inference ─────────────────────────────────────────────────────────────────

class InferenceEndpoint(Base):
    __tablename__ = "inference_endpoints"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False, index=True)
    model_version_id = Column(UUID(as_uuid=False), ForeignKey("model_versions.id"), nullable=False)
    name = Column(String, nullable=False)
    endpoint_type = Column(String, default="rest")       # rest, triton, torchserve
    url = Column(String, nullable=True)
    # active, inactive, deploying, error
    status = Column(String, default="inactive", index=True)
    config = Column(JSONB, nullable=True)                # confidence_threshold, iou_threshold, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="inference_endpoints")
    model_version = relationship("ModelVersion", back_populates="inference_endpoints")
    logs = relationship("InferenceLog", back_populates="endpoint")


class InferenceLog(Base):
    __tablename__ = "inference_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    endpoint_id = Column(UUID(as_uuid=False), ForeignKey("inference_endpoints.id", ondelete="CASCADE"), nullable=False, index=True)
    image_hash = Column(String, nullable=True)
    predictions = Column(JSONB, nullable=True)
    confidence_scores = Column(ARRAY(Float), nullable=True)
    inference_time_ms = Column(Integer, nullable=True)
    logged_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    endpoint = relationship("InferenceEndpoint", back_populates="logs")


# ── Workflows ─────────────────────────────────────────────────────────────────

class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    graph = Column(JSONB, nullable=False)                # ReactFlow nodes+edges JSON
    # running, stopped, error
    status = Column(String, default="stopped", index=True)
    schedule_cron = Column(String, nullable=True)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="workflows")
    runs = relationship("WorkflowRun", back_populates="workflow")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    workflow_id = Column(UUID(as_uuid=False), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    # running, completed, failed, cancelled
    status = Column(String, default="running", index=True)
    frames_processed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    workflow = relationship("WorkflowDefinition", back_populates="runs")
    events = relationship("WorkflowEvent", back_populates="run")


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    workflow_run_id = Column(UUID(as_uuid=False), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(String, nullable=False)
    event_type = Column(String, nullable=True)          # detection, count, alert, classification
    data = Column(JSONB, nullable=True)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    run = relationship("WorkflowRun", back_populates="events")


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(UUID(as_uuid=False), ForeignKey("organizations.id"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False, index=True)   # dataset.create, model.deploy, etc.
    resource_type = Column(String, nullable=True)
    resource_id = Column(UUID(as_uuid=False), nullable=True)
    metadata = Column(JSONB, nullable=True)
    ip_address = Column(INET, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
