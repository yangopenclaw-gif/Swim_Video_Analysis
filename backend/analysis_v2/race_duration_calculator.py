import logging
import numpy as np
from typing import Optional, Dict, Any, List, Tuple

from .base_module import AnalysisModule
from .shared import AnalysisContext, ModuleResult, AccuracyInfo
from .utils import format_race_time, get_lm, midpoint, get_timestamp

logger = logging.getLogger(__name__)


class RaceDurationCalculator(AnalysisModule):
    VERSION = "4.1.0"

    @property
    def name(self) -> str:
        return "比赛用时计算"

    def analyze(self, context: AnalysisContext) -> ModuleResult:
        events = context.events
        is_50m_50pool = context.is_50m_50pool
        pose_frames = list(context.pose_frames)

        metrics = {}
        duration_label = "实测值"

        signal_time = events.signal_time
        dive_start = events.dive_start
        turn_touch = events.turn_touch
        turn_touch_confidence = events.turn_touch_confidence
        turn_touch_method = events.turn_touch_method
        race_end = events.race_end

        start_time = signal_time
        if start_time is None:
            start_time = dive_start
            duration_label = "估算值（以起跳时刻为起点）"

        first_half_label = ""
        second_half_label = ""

        if not is_50m_50pool:
            if turn_touch is not None and start_time is not None:
                if turn_touch_confidence is not None and turn_touch_confidence >= 0.5:
                    first_half = turn_touch - start_time
                    metrics["前程整体用时"] = format_race_time(first_half)
                    first_half_label = "实测值"
                elif turn_touch_confidence is not None and turn_touch_confidence >= 0.2:
                    first_half = turn_touch - start_time
                    metrics["前程整体用时"] = format_race_time(first_half)
                    first_half_label = f"低置信度转身点（{turn_touch_method or '重试检测'}）"
                else:
                    first_half_label, first_half_time = self._try_degradation_strategies(
                        pose_frames, events, context
                    )
                    if first_half_time is not None:
                        metrics["前程整体用时"] = format_race_time(first_half_time)
                    else:
                        metrics["前程整体用时"] = "未检测到"
            else:
                first_half_label, first_half_time = self._try_degradation_strategies(
                    pose_frames, events, context
                )
                if first_half_time is not None:
                    metrics["前程整体用时"] = format_race_time(first_half_time)
                else:
                    metrics["前程整体用时"] = "未检测到"

            if turn_touch is not None and race_end is not None:
                second_half = race_end - turn_touch
                metrics["后程整体用时"] = format_race_time(second_half)
                if turn_touch_confidence is not None and turn_touch_confidence >= 0.5:
                    second_half_label = "实测值"
                elif turn_touch_confidence is not None and turn_touch_confidence >= 0.2:
                    second_half_label = f"低置信度转身点（{turn_touch_method or '重试检测'}）"
                else:
                    second_half_label = first_half_label
            else:
                metrics["后程整体用时"] = "未检测到"
                second_half_label = "未检测到"

            if first_half_label:
                metrics["前程标注详情"] = first_half_label
            if second_half_label:
                metrics["后程标注详情"] = second_half_label

        if start_time is not None and race_end is not None:
            total_duration = race_end - start_time
            metrics["触壁终点用时"] = format_race_time(total_duration)
        else:
            metrics["触壁终点用时"] = "未检测到"
            duration_label = "未检测到"

        metrics["用时标注"] = duration_label

        confidence = 1.0 if signal_time is not None else 0.6
        if turn_touch is None and not is_50m_50pool:
            confidence *= 0.5
        if first_half_label and first_half_label != "实测值":
            confidence *= 0.7

        accuracy = AccuracyInfo(
            confidence=round(confidence, 3),
            coverage=1.0 if start_time is not None else 0.0,
            quality="高" if confidence >= 0.7 else ("中" if confidence >= 0.4 else "低"),
            low_confidence=confidence < 0.3,
            warnings=[] if confidence >= 0.3 else ["比赛用时计算置信度低"],
        )

        return ModuleResult(
            module_name=self.name,
            metrics=metrics,
            module_events={},
            accuracy=accuracy,
            detection_method=f"直接计算（{duration_label}）",
        )

    def _try_degradation_strategies(
        self, pose_frames, events, context
    ) -> Tuple[str, Optional[float]]:
        if events.signal_time is None:
            return "未检测到", None

        label, turn_time = self._try_low_confidence_turn(events, context)
        if turn_time is not None:
            return label, turn_time - events.signal_time

        label, turn_time = self._try_alternative_body_part_turn(pose_frames, events)
        if turn_time is not None:
            return label, turn_time - events.signal_time

        label, turn_time = self._try_velocity_change_turn(pose_frames, events)
        if turn_time is not None:
            return label, turn_time - events.signal_time

        label, turn_time = self._try_y_direction_turn(pose_frames, events)
        if turn_time is not None:
            return label, turn_time - events.signal_time

        label, turn_time = self._try_2d_velocity_turn(pose_frames, events)
        if turn_time is not None:
            return label, turn_time - events.signal_time

        return "未检测到", None

    def _try_low_confidence_turn(
        self, events, context
    ) -> Tuple[str, Optional[float]]:
        turn_result = context.previous_results.get("转身检测")
        if turn_result is None:
            return "", None

        for rr in turn_result.retry_records:
            if rr.success and rr.confidence >= 0.2 and rr.result is not None:
                label = f"低置信度转身点（{rr.strategy_name}）"
                return label, rr.result

        if events.turn_touch is not None and events.turn_touch_confidence is not None:
            if events.turn_touch_confidence >= 0.2:
                label = f"低置信度转身点（{events.turn_touch_method or '重试检测'}）"
                return label, events.turn_touch

        return "", None

    def _try_alternative_body_part_turn(
        self, pose_frames, events
    ) -> Tuple[str, Optional[float]]:
        if events.signal_time is None or events.race_end is None:
            return "", None

        race_dur = events.race_end - events.signal_time
        if race_dur <= 0:
            return "", None

        shoulder_x_series = []
        for pf in pose_frames:
            ts = get_timestamp(pf)
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            ls = get_lm(lm, "left_shoulder")
            rs = get_lm(lm, "right_shoulder")
            mid = midpoint(ls, rs)
            if mid is not None:
                shoulder_x_series.append((ts, mid[0]))

        if len(shoulder_x_series) >= 10:
            turn_time = self._detect_direction_change(shoulder_x_series, events, race_dur)
            if turn_time is not None:
                return "估算值（基于肩膀运动检测）", turn_time

        wrist_x_series = []
        for pf in pose_frames:
            ts = get_timestamp(pf)
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lw = get_lm(lm, "left_wrist")
            rw = get_lm(lm, "right_wrist")
            mid = midpoint(lw, rw)
            if mid is not None:
                wrist_x_series.append((ts, mid[0]))

        if len(wrist_x_series) >= 10:
            turn_time = self._detect_direction_change(wrist_x_series, events, race_dur)
            if turn_time is not None:
                return "估算值（基于手腕运动检测）", turn_time

        return "", None

    def _try_velocity_change_turn(
        self, pose_frames, events
    ) -> Tuple[str, Optional[float]]:
        if events.signal_time is None or events.race_end is None:
            return "", None

        race_dur = events.race_end - events.signal_time
        if race_dur <= 0:
            return "", None

        x_series = []
        for pf in pose_frames:
            ts = get_timestamp(pf)
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = get_lm(lm, "left_hip")
            rh = get_lm(lm, "right_hip")
            mid = midpoint(lh, rh)
            if mid is not None:
                x_series.append((ts, mid[0]))
            else:
                ls = get_lm(lm, "left_shoulder")
                rs = get_lm(lm, "right_shoulder")
                mid_s = midpoint(ls, rs)
                if mid_s is not None:
                    x_series.append((ts, mid_s[0]))

        if len(x_series) < 3:
            return "", None

        ts_arr = np.array([t for t, _ in x_series])
        x_arr = np.array([v for _, v in x_series])

        velocities = []
        for i in range(1, len(ts_arr)):
            dt = ts_arr[i] - ts_arr[i - 1]
            if dt <= 0:
                continue
            vx = (x_arr[i] - x_arr[i - 1]) / dt
            velocities.append((ts_arr[i], vx))

        if len(velocities) < 2:
            return "", None

        min_time = events.signal_time + race_dur * 0.2
        max_time = events.signal_time + race_dur * 0.8
        expected_turn = events.signal_time + race_dur / 2.0

        candidates = []
        for i in range(1, len(velocities)):
            ts, vx_curr = velocities[i]
            _, vx_prev = velocities[i - 1]

            if ts < min_time or ts > max_time:
                continue

            if vx_prev * vx_curr < 0:
                magnitude = abs(vx_prev - vx_curr)
                proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                candidates.append((ts, magnitude * max(0, proximity)))

        if candidates:
            candidates.sort(key=lambda c: -c[1])
            return "估算值（基于速度变化检测）", float(candidates[0][0])

        return "", None

    def _detect_direction_change(
        self, x_series: List[Tuple[float, float]], events, race_dur: float
    ) -> Optional[float]:
        if len(x_series) < 10:
            return None

        ts_arr = np.array([t for t, _ in x_series])
        x_arr = np.array([v for _, v in x_series])

        min_turn_time = events.signal_time + race_dur * 0.2
        max_turn_time = events.signal_time + race_dur * 0.8
        expected_turn = events.signal_time + race_dur / 2.0

        direction_change_threshold = 0.002

        candidates = []
        for i in range(1, len(ts_arr)):
            ts = ts_arr[i]
            if ts < min_turn_time or ts > max_turn_time:
                continue
            before = [(t, x) for t, x in zip(ts_arr[:i], x_arr[:i]) if min_turn_time <= t <= ts]
            after = [(t, x) for t, x in zip(ts_arr[i:], x_arr[i:]) if ts <= t <= max_turn_time]
            if len(before) < 3 or len(after) < 3:
                continue
            before_dx = np.mean(np.diff([x for _, x in before]))
            after_dx = np.mean(np.diff([x for _, x in after]))
            if (before_dx > direction_change_threshold and after_dx < -direction_change_threshold) or \
               (before_dx < -direction_change_threshold and after_dx > direction_change_threshold):
                direction_change = abs(before_dx - after_dx)
                proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                candidates.append((ts, direction_change * max(0, proximity)))

        if candidates:
            candidates.sort(key=lambda c: -c[1])
            best_ts = candidates[0][0]
            if abs(best_ts - expected_turn) < race_dur * 0.2:
                return float(best_ts)

        return None

    def _try_y_direction_turn(
        self, pose_frames, events
    ) -> Tuple[str, Optional[float]]:
        if events.signal_time is None or events.race_end is None:
            return "", None

        race_dur = events.race_end - events.signal_time
        if race_dur <= 0:
            return "", None

        hip_y_series = []
        for pf in pose_frames:
            ts = get_timestamp(pf)
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = get_lm(lm, "left_hip")
            rh = get_lm(lm, "right_hip")
            mid = midpoint(lh, rh)
            if mid is not None:
                hip_y_series.append((ts, mid[1]))

        if len(hip_y_series) < 10:
            return "", None

        ts_arr = np.array([t for t, _ in hip_y_series])
        y_arr = np.array([v for _, v in hip_y_series])

        dt = np.diff(ts_arr)
        dt[dt == 0] = 1e-6
        vy = np.diff(y_arr) / dt
        speed_y = np.abs(vy)

        kernel_size = 15
        if kernel_size % 2 == 0:
            kernel_size += 1
        if len(speed_y) >= kernel_size:
            speed_smooth = np.convolve(speed_y, np.ones(kernel_size) / kernel_size, mode='same')
        else:
            speed_smooth = speed_y

        speed_ts = ts_arr[1:]
        overall_median = np.median(speed_smooth) if len(speed_smooth) > 0 else 1.0

        min_time = events.signal_time + race_dur * 0.2
        max_time = events.signal_time + race_dur * 0.8
        expected_turn = events.signal_time + race_dur / 2.0

        candidates = []
        for i in range(1, len(speed_smooth) - 1):
            ts = speed_ts[i]
            if ts < min_time or ts > max_time:
                continue
            if speed_smooth[i] < speed_smooth[i - 1] and speed_smooth[i] < speed_smooth[i + 1]:
                speed_ratio = speed_smooth[i] / max(overall_median, 1e-10)
                if speed_ratio < 0.5:
                    proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                    candidates.append((ts, (1.0 - speed_ratio) * max(0, proximity)))

        if candidates:
            candidates.sort(key=lambda c: -c[1])
            return "估算值（基于纵向速度变化检测）", float(candidates[0][0])

        return "", None

    def _try_2d_velocity_turn(
        self, pose_frames, events
    ) -> Tuple[str, Optional[float]]:
        if events.signal_time is None or events.race_end is None:
            return "", None

        race_dur = events.race_end - events.signal_time
        if race_dur <= 0:
            return "", None

        x_series = []
        y_series = []
        for pf in pose_frames:
            ts = get_timestamp(pf)
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = get_lm(lm, "left_hip")
            rh = get_lm(lm, "right_hip")
            mid = midpoint(lh, rh)
            if mid is not None:
                x_series.append((ts, mid[0]))
                y_series.append((ts, mid[1]))

        if len(x_series) < 5 or len(y_series) < 5:
            return "", None

        ts_x = {t: v for t, v in x_series}
        ts_y = {t: v for t, v in y_series}
        common_ts = sorted(set(ts_x.keys()) & set(ts_y.keys()))

        if len(common_ts) < 5:
            return "", None

        x_vals = np.array([ts_x[t] for t in common_ts])
        y_vals = np.array([ts_y[t] for t in common_ts])
        ts_arr = np.array(common_ts)

        dt = np.diff(ts_arr)
        dt[dt == 0] = 1e-6
        vx = np.diff(x_vals) / dt
        vy = np.diff(y_vals) / dt

        speed_2d = np.sqrt(vx ** 2 + vy ** 2)
        angles = np.degrees(np.arctan2(vy, vx))

        kernel_size = 15
        if kernel_size % 2 == 0:
            kernel_size += 1
        if len(speed_2d) >= kernel_size:
            speed_smooth = np.convolve(speed_2d, np.ones(kernel_size) / kernel_size, mode='same')
        else:
            speed_smooth = speed_2d

        angle_diff = np.abs(np.diff(angles))
        angle_diff = np.minimum(angle_diff, 360 - angle_diff)

        min_time = events.signal_time + race_dur * 0.2
        max_time = events.signal_time + race_dur * 0.8
        expected_turn = events.signal_time + race_dur / 2.0

        candidates = []
        for i in range(1, len(speed_smooth) - 1):
            ts = ts_arr[min(i + 1, len(ts_arr) - 1)]
            if ts < min_time or ts > max_time:
                continue
            if speed_smooth[i] < speed_smooth[i - 1] and speed_smooth[i] < speed_smooth[i + 1]:
                angle_idx = min(i, len(angle_diff) - 1)
                angle_score = angle_diff[angle_idx] / 180.0 if angle_idx < len(angle_diff) else 0
                proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                candidates.append((ts, (0.5 + angle_score) * max(0, proximity)))

        if candidates:
            candidates.sort(key=lambda c: -c[1])
            return "估算值（基于2D速度变化检测）", float(candidates[0][0])

        return "", None
