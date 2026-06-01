from __future__ import annotations

from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
XML_FILE = DATA_DIR / "Result.xml"

# 这里按“页面显示顺序”配置五张图片。
# txt温度矩阵文件名和jpg同名时会自动绑定；没有txt时，前端只显示原始jpg预览。
IMAGE_FILES = [
    "2024-07-01-08-30-34.jpg",
    "2024-07-01-08-30-43.jpg",
    "2024-07-01-08-30-54.jpg",
    "2024-07-01-08-31-19.jpg",
    "2024-07-01-08-31-50.jpg",
]

app = FastAPI(title="人体红外热成像伪彩渲染系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(DATA_DIR)), name="static")


def _read_xml() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not XML_FILE.exists():
        raise FileNotFoundError(f"缺少XML文件：{XML_FILE}")

    root = ET.parse(XML_FILE).getroot()
    images_node = root.find("images")
    if images_node is None:
        raise ValueError("Result.xml中缺少images节点")

    width = int(images_node.attrib.get("width", 0))
    height = int(images_node.attrib.get("height", 0))

    case_info = {
        "snun": root.attrib.get("snun", ""),
        "username": root.attrib.get("username", ""),
        "age": root.attrib.get("age", ""),
        "gender": root.attrib.get("Gender", ""),
        "doctor": root.attrib.get("doctor", ""),
        "matrixWidth": width,
        "matrixHeight": height,
        "result": (root.findtext("result") or "").strip(),
    }

    image_meta: list[dict[str, Any]] = []
    for idx in range(5):
        node = images_node.find(f"image{idx}")
        rois: list[dict[str, Any]] = []
        status = {}

        if node is not None:
            status_node = node.find("status")
            if status_node is not None:
                status = {
                    "curMin": float(status_node.attrib.get("CurMin", 0)),
                    "curMax": float(status_node.attrib.get("CurMax", 0)),
                    "widthName": status_node.attrib.get("Width", ""),
                    "percentage": status_node.attrib.get("Percentage", ""),
                    "paletteName": status_node.attrib.get("PaletteName", ""),
                }

            rois_node = node.find("rois")
            if rois_node is not None:
                for roi_node in list(rois_node):
                    points = []
                    for pt in roi_node.findall("pt"):
                        points.append({
                            "x": float(pt.attrib.get("x", 0)),
                            "y": float(pt.attrib.get("y", 0)),
                        })
                    rois.append({
                        "name": roi_node.attrib.get("name", ""),
                        "type": roi_node.attrib.get("type", ""),
                        "points": points,
                    })

        jpg_name = IMAGE_FILES[idx]
        txt_name = Path(jpg_name).with_suffix(".txt").name
        matrix_path = DATA_DIR / txt_name

        image_meta.append({
            "id": idx,
            "title": f"图像{idx + 1}",
            "imageFile": jpg_name,
            "imageUrl": f"/static/{jpg_name}",
            "matrixFile": txt_name if matrix_path.exists() else "",
            "hasMatrix": matrix_path.exists(),
            "width": width,
            "height": height,
            "status": status,
            "rois": rois,
        })

    return case_info, image_meta


def _load_matrix(txt_path: Path, width: int, height: int) -> np.ndarray:
    if not txt_path.exists():
        raise HTTPException(status_code=404, detail=f"缺少温度矩阵文件：{txt_path.name}")

    text = txt_path.read_text(encoding="utf-8", errors="ignore")
    # 兼容空格、换行、逗号、制表符分隔。
    arr = np.fromstring(text.replace(",", " "), sep=" ", dtype=np.float32)
    expected = width * height
    if arr.size != expected:
        raise HTTPException(
            status_code=400,
            detail=f"矩阵数量不匹配：{txt_path.name}中有{arr.size}个数，期望{expected}个数",
        )
    return arr.reshape((height, width))


@app.get("/")
def index():
    return {"msg": "Thermal pseudo color system is running"}


@app.get("/api/case")
def get_case():
    case_info, images = _read_xml()
    return {"case": case_info, "images": images}


@app.get("/api/images/{image_id}")
def get_image_data(image_id: int):
    case_info, images = _read_xml()
    if image_id < 0 or image_id >= len(images):
        raise HTTPException(status_code=404, detail="图像编号不存在")

    meta = images[image_id]
    width = int(case_info["matrixWidth"])
    height = int(case_info["matrixHeight"])

    if not meta["hasMatrix"]:
        return {
            "meta": meta,
            "matrix": [],
            "dataMin": None,
            "dataMax": None,
            "message": "该图片暂未提供同名txt温度矩阵，前端只能显示原始JPG预览。",
        }

    matrix = _load_matrix(DATA_DIR / meta["matrixFile"], width, height)
    return {
        "meta": meta,
        "matrix": matrix.reshape(-1).round(3).tolist(),
        "dataMin": float(np.min(matrix)),
        "dataMax": float(np.max(matrix)),
    }
