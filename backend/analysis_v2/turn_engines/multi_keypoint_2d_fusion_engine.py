import logging
import numpy as np
from typing import Dict, Any, List

from ..engines.engine_protocol import EngineProtocol, EngineResult

logger = logging.getLogger(__name__)


class MultiKeypoint2DFusionEngine(EngineProtocol):
    @property
    def name(self) -> str:
        return "多关键点2D融合"

    @property
    def priority(self) -> int:
        return 2

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

        min_time = signal_time + race_dur * 0.2
        max_time = signal_time + race_dur * 0.8
        expected_turn = signal_time + race_dur / 2.0
        dive_exclusion = params.get("y_motion_dive_exclusion", 5.0)
        dive_cutoff = signal_time + dive_exclusion

        x_variance_ratio = self._compute_axis_variance_ratio(x_series_dict, y_series_dict, availability)
        y_weight_boost = max(1.0, 1.0 / max(x_variance_ratio, 0.01))

        keypoint_weights = {"hip": 0.35, "shoulder": 0.30, "wrist": 0.20, "head": 0.15}
        available_keypoints = {}

        for kp_name in keypoint_weights:
            x_key = f"{kp_name}_x"
            y_key = f"{kp_name}_y"
            if x_key in x_series_dict and y_key in y_series_dict:
                x_s = x_series_dict[x_key]
                y_s = y_series_dict[y_key]
                if len(x_s) >= 5 and len(y_s) >= 5:
                    available_keypoints[kp_name] = (x_s, y_s)

        if len(available_keypoints) < 1:
            return EngineResult(success=False, engine_name=self.name)

        total_weight = sum(keypoint_weights[kp] for kp in available_keypoints)
        normalized_weights = {kp: keypoint_weights[kp] / total_weight for kp in available_keypoints}

        candidates = []

        for kp_name, (x_s, y_s) in available_keypoints.items():
            ts_x = {t: v for t, v in x_s}
            ts_y = {t: v for t, v in y_s}
            common_ts = sorted(set(ts_x.keys()) & set(ts_y.keys()))

            if len(common_ts) < 5:
                continue

            x_vals = np.array([ts_x[t] for t in common_ts])
            y_vals = np.array([ts_y[t] for t in common_ts])
            ts_arr = np.array(common_ts)

            for i in range(1, len(ts_arr) - 1):
                ts = ts_arr[i]
                if ts < min_time or ts > max_time:
                    continue
                if ts < dive_cutoff:
                    continue

                before_mask = ts_arr <= ts
                after_mask = ts_arr >= ts

                before_x = x_vals[before_mask]
                after_x = x_vals[after_mask]
                before_y = y_vals[before_mask]
                after_y = y_vals[after_mask]

                if len(before_x) < 3 or len(after_x) < 3:
                    continue

                before_ts = ts_arr[before_mask]
                after_ts = ts_arr[after_mask]

                slope_x_before = np.polyfit(before_ts, before_x, 1)[0] if len(before_ts) >= 2 else 0
                slope_x_after = np.polyfit(after_ts, after_x, 1)[0] if len(after_ts) >= 2 else 0
                slope_y_before = np.polyfit(before_ts, before_y, 1)[0] if len(before_ts) >= 2 else 0
                slope_y_after = np.polyfit(after_ts, after_y, 1)[0] if len(after_ts) >= 2 else 0

                delta_slope_x = abs(slope_x_before - slope_x_after)
                delta_slope_y = abs(slope_y_before - slope_y_after)

                y_direction_changed = (slope_y_before * slope_y_after < 0)
                x_direction_changed = (slope_x_before * slope_x_after < 0)

                score_y = delta_slope_y * y_weight_boost
                score_x = delta_slope_x
                if y_direction_changed:
                    score_y *= 2.0
                if x_direction_changed:
                    score_x *= 1.5

                score_2d = np.sqrt(score_x ** 2 + score_y ** 2)

                w = normalized_weights[kp_name]
                proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                candidates.append((float(ts), score_2d * w * max(0, proximity), kp_name,
                                   delta_slope_x, delta_slope_y, y_direction_changed))

        if not candidates:
            return EngineResult(success=False, engine_name=self.name)

        candidates.sort(key=lambda c: -c[1])
        best = candidates[0]

        n_keypoints_consistent = sum(1 for c in candidates[:20] if abs(c[0] - best[0]) < 1.0)
        y_dir_changed = best[5]
        has_xy = best[3] > 0.0005 and best[4] > 0.0005

        confidence = min(0.9, 0.2 + n_keypoints_consistent * 0.1 +
                         (0.25 if y_dir_changed else 0.1) +
                         (0.15 if has_xy else 0.05))

        return EngineResult(
            success=True,
            data={"turn_time": best[0], "keypoint": best[2],
                  "delta_slope_x": float(best[3]), "delta_slope_y": float(best[4]),
                  "y_direction_changed": y_dir_changed,
                  "y_weight_boost": y_weight_boost},
            engine_name=self.name,
            confidence=confidence,
        )

    def _compute_axis_variance_ratio(self, x_series_dict, y_series_dict, availability):
        x_variances = []
        y_variances = []
        for key in x_series_dict:
            if availability and availability.get(key) == "不可用":
                continue
            vals = np.array([v for _, v in x_series_dict[key]])
            if len(vals) >= 5:
                x_variances.append(np.var(vals))
        for key in y_series_dict:
            if availability and availability.get(key) == "不可用":
                continue
            vals = np.array([v for _, v in y_series_dict[key]])
            if len(vals) >= 5:
                y_variances.append(np.var(vals))

        if not x_variances or not y_variances:
            return 1.0
        return np.mean(x_variances) / max(np.mean(y_variances), 1e-10)
