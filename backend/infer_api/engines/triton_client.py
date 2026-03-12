"""Triton Inference Server gRPC/HTTP client wrapper."""
from __future__ import annotations

import numpy as np

try:
    import tritonclient.http as httpclient
    import tritonclient.grpc as grpcclient
    TRITON_AVAILABLE = True
except ImportError:
    TRITON_AVAILABLE = False


class TritonEngine:
    """Send inference requests to a Triton Inference Server.

    Supports HTTP and gRPC transports. Model must be pre-loaded in Triton
    with the appropriate backend (onnxruntime, tensorrt, pytorch_libtorch).
    """

    def __init__(
        self,
        server_url: str = "localhost:8000",
        model_name: str = "yolov8n",
        model_version: str = "1",
        protocol: str = "http",
    ) -> None:
        if not TRITON_AVAILABLE:
            raise RuntimeError(
                "tritonclient is not installed. Install with: pip install tritonclient[http,grpc]"
            )
        self.model_name = model_name
        self.model_version = model_version
        self.protocol = protocol

        if protocol == "grpc":
            self.client = grpcclient.InferenceServerClient(url=server_url)
        else:
            self.client = httpclient.InferenceServerClient(url=server_url)

        # Fetch model metadata once at init
        self.metadata = self.client.get_model_metadata(model_name, model_version)

    # ------------------------------------------------------------------
    def _make_input(self, tensor: np.ndarray, name: str = "images") -> Any:
        if self.protocol == "grpc":
            infer_input = grpcclient.InferInput(name, tensor.shape, "FP32")
        else:
            infer_input = httpclient.InferInput(name, tensor.shape, "FP32")
        infer_input.set_data_from_numpy(tensor)
        return infer_input

    # ------------------------------------------------------------------
    def predict_raw(self, tensor: np.ndarray) -> list[np.ndarray]:
        """Send preprocessed NCHW float32 tensor; return list of raw output arrays."""
        infer_inputs = [self._make_input(tensor)]
        response = self.client.infer(
            model_name=self.model_name,
            model_version=self.model_version,
            inputs=infer_inputs,
        )
        outputs = []
        for output in self.metadata.outputs:
            outputs.append(response.as_numpy(output.name))
        return outputs
