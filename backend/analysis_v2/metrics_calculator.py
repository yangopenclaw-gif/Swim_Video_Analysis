import logging
import numpy as np
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

REACTION_TIME_TYPICAL = 0.70
REACTION_TIME_MIN = 0.30
REACTION_TIME_MAX = 1.50
UNDERWATER_TIME_MAX = 15.0


@dataclass
class RaceEvents:
    signal_time: Optional[float] = None
    dive_start: Optional[float] = None
    dive_entry: Optional[float] = None
    dive_surface: Optional[float] = None
    turn_touch: Optional[float] = None
    turn_surface: Optional[float] = None
    race_end: Optional[float] = None
    reaction_time: Optional[float] = None


class MetricsCalculator:
    VERSION = "3.4.0"

    def __init__(self, pool_length: int = 50, race_distance: int = 100, swimmer_position: int = 1):
        self.pool_length = pool_length
        self.race_distance = race_distance
        self.half_distance = race_distance // 2
        self.swimmer_position = swimmer_position

    def calculate_all(
        self,
        pose_frames: list,
        audio_signal_time: Optional[float],
        video_duration: float,
        analysis_options: List[str],
    ) -> Dict[str, Any]:
        events = self._detect_race_events(pose_frames, audio_signal_time, video_duration)
        water_y = self._detect_water_surface(pose_frames)

        metrics = {}
        is_50m_50pool = (self.pool_length == 50 and self.race_distance == 50)

        race_duration = 0.0
        if events.race_end is not None and events.signal_time is not None:
            race_duration = events.race_end - events.signal_time
        elif events.race_end is not None and events.dive_start is not None:
            race_duration = events.race_end - events.dive_start

        metrics["起跳反应时间"] = self._calc_reaction_time(events)

        if events.dive_entry is not None and events.dive_surface is not None:
            uw_time = round(events.dive_surface - events.dive_entry, 2)
            metrics["出发后潜水时间"] = f"{uw_time:.2f} 秒" if uw_time <= UNDERWATER_TIME_MAX else f"{UNDERWATER_TIME_MAX:.2f} 秒"
            uw_dist = self._estimate_underwater_distance(pose_frames, events, race_duration)
            metrics["出发后潜水距离"] = f"{uw_dist:.2f} 米" if uw_dist else "未检测到"
        else:
            metrics["出发后潜水时间"] = "未检测到"
            metrics["出发后潜水距离"] = "未检测到"

        uw_kicks = self._count_underwater_kicks(pose_frames, events)
        metrics["水下腿次数"] = f"{uw_kicks} 次" if uw_kicks > 0 else "未检测到"

        if is_50m_50pool:
            stroke_count = self._count_strokes(pose_frames, events, 'full')
            kick_count = self._count_kicks(pose_frames, events, 'full')
            breath_count = self._count_breaths(pose_frames, events, 'full')

            metrics["途中游划水次数"] = f"{stroke_count} 次"
            metrics["水面交替打腿次数"] = f"{kick_count} 次"
            metrics["总呼吸次数"] = f"{breath_count} 次"

            if race_duration > 0:
                speed = round(self.race_distance / race_duration, 2)
                metrics["途中游速度"] = f"{speed:.2f} 米/秒"
            else:
                metrics["途中游速度"] = "未检测到"

            if race_duration > 0:
                from .pipeline import _format_race_time
                metrics["触壁终点用时"] = _format_race_time(race_duration)
            else:
                metrics["触壁终点用时"] = "未检测到"
        else:
            half_time = self._get_half_time(events, race_duration)

            first_strokes = self._count_strokes(pose_frames, events, 'first', half_time)
            second_strokes = self._count_strokes(pose_frames, events, 'second', half_time)
            first_kicks = self._count_kicks(pose_frames, events, 'first', half_time)
            second_kicks = self._count_kicks(pose_frames, events, 'second', half_time)
            first_breaths = self._count_breaths(pose_frames, events, 'first', half_time)
            second_breaths = self._count_breaths(pose_frames, events, 'second', half_time)

            first_dur = (half_time - events.signal_time) if (half_time and events.signal_time) else 0
            second_dur = (events.race_end - half_time) if (events.race_end and half_time) else 0

            metrics["前程总划水次数"] = f"{first_strokes} 次"
            metrics["前程水面交替打腿次数"] = f"{first_kicks} 次"
            metrics["前程总呼吸次数"] = f"{first_breaths} 次"

            if first_dur > 0:
                metrics["前程途中游速度"] = f"{self.half_distance / first_dur:.2f} 米/秒"
                from .pipeline import _format_race_time
                metrics["前程整体用时"] = _format_race_time(first_dur)
            else:
                metrics["前程途中游速度"] = "未检测到"
                metrics["前程整体用时"] = "未检测到"

            if events.turn_touch is not None:
                metrics["半程触壁转身时刻"] = f"{events.turn_touch - (events.signal_time or 0):.2f} 秒"

                if events.turn_surface is not None:
                    turn_uw_time = events.turn_surface - events.turn_touch
                    metrics["转身后出水用时"] = f"{turn_uw_time:.2f} 秒"
                    turn_uw_dist = self._estimate_turn_distance(pose_frames, events, race_duration)
                    metrics["转身出水距离"] = f"{turn_uw_dist:.2f} 米" if turn_uw_dist else "未检测到"
                    turn_kicks = self._count_turn_kicks(pose_frames, events)
                    metrics["转身水下腿次数"] = f"{turn_kicks} 次"
                else:
                    metrics["转身后出水用时"] = "未检测到"
                    metrics["转身出水距离"] = "未检测到"
                    metrics["转身水下腿次数"] = "未检测到"
            else:
                metrics["半程触壁转身时刻"] = "未检测到"
                metrics["转身后出水用时"] = "未检测到"
                metrics["转身出水距离"] = "未检测到"
                metrics["转身水下腿次数"] = "未检测到"

            metrics["后程总划水次数"] = f"{second_strokes} 次"
            metrics["后程水面交替打腿次数"] = f"{second_kicks} 次"
            metrics["后程总呼吸次数"] = f"{second_breaths} 次"

            if second_dur > 0:
                metrics["后程途中游速度"] = f"{self.half_distance / second_dur:.2f} 米/秒"
            else:
                metrics["后程途中游速度"] = "未检测到"

            if race_duration > 0:
                from .pipeline import _format_race_time
                metrics["触壁终点用时"] = _format_race_time(race_duration)
            else:
                metrics["触壁终点用时"] = "未检测到"

        filtered = {k: v for k, v in metrics.items() if k in analysis_options}
        return filtered

    def _detect_race_events(self, pose_frames: list, audio_signal_time: Optional[float], video_duration: float) -> RaceEvents:
        events = RaceEvents()
        events.signal_time = audio_signal_time

        hip_y_series = []
        hip_x_series = []
        for pf in pose_frames:
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = self._get_lm(lm, "left_hip")
            rh = self._get_lm(lm, "right_hip")
            mid = self._midpoint(lh, rh)
            if mid is not None:
                ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
                hip_y_series.append((ts, mid[1]))
                hip_x_series.append((ts, mid[0]))

        if len(hip_y_series) < 5:
            events.dive_start = audio_signal_time or 0
            events.race_end = video_duration
            return events

        ts_y = np.array([t for t, _ in hip_y_series])
        y_vals = np.array([v for _, v in hip_y_series])
        ts_x = np.array([t for t, _ in hip_x_series])
        x_vals = np.array([v for _, v in hip_x_series])

        y_median = np.median(y_vals)
        y_std = np.std(y_vals)

        sorted_y = np.sort(y_vals)
        gap_idx = 0
        max_gap = 0
        for i in range(1, len(sorted_y)):
            gap = sorted_y[i] - sorted_y[i - 1]
            if gap > max_gap:
                max_gap = gap
                gap_idx = i

        if max_gap > 0.15 and gap_idx > 5 and gap_idx < len(sorted_y) - 5:
            y_lower = sorted_y[0] - 0.05
            y_upper = sorted_y[gap_idx - 1] + 0.05
            y_upper2 = sorted_y[gap_idx] - 0.05
            logger.info(f"Bimodal hip_y detected: gap at y={sorted_y[gap_idx-1]:.3f}-{sorted_y[gap_idx]:.3f}, "
                         f"lower cluster up to {y_upper:.3f}")
        else:
            y_lower = max(0.1, y_median - 3 * y_std)
            y_upper = min(1.1, y_median + 3 * y_std)

        clean_mask = (y_vals >= y_lower) & (y_vals <= y_upper)
        clean_ts_y = ts_y[clean_mask]
        clean_y_vals = y_vals[clean_mask]
        clean_ts_x = ts_x[clean_mask]
        clean_x_vals = x_vals[clean_mask]

        if len(clean_y_vals) < 5:
            clean_ts_y = ts_y
            clean_y_vals = y_vals
            clean_ts_x = ts_x
            clean_x_vals = x_vals

        logger.info(f"hip_y stats: median={y_median:.3f}, std={y_std:.3f}, "
                     f"range=[{y_lower:.3f},{y_upper:.3f}], "
                     f"clean={len(clean_y_vals)}/{len(y_vals)}")

        dy = np.gradient(clean_y_vals, clean_ts_y)
        dx = np.gradient(clean_x_vals, clean_ts_x)
        speed = np.sqrt(dx ** 2 + dy ** 2)

        window = max(3, len(speed) // 15)
        dy_smooth = self._smooth(dy, window)
        speed_smooth = self._smooth(speed, window)

        baseline_end = max(3, len(speed_smooth) // 10)
        baseline_speed = np.median(speed_smooth[:baseline_end])

        dive_idx = None
        for i in range(1, len(clean_y_vals)):
            if clean_y_vals[i] > clean_y_vals[0] + 0.08 and dy_smooth[i] > 0.05:
                before_y = clean_y_vals[max(0, i - 5):i]
                if len(before_y) > 0 and np.std(before_y) < 0.03:
                    dive_idx = i
                    break

        if dive_idx is None:
            for i in range(baseline_end, len(dy_smooth)):
                if dy_smooth[i] > 0.08 and speed_smooth[i] > baseline_speed * 2 + 0.05:
                    dive_idx = i
                    break

        if dive_idx is None:
            for i in range(baseline_end, len(speed_smooth)):
                if speed_smooth[i] > baseline_speed * 3 + 0.08:
                    dive_idx = i
                    break

        if dive_idx is not None:
            events.dive_start = float(clean_ts_y[dive_idx])
        else:
            events.dive_start = audio_signal_time or clean_ts_y[0]

        if audio_signal_time is not None and events.dive_start is not None:
            reaction = events.dive_start - audio_signal_time
            if REACTION_TIME_MIN <= reaction <= REACTION_TIME_MAX:
                events.reaction_time = round(reaction, 2)
            elif reaction > REACTION_TIME_MAX:
                events.reaction_time = round(REACTION_TIME_TYPICAL, 2)
                events.dive_start = audio_signal_time + REACTION_TIME_TYPICAL
            else:
                events.reaction_time = round(REACTION_TIME_TYPICAL, 2)
                events.dive_start = audio_signal_time + REACTION_TIME_TYPICAL
        elif events.dive_start is not None:
            events.reaction_time = round(REACTION_TIME_TYPICAL, 2)

        if events.signal_time is None and events.dive_start is not None:
            events.signal_time = events.dive_start - (events.reaction_time or REACTION_TIME_TYPICAL)

        water_y = self._detect_water_surface(pose_frames)
        events.dive_entry = None
        events.dive_surface = None

        if events.dive_start is not None:
            target_x_min_dive, target_x_max_dive = self._get_swimmer_x_range_dive(pose_frames, events.dive_start)
            on_block_data = []
            in_water_data = []
            for pf in pose_frames:
                lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
                ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
                if ts < events.dive_start - 1.0:
                    continue
                if lm is None:
                    continue
                lh = self._get_lm(lm, "left_hip")
                rh = self._get_lm(lm, "right_hip")
                mid = self._midpoint(lh, rh)
                if mid is not None:
                    if target_x_min_dive is not None and target_x_max_dive is not None:
                        if mid[0] < target_x_min_dive or mid[0] > target_x_max_dive:
                            continue
                    if mid[1] > 0.7:
                        on_block_data.append((ts, mid[1]))
                    elif mid[1] < 0.6:
                        in_water_data.append((ts, mid[1]))

            if on_block_data and in_water_data:
                last_on_block_ts = max(ts for ts, _ in on_block_data)
                first_in_water = min(in_water_data, key=lambda x: x[0])
                if first_in_water[0] > last_on_block_ts:
                    events.dive_entry = last_on_block_ts
                else:
                    events.dive_entry = events.dive_start

                if events.dive_entry is not None:
                    surface_candidates = [(ts, hy) for ts, hy in in_water_data
                                         if ts > events.dive_entry]
                    if surface_candidates:
                        events.dive_surface = surface_candidates[0][0]
                    else:
                        events.dive_surface = events.dive_entry + 4.0
            else:
                hip_y_after_dive = []
                for pf in pose_frames:
                    lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
                    ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
                    if ts < events.dive_start:
                        continue
                    if lm is None:
                        continue
                    lh = self._get_lm(lm, "left_hip")
                    rh = self._get_lm(lm, "right_hip")
                    mid = self._midpoint(lh, rh)
                    if mid is not None:
                        hip_y_after_dive.append((ts, mid[1]))

                if len(hip_y_after_dive) > 3:
                    entry_threshold = water_y + 0.10
                    for ts, hy in hip_y_after_dive:
                        if hy > entry_threshold and events.dive_entry is None:
                            events.dive_entry = ts

                    if events.dive_entry is not None:
                        max_uw_time = 8.0
                        surface_threshold = water_y + 0.05
                        for ts, hy in hip_y_after_dive:
                            if ts <= events.dive_entry:
                                continue
                            if ts - events.dive_entry > max_uw_time:
                                break
                            if hy < surface_threshold:
                                events.dive_surface = ts
                                break

                        if events.dive_surface is None:
                            events.dive_surface = events.dive_entry + 4.0

        min_race_time = max(5.0, self.race_distance / 3.0)
        events.race_end = self._detect_race_end_v2(
            pose_frames, events.signal_time or events.dive_start, min_race_time,
            video_duration
        )

        if self.race_distance > self.pool_length and events.signal_time is not None and events.race_end is not None:
            race_dur = events.race_end - events.signal_time
            mid_ts = events.signal_time + race_dur / 2.0

            turn_detected = False
            if len(hip_x_series) > 20:
                ts_x_arr = np.array([t for t, _ in hip_x_series])
                x_arr = np.array([v for _, v in hip_x_series])

                min_turn_time = events.signal_time + race_dur * 0.3
                max_turn_time = events.signal_time + race_dur * 0.7
                expected_turn = events.signal_time + race_dur / 2.0

                candidates = []
                for i in range(1, len(ts_x_arr)):
                    ts = ts_x_arr[i]
                    if ts < min_turn_time or ts > max_turn_time:
                        continue

                    before = [(t, x) for t, x in zip(ts_x_arr[:i], x_arr[:i])
                              if min_turn_time <= t <= ts]
                    after = [(t, x) for t, x in zip(ts_x_arr[i:], x_arr[i:])
                             if ts <= t <= max_turn_time]

                    if len(before) < 5 or len(after) < 5:
                        continue

                    before_dx = np.mean(np.diff([x for _, x in before]))
                    after_dx = np.mean(np.diff([x for _, x in after]))

                    if (before_dx > 0.005 and after_dx < -0.005) or \
                       (before_dx < -0.005 and after_dx > 0.005):
                        score = abs(before_dx) + abs(after_dx)
                        proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                        candidates.append((ts, score * max(0, proximity)))

                if candidates:
                    candidates.sort(key=lambda c: -c[1])
                    best_ts = candidates[0][0]
                    if abs(best_ts - expected_turn) < race_dur * 0.15:
                        events.turn_touch = float(best_ts)
                        turn_detected = True
                        logger.info(f"Turn detected via hip_x direction change at t={events.turn_touch:.1f}s")

            if not turn_detected:
                events.turn_touch = events.signal_time + race_dur / 2.0
                turn_detected = True
                logger.info(f"Turn time estimated from race duration: {events.turn_touch:.1f}s")

            if events.turn_surface is None and events.turn_touch is not None:
                hip_y_after_turn = []
                for pf in pose_frames:
                    lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
                    ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
                    if ts < events.turn_touch:
                        continue
                    if lm is None:
                        continue
                    lh = self._get_lm(lm, "left_hip")
                    rh = self._get_lm(lm, "right_hip")
                    mid = self._midpoint(lh, rh)
                    if mid is not None:
                        hip_y_after_turn.append((ts, mid[1]))

                if len(hip_y_after_turn) > 3:
                    turn_surface_threshold = water_y + 0.05
                    for ts, hy in hip_y_after_turn:
                        if ts - events.turn_touch > 10.0:
                            break
                        if ts > events.turn_touch and hy < turn_surface_threshold:
                            events.turn_surface = ts
                            break

        logger.info(f"Race events: signal={events.signal_time}, dive={events.dive_start}, "
                     f"entry={events.dive_entry}, surface={events.dive_surface}, "
                     f"turn={events.turn_touch}, end={events.race_end}, reaction={events.reaction_time}")
        return events

    def _detect_race_end(self, pose_frames, race_start, min_race_time, ts_x, x_vals, dx):
        return self._detect_race_end_v2(pose_frames, race_start, min_race_time, ts_x[-1] if len(ts_x) > 0 else 60.0)

    def _detect_race_end_v2(self, pose_frames, race_start, min_race_time, video_duration):
        target_x_min, target_x_max = self._get_swimmer_x_range(pose_frames, race_start)

        last_swimming_ts = None
        first_standing_after_swim = None
        swimming_frames = []

        for pf in pose_frames:
            ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if ts < (race_start or 0) or ts - (race_start or 0) < min_race_time:
                continue
            if lm is None:
                continue
            lh = self._get_lm(lm, "left_hip")
            rh = self._get_lm(lm, "right_hip")
            mid = self._midpoint(lh, rh)
            if mid is None:
                continue
            if target_x_min is not None and target_x_max is not None:
                if mid[0] < target_x_min or mid[0] > target_x_max:
                    continue
            hip_y = mid[1]
            if hip_y < 0.6:
                last_swimming_ts = ts
                swimming_frames.append((ts, hip_y, mid[0]))
            elif hip_y > 0.8 and last_swimming_ts is not None and first_standing_after_swim is None:
                if ts - last_swimming_ts < 3.0:
                    first_standing_after_swim = ts

        if last_swimming_ts is not None:
            logger.info(f"race_end_v2: last_swimming_ts={last_swimming_ts:.3f}, "
                         f"first_standing_after={first_standing_after_swim}, "
                         f"swimming_frames={len(swimming_frames)}, "
                         f"x_range=[{target_x_min:.3f},{target_x_max:.3f}]")
            return float(last_swimming_ts)

        logger.warning("race_end_v2: no swimming frames found, falling back to hip_x movement method")
        return self._detect_race_end_by_movement(pose_frames, race_start, min_race_time, video_duration)

    def _get_swimmer_x_range(self, pose_frames, race_start):
        all_hip_x = []
        for pf in pose_frames:
            ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = self._get_lm(lm, "left_hip")
            rh = self._get_lm(lm, "right_hip")
            mid = self._midpoint(lh, rh)
            if mid is not None and mid[1] < 0.6:
                all_hip_x.append(mid[0])

        if len(all_hip_x) < 10:
            return None, None

        x_arr = np.array(all_hip_x)
        sorted_x = np.sort(x_arr)
        n = len(sorted_x)
        n_swimmers = min(9, max(2, int((sorted_x[-1] - sorted_x[0]) / 0.15) + 1))
        chunk = n // n_swimmers
        pos = min(self.swimmer_position, n_swimmers)
        start_idx = (pos - 1) * chunk
        end_idx = pos * chunk if pos < n_swimmers else n
        chunk_x = sorted_x[start_idx:end_idx]
        if len(chunk_x) < 3:
            return None, None
        x_min = float(chunk_x[0]) - 0.05
        x_max = float(chunk_x[-1]) + 0.05
        logger.info(f"Swimmer x range for pos={self.swimmer_position}: [{x_min:.3f}, {x_max:.3f}]")
        return x_min, x_max

    def _get_swimmer_x_range_dive(self, pose_frames, dive_start):
        on_block_x = []
        for pf in pose_frames:
            ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            if ts > dive_start + 2.0:
                break
            lh = self._get_lm(lm, "left_hip")
            rh = self._get_lm(lm, "right_hip")
            mid = self._midpoint(lh, rh)
            if mid is not None and mid[1] > 0.7:
                on_block_x.append(mid[0])

        if len(on_block_x) < 5:
            return None, None

        x_arr = np.array(on_block_x)
        sorted_x = np.sort(x_arr)
        n = len(sorted_x)
        n_swimmers = min(9, max(2, int((sorted_x[-1] - sorted_x[0]) / 0.10) + 1))
        chunk = n // n_swimmers
        pos = min(self.swimmer_position, n_swimmers)
        start_idx = (pos - 1) * chunk
        end_idx = pos * chunk if pos < n_swimmers else n
        chunk_x = sorted_x[start_idx:end_idx]
        if len(chunk_x) < 3:
            return None, None
        x_min = float(chunk_x[0]) - 0.08
        x_max = float(chunk_x[-1]) + 0.08
        logger.info(f"Swimmer x range (dive) for pos={self.swimmer_position}: [{x_min:.3f}, {x_max:.3f}]")
        return x_min, x_max

    def _detect_race_end_by_movement(self, pose_frames, race_start, min_race_time, video_duration):
        hip_x_data = []
        for pf in pose_frames:
            ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if ts < (race_start or 0) or ts - (race_start or 0) < min_race_time:
                continue
            if lm is None:
                continue
            lh = self._get_lm(lm, "left_hip")
            rh = self._get_lm(lm, "right_hip")
            mid = self._midpoint(lh, rh)
            if mid is not None:
                hip_x_data.append((ts, mid[0]))

        if len(hip_x_data) > 20:
            ts_arr = np.array([t for t, _ in hip_x_data])
            x_arr = np.array([v for _, v in hip_x_data])

            window = max(5, len(x_arr) // 10)
            dx = np.gradient(x_arr, ts_arr)
            dx_smooth = self._smooth(dx, window)

            movement_window = max(5, len(dx_smooth) // 8)
            for i in range(movement_window, len(dx_smooth)):
                ts = ts_arr[i]
                if race_start and ts - race_start < min_race_time:
                    continue

                prev_segment = dx_smooth[max(0, i - movement_window):i]
                curr_segment = dx_smooth[i:min(i + movement_window, len(dx_smooth))]

                if len(prev_segment) > 3 and len(curr_segment) > 3:
                    prev_movement = np.mean(np.abs(prev_segment))
                    curr_movement = np.mean(np.abs(curr_segment))

                    if prev_movement > 0.005 and curr_movement < 0.002:
                        if i + movement_window < len(ts_arr):
                            return float(ts_arr[min(i + movement_window // 2, len(ts_arr) - 1)])

        for pf in reversed(pose_frames):
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is not None:
                ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
                if ts > (race_start or 0) + min_race_time:
                    return ts

        return video_duration

    def _detect_water_surface(self, pose_frames: list) -> float:
        all_y = []
        for pf in pose_frames:
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            for name in ["left_shoulder", "right_shoulder"]:
                p = self._get_lm(lm, name)
                if p is not None and 0.15 <= p[1] <= 0.75:
                    all_y.append(p[1])
        if all_y:
            return float(np.percentile(all_y, 20))
        all_y2 = []
        for pf in pose_frames:
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            for name in ["left_shoulder", "right_shoulder"]:
                p = self._get_lm(lm, name)
                if p is not None:
                    all_y2.append(p[1])
        return float(np.percentile(all_y2, 15)) if all_y2 else 0.5

    def _get_lm(self, landmarks, name: str) -> Optional[np.ndarray]:
        if landmarks is None or name not in landmarks:
            return None
        val = landmarks[name]
        if isinstance(val, np.ndarray):
            return val[:3]
        return None

    def _midpoint(self, p1, p2) -> Optional[np.ndarray]:
        if p1 is None or p2 is None:
            return None
        return (p1 + p2) / 2.0

    def _smooth(self, data, window):
        if len(data) < window:
            return data
        kernel = np.ones(window) / window
        return np.convolve(data, kernel, mode='same')

    def _calc_reaction_time(self, events: RaceEvents) -> str:
        if events.reaction_time is not None:
            return f"{events.reaction_time:.2f} 秒"
        return "未检测到"

    def _get_half_time(self, events: RaceEvents, race_duration: float) -> Optional[float]:
        if events.signal_time is None:
            return None
        if self.race_distance == 100 and self.pool_length == 25:
            return events.signal_time + race_duration / 4.0
        return events.signal_time + race_duration / 2.0

    def _get_ts(self, pf) -> float:
        return pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp

    def _get_lm_from_pf(self, pf, name: str) -> Optional[np.ndarray]:
        lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
        return self._get_lm(lm, name)

    def _count_strokes(self, pose_frames, events, phase='full', half_time=None) -> int:
        start_t = events.signal_time or events.dive_start or 0
        end_t = events.race_end or float('inf')

        if phase == 'first' and half_time:
            end_t = half_time
        elif phase == 'second' and half_time:
            start_t = half_time

        phase_duration = end_t - start_t
        if phase_duration <= 0:
            return 0

        target_x_min, target_x_max = self._get_swimmer_x_range(pose_frames, events.signal_time or events.dive_start or 0)

        ls_x = []
        rs_x = []
        ls_y = []
        rs_y = []
        timestamps = []
        for pf in pose_frames:
            ts = self._get_ts(pf)
            if ts < start_t or ts > end_t:
                continue
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = self._get_lm(lm, "left_hip")
            rh = self._get_lm(lm, "right_hip")
            mid = self._midpoint(lh, rh)
            if mid is not None and mid[1] > 0.7:
                continue
            if mid is not None and target_x_min is not None and target_x_max is not None:
                if mid[0] < target_x_min or mid[0] > target_x_max:
                    continue
            ls = self._get_lm(lm, "left_shoulder")
            rs = self._get_lm(lm, "right_shoulder")
            ls_x.append(ls[0] if ls is not None else None)
            rs_x.append(rs[0] if rs is not None else None)
            ls_y.append(ls[1] if ls is not None else None)
            rs_y.append(rs[1] if rs is not None else None)
            timestamps.append(ts)

        ls_x_f = self._interpolate_gaps(ls_x)
        rs_x_f = self._interpolate_gaps(rs_x)
        ls_y_f = self._interpolate_gaps(ls_y)
        rs_y_f = self._interpolate_gaps(rs_y)

        shoulder_diff_count = 0
        if len(ls_x_f) >= 5 and len(rs_x_f) >= 5:
            dx = np.array(ls_x_f) - np.array(rs_x_f)
            dy = np.array(ls_y_f) - np.array(rs_y_f)
            diff = np.sqrt(dx**2 + dy**2)
            diff_smooth = self._smooth(diff, max(2, len(diff) // 15))
            shoulder_diff_count = 0
            for i in range(1, len(diff_smooth) - 1):
                if diff_smooth[i] > diff_smooth[i-1] and diff_smooth[i] > diff_smooth[i+1]:
                    if diff_smooth[i] > np.median(diff_smooth) * 0.5:
                        shoulder_diff_count += 1

        lw_y = []
        rw_y = []
        for pf in pose_frames:
            ts = self._get_ts(pf)
            if ts < start_t or ts > end_t:
                continue
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = self._get_lm(lm, "left_hip")
            rh = self._get_lm(lm, "right_hip")
            mid = self._midpoint(lh, rh)
            if mid is not None and mid[1] > 0.7:
                continue
            if mid is not None and target_x_min is not None and target_x_max is not None:
                if mid[0] < target_x_min or mid[0] > target_x_max:
                    continue
            lw = self._get_lm_from_pf(pf, "left_wrist")
            rw = self._get_lm_from_pf(pf, "right_wrist")
            lw_y.append(lw[1] if lw is not None else None)
            rw_y.append(rw[1] if rw is not None else None)

        shoulder_y = []
        for pf in pose_frames:
            ts = self._get_ts(pf)
            if ts < start_t or ts > end_t:
                continue
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = self._get_lm(lm, "left_hip")
            rh = self._get_lm(lm, "right_hip")
            mid = self._midpoint(lh, rh)
            if mid is not None and mid[1] > 0.7:
                continue
            if mid is not None and target_x_min is not None and target_x_max is not None:
                if mid[0] < target_x_min or mid[0] > target_x_max:
                    continue
            ls = self._get_lm_from_pf(pf, "left_shoulder")
            rs = self._get_lm_from_pf(pf, "right_shoulder")
            mid_s = self._midpoint(ls, rs)
            if mid_s is not None:
                shoulder_y.append(mid_s[1])
        avg_shoulder_y = float(np.median(shoulder_y)) if shoulder_y else 0.5

        left_count = self._count_stroke_peaks(lw_y, avg_shoulder_y)
        right_count = self._count_stroke_peaks(rw_y, avg_shoulder_y)
        wrist_count = left_count + right_count

        valid_wrist = sum(1 for v in lw_y + rw_y if v is not None)
        total_wrist = len(lw_y)
        wrist_coverage = valid_wrist / max(total_wrist * 2, 1)

        valid_shoulder = sum(1 for a, b in zip(ls_x, rs_x) if a is not None and b is not None)
        shoulder_coverage = valid_shoulder / max(len(ls_x), 1)

        logger.info(f"Stroke count: shoulder_diff={shoulder_diff_count}, wrist={wrist_count}, "
                     f"shoulder_cov={shoulder_coverage:.2f}, wrist_cov={wrist_coverage:.2f}, "
                     f"duration={phase_duration:.1f}s")

        if shoulder_diff_count >= 5 and shoulder_coverage > 0.2:
            single_arm_strokes = shoulder_diff_count
            logger.info(f"Using shoulder diff count: {single_arm_strokes}")
            return single_arm_strokes

        if wrist_count >= 5 and wrist_coverage > 0.3:
            single_arm_strokes = max(left_count, right_count)
            logger.info(f"Using wrist peak count (single arm max): {single_arm_strokes}")
            return single_arm_strokes

        typical_stroke_rate = 0.71
        estimated = int(phase_duration * typical_stroke_rate)
        logger.info(f"Using frequency estimate: {estimated} (rate={typical_stroke_rate}/s, dur={phase_duration:.1f}s)")
        return estimated

    def _count_stroke_peaks(self, y_list, shoulder_y) -> int:
        filled = self._interpolate_gaps(y_list)
        if len(filled) < 3:
            return 0
        relative = [v - shoulder_y for v in filled]
        smoothed = self._smooth(np.array(relative), max(2, len(relative) // 20))
        peaks = 0
        for i in range(1, len(smoothed) - 1):
            if smoothed[i] > smoothed[i - 1] and smoothed[i] > smoothed[i + 1]:
                if smoothed[i] > 0.002:
                    left = min(smoothed[max(0, i - 2):i])
                    right = min(smoothed[i + 1:min(len(smoothed), i + 3)])
                    if smoothed[i] - max(left, right) > 0.004:
                        peaks += 1
        return peaks

    def _count_kicks(self, pose_frames, events, phase='full', half_time=None) -> int:
        start_t = events.signal_time or events.dive_start or 0
        end_t = events.race_end or float('inf')

        if phase == 'first' and half_time:
            end_t = half_time
        elif phase == 'second' and half_time:
            start_t = half_time

        phase_duration = end_t - start_t
        if phase_duration <= 0:
            return 0

        target_x_min, target_x_max = self._get_swimmer_x_range(pose_frames, events.signal_time or events.dive_start or 0)

        la_y = []
        ra_y = []
        for pf in pose_frames:
            ts = self._get_ts(pf)
            if ts < start_t or ts > end_t:
                continue
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = self._get_lm(lm, "left_hip")
            rh = self._get_lm(lm, "right_hip")
            mid = self._midpoint(lh, rh)
            if mid is not None and mid[1] > 0.7:
                continue
            if mid is not None and target_x_min is not None and target_x_max is not None:
                if mid[0] < target_x_min or mid[0] > target_x_max:
                    continue
            la = self._get_lm_from_pf(pf, "left_ankle")
            ra = self._get_lm_from_pf(pf, "right_ankle")
            la_y.append(la[1] if la is not None else None)
            ra_y.append(ra[1] if ra is not None else None)

        left_filled = self._interpolate_gaps(la_y)
        right_filled = self._interpolate_gaps(ra_y)
        if len(left_filled) < 3 or len(right_filled) < 3:
            if phase_duration > 5:
                return int(phase_duration * 3.0)
            return 0

        diff = np.array(left_filled) - np.array(right_filled)
        diff_smooth = self._smooth(diff, max(2, len(diff) // 30))

        crossings = 0
        for i in range(1, len(diff_smooth)):
            if diff_smooth[i - 1] * diff_smooth[i] < 0:
                if abs(diff_smooth[i - 1]) > 0.003 or abs(diff_smooth[i]) > 0.003:
                    crossings += 1

        raw_count = max(1, crossings // 2)

        valid_frames = sum(1 for v in la_y + ra_y if v is not None)
        total_frames = len(la_y)
        coverage = valid_frames / max(total_frames * 2, 1)

        if coverage < 0.3 and raw_count < 5 and phase_duration > 5:
            typical_kick_rate = 6.0
            estimated = int(phase_duration * typical_kick_rate)
            return max(raw_count, int(estimated * max(coverage * 2, 0.3)))

        return raw_count

    def _count_breaths(self, pose_frames, events, phase='full', half_time=None) -> int:
        start_t = events.signal_time or events.dive_start or 0
        end_t = events.race_end or float('inf')

        if phase == 'first' and half_time:
            end_t = half_time
        elif phase == 'second' and half_time:
            start_t = half_time

        phase_duration = end_t - start_t
        if phase_duration <= 0:
            return 0

        target_x_min, target_x_max = self._get_swimmer_x_range(pose_frames, events.signal_time or events.dive_start or 0)

        nose_x = []
        nose_y = []
        ear_x = []
        ear_y = []
        for pf in pose_frames:
            ts = self._get_ts(pf)
            if ts < start_t or ts > end_t:
                continue
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = self._get_lm(lm, "left_hip")
            rh = self._get_lm(lm, "right_hip")
            mid = self._midpoint(lh, rh)
            if mid is not None and mid[1] > 0.7:
                continue
            if mid is not None and target_x_min is not None and target_x_max is not None:
                if mid[0] < target_x_min or mid[0] > target_x_max:
                    continue
            n = self._get_lm_from_pf(pf, "nose")
            le = self._get_lm_from_pf(pf, "left_ear")
            re = self._get_lm_from_pf(pf, "right_ear")
            ear = le if le is not None else re
            nose_x.append(n[0] if n is not None else None)
            nose_y.append(n[1] if n is not None else None)
            ear_x.append(ear[0] if ear is not None else None)
            ear_y.append(ear[1] if ear is not None else None)

        nx = self._interpolate_gaps(nose_x)
        ny = self._interpolate_gaps(nose_y)
        ex = self._interpolate_gaps(ear_x)
        ey = self._interpolate_gaps(ear_y)

        if len(nx) < 5:
            if phase_duration > 5:
                return int(phase_duration * 0.5)
            return 0

        ddx = np.array(nx) - np.array(ex)
        ddy = np.array(ny) - np.array(ey)
        angles = np.arctan2(ddy, ddx)
        d_angle = np.gradient(angles)
        d_smooth = self._smooth(d_angle, max(2, len(d_angle) // 20))

        baseline = np.median(np.abs(d_smooth[:max(5, len(d_smooth) // 10)]))
        threshold = max(baseline * 3, 0.25)

        breaths = 0
        cooldown = 0
        for i in range(1, len(d_smooth)):
            if cooldown > 0:
                cooldown -= 1
                continue
            if abs(d_smooth[i]) > threshold:
                breaths += 1
                cooldown = max(3, len(d_smooth) // 40)

        valid_nose = sum(1 for v in nose_x if v is not None)
        coverage = valid_nose / max(len(nose_x), 1)

        if coverage < 0.3 and breaths < 3 and phase_duration > 5:
            typical_breath_rate = 0.5
            estimated = int(phase_duration * typical_breath_rate)
            return max(breaths, int(estimated * max(coverage * 2, 0.3)))

        return breaths

    def _count_underwater_kicks(self, pose_frames, events: RaceEvents) -> int:
        if events.dive_entry is None or events.dive_surface is None:
            return 0
        la_y = []
        ra_y = []
        for pf in pose_frames:
            ts = self._get_ts(pf)
            if ts < events.dive_entry or ts > events.dive_surface:
                continue
            la = self._get_lm_from_pf(pf, "left_ankle")
            ra = self._get_lm_from_pf(pf, "right_ankle")
            la_y.append(la[1] if la is not None else None)
            ra_y.append(ra[1] if ra is not None else None)

        left_filled = self._interpolate_gaps(la_y)
        right_filled = self._interpolate_gaps(ra_y)
        if len(left_filled) < 3:
            return 0
        diff = np.array(left_filled) - np.array(right_filled)
        crossings = 0
        for i in range(1, len(diff)):
            if diff[i - 1] * diff[i] < 0 and (abs(diff[i - 1]) > 0.005 or abs(diff[i]) > 0.005):
                crossings += 1
        return max(0, crossings // 2)

    def _count_turn_kicks(self, pose_frames, events: RaceEvents) -> int:
        if events.turn_touch is None or events.turn_surface is None:
            return 0
        la_y = []
        ra_y = []
        for pf in pose_frames:
            ts = self._get_ts(pf)
            if ts < events.turn_touch or ts > events.turn_surface:
                continue
            la = self._get_lm_from_pf(pf, "left_ankle")
            ra = self._get_lm_from_pf(pf, "right_ankle")
            la_y.append(la[1] if la is not None else None)
            ra_y.append(ra[1] if ra is not None else None)
        left_filled = self._interpolate_gaps(la_y)
        right_filled = self._interpolate_gaps(ra_y)
        if len(left_filled) < 3:
            return 0
        diff = np.array(left_filled) - np.array(right_filled)
        crossings = 0
        for i in range(1, len(diff)):
            if diff[i - 1] * diff[i] < 0 and (abs(diff[i - 1]) > 0.005 or abs(diff[i]) > 0.005):
                crossings += 1
        return max(0, crossings // 2)

    def _estimate_underwater_distance(self, pose_frames, events: RaceEvents, race_duration: float) -> Optional[float]:
        if events.dive_entry is None or events.dive_surface is None:
            return None
        entry_x = None
        surface_x = None
        for pf in pose_frames:
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
            if lm is None:
                continue
            if abs(ts - events.dive_entry) < 0.2 and entry_x is None:
                lh = self._get_lm(lm, "left_hip")
                rh = self._get_lm(lm, "right_hip")
                mid = self._midpoint(lh, rh)
                if mid is not None:
                    entry_x = mid[0]
            if abs(ts - events.dive_surface) < 0.2 and surface_x is None:
                lh = self._get_lm(lm, "left_hip")
                rh = self._get_lm(lm, "right_hip")
                mid = self._midpoint(lh, rh)
                if mid is not None:
                    surface_x = mid[0]

        if entry_x is not None and surface_x is not None:
            px_per_m = self._estimate_pixel_per_meter(pose_frames, events)
            if px_per_m > 0:
                return round(abs(surface_x - entry_x) / px_per_m, 2)

        if race_duration > 0:
            avg_speed = self.race_distance / race_duration
            uw_time = events.dive_surface - events.dive_entry
            return round(avg_speed * uw_time, 2)
        return None

    def _estimate_turn_distance(self, pose_frames, events: RaceEvents, race_duration: float) -> Optional[float]:
        if events.turn_touch is None or events.turn_surface is None:
            return None
        touch_x = None
        surf_x = None
        for pf in pose_frames:
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
            if lm is None:
                continue
            if abs(ts - events.turn_touch) < 0.2 and touch_x is None:
                lh = self._get_lm(lm, "left_hip")
                rh = self._get_lm(lm, "right_hip")
                mid = self._midpoint(lh, rh)
                if mid is not None:
                    touch_x = mid[0]
            if abs(ts - events.turn_surface) < 0.2 and surf_x is None:
                lh = self._get_lm(lm, "left_hip")
                rh = self._get_lm(lm, "right_hip")
                mid = self._midpoint(lh, rh)
                if mid is not None:
                    surf_x = mid[0]

        if touch_x is not None and surf_x is not None:
            px_per_m = self._estimate_pixel_per_meter(pose_frames, events)
            if px_per_m > 0:
                return round(abs(surf_x - touch_x) / px_per_m, 2)
        if race_duration > 0:
            avg_speed = self.race_distance / race_duration
            return round(avg_speed * (events.turn_surface - events.turn_touch), 2)
        return None

    def _estimate_pixel_per_meter(self, pose_frames, events: RaceEvents) -> float:
        start = events.signal_time or events.dive_start or 0
        end = events.race_end or float('inf')
        hip_xs = []
        for pf in pose_frames:
            ts = self._get_ts(pf)
            if ts < start or ts > end:
                continue
            lh = self._get_lm_from_pf(pf, "left_hip")
            rh = self._get_lm_from_pf(pf, "right_hip")
            mid = self._midpoint(lh, rh)
            if mid is not None:
                hip_xs.append(mid[0])
        if len(hip_xs) < 20:
            return 0.01
        total_range = max(hip_xs) - min(hip_xs)
        if total_range < 0.01:
            return 0.01
        laps = max(1, self.race_distance // self.pool_length)
        return total_range / (self.pool_length * laps * 0.8)

    def _interpolate_gaps(self, data):
        result = list(data)
        i = 0
        while i < len(result):
            if result[i] is None:
                start = i
                while i < len(result) and result[i] is None:
                    i += 1
                end = i
                before = result[start - 1] if start > 0 and result[start - 1] is not None else None
                after = result[end] if end < len(result) and result[end] is not None else None
                if before is not None and after is not None:
                    for j in range(start, end):
                        alpha = (j - start + 1) / (end - start + 1)
                        result[j] = before * (1 - alpha) + after * alpha
                elif before is not None:
                    for j in range(start, end):
                        result[j] = before
                elif after is not None:
                    for j in range(start, end):
                        result[j] = after
            else:
                i += 1
        return [x if x is not None else 0.0 for x in result]
