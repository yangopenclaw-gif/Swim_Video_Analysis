import logging
import numpy as np
from typing import Dict, Any, List

from ..engines.engine_protocol import EngineProtocol, EngineResult

logger = logging.getLogger(__name__)


class Velocity2DEngine(EngineProtocol):
    @property
    def name(self) -> str:
        return "2D速度向量融合"

    @property
    def priority(self) -> int:
        return 4

    def is_available(self) -> bool:
        return True

    def get_dependencies(self) -> List[str]:
        return ["numpy"]

    def detect(self, signal: np.ndarray, params: Dict[str, Any], context: Dict[str, Any]) -> EngineResult:
        x_series_dict = context.get("x_series", {})
        y_series_dict = context.get("y_series", {})
        availability = context.get("availability")
        signal_time = context.get("signal_time")
        race_end = context.get("race_end")

        if signal_time is None or race_end is None:
            return EngineResult(success=False, engine_name=self.name)

        race_dur = race_end - signal_time
        if race_dur <= 0:
            return EngineResult(success=False, engine_name=self.name)

        smooth_window = params.get("velocity_smooth_window", 0.5)
        angle_threshold = params.get("velocity_angle_change_threshold", 60.0)
        dive_exclusion = params.get("y_motion_dive_exclusion", 5.0)

        min_time = signal_time + race_dur * 0.2
        max_time = signal_time + race_dur * 0.8
        expected_turn = signal_time + race_dur / 2.0
        dive_cutoff = signal_time + dive_exclusion

        keypoint_names = ["hip", "shoulder", "wrist", "head"]
        all_candidates = []

        for kp_name in keypoint_names:
            x_key = f"{kp_name}_x"
            y_key = f"{kp_name}_y"
            if x_key not in x_series_dict or y_key not in y_series_dict:
                continue

            x_series = x_series_dict[x_key]
            y_series = y_series_dict[y_key]

            if len(x_series) < 5 or len(y_series) < 5:
                continue

            ts_x = {t: v for t, v in x_series}
            ts_y = {t: v for t, v in y_series}
            common_ts = sorted(set(ts_x.keys()) & set(ts_y.keys()))

            if len(common_ts) < 5:
                continue

            x_vals = np.array([ts_x[t] for t in common_ts])
            y_vals = np.array([ts_y[t] for t in common_ts])
            ts_arr = np.array(common_ts)

            dt = np.diff(ts_arr)
            dt[dt == 0] = 1e-6
            vx = np.diff(x_vals) / dt
            vy = np.diff(y_vals) / dt

            if smooth_window > 0:
                fps = max(1, 1.0 / np.median(dt))
                kernel_size = max(3, int(smooth_window * fps))
                if kernel_size % 2 == 0:
                    kernel_size += 1
                if len(vx) >= kernel_size:
                    vx = np.convolve(vx, np.ones(kernel_size) / kernel_size, mode='same')
                    vy = np.convolve(vy, np.ones(kernel_size) / kernel_size, mode='same')

            angles = np.degrees(np.arctan2(vy, vx))
            speed = np.sqrt(vx ** 2 + vy ** 2)

            angle_diff = np.abs(np.diff(angles))
            angle_diff = np.minimum(angle_diff, 360 - angle_diff)

            speed_median = np.median(speed) if len(speed) > 0 else 1.0

            for i in range(1, len(angle_diff)):
                ts = ts_arr[min(i + 1, len(ts_arr) - 1)]
                if ts < min_time or ts > max_time:
                    continue
                if ts < dive_cutoff:
                    continue

                if angle_diff[i - 1] > angle_threshold:
                    proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                    spd = speed[min(i, len(speed) - 1)]
                    speed_factor = min(1.0, spd / max(speed_median, 1e-10))
                    vy_before = vy[max(0, i - 1)]
                    vy_after = vy[min(i, len(vy) - 1)]
                    y_direction_changed = (vy_before * vy_after < 0)
                    direction_bonus = 1.5 if y_direction_changed else 1.0
                    score = angle_diff[i - 1] / 180.0 * max(0, proximity) * speed_factor * direction_bonus
                    all_candidates.append((float(ts), score, kp_name, angle_diff[i - 1], y_direction_changed))

        if not all_candidates:
            return EngineResult(success=False, engine_name=self.name)

        all_candidates.sort(key=lambda c: -c[1])
        best_ts = all_candidates[0][0]
        best_kp = all_candidates[0][2]
        best_angle = all_candidates[0][3]
        y_dir_changed = all_candidates[0][4]

        consistency_window = 3.0
        consistent_count = sum(
            1 for c in all_candidates
            if abs(c[0] - best_ts) < consistency_window and c[2] != best_kp
        )
        consistency_bonus = min(0.15, consistent_count * 0.05)

        confidence = min(0.9, 0.25 + best_angle / 360.0 * 0.3 +
                         (0.15 if y_dir_changed else 0.05) + consistency_bonus)

        return EngineResult(
            success=True,
            data={"turn_time": best_ts, "keypoint": best_kp,
                  "angle_change": float(best_angle), "y_direction_changed": y_dir_changed},
            engine_name=self.name,
            confidence=confidence,
        )
