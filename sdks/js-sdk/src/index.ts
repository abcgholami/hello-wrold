/**
 * VisionForge JavaScript SDK
 *
 * Usage:
 *   import { VisionForgeClient } from '@visionforge/sdk';
 *
 *   const client = new VisionForgeClient({
 *     baseUrl: 'https://your-platform.com',
 *     apiKey: 'vf_...',
 *   });
 *
 *   // Run inference
 *   const result = await client.predict('endpoint-id', imageBlob);
 *   console.log(result.predictions);
 */

import axios, { AxiosInstance } from 'axios';

export interface Prediction {
  class_id: number;
  class_name: string;
  confidence: number;
  bbox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

export interface PredictResult {
  predictions: Prediction[];
  inference_time_ms: number;
  model_version_id: string;
  endpoint_id: string;
}

export interface Project {
  id: string;
  name: string;
  task_type: string;
  description: string | null;
  org_id: string;
  created_at: string;
}

export interface VisionForgeClientOptions {
  baseUrl: string;
  apiKey?: string;
  accessToken?: string;
  timeout?: number;
}

export class VisionForgeClient {
  private coreHttp: AxiosInstance;
  private inferHttp: AxiosInstance;
  private trainHttp: AxiosInstance;

  constructor(options: VisionForgeClientOptions) {
    const { baseUrl, apiKey, accessToken, timeout = 60000 } = options;

    const authHeaders = apiKey
      ? { Authorization: `Bearer ${apiKey}` }
      : accessToken
      ? { Authorization: `Bearer ${accessToken}` }
      : {};

    const commonConfig = {
      timeout,
      headers: { ...authHeaders, Accept: 'application/json' },
    };

    this.coreHttp = axios.create({ baseURL: `${baseUrl}/api/core`, ...commonConfig });
    this.inferHttp = axios.create({ baseURL: `${baseUrl}/api/infer`, ...commonConfig });
    this.trainHttp = axios.create({ baseURL: `${baseUrl}/api/train`, ...commonConfig });
  }

  // ── Auth ──────────────────────────────────────────────────────────────────

  async login(email: string, password: string): Promise<{ access_token: string; user_id: string }> {
    const res = await this.coreHttp.post('/auth/login', { email, password });
    const token = res.data.access_token;
    this.coreHttp.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    this.inferHttp.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    this.trainHttp.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    return res.data;
  }

  // ── Projects ──────────────────────────────────────────────────────────────

  async listProjects(orgId = 'default'): Promise<Project[]> {
    const res = await this.coreHttp.get('/projects', { params: { org_id: orgId } });
    return res.data;
  }

  async getProject(projectId: string): Promise<Project> {
    const res = await this.coreHttp.get(`/projects/${projectId}`);
    return res.data;
  }

  async createProject(name: string, taskType: string, orgId = 'default', description = ''): Promise<Project> {
    const res = await this.coreHttp.post('/projects', {
      name, task_type: taskType, org_id: orgId, description,
    });
    return res.data;
  }

  // ── Inference ─────────────────────────────────────────────────────────────

  /**
   * Run inference on an image using a deployed endpoint.
   * @param endpointId The inference endpoint ID
   * @param image Image as Blob, File, or ArrayBuffer
   * @param options Optional confidence/IOU thresholds
   */
  async predict(
    endpointId: string,
    image: Blob | File | ArrayBuffer,
    options: { confidenceThreshold?: number; iouThreshold?: number } = {},
  ): Promise<PredictResult> {
    const formData = new FormData();

    if (image instanceof ArrayBuffer) {
      formData.append('file', new Blob([image], { type: 'image/jpeg' }), 'image.jpg');
    } else {
      formData.append('file', image, (image as File).name || 'image.jpg');
    }

    const params: Record<string, number> = {};
    if (options.confidenceThreshold !== undefined) params.confidence_threshold = options.confidenceThreshold;
    if (options.iouThreshold !== undefined) params.iou_threshold = options.iouThreshold;

    const res = await this.inferHttp.post(`/predict/${endpointId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params,
    });
    return res.data;
  }

  /**
   * Run inference using WebSocket for real-time streaming.
   * @param endpointId The inference endpoint ID
   * @param wsUrl WebSocket server URL
   * @param onResult Callback for each prediction result
   */
  createStreamSession(
    endpointId: string,
    wsUrl: string,
    onResult: (result: { frame_number: number; predictions: Prediction[]; inference_ms: number }) => void,
    onError?: (error: Event) => void,
  ): { send: (imageBase64: string) => void; close: () => void } {
    const ws = new WebSocket(`${wsUrl}/ws/stream/${endpointId}`);

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'prediction') {
        onResult(data);
      }
    };

    if (onError) ws.onerror = onError;

    return {
      send: (imageBase64: string) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ frame: imageBase64 }));
        }
      },
      close: () => ws.close(),
    };
  }

  // ── Training ──────────────────────────────────────────────────────────────

  async listModelVersions(projectId: string) {
    const res = await this.trainHttp.get('/model-versions', { params: { project_id: projectId } });
    return res.data;
  }

  async createTrainingJob(data: {
    projectId: string;
    datasetVersionId: string;
    taskType: string;
    architecture: string;
    preset?: string;
  }) {
    const res = await this.trainHttp.post('/training-jobs', {
      project_id: data.projectId,
      dataset_version_id: data.datasetVersionId,
      task_type: data.taskType,
      architecture: data.architecture,
      preset: data.preset || 'balanced',
    });
    return res.data;
  }

  // ── Utility ───────────────────────────────────────────────────────────────

  /**
   * Draw bounding box predictions on an HTMLCanvasElement.
   */
  static drawPredictions(
    canvas: HTMLCanvasElement,
    predictions: Prediction[],
    options: { lineWidth?: number; fontSize?: number; colors?: string[] } = {},
  ): void {
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { lineWidth = 2, fontSize = 14, colors = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7'] } = options;

    ctx.lineWidth = lineWidth;
    ctx.font = `${fontSize}px Inter, sans-serif`;

    predictions.forEach((pred, idx) => {
      const color = colors[pred.class_id % colors.length];
      const { x, y, width, height } = pred.bbox;

      // Scale from normalized to pixel coords
      const px = x * canvas.width;
      const py = y * canvas.height;
      const pw = width * canvas.width;
      const ph = height * canvas.height;

      ctx.strokeStyle = color;
      ctx.strokeRect(px, py, pw, ph);

      const label = `${pred.class_name} ${(pred.confidence * 100).toFixed(0)}%`;
      const textWidth = ctx.measureText(label).width;
      ctx.fillStyle = color;
      ctx.fillRect(px - 1, py - fontSize - 4, textWidth + 8, fontSize + 4);
      ctx.fillStyle = '#fff';
      ctx.fillText(label, px + 3, py - 3);
    });
  }
}

export default VisionForgeClient;
