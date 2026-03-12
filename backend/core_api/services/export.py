"""
Dataset export service.
Generates COCO JSON, YOLO TXT, Pascal VOC XML, TFRecord, CreateML JSON, CSV.
"""
import io
import json
import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from shared.db.models import DatasetVersion, DatasetVersionImage, Image, Annotation, LabelClass


async def export_dataset_version(
    version_id: str,
    fmt: str,
    db: AsyncSession,
    output_dir: str,
) -> str:
    """
    Export dataset version to given format. Returns path to generated zip file.
    fmt: 'coco', 'yolo', 'voc', 'createml', 'csv'
    """
    # Load version + images + annotations
    result = await db.execute(
        select(DatasetVersion)
        .where(DatasetVersion.id == version_id)
        .options(
            selectinload(DatasetVersion.version_images)
            .selectinload(DatasetVersionImage.image)
            .selectinload(Image.annotations)
            .selectinload(Annotation.label_class)
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise ValueError(f"DatasetVersion {version_id} not found")

    zip_path = os.path.join(output_dir, f"dataset_v{version.version_number}_{fmt}.zip")
    os.makedirs(output_dir, exist_ok=True)

    if fmt == "coco":
        _export_coco(version, zip_path)
    elif fmt == "yolo":
        _export_yolo(version, zip_path)
    elif fmt == "voc":
        _export_voc(version, zip_path)
    elif fmt == "createml":
        _export_createml(version, zip_path)
    elif fmt == "csv":
        _export_csv(version, zip_path)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")

    return zip_path


def _get_label_map(version: DatasetVersion) -> dict:
    """Build {label_class_id: {name, coco_id}} map."""
    classes = {}
    coco_id = 1
    for vi in version.version_images:
        for ann in vi.image.annotations:
            if ann.label_class and ann.label_class.id not in classes:
                classes[ann.label_class.id] = {
                    "id": coco_id,
                    "name": ann.label_class.name,
                    "color": ann.label_class.color,
                }
                coco_id += 1
    return classes


def _export_coco(version: DatasetVersion, zip_path: str):
    splits = {"train": [], "val": [], "test": []}
    for vi in version.version_images:
        splits[vi.split].append(vi)

    label_map = _get_label_map(version)
    categories = [
        {"id": v["id"], "name": v["name"], "supercategory": "object"}
        for v in label_map.values()
    ]

    with zipfile.ZipFile(zip_path, "w") as zf:
        for split_name, items in splits.items():
            if not items:
                continue
            images_coco, annotations_coco = [], []
            ann_id = 1
            for idx, vi in enumerate(items, 1):
                img = vi.image
                images_coco.append({
                    "id": idx, "file_name": img.filename,
                    "width": img.width or 0, "height": img.height or 0,
                })
                for ann in img.annotations:
                    if ann.annotation_type == "classification":
                        continue
                    coco_ann: dict = {
                        "id": ann_id, "image_id": idx,
                        "category_id": label_map.get(ann.label_class_id, {}).get("id", 0),
                        "iscrowd": 0,
                    }
                    if ann.annotation_type in ("bbox",):
                        w = img.width or 1
                        h = img.height or 1
                        x = ann.bbox_x * w
                        y = ann.bbox_y * h
                        bw = ann.bbox_w * w
                        bh = ann.bbox_h * h
                        coco_ann["bbox"] = [x, y, bw, bh]
                        coco_ann["area"] = bw * bh
                    if ann.segmentation:
                        coco_ann["segmentation"] = ann.segmentation
                    annotations_coco.append(coco_ann)
                    ann_id += 1

            coco_data = {
                "images": images_coco,
                "annotations": annotations_coco,
                "categories": categories,
            }
            zf.writestr(
                f"annotations/instances_{split_name}.json",
                json.dumps(coco_data, indent=2),
            )


def _export_yolo(version: DatasetVersion, zip_path: str):
    label_map = _get_label_map(version)
    # Build sorted class list by coco_id
    classes = sorted(label_map.values(), key=lambda x: x["id"])
    class_names = [c["name"] for c in classes]
    id_to_idx = {v["id"]: i for i, v in enumerate(classes)}

    data_yaml = {
        "names": class_names,
        "nc": len(class_names),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
    }

    with zipfile.ZipFile(zip_path, "w") as zf:
        import yaml
        zf.writestr("data.yaml", yaml.dump(data_yaml))
        for vi in version.version_images:
            img = vi.image
            split = vi.split
            img_w = img.width or 1
            img_h = img.height or 1

            lines = []
            for ann in img.annotations:
                if ann.annotation_type == "classification":
                    continue
                if ann.label_class_id not in label_map:
                    continue
                coco_id = label_map[ann.label_class_id]["id"]
                cls_idx = id_to_idx[coco_id]
                cx = ann.bbox_x + ann.bbox_w / 2
                cy = ann.bbox_y + ann.bbox_h / 2
                lines.append(f"{cls_idx} {cx:.6f} {cy:.6f} {ann.bbox_w:.6f} {ann.bbox_h:.6f}")

            stem = Path(img.filename).stem
            zf.writestr(f"labels/{split}/{stem}.txt", "\n".join(lines))


def _export_voc(version: DatasetVersion, zip_path: str):
    with zipfile.ZipFile(zip_path, "w") as zf:
        for vi in version.version_images:
            img = vi.image
            img_w = img.width or 1
            img_h = img.height or 1
            root = ET.Element("annotation")
            ET.SubElement(root, "filename").text = img.filename
            size_el = ET.SubElement(root, "size")
            ET.SubElement(size_el, "width").text = str(img_w)
            ET.SubElement(size_el, "height").text = str(img_h)
            ET.SubElement(size_el, "depth").text = "3"

            for ann in img.annotations:
                if ann.annotation_type != "bbox" or not ann.label_class:
                    continue
                obj = ET.SubElement(root, "object")
                ET.SubElement(obj, "name").text = ann.label_class.name
                ET.SubElement(obj, "difficult").text = "0"
                bndbox = ET.SubElement(obj, "bndbox")
                ET.SubElement(bndbox, "xmin").text = str(int(ann.bbox_x * img_w))
                ET.SubElement(bndbox, "ymin").text = str(int(ann.bbox_y * img_h))
                ET.SubElement(bndbox, "xmax").text = str(int((ann.bbox_x + ann.bbox_w) * img_w))
                ET.SubElement(bndbox, "ymax").text = str(int((ann.bbox_y + ann.bbox_h) * img_h))

            stem = Path(img.filename).stem
            zf.writestr(f"Annotations/{stem}.xml", ET.tostring(root, encoding="unicode"))


def _export_createml(version: DatasetVersion, zip_path: str):
    data: list = []
    for vi in version.version_images:
        img = vi.image
        img_w = img.width or 1
        img_h = img.height or 1
        anns = []
        for ann in img.annotations:
            if ann.annotation_type != "bbox" or not ann.label_class:
                continue
            cx = (ann.bbox_x + ann.bbox_w / 2) * img_w
            cy = (ann.bbox_y + ann.bbox_h / 2) * img_h
            anns.append({
                "label": ann.label_class.name,
                "coordinates": {
                    "x": round(cx, 2), "y": round(cy, 2),
                    "width": round(ann.bbox_w * img_w, 2),
                    "height": round(ann.bbox_h * img_h, 2),
                },
            })
        data.append({"image": img.filename, "annotations": anns})

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("annotations.json", json.dumps(data, indent=2))


def _export_csv(version: DatasetVersion, zip_path: str):
    rows = ["image_filename,x_min,y_min,x_max,y_max,class_name,split"]
    for vi in version.version_images:
        img = vi.image
        img_w = img.width or 1
        img_h = img.height or 1
        for ann in img.annotations:
            if ann.annotation_type != "bbox" or not ann.label_class:
                continue
            x1 = int(ann.bbox_x * img_w)
            y1 = int(ann.bbox_y * img_h)
            x2 = int((ann.bbox_x + ann.bbox_w) * img_w)
            y2 = int((ann.bbox_y + ann.bbox_h) * img_h)
            rows.append(f"{img.filename},{x1},{y1},{x2},{y2},{ann.label_class.name},{vi.split}")

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("annotations.csv", "\n".join(rows))
