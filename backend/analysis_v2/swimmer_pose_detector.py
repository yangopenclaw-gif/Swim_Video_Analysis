import logging
import gc
from typing import Optional, Dict, Any, List

from .base_module import AnalysisModule
from .shared import AnalysisContext, ModuleResult, AccuracyInfo, RetryRecord

logger = logging.getLogger(__name__)


class SwimmerPoseDetector(AnalysisModule):
    VERSION = "4.1.0"

    @property
    def name(self) -> str:
        return "泳者检测与姿态估计"

    def analyze(self, context: AnalysisContext) -> ModuleResult:
        from .swimmer_detector import SwimmerDetector
        from .pose_estimator import PoseEstimator

        video_path = context.video_path
        params = context.detection_params.pose_estimation
        swimmer_position = context.swimmer_position

        coverage_retry_threshold = params.get("coverage_retry_threshold", 0.3)
        max_coverage_retries = params.get("max_coverage_retries", 3)
        retry_confidence_steps = params.get("retry_confidence_steps", [0.3, 0.2, 0.1])
        retry_yolo_confidence_steps = params.get("retry_yolo_confidence_steps", [0.3, 0.15, 0.15])
        retry_hip_visibility_steps = params.get("retry_hip_visibility_steps", [0.1, 0.1, 0.05])
        aggressive_supplementary_threshold = params.get("aggressive_supplementary_threshold", 0.5)
        aggressive_supplementary_confidence = params.get("aggressive_supplementary_confidence", 0.3)
        aggressive_supplementary_num_poses = params.get("aggressive_supplementary_num_poses", 4)

        detector = SwimmerDetector(swimmer_position=swimmer_position)
        detection_results = detector.detect_and_track(video_path)

        max_persons = 0
        for d in detection_results:
            np_val = d.get("num_persons", 0)
            max_persons = max(max_persons, np_val)

        if detector.mp_landmarker is not None:
            detector.mp_landmarker.close()
            detector.mp_landmarker = None

        estimator = PoseEstimator()
        pose_results = estimator.estimate_from_video(video_path, detection_results)

        valid_poses = sum(1 for d in pose_results if d.get("landmarks") is not None)
        detection_count = len(detection_results)
        del detection_results
        gc.collect()

        if estimator.mp_landmarker is not None:
            estimator.mp_landmarker.close()
            estimator.mp_landmarker = None
            gc.collect()

        if detector.yolo_model is not None:
            del detector.yolo_model
            detector.yolo_model = None
            gc.collect()

        coverage = valid_poses / max(detection_count, 1)

        retry_records: List[RetryRecord] = []
        retry_count = 0
        best_coverage = coverage
        best_pose_results = pose_results
        best_valid_poses = valid_poses

        if coverage < coverage_retry_threshold and max_coverage_retries > 0:
            logger.info(f"Coverage {coverage:.1%} below threshold {coverage_retry_threshold:.1%}, starting retries")

            for attempt in range(min(max_coverage_retries, len(retry_confidence_steps))):
                retry_count += 1
                mp_conf = retry_confidence_steps[attempt]
                yolo_conf = retry_yolo_confidence_steps[attempt] if attempt < len(retry_yolo_confidence_steps) else retry_yolo_confidence_steps[-1]
                hip_vis = retry_hip_visibility_steps[attempt] if attempt < len(retry_hip_visibility_steps) else retry_hip_visibility_steps[-1]

                logger.info(f"Coverage retry {retry_count}/{max_coverage_retries}: mp_conf={mp_conf}, yolo_conf={yolo_conf}, hip_vis={hip_vis}")

                retry_detector = SwimmerDetector(
                    swimmer_position=swimmer_position,
                    mp_confidence=mp_conf,
                    yolo_confidence=yolo_conf,
                    hip_visibility_threshold=hip_vis,
                )
                retry_detection_results = retry_detector.detect_and_track(video_path)

                if retry_detector.mp_landmarker is not None:
                    retry_detector.mp_landmarker.close()
                    retry_detector.mp_landmarker = None

                retry_estimator = PoseEstimator(
                    confidence=mp_conf,
                    num_poses=aggressive_supplementary_num_poses,
                )
                retry_pose_results = retry_estimator.estimate_from_video(video_path, retry_detection_results)

                retry_valid = sum(1 for d in retry_pose_results if d.get("landmarks") is not None)
                retry_coverage = retry_valid / max(len(retry_detection_results), 1)

                if retry_detector.mp_landmarker is not None:
                    retry_estimator.mp_landmarker.close()
                    retry_estimator.mp_landmarker = None
                    gc.collect()

                if retry_detector.yolo_model is not None:
                    del retry_detector.yolo_model
                    retry_detector.yolo_model = None
                    gc.collect()

                del retry_detection_results
                gc.collect()

                retry_records.append(RetryRecord(
                    attempt=retry_count,
                    success=retry_coverage >= coverage_retry_threshold,
                    strategy_name=f"覆盖率重试{retry_count}(mp={mp_conf},yolo={yolo_conf})",
                    result=retry_coverage,
                    confidence=mp_conf,
                ))

                logger.info(f"Retry {retry_count} coverage: {retry_coverage:.1%} (was {best_coverage:.1%})")

                if retry_coverage > best_coverage:
                    best_coverage = retry_coverage
                    best_pose_results = retry_pose_results
                    best_valid_poses = retry_valid
                else:
                    del retry_pose_results
                    gc.collect()

                if retry_coverage >= coverage_retry_threshold:
                    logger.info(f"Retry {retry_count} reached threshold, stopping retries")
                    break

        pose_results = best_pose_results
        coverage = best_coverage
        valid_poses = best_valid_poses

        if coverage < aggressive_supplementary_threshold:
            logger.info(f"Coverage {coverage:.1%} below aggressive threshold {aggressive_supplementary_threshold:.1%}, running aggressive supplementary")
            pose_results = self._aggressive_supplementary_estimation(
                video_path, pose_results, aggressive_supplementary_confidence, aggressive_supplementary_num_poses
            )
            valid_poses = sum(1 for d in pose_results if d.get("landmarks") is not None)
            coverage = valid_poses / max(detection_count, 1)

        metrics = {
            "检测帧数": detection_count,
            "有效姿态帧数": valid_poses,
            "关键点覆盖率": f"{coverage * 100:.1f}%",
            "最大检测人数": max_persons,
            "分析泳者位置": swimmer_position,
            "覆盖率重试次数": retry_count,
        }
        if retry_count > 0:
            metrics["重试后覆盖率"] = f"{coverage * 100:.1f}%"

        warnings = []
        if coverage < 0.3:
            if retry_count > 0:
                warnings.append(f"低覆盖率（已重试{retry_count}次）")
            else:
                warnings.append("关键点覆盖率低")
        if coverage < 0.05:
            warnings.append("极低覆盖率（已重试3次）" if retry_count >= 3 else "极低覆盖率")

        accuracy = AccuracyInfo(
            confidence=min(coverage * 1.2, 1.0),
            coverage=round(coverage, 3),
            quality="高" if coverage >= 0.7 else ("中" if coverage >= 0.4 else "低"),
            low_confidence=coverage < 0.3,
            warnings=warnings,
        )

        module_result = ModuleResult(
            module_name=self.name,
            metrics=metrics,
            module_events={},
            accuracy=accuracy,
            retry_records=retry_records,
            detection_method="MediaPipe+YOLOv8逐帧全量" + (f"+覆盖率重试{retry_count}次" if retry_count > 0 else ""),
        )
        module_result._pose_frames = tuple(pose_results)
        return module_result

    def _aggressive_supplementary_estimation(
        self,
        video_path: str,
        pose_results: List[Dict[str, Any]],
        confidence: float,
        num_poses: int,
    ) -> List[Dict[str, Any]]:
        from .pose_estimator import PoseEstimator
        import cv2

        missing_indices = [i for i, d in enumerate(pose_results) if d.get("landmarks") is None]
        if not missing_indices:
            return pose_results

        logger.info(f"Aggressive supplementary: {len(missing_indices)} missing frames, confidence={confidence}, num_poses={num_poses}")

        aggressive_estimator = PoseEstimator(confidence=confidence, num_poses=num_poses)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            if aggressive_estimator.mp_landmarker is not None:
                aggressive_estimator.mp_landmarker.close()
            return pose_results

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        refined = 0

        for idx in missing_indices:
            det = pose_results[idx]
            frame_idx = det.get("frame_idx")
            if frame_idx is None:
                continue

            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue

            bbox = det.get("bbox")
            if bbox is not None:
                cropped = aggressive_estimator._crop_with_bbox(frame, bbox)
            else:
                cropped = frame

            landmarks = aggressive_estimator._estimate_frame(cropped, frame_idx, fps)
            if landmarks is not None:
                det["landmarks"] = landmarks
                refined += 1

            if refined % 100 == 0:
                gc.collect()

        cap.release()

        if aggressive_estimator.mp_landmarker is not None:
            aggressive_estimator.mp_landmarker.close()
            aggressive_estimator.mp_landmarker = None
        gc.collect()

        logger.info(f"Aggressive supplementary refined {refined}/{len(missing_indices)} frames")
        return pose_results
