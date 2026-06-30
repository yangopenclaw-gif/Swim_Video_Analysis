import logging
import os
import numpy as np
import cv2
from typing import List, Optional, Dict, Any

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

KEY_NAMES = [
    "nose", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
    "left_heel", "right_heel",
]

KEY_INDICES = [
    NOSE, LEFT_EAR, RIGHT_EAR,
    LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_ELBOW, RIGHT_ELBOW,
    LEFT_WRIST, RIGHT_WRIST,
    LEFT_HIP, RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE,
    LEFT_HEEL, RIGHT_HEEL,
]


class SwimmerDetector:
    VERSION = "3.3.0"

    def __init__(self, swimmer_position: int = 1):
        self.swimmer_position = max(1, min(swimmer_position, 9))
        self.mp_landmarker = None
        self._init_mediapipe()

    def _init_mediapipe(self):
        try:
            from mediapipe.tasks.python import vision
            from mediapipe.tasks.python.core import base_options

            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "models", "pose_landmarker_heavy.task"
            )
            if not os.path.exists(model_path):
                logger.error(f"MediaPipe model not found: {model_path}")
                return

            options = vision.PoseLandmarkerOptions(
                base_options=base_options.BaseOptions(model_asset_path=model_path),
                running_mode=vision.RunningMode.VIDEO,
                num_poses=4,
                min_pose_detection_confidence=0.2,
                min_pose_presence_confidence=0.2,
                min_tracking_confidence=0.2,
                output_segmentation_masks=False,
            )
            self.mp_landmarker = vision.PoseLandmarker.create_from_options(options)
            logger.info("MediaPipe multi-pose landmarker initialized (num_poses=4, VIDEO mode, conf=0.2)")
        except Exception as e:
            logger.error(f"MediaPipe init failed: {e}")
            self.mp_landmarker = None

    def detect_and_track(self, video_path: str, progress_callback=None) -> List[Dict[str, Any]]:
        if self.mp_landmarker is None:
            logger.warning("MediaPipe not available, using fallback")
            return self._fallback_detect(video_path, progress_callback)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_rate = max(1, int(fps / 15))
        total_sampled = total_frames // sample_rate

        frame_persons = []
        frame_idx = 0
        processed = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_rate == 0:
                ts = frame_idx / fps
                ts_ms = int(frame_idx * 1000 / fps)
                persons = self._detect_poses_in_frame_video(frame, ts_ms)
                frame_persons.append((frame_idx, ts, persons))
                processed += 1
                if processed % 15 == 0 and progress_callback:
                    pct = int(55 * processed / max(total_sampled, 1))
                    progress_callback(min(pct, 55), f"检测泳者+姿态 {processed}/{total_sampled}...")

            frame_idx += 1

        cap.release()

        max_persons = max((len(p) for _, _, p in frame_persons), default=0)
        total_with_lm = sum(1 for _, _, persons in frame_persons for p in persons if p.get("landmarks"))
        logger.info(f"MediaPipe VIDEO: {len(frame_persons)} frames, max_persons={max_persons}, total_persons_with_lm={total_with_lm}")

        results = self._select_target_swimmer(frame_persons)
        results = self._filter_outliers(results)
        return results

    def _detect_poses_in_frame_video(self, frame: np.ndarray, ts_ms: int) -> List[Dict]:
        if self.mp_landmarker is None:
            return []

        try:
            from mediapipe import Image, ImageFormat
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = Image(image_format=ImageFormat.SRGB, data=rgb)
            result = self.mp_landmarker.detect_for_video(mp_image, ts_ms)

            persons = []
            if result.pose_landmarks:
                for landmarks in result.pose_landmarks:
                    person = self._extract_person_data(landmarks)
                    if person is not None:
                        persons.append(person)

            persons.sort(key=lambda p: p["center_x"])
            return persons
        except Exception as e:
            logger.debug(f"Pose detection failed at ts_ms={ts_ms}: {e}")
            return []

    def _extract_person_data(self, landmarks) -> Optional[Dict]:
        left_hip = landmarks[LEFT_HIP]
        right_hip = landmarks[RIGHT_HIP]

        avg_vis = (left_hip.visibility + right_hip.visibility) / 2
        if avg_vis < 0.15:
            return None

        mid_x = (left_hip.x + right_hip.x) / 2
        mid_y = (left_hip.y + right_hip.y) / 2

        visible_xs = [lm.x for lm in landmarks if lm.visibility > 0.15]
        visible_ys = [lm.y for lm in landmarks if lm.visibility > 0.15]

        bbox = None
        if visible_xs and visible_ys:
            bbox = [min(visible_xs), min(visible_ys), max(visible_xs), max(visible_ys)]

        key_landmarks = {}
        for name, idx in zip(KEY_NAMES, KEY_INDICES):
            if idx < len(landmarks):
                lm = landmarks[idx]
                key_landmarks[name] = np.array([lm.x, lm.y, lm.z, lm.visibility])

        return {
            "center_x": mid_x,
            "center_y": mid_y,
            "bbox": bbox,
            "landmarks": key_landmarks,
            "hip_vis": avg_vis,
        }

    def _select_target_swimmer(self, frame_persons) -> List[Dict[str, Any]]:
        results = []
        for frame_idx, ts, persons in frame_persons:
            if not persons:
                results.append({
                    "timestamp": ts, "frame_idx": frame_idx,
                    "bbox": None, "landmarks": None, "num_persons": 0,
                })
                continue

            if len(persons) >= 2:
                sorted_ps = sorted(persons, key=lambda p: p["center_x"])
                idx = min(self.swimmer_position - 1, len(sorted_ps) - 1)
                target = sorted_ps[idx]
            else:
                target = persons[0]

            results.append({
                "timestamp": ts, "frame_idx": frame_idx,
                "bbox": target["bbox"], "landmarks": target["landmarks"],
                "num_persons": len(persons),
                "center_x": target["center_x"], "center_y": target["center_y"],
            })

        return results

    def _filter_outliers(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        valid = [(i, r) for i, r in enumerate(results) if r.get("landmarks") is not None]
        if len(valid) < 5:
            return results

        positions = []
        for i, r in valid:
            lm = r["landmarks"]
            lh = lm.get("left_hip")
            rh = lm.get("right_hip")
            if lh is not None and rh is not None:
                mid_x = (lh[0] + rh[0]) / 2
                mid_y = (lh[1] + rh[1]) / 2
                positions.append((i, mid_x, mid_y))

        if len(positions) < 5:
            return results

        outlier_indices = set()

        for k in range(1, len(positions)):
            i_prev, px, py = positions[k - 1]
            i_curr, cx, cy = positions[k]

            dt = results[i_curr]["timestamp"] - results[i_prev]["timestamp"]
            if dt <= 0:
                continue

            dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
            speed = dist / dt

            if speed > 2.0:
                outlier_indices.add(i_curr)

        for i in outlier_indices:
            results[i]["landmarks"] = None

        if outlier_indices:
            logger.info(f"Filtered {len(outlier_indices)} outlier frames out of {len(valid)}")

        return results

    def _fallback_detect(self, video_path: str, progress_callback=None) -> List[Dict[str, Any]]:
        logger.warning("Using fallback detection (no pose estimation)")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_rate = max(1, int(fps / 15))

        results = []
        frame_idx = 0
        processed = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_rate == 0:
                ts = frame_idx / fps
                results.append({
                    "timestamp": ts,
                    "frame_idx": frame_idx,
                    "bbox": None,
                    "landmarks": None,
                    "num_persons": 0,
                })
                processed += 1
                if processed % 30 == 0 and progress_callback:
                    pct = int(55 * processed / max(total_frames // sample_rate, 1))
                    progress_callback(min(pct, 55), f"帧采样 {processed}...")

            frame_idx += 1

        cap.release()
        return results

    def crop_swimmer(self, frame: np.ndarray, bbox: List[float], padding: float = 0.15) -> np.ndarray:
        if bbox is None:
            return frame
        h, w = frame.shape[:2]
        if isinstance(bbox, list) and len(bbox) == 4:
            if bbox[0] <= 1.0 and bbox[2] <= 1.0:
                x1, y1 = int(bbox[0] * w * (1 - padding)), int(bbox[1] * h * (1 - padding))
                x2, y2 = int(bbox[2] * w * (1 + padding)), int(bbox[3] * h * (1 + padding))
            else:
                x1 = max(0, int(bbox[0] - bbox[2] * padding))
                y1 = max(0, int(bbox[1] - bbox[3] * padding))
                x2 = min(w, int(bbox[2] + bbox[2] * padding))
                y2 = min(h, int(bbox[3] + bbox[3] * padding))
            return frame[y1:y2, x1:x2]
        return frame
