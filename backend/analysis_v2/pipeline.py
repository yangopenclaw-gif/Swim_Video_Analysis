import logging
import os
from typing import List, Optional, Callable, Dict, Any

from .audio_detector import AudioDetector
from .swimmer_detector import SwimmerDetector
from .pose_estimator import PoseEstimator
from .metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)

ANALYSIS_VERSION = "3.0.0"


def _format_race_time(seconds: float) -> str:
    if seconds < 0:
        return "0.00秒"
    if seconds < 60:
        return f"{seconds:.2f}秒"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}分{s:05.2f}秒"


class AnalysisPipeline:
    VERSION = ANALYSIS_VERSION

    def __init__(
        self,
        pool_length: int = 50,
        race_distance: int = 100,
        swimmer_position: int = 1,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ):
        self.pool_length = pool_length
        self.race_distance = race_distance
        self.swimmer_position = swimmer_position
        self.progress_callback = progress_callback

        self.audio_detector = AudioDetector()
        self.swimmer_detector = SwimmerDetector(swimmer_position=swimmer_position)
        self.pose_estimator = PoseEstimator()
        self.metrics_calculator = MetricsCalculator(
            pool_length=pool_length,
            race_distance=race_distance,
            swimmer_position=swimmer_position,
        )

    def _report(self, percent: int, message: str):
        if self.progress_callback:
            self.progress_callback(percent, message)

    def analyze(self, video_path: str, analysis_options: List[str]) -> Dict[str, Any]:
        logger.info(f"[v{self.VERSION}] Starting analysis: {video_path}")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / fps
        cap.release()

        self._report(0, "阶段1/4：检测出发信号...")
        audio_result = self.audio_detector.detect_start_signal(video_path)
        signal_time = audio_result.get("signal_time")
        signal_type = audio_result.get("signal_type")
        signal_conf = audio_result.get("confidence", 0.0)
        logger.info(f"Audio: signal_time={signal_time}, type={signal_type}, conf={signal_conf}")

        self._report(5, "阶段2/4：MediaPipe检测泳者+姿态估计...")
        detection_results = self.swimmer_detector.detect_and_track(
            video_path,
            progress_callback=lambda p, m: self._report(5 + int(p * 0.50), m),
        )
        max_persons = 0
        for d in detection_results:
            np_val = d.get("num_persons", 0)
            max_persons = max(max_persons, np_val)
        valid_poses = sum(1 for d in detection_results if d.get("landmarks") is not None)
        logger.info(f"Detection+Pose: {len(detection_results)} frames, max_persons={max_persons}, with_landmarks={valid_poses}")

        self._report(55, "阶段3/4：补充姿态估计...")
        pose_results = self.pose_estimator.estimate_from_video(
            video_path,
            detection_results,
            progress_callback=lambda p, m: self._report(55 + int(p * 0.10), m),
        )
        valid_poses_after = sum(1 for d in pose_results if d.get("landmarks") is not None)
        logger.info(f"After refinement: {valid_poses_after} frames with landmarks")

        self._report(65, "阶段4/4：计算分析指标...")
        metrics = self.metrics_calculator.calculate_all(
            pose_frames=pose_results,
            audio_signal_time=signal_time,
            video_duration=video_duration,
            analysis_options=analysis_options,
        )

        result = dict(metrics)
        result["_meta"] = {
            "analysis_version": self.VERSION,
            "max_persons_detected": max_persons,
            "swimmer_position": self.swimmer_position,
            "video_duration": round(video_duration, 2),
            "audio_signal_time": signal_time,
            "audio_signal_type": signal_type,
            "audio_confidence": round(signal_conf, 2),
            "detection_frames": len(detection_results),
            "pose_frames": valid_poses_after,
        }

        self._report(100, "分析完成")
        logger.info(f"[v{self.VERSION}] Analysis complete: {len(metrics)} metrics")
        return result
