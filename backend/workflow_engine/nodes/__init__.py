from .base_node import BaseNode, NodeOutput  # noqa: F401
from .input_nodes import CameraCapture, RTSPStream, VideoFile, WebSocketFrameSource  # noqa: F401
from .vision_nodes import DetectObjects, ClassifyImage, TrackObjects, CountObjects, ExtractROI, DrawAnnotations  # noqa: F401
from .logic_nodes import FilterByClass, FilterByConfidence, Conditional, Throttle, Aggregate  # noqa: F401
from .output_nodes import LiveDashboard, SaveToDB, TriggerAlert, ExportCSV, RobotOutput  # noqa: F401

NODE_REGISTRY: dict[str, type[BaseNode]] = {
    "CameraCapture": CameraCapture,
    "RTSPStream": RTSPStream,
    "VideoFile": VideoFile,
    "WebSocketFrameSource": WebSocketFrameSource,
    "DetectObjects": DetectObjects,
    "ClassifyImage": ClassifyImage,
    "TrackObjects": TrackObjects,
    "CountObjects": CountObjects,
    "ExtractROI": ExtractROI,
    "DrawAnnotations": DrawAnnotations,
    "FilterByClass": FilterByClass,
    "FilterByConfidence": FilterByConfidence,
    "Conditional": Conditional,
    "Throttle": Throttle,
    "Aggregate": Aggregate,
    "LiveDashboard": LiveDashboard,
    "SaveToDB": SaveToDB,
    "TriggerAlert": TriggerAlert,
    "ExportCSV": ExportCSV,
    "RobotOutput": RobotOutput,
}
