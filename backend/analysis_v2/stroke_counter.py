import logging
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from scipy.signal import find_peaks

from .base_module import AnalysisModule
from .shared import AnalysisContext, ModuleResult, EngineResult, AccuracyInfo
from .utils import get_lm, midpoint, get_timestamp, get_landmark_from_pf, smooth

logger = logging.getLogger(__name__)


class StrokeCounter(AnalysisModule):
    VERSION = "4.0.0"

    @property
    def name(self) -> str:
        return "划水计数"

    def analyze(self, context: AnalysisContext) -> ModuleResult:
        pose_frames = list(context.pose_frames)
        events = context.events
        params = context.detection_params.stroke_detection
        is_50m_50pool = context.is_50m_50pool

        half_time = self._get_half_time(events, context.race_duration)

        if is_50m_50pool:
            left, right = self._count_strokes_full(pose_frames, events, params)
            metrics = {"左臂划水次数": f"{left} 次", "右臂划水次数": f"{right} 次"}
        else:
            first_left, first_right = self._count_strokes_phase(pose_frames, events, 'first', half_time, params)
            second_left, second_right = self._count_strokes_phase(pose_frames, events, 'second', half_time, params)
            metrics = {
                "前程左臂划水次数": f"{first_left} 次",
                "前程右臂划水次数": f"{first_right} 次",
                "后程左臂划水次数": f"{second_left} 次",
                "后程右臂划水次数": f"{second_right} 次",
            }

        coverage = self._estimate_coverage(pose_frames, events, half_time, is_50m_50pool)
        accuracy = AccuracyInfo(
            confidence=min(coverage * 1.1, 1.0),
            coverage=round(coverage, 3),
            quality="高" if coverage >= 0.7 else ("中" if coverage >= 0.4 else "低"),
            low_confidence=coverage < 0.3,
            warnings=[] if coverage >= 0.3 else ["划水检测覆盖率低"],
        )

        return ModuleResult(
            module_name=self.name,
            metrics=metrics,
            module_events={},
            accuracy=accuracy,
            detection_method="三引擎融合(y峰值+x周期性+手臂伸展)",
        )

    def _get_half_time(self, events, race_duration: float) -> Optional[float]:
        if events.signal_time is None:
            return None
        if events.turn_touch is not None:
            return events.turn_touch
        return None

    def _count_strokes_full(self, pose_frames, events, params) -> Tuple[int, int]:
        left_y, right_y, left_x, right_x, left_dist, right_dist, timestamps = self._extract_stroke_signals(
            pose_frames, events, None, None
        )
        left = self._fusion_count(left_y, left_x, left_dist, timestamps, params)
        right = self._fusion_count(right_y, right_x, right_dist, timestamps, params)
        return left, right

    def _count_strokes_phase(self, pose_frames, events, phase, half_time, params) -> Tuple[int, int]:
        start_t = events.signal_time or events.dive_start or 0
        end_t = events.race_end or float('inf')
        if phase == 'first' and half_time:
            end_t = half_time
        elif phase == 'second' and half_time:
            start_t = half_time

        left_y, right_y, left_x, right_x, left_dist, right_dist, timestamps = self._extract_stroke_signals(
            pose_frames, events, start_t, end_t
        )
        left = self._fusion_count(left_y, left_x, left_dist, timestamps, params)
        right = self._fusion_count(right_y, right_x, right_dist, timestamps, params)
        return left, right

    def _extract_stroke_signals(self, pose_frames, events, start_t, end_t):
        if start_t is None:
            start_t = events.signal_time or events.dive_start or 0
        if end_t is None:
            end_t = events.race_end or float('inf')

        left_y, right_y = [], []
        left_x, right_x = [], []
        left_dist, right_dist = [], []
        timestamps = []

        for pf in pose_frames:
            ts = get_timestamp(pf)
            if ts < start_t or ts > end_t:
                continue
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = get_lm(lm, "left_hip")
            rh = get_lm(lm, "right_hip")
            mid = midpoint(lh, rh)
            if mid is not None and mid[1] > 0.9:
                continue

            lw = get_lm(lm, "left_wrist")
            rw = get_lm(lm, "right_wrist")
            ls = get_lm(lm, "left_shoulder")
            rs = get_lm(lm, "right_shoulder")

            left_y.append(lw[1] if lw is not None and 0 <= lw[1] <= 1 else None)
            right_y.append(rw[1] if rw is not None and 0 <= rw[1] <= 1 else None)
            left_x.append(lw[0] if lw is not None else None)
            right_x.append(rw[0] if rw is not None else None)

            if lw is not None and ls is not None:
                left_dist.append(float(np.linalg.norm(lw[:2] - ls[:2])))
            else:
                left_dist.append(None)
            if rw is not None and rs is not None:
                right_dist.append(float(np.linalg.norm(rw[:2] - rs[:2])))
            else:
                right_dist.append(None)

            timestamps.append(ts)

        return left_y, right_y, left_x, right_x, left_dist, right_dist, timestamps

    def _fusion_count(self, y_signal, x_signal, dist_signal, timestamps, params) -> int:
        counts = []

        count_y = self._count_y_peaks(y_signal, params)
        if count_y is not None:
            counts.append(count_y)

        count_x = self._count_x_periodicity(x_signal, timestamps, params)
        if count_x is not None:
            counts.append(count_x)

        count_dist = self._count_dist_peaks(dist_signal, params)
        if count_dist is not None:
            counts.append(count_dist)

        if not counts:
            return 0

        if len(counts) >= 3:
            sorted_counts = sorted(counts)
            result = sorted_counts[1]
            max_diff = max(abs(c - result) for c in counts)
            if max_diff > result * 0.3:
                logger.info(f"Stroke fusion: multi-signal inconsistency, counts={counts}, using median={result}")
        else:
            result = int(np.median(counts))

        return max(0, result)

    def _count_y_peaks(self, y_signal, params) -> Optional[int]:
        segments = self._split_valid_segments(y_signal, min_segment=3)
        total_peaks = 0
        for seg in segments:
            if len(seg) < 3:
                continue
            arr = np.array(seg)
            baseline_window = max(3, int(params.get("baseline_window_seconds", 2.0) * 15))
            local_baselines = self._sliding_median(arr, baseline_window)
            local_stds = self._sliding_std(arr, baseline_window)
            height_threshold = local_baselines + np.maximum(0.01, local_stds * params.get("peak_height_factor", 0.15))
            min_distance = max(3, int(params.get("min_distance_seconds", 0.3) * 15))
            min_prominence = np.maximum(0.008, local_stds * params.get("min_prominence_factor", 0.1))
            avg_height = float(np.median(height_threshold))
            avg_prominence = float(np.median(min_prominence))
            peaks, _ = find_peaks(arr, height=avg_height, distance=min_distance, prominence=avg_prominence)
            total_peaks += len(peaks)
        return total_peaks if total_peaks > 0 else None

    def _count_x_periodicity(self, x_signal, timestamps, params) -> Optional[int]:
        segments = self._split_valid_segments(x_signal, min_segment=10)
        total_peaks = 0
        for seg in segments:
            if len(seg) < 10:
                continue
            arr = np.array(seg)
            arr_smooth = smooth(arr, max(2, len(arr) // 20))
            min_distance = max(3, int(params.get("min_distance_seconds", 0.3) * 15))
            std_val = float(np.std(arr_smooth))
            peaks, _ = find_peaks(arr_smooth, height=float(np.median(arr_smooth)) + std_val * 0.1,
                                  distance=min_distance, prominence=max(0.005, std_val * 0.1))
            total_peaks += len(peaks)
        return total_peaks if total_peaks > 0 else None

    def _count_dist_peaks(self, dist_signal, params) -> Optional[int]:
        segments = self._split_valid_segments(dist_signal, min_segment=3)
        total_peaks = 0
        for seg in segments:
            if len(seg) < 3:
                continue
            arr = np.array(seg)
            median_val = float(np.median(arr))
            std_val = float(np.std(arr))
            min_distance = max(3, int(params.get("min_distance_seconds", 0.3) * 15))
            peaks, _ = find_peaks(arr, height=median_val + max(0.005, std_val * 0.1),
                                  distance=min_distance, prominence=max(0.005, std_val * 0.1))
            total_peaks += len(peaks)
        return total_peaks if total_peaks > 0 else None

    def _split_valid_segments(self, data, min_segment=3):
        segments = []
        current = []
        for v in data:
            if v is not None:
                current.append(v)
            else:
                if len(current) >= min_segment:
                    segments.append(current)
                current = []
        if len(current) >= min_segment:
            segments.append(current)
        return segments

    def _sliding_median(self, arr, window):
        result = np.zeros_like(arr)
        half = window // 2
        for i in range(len(arr)):
            start = max(0, i - half)
            end = min(len(arr), i + half + 1)
            result[i] = np.median(arr[start:end])
        return result

    def _sliding_std(self, arr, window):
        result = np.zeros_like(arr)
        half = window // 2
        for i in range(len(arr)):
            start = max(0, i - half)
            end = min(len(arr), i + half + 1)
            result[i] = np.std(arr[start:end])
        return result

    def _estimate_coverage(self, pose_frames, events, half_time, is_50m_50pool):
        start_t = events.signal_time or events.dive_start or 0
        end_t = events.race_end or float('inf')
        total = 0
        valid = 0
        for pf in pose_frames:
            ts = get_timestamp(pf)
            if ts < start_t or ts > end_t:
                continue
            total += 1
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is not None:
                lw = get_lm(lm, "left_wrist")
                rw = get_lm(lm, "right_wrist")
                if lw is not None or rw is not None:
                    valid += 1
        return valid / max(total, 1)