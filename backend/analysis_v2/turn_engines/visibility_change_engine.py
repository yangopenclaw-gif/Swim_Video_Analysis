import logging
import numpy as np
from typing import Dict, Any, List

from ..engines.engine_protocol import EngineProtocol, EngineResult

logger = logging.getLogger(__name__)


class VisibilityChangeEngine(EngineProtocol):
    @property
    def name(self) -> str:
        return "可见度变化"

    @property
    def priority(self) -> int:
        return 5

    def is_available(self) -> bool:
        return True

    def get_dependencies(self) -> List[str]:
        return ["numpy"]

    def detect(self, signal: np.ndarray, params: Dict[str, Any], context: Dict[str, Any]) -> EngineResult:
        visibility_diff_series = context.get("visibility_diff_series", {})
        signal_time = context.get("signal_time")
        race_end = context.get("race_end")

        if signal_time is None or race_end is None:
            return EngineResult(success=False, engine_name=self.name)

        race_dur = race_end - signal_time
        if race_dur <= 0:
            return EngineResult(success=False, engine_name=self.name)

        smooth_window = params.get("visibility_smooth_window", 5)
        change_threshold = params.get("visibility_change_threshold", 0.2)
        dive_exclusion = params.get("y_motion_dive_exclusion", 8.0)

        min_time = signal_time + race_dur * 0.2
        max_time = signal_time + race_dur * 0.8
        expected_turn = signal_time + race_dur / 2.0
        dive_cutoff = signal_time + dive_exclusion

        keypoint_weights = {"hip_vis_diff": 1.0, "shoulder_vis_diff": 0.8, "wrist_vis_diff": 0.6}
        all_candidates = []

        for diff_name, diff_series in visibility_diff_series.items():
            if len(diff_series) < 10:
                continue

            w = keypoint_weights.get(diff_name, 0.5)

            ts_arr = np.array([t for t, _ in diff_series])
            vals = np.array([v for _, v in diff_series])

            if smooth_window > 1 and len(vals) >= smooth_window:
                kernel = np.ones(smooth_window) / smooth_window
                smoothed = np.convolve(vals, kernel, mode='same')
            else:
                smoothed = vals

            for i in range(1, len(smoothed) - 1):
                ts = ts_arr[i]
                if ts < min_time or ts > max_time:
                    continue
                if ts < dive_cutoff:
                    continue

                prev_val = smoothed[i - 1]
                curr_val = smoothed[i]
                next_val = smoothed[i + 1]

                is_zero_crossing = (prev_val * curr_val < 0) or (curr_val * next_val < 0)
                magnitude = abs(prev_val - next_val)

                if is_zero_crossing and magnitude > change_threshold:
                    proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                    score = magnitude * w * max(0, proximity) * 10.0
                    all_candidates.append((float(ts), score, diff_name, magnitude, "vis_zero_crossing"))

            for i in range(1, len(smoothed)):
                ts = ts_arr[i]
                if ts < min_time or ts > max_time:
                    continue
                if ts < dive_cutoff:
                    continue

                abs_change = abs(smoothed[i] - smoothed[i - 1])
                if abs_change > change_threshold * 2:
                    proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                    score = abs_change * w * max(0, proximity) * 5.0
                    all_candidates.append((float(ts), score, diff_name, abs_change, "vis_sudden_change"))

        if not all_candidates:
            return EngineResult(success=False, engine_name=self.name)

        all_candidates.sort(key=lambda c: -c[1])
        best_ts = all_candidates[0][0]
        best_sig = all_candidates[0][2]
        best_mag = all_candidates[0][3]
        best_type = all_candidates[0][4]

        consistency_window = 3.0
        consistent_count = sum(
            1 for c in all_candidates
            if abs(c[0] - best_ts) < consistency_window and c[2] != best_sig
        )
        consistency_bonus = min(0.15, consistent_count * 0.05)

        confidence = min(0.85, 0.3 + best_mag * 2.0 + consistency_bonus)

        return EngineResult(
            success=True,
            data={"turn_time": best_ts, "signal_source": best_sig,
                  "magnitude": best_mag, "detection_type": best_type},
            engine_name=self.name,
            confidence=confidence,
        )