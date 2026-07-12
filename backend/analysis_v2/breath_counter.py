import logging
import numpy as np
from typing import Optional, Dict, Any, List, Tuple

from .base_module import AnalysisModule
from .shared import AnalysisContext, ModuleResult, AccuracyInfo
from .utils import get_lm, midpoint, get_timestamp, smooth

logger = logging.getLogger(__name__)


class BreathCounter(AnalysisModule):
    VERSION = "4.0.0"

    @property
    def name(self) -> str:
        return "换气计数"

    def analyze(self, context: AnalysisContext) -> ModuleResult:
        pose_frames = list(context.pose_frames)
        events = context.events
        params = context.detection_params.breath_detection
        is_50m_50pool = context.is_50m_50pool

        half_time = self._get_half_time(events, context.race_duration)

        if is_50m_50pool:
            count = self._count_breaths_full(pose_frames, events, params)
            metrics = {"总换气次数": f"{count} 次"}
        else:
            first_count = self._count_breaths_phase(pose_frames, events, 'first', half_time, params)
            second_count = self._count_breaths_phase(pose_frames, events, 'second', half_time, params)
            metrics = {
                "前程总换气次数": f"{first_count} 次",
                "后程总换气次数": f"{second_count} 次",
            }

        coverage = self._estimate_coverage(pose_frames, events, half_time, is_50m_50pool)
        accuracy = AccuracyInfo(
            confidence=min(coverage * 1.1, 1.0),
            coverage=round(coverage, 3),
            quality="高" if coverage >= 0.7 else ("中" if coverage >= 0.4 else "低"),
            low_confidence=coverage < 0.3,
            warnings=[] if coverage >= 0.3 else ["换气检测覆盖率低"],
        )

        return ModuleResult(
            module_name=self.name,
            metrics=metrics,
            module_events={},
            accuracy=accuracy,
            detection_method="头部旋转联合检测(前后倾斜+左右旋转OR融合)",
        )

    def _get_half_time(self, events, race_duration: float) -> Optional[float]:
        if events.signal_time is None:
            return None
        if events.turn_touch is not None:
            return events.turn_touch
        return None

    def _count_breaths_full(self, pose_frames, events, params) -> int:
        return self._count_breaths_phase(pose_frames, events, 'full', None, params)

    def _count_breaths_phase(self, pose_frames, events, phase, half_time, params) -> int:
        start_t = events.signal_time or events.dive_start or 0
        end_t = events.race_end or float('inf')
        if phase == 'first' and half_time:
            end_t = half_time
        elif phase == 'second' and half_time:
            start_t = half_time

        nose_x, nose_y, ear_x, ear_y, l_shoulder_y, r_shoulder_y = [], [], [], [], [], []
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

            n = get_lm(lm, "nose")
            le = get_lm(lm, "left_ear")
            re = get_lm(lm, "right_ear")
            ls = get_lm(lm, "left_shoulder")
            rs = get_lm(lm, "right_shoulder")

            ear = le if le is not None else re
            nose_x.append(n[0] if n is not None else None)
            nose_y.append(n[1] if n is not None else None)
            ear_x.append(ear[0] if ear is not None else None)
            ear_y.append(ear[1] if ear is not None else None)
            l_shoulder_y.append(ls[1] if ls is not None else None)
            r_shoulder_y.append(rs[1] if rs is not None else None)
            timestamps.append(ts)

        breaths_tilt = self._detect_by_head_tilt(nose_x, nose_y, ear_x, ear_y, params)
        breaths_rotation = self._detect_by_head_rotation(nose_x, ear_x, params)
        breaths_shoulder = self._detect_by_shoulder_roll(l_shoulder_y, r_shoulder_y, params)

        return self._or_fusion(breaths_tilt, breaths_rotation, breaths_shoulder, timestamps, params)

    def _detect_by_head_tilt(self, nose_x, nose_y, ear_x, ear_y, params) -> List[Tuple[int, str]]:
        segments = self._split_valid_segments_4(nose_x, nose_y, ear_x, ear_y, min_segment=3)
        events = []
        for seg_indices, seg_ny, seg_ey in segments:
            if len(seg_ny) < 3:
                continue
            head_tilt = np.array(seg_ny) - np.array(seg_ey)
            ht_smooth = smooth(head_tilt, max(2, len(head_tilt) // 15))
            baseline_window = max(3, int(params.get("baseline_window_seconds", 2.0) * 15))
            baselines = self._sliding_median(ht_smooth, baseline_window)
            deviation_factor = params.get("deviation_factor", 0.3)
            min_deviation = params.get("min_deviation", 0.002)
            thresholds = np.maximum(np.abs(ht_smooth - baselines) * deviation_factor, min_deviation)
            cooldown = max(3, int(params.get("cooldown_seconds", 0.8) * 15))
            prev_near = True
            cd = 0
            for i in range(len(ht_smooth)):
                if cd > 0:
                    cd -= 1
                    continue
                deviation = abs(ht_smooth[i] - baselines[i])
                if deviation > thresholds[i] and prev_near:
                    events.append((seg_indices[i], "tilt"))
                    cd = cooldown
                prev_near = deviation <= thresholds[i]
        return events

    def _detect_by_head_rotation(self, nose_x, ear_x, params) -> List[Tuple[int, str]]:
        segments = self._split_valid_segments_2(nose_x, ear_x, min_segment=3)
        events = []
        min_nose_x_deviation = params.get("min_nose_x_deviation", 0.01)
        cooldown = max(3, int(params.get("cooldown_seconds", 0.8) * 15))

        for seg_indices, seg_nx, seg_ex in segments:
            if len(seg_nx) < 3:
                continue
            nose_ear_diff = np.array(seg_nx) - np.array(seg_ex)
            diff_smooth = smooth(nose_ear_diff, max(2, len(nose_ear_diff) // 15))
            baseline_window = max(3, int(params.get("baseline_window_seconds", 2.0) * 15))
            baselines = self._sliding_median(diff_smooth, baseline_window)
            cd = 0
            prev_near = True
            for i in range(len(diff_smooth)):
                if cd > 0:
                    cd -= 1
                    continue
                deviation = abs(diff_smooth[i] - baselines[i])
                if deviation > min_nose_x_deviation and prev_near:
                    events.append((seg_indices[i], "rotation"))
                    cd = cooldown
                prev_near = deviation <= min_nose_x_deviation
        return events

    def _detect_by_shoulder_roll(self, l_shoulder_y, r_shoulder_y, params) -> List[Tuple[int, str]]:
        segments = self._split_valid_segments_2(l_shoulder_y, r_shoulder_y, min_segment=3)
        events = []
        cooldown = max(3, int(params.get("cooldown_seconds", 0.8) * 15))

        for seg_indices, seg_ly, seg_ry in segments:
            if len(seg_ly) < 3:
                continue
            diff = np.array(seg_ly) - np.array(seg_ry)
            diff_smooth = smooth(diff, max(2, len(diff) // 15))
            baseline_window = max(3, int(params.get("baseline_window_seconds", 2.0) * 15))
            baselines = self._sliding_median(diff_smooth, baseline_window)
            std_val = float(np.std(diff_smooth))
            threshold = max(std_val * 0.3, 0.003)
            cd = 0
            prev_near = True
            for i in range(len(diff_smooth)):
                if cd > 0:
                    cd -= 1
                    continue
                deviation = abs(diff_smooth[i] - baselines[i])
                if deviation > threshold and prev_near:
                    events.append((seg_indices[i], "shoulder"))
                    cd = cooldown
                prev_near = deviation <= threshold
        return events

    def _or_fusion(self, tilt_events, rotation_events, shoulder_events, timestamps, params) -> int:
        all_events = []
        for idx, etype in tilt_events:
            all_events.append((idx, etype))
        for idx, etype in rotation_events:
            all_events.append((idx, etype))
        for idx, etype in shoulder_events:
            all_events.append((idx, etype))

        if not all_events:
            return 0

        all_events.sort(key=lambda x: x[0])
        cooldown = max(3, int(params.get("cooldown_seconds", 0.8) * 15))
        count = 0
        last_idx = -cooldown - 1

        for idx, etype in all_events:
            if idx - last_idx >= cooldown:
                count += 1
                last_idx = idx

        return count

    def _split_valid_segments_4(self, nx, ny, ex, ey, min_segment=3):
        segments = []
        curr_indices, curr_ny, curr_ey = [], [], []
        for i, (nvx, nvy, evx, evy) in enumerate(zip(nx, ny, ex, ey)):
            if nvx is not None and nvy is not None and evx is not None and evy is not None:
                curr_indices.append(i)
                curr_ny.append(nvy)
                curr_ey.append(evy)
            else:
                if len(curr_ny) >= min_segment:
                    segments.append((curr_indices, curr_ny, curr_ey))
                curr_indices, curr_ny, curr_ey = [], [], []
        if len(curr_ny) >= min_segment:
            segments.append((curr_indices, curr_ny, curr_ey))
        return segments

    def _split_valid_segments_2(self, a, b, min_segment=3):
        segments = []
        curr_indices, curr_a, curr_b = [], [], []
        for i, (va, vb) in enumerate(zip(a, b)):
            if va is not None and vb is not None:
                curr_indices.append(i)
                curr_a.append(va)
                curr_b.append(vb)
            else:
                if len(curr_a) >= min_segment:
                    segments.append((curr_indices, curr_a, curr_b))
                curr_indices, curr_a, curr_b = [], [], []
        if len(curr_a) >= min_segment:
            segments.append((curr_indices, curr_a, curr_b))
        return segments

    def _sliding_median(self, arr, window):
        result = np.zeros_like(arr, dtype=float)
        half = window // 2
        for i in range(len(arr)):
            start = max(0, i - half)
            end = min(len(arr), i + half + 1)
            result[i] = np.median(arr[start:end])
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
                n = get_lm(lm, "nose")
                le = get_lm(lm, "left_ear")
                if n is not None and le is not None:
                    valid += 1
        return valid / max(total, 1)