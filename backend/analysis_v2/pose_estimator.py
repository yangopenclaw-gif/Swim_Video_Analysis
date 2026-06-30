import logging
import numpy as np
import cv2
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

NOSE = 0
LEFT_EAR = 7
RIGHT_EAR = 8
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28
LEFT_HEEL = 29
RIGHT_HEEL = 30


class PoseEstimator:
    VERSION = "3.0.0"

    def __init__(self):
        self.mp_landmarker = None
        self._init_mediapipe()

    def _init_mediapipe(self):
        try:
            from mediapipe.tasks.python import vision
            from mediapipe.tasks.python.core import base_options
            import os

            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "models", "pose_landmarker_heavy.task"
            )
            if not os.path.exists(model_path):
                logger.error(f"MediaPipe model not found: {model_path}")
                return

            options = vision.PoseLandmarkerOptions(
                base_options=base_options.BaseOptions(model_asset_path=model_path),
                running_mode=vision.RunningMode.IMAGE,
                min_pose_detection_confidence=0.4,
                min_pose_presence_confidence=0.4,
                num_poses=1,
                output_segmentation_masks=False,
            )
            self.mp_landmarker = vision.PoseLandmarker.create_from_options(options)
            logger.info("MediaPipe PoseLandmarker initialized (IMAGE mode, for refinement)")
        except Exception as e:
            logger.error(f"MediaPipe init failed: {e}")
            self.mp_landmarker = None

    def estimate_from_video(
        self,
        video_path: str,
        detection_results: List[Dict[str, Any]],
        progress_callback=None,
    ) -> List[Dict[str, Any]]:
        results = []
        frames_with_landmarks = 0
        frames_without_landmarks = 0

        for det in detection_results:
            if det.get("landmarks") is not None:
                results.append(det)
                frames_with_landmarks += 1
            else:
                frames_without_landmarks += 1
                results.append(det)

        logger.info(f"PoseEstimator: {frames_with_landmarks} frames already have landmarks, "
                     f"{frames_without_landmarks} without")

        if frames_without_landmarks > 0 and self.mp_landmarker is not None:
            candidates = [(i, det) for i, det in enumerate(results)
                          if det.get("landmarks") is None and det.get("frame_idx") is not None]
            max_refine = 200
            if len(candidates) > max_refine:
                step = len(candidates) / max_refine
                candidates = [candidates[int(j * step)] for j in range(max_refine)]

            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                refined = 0

                for idx, (i, det) in enumerate(candidates):
                    frame_idx = det.get("frame_idx")

                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    if not ret:
                        continue

                    bbox = det.get("bbox")
                    if bbox is not None:
                        cropped = self._crop_with_bbox(frame, bbox)
                    else:
                        cropped = frame

                    landmarks = self._estimate_frame(cropped, frame_idx, fps)
                    if landmarks is not None:
                        det["landmarks"] = landmarks
                        refined += 1

                    if refined % 20 == 0 and progress_callback:
                        pct = 30 + int(25 * idx / max(len(candidates), 1))
                        progress_callback(min(pct, 55), f"补充姿态估计 {refined}/{len(candidates)}...")

                cap.release()
                logger.info(f"Refined {refined} additional frames with landmarks")

        return results

    def _crop_with_bbox(self, frame: np.ndarray, bbox, padding: float = 0.1) -> np.ndarray:
        h, w = frame.shape[:2]
        if isinstance(bbox, list) and len(bbox) == 4:
            if bbox[0] <= 1.0 and bbox[2] <= 1.0:
                x1, y1 = int(bbox[0] * w), int(bbox[1] * h)
                x2, y2 = int(bbox[2] * w), int(bbox[3] * h)
            else:
                x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        else:
            return frame

        bw = x2 - x1
        bh = y2 - y1
        pad_w = int(bw * padding)
        pad_h = int(bh * padding)
        x1 = max(0, x1 - pad_w)
        y1 = max(0, y1 - pad_h)
        x2 = min(w, x2 + pad_w)
        y2 = min(h, y2 + pad_h)
        return frame[y1:y2, x1:x2]

    def _estimate_frame(self, frame: np.ndarray, frame_idx: int, fps: float) -> Optional[Dict[str, np.ndarray]]:
        if self.mp_landmarker is None:
            return None

        try:
            from mediapipe import Image, ImageFormat
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = Image(image_format=ImageFormat.SRGB, data=rgb)
            result = self.mp_landmarker.detect(mp_image)

            if result.pose_landmarks and len(result.pose_landmarks) > 0:
                lm = result.pose_landmarks[0]
                landmarks = {}
                key_names = [
                    "nose", "left_ear", "right_ear",
                    "left_shoulder", "right_shoulder",
                    "left_elbow", "right_elbow",
                    "left_wrist", "right_wrist",
                    "left_hip", "right_hip",
                    "left_knee", "right_knee",
                    "left_ankle", "right_ankle",
                    "left_heel", "right_heel",
                ]
                key_indices = [
                    NOSE, LEFT_EAR, RIGHT_EAR,
                    LEFT_SHOULDER, RIGHT_SHOULDER,
                    LEFT_ELBOW, RIGHT_ELBOW,
                    LEFT_WRIST, RIGHT_WRIST,
                    LEFT_HIP, RIGHT_HIP,
                    LEFT_KNEE, RIGHT_KNEE,
                    LEFT_ANKLE, RIGHT_ANKLE,
                    LEFT_HEEL, RIGHT_HEEL,
                ]
                for name, idx in zip(key_names, key_indices):
                    if idx < len(lm):
                        p = lm[idx]
                        landmarks[name] = np.array([p.x, p.y, p.z, p.visibility])
                return landmarks
        except Exception as e:
            logger.debug(f"Pose refinement failed for frame {frame_idx}: {e}")

        return None

    @staticmethod
    def get_landmark(landmarks: Optional[Dict], name: str) -> Optional[np.ndarray]:
        if landmarks is None or name not in landmarks:
            return None
        return landmarks[name][:3]

    @staticmethod
    def midpoint(p1: Optional[np.ndarray], p2: Optional[np.ndarray]) -> Optional[np.ndarray]:
        if p1 is None or p2 is None:
            return None
        return (p1 + p2) / 2.0
