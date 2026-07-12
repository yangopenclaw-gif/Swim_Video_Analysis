import logging
import numpy as np
from typing import Dict, Any, List

from ..engines.engine_protocol import EngineProtocol, EngineResult

logger = logging.getLogger(__name__)


class YMotionEngine(EngineProtocol):
    @property
    def name(self) -> str:
        return "纵向运动模式"

    @property
    def priority(self) -> int:
        return 3

    def is_available(self) -> bool:
        return True

    def get_dependencies(self) -> List[str]:
        return []

    def detect(self, signal: np.ndarray, params: Dict[str, Any], context: Dict[str, Any]) -> EngineResult:
        y_series_dict = context.get("y_series", {})
        availability = context.get("availability")
        signal_time = context.get("signal_time")
        race_end = context.get("race_end")

        if signal_time is None or race_end is None:
            return EngineResult(success=False, engine_name=self.name)

        race_dur = race_end - signal_time
        if race_dur <= 0:
            return EngineResult(success=False, engine_name=self.name)

        slope_window = params.get("y_motion_slope_window", 1.0)
        min_change = params.get("y_motion_min_change", 0.001)
        change_factor = params.get("y_motion_change_factor", 0.3)
        persistence_window = params.get("y_motion_persistence_window", 2.0)
        dive_exclusion = params.get("y_motion_dive_exclusion", 8.0)

        priority_order = ["hip_y", "shoulder_y", "wrist_y", "head_y"]
        available_y_signals = []
        for sig_name in priority_order:
            if sig_name in y_series_dict and len(y_series_dict[sig_name]) >= 10:
                sig_quality = "可用"
                if availability:
                    sig_quality = availability.get(sig_name, "可用")
                if sig_quality != "不可用":
                    available_y_signals.append((sig_name, y_series_dict[sig_name]))

        if not available_y_signals:
            return EngineResult(success=False, engine_name=self.name)

        min_time = signal_time + race_dur * 0.2
        max_time = signal_time + race_dur * 0.8
        expected_turn = signal_time + race_dur / 2.0
        dive_cutoff = signal_time + dive_exclusion

        extrema_candidates = self._detect_extrema(
            available_y_signals, min_time, max_time, dive_cutoff,
            expected_turn, race_dur, params
        )

        slope_candidates = self._detect_slope_sign_changes(
            available_y_signals, min_time, max_time, dive_cutoff,
            expected_turn, race_dur, slope_window, min_change, change_factor,
            persistence_window, params
        )

        speed_min_candidates = self._detect_speed_minima(
            available_y_signals, min_time, max_time, dive_cutoff,
            expected_turn, race_dur, params
        )

        all_candidates = extrema_candidates + slope_candidates + speed_min_candidates

        if not all_candidates:
            return EngineResult(success=False, engine_name=self.name)

        all_candidates.sort(key=lambda c: -c[1])

        weights = {"hip_y": 1.0, "shoulder_y": 0.8, "wrist_y": 0.6, "head_y": 0.5}
        consistency_window = 3.0
        best_ts = all_candidates[0][0]
        consistent_count = sum(
            1 for c in all_candidates
            if abs(c[0] - best_ts) < consistency_window and c[2] != all_candidates[0][2]
        )
        consistency_bonus = min(1.0, consistent_count * 0.25)

        best_sig = all_candidates[0][2]
        y_series = y_series_dict.get(best_sig, [])
        coverage = len([t for t, _ in y_series if min_time <= t <= max_time]) / max(1, (max_time - min_time) * 30)
        significance = min(1.0, all_candidates[0][1] / max(0.001, np.std([c[1] for c in all_candidates[:5]])))
        proximity = max(0, 1.0 - abs(best_ts - expected_turn) / (race_dur / 2.0))
        source_score = weights.get(best_sig, 0.5)
        detection_type = all_candidates[0][4] if len(all_candidates[0]) > 4 else "unknown"

        confidence = min(0.95, significance * 0.2 + coverage * 0.15 + proximity * 0.15 +
                         source_score * 0.1 + consistency_bonus * 0.2 +
                         (0.2 if detection_type == "extrema" else 0.1))

        return EngineResult(
            success=True,
            data={"turn_time": best_ts, "signal_source": best_sig,
                  "detection_type": detection_type, "consistency": consistent_count},
            engine_name=self.name,
            confidence=confidence,
        )

    def _detect_extrema(
        self, available_y_signals, min_time, max_time, dive_cutoff,
        expected_turn, race_dur, params
    ):
        extrema_min_window = params.get("y_extrema_min_window", 3.0)
        extrema_before_after_window = params.get("y_extrema_before_after_window", 5.0)
        weights = {"hip_y": 1.0, "shoulder_y": 0.8, "wrist_y": 0.6, "head_y": 0.5}
        candidates = []

        for sig_name, y_series in available_y_signals:
            ts_arr = np.array([t for t, _ in y_series])
            y_arr = np.array([v for _, v in y_series])

            if len(ts_arr) < 10:
                continue

            smooth_w = max(3, int(extrema_min_window * 5))
            if len(y_arr) >= smooth_w:
                kernel = np.ones(smooth_w) / smooth_w
                y_smooth = np.convolve(y_arr, kernel, mode='same')
            else:
                y_smooth = y_arr

            for i in range(1, len(y_smooth) - 1):
                ts = ts_arr[i]
                if ts < min_time or ts > max_time:
                    continue
                if ts < dive_cutoff:
                    continue

                is_local_min = y_smooth[i] < y_smooth[i - 1] and y_smooth[i] < y_smooth[i + 1]
                is_local_max = y_smooth[i] > y_smooth[i - 1] and y_smooth[i] > y_smooth[i + 1]

                if is_local_min or is_local_max:
                    ba_window = extrema_before_after_window
                    before_mask = (ts_arr >= ts - ba_window) & (ts_arr <= ts)
                    after_mask = (ts_arr >= ts) & (ts_arr <= ts + ba_window)
                    before_vals = y_arr[before_mask]
                    after_vals = y_arr[after_mask]

                    if len(before_vals) < 3 or len(after_vals) < 3:
                        continue

                    before_mean = np.mean(before_vals)
                    after_mean = np.mean(after_vals)
                    current_val = y_smooth[i]

                    if is_local_min:
                        depth = max(before_mean - current_val, after_mean - current_val)
                    else:
                        depth = max(current_val - before_mean, current_val - after_mean)

                    if depth < 0.02:
                        continue

                    before_trend = before_vals[-1] - before_vals[0] if len(before_vals) >= 2 else 0
                    after_trend = after_vals[-1] - after_vals[0] if len(after_vals) >= 2 else 0
                    trend_reversal = (before_trend * after_trend < 0)

                    direction_change_magnitude = abs(before_mean - after_mean)

                    w = weights.get(sig_name, 0.5)
                    proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)

                    score = depth * w * max(0, proximity) * 10.0
                    if trend_reversal:
                        score *= 2.0
                    score *= (1.0 + direction_change_magnitude * 5.0)

                    candidates.append((float(ts), score, sig_name, depth, "extrema"))

        return candidates

    def _detect_slope_sign_changes(
        self, available_y_signals, min_time, max_time, dive_cutoff,
        expected_turn, race_dur, slope_window, min_change, change_factor,
        persistence_window, params
    ):
        weights = {"hip_y": 1.0, "shoulder_y": 0.8, "wrist_y": 0.6, "head_y": 0.5}
        all_candidates = []

        for sig_name, y_series in available_y_signals:
            ts_arr = np.array([t for t, _ in y_series])
            y_arr = np.array([v for _, v in y_series])

            if len(ts_arr) < 10:
                continue

            slopes = []
            for i in range(len(ts_arr)):
                t_center = ts_arr[i]
                mask = (ts_arr >= t_center - slope_window / 2) & (ts_arr <= t_center + slope_window / 2)
                window_ts = ts_arr[mask]
                window_y = y_arr[mask]
                if len(window_ts) >= 3:
                    slope = np.polyfit(window_ts, window_y, 1)[0]
                    slopes.append((t_center, slope))

            if len(slopes) < 3:
                continue

            slope_ts = np.array([t for t, _ in slopes])
            slope_vals = np.array([s for _, s in slopes])

            adaptive_threshold = max(min_change, np.std(slope_vals) * change_factor)

            for i in range(1, len(slope_vals)):
                if slope_ts[i] < min_time or slope_ts[i] > max_time:
                    continue
                if slope_ts[i] < dive_cutoff:
                    continue

                prev_s = slope_vals[i - 1]
                curr_s = slope_vals[i]
                direction_changed = (prev_s * curr_s < 0)
                magnitude_sufficient = abs(prev_s - curr_s) > adaptive_threshold
                if direction_changed and magnitude_sufficient:
                    change_magnitude = abs(prev_s - curr_s)

                    persistence_score = self._calc_persistence(
                        slope_ts, slope_vals, i, persistence_window
                    )

                    proximity = 1.0 - abs(slope_ts[i] - expected_turn) / (race_dur / 2.0)
                    w = weights.get(sig_name, 0.5)
                    score = change_magnitude * max(0, proximity) * w * (0.4 + 0.6 * persistence_score)
                    all_candidates.append((float(slope_ts[i]), score, sig_name, change_magnitude, "slope_sign"))

        return all_candidates

    def _calc_persistence(self, slope_ts, slope_vals, change_idx, window):
        if change_idx >= len(slope_vals) - 1:
            return 0.0

        change_time = slope_ts[change_idx]
        after_slopes = slope_vals[change_idx:]
        after_ts = slope_ts[change_idx:]

        new_direction = np.sign(slope_vals[change_idx])
        if new_direction == 0:
            return 0.0

        persistent_count = 0
        total_count = 0
        for j in range(len(after_ts)):
            if after_ts[j] - change_time > window:
                break
            total_count += 1
            if np.sign(after_slopes[j]) == new_direction:
                persistent_count += 1

        if total_count == 0:
            return 0.0
        return persistent_count / total_count

    def _detect_speed_minima(
        self, available_y_signals, min_time, max_time, dive_cutoff,
        expected_turn, race_dur, params
    ):
        speed_smooth_window = params.get("y_speed_smooth_window", 15)
        weights = {"hip_y": 1.0, "shoulder_y": 0.8, "wrist_y": 0.6, "head_y": 0.5}
        candidates = []

        for sig_name, y_series in available_y_signals:
            ts_arr = np.array([t for t, _ in y_series])
            y_arr = np.array([v for _, v in y_series])

            if len(ts_arr) < 10:
                continue

            dt = np.diff(ts_arr)
            dt[dt == 0] = 1e-6
            vy = np.diff(y_arr) / dt
            speed_y = np.abs(vy)

            kernel_size = max(3, speed_smooth_window)
            if kernel_size % 2 == 0:
                kernel_size += 1
            if len(speed_y) >= kernel_size:
                speed_smooth = np.convolve(speed_y, np.ones(kernel_size) / kernel_size, mode='same')
            else:
                speed_smooth = speed_y

            speed_ts = ts_arr[1:]

            overall_median_speed = np.median(speed_smooth) if len(speed_smooth) > 0 else 1.0

            for i in range(1, len(speed_smooth) - 1):
                ts = speed_ts[i]
                if ts < min_time or ts > max_time:
                    continue
                if ts < dive_cutoff:
                    continue

                if speed_smooth[i] < speed_smooth[i - 1] and speed_smooth[i] < speed_smooth[i + 1]:
                    speed_ratio = speed_smooth[i] / max(overall_median_speed, 1e-10)
                    if speed_ratio > 0.5:
                        continue

                    w = weights.get(sig_name, 0.5)
                    proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                    low_speed_score = (1.0 - speed_ratio) * w * max(0, proximity) * 8.0
                    candidates.append((float(ts), low_speed_score, sig_name, speed_smooth[i], "speed_min"))

        return candidates
