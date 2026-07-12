import logging
import numpy as np
from typing import Optional, Dict, Any

from .base_module import AnalysisModule
from .shared import AnalysisContext, ModuleResult, AccuracyInfo
from .utils import get_lm, midpoint, get_timestamp, detect_water_surface

logger = logging.getLogger(__name__)


class UnderwaterPhaseDetector(AnalysisModule):
    VERSION = "4.0.0"

    @property
    def name(self) -> str:
        return "水下阶段"

    def analyze(self, context: AnalysisContext) -> ModuleResult:
        pose_frames = list(context.pose_frames)
        events = context.events
        params = context.detection_params.underwater_phase

        water_y = context.water_y
        if water_y == 0.5:
            water_y = detect_water_surface(pose_frames)

        dive_entry = events.dive_entry
        dive_surface = events.dive_surface

        if dive_entry is None:
            dive_entry = self._detect_dive_entry(pose_frames, events.dive_start, water_y)
        if dive_surface is None:
            dive_surface = self._detect_dive_surface(pose_frames, dive_entry, water_y)

        metrics = {}
        if dive_entry is not None and dive_surface is not None:
            uw_time = round(dive_surface - dive_entry, 2)
            metrics["出发后潜水时间"] = f"{uw_time:.2f} 秒"
        else:
            metrics["出发后潜水时间"] = "未检测到"

        uw_dist = self._estimate_underwater_distance(pose_frames, events, context.race_duration)
        metrics["出发后潜水距离"] = f"{uw_dist:.2f} 米" if uw_dist else "未检测到"

        uw_kicks = self._count_underwater_kicks(pose_frames, dive_entry, dive_surface)
        metrics["水下腿次数"] = f"{uw_kicks} 次" if uw_kicks > 0 else "未检测到"

        module_events = {}
        if dive_entry is not None:
            module_events["dive_entry"] = dive_entry
        if dive_surface is not None:
            module_events["dive_surface"] = dive_surface

        confidence = 1.0 if dive_entry is not None and dive_surface is not None else 0.0
        accuracy = AccuracyInfo(
            confidence=round(confidence, 3),
            coverage=1.0 if dive_entry is not None else 0.0,
            quality="高" if confidence >= 0.7 else ("中" if confidence >= 0.4 else "低"),
            low_confidence=confidence < 0.3,
            warnings=[] if confidence >= 0.3 else ["水下阶段检测置信度低"],
        )

        return ModuleResult(
            module_name=self.name,
            metrics=metrics,
            module_events=module_events,
            accuracy=accuracy,
            detection_method="髋部y穿越水面+速度变化",
        )

    def _detect_dive_entry(self, pose_frames, dive_start, water_y):
        if dive_start is None or not pose_frames:
            return None
        for pf in pose_frames:
            ts = get_timestamp(pf)
            if ts < dive_start:
                continue
            if ts > dive_start + 5.0:
                break
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = get_lm(lm, "left_hip")
            rh = get_lm(lm, "right_hip")
            mid = midpoint(lh, rh)
            if mid is not None and mid[1] < water_y:
                return float(ts)
        return None

    def _detect_dive_surface(self, pose_frames, dive_entry, water_y):
        if dive_entry is None or not pose_frames:
            return None
        surface_threshold = water_y + 0.03
        surface_count = 0
        min_surface_frames = 2
        for pf in pose_frames:
            ts = get_timestamp(pf)
            if ts < dive_entry:
                continue
            if ts > dive_entry + 15.0:
                break
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = get_lm(lm, "left_hip")
            rh = get_lm(lm, "right_hip")
            mid = midpoint(lh, rh)
            if mid is not None:
                if mid[1] < surface_threshold:
                    surface_count += 1
                    if surface_count >= min_surface_frames:
                        return float(ts)
                else:
                    surface_count = 0
        return None

    def _count_underwater_kicks(self, pose_frames, dive_entry, dive_surface):
        if dive_entry is None or dive_surface is None:
            return 0
        from .kick_counter import KickCounter
        la_y, ra_y = [], []
        for pf in pose_frames:
            ts = get_timestamp(pf)
            if ts < dive_entry or ts > dive_surface:
                continue
            la = get_lm(pf.get("landmarks", {}) if isinstance(pf, dict) else getattr(pf, 'landmarks', {}), "left_ankle")
            ra = get_lm(pf.get("landmarks", {}) if isinstance(pf, dict) else getattr(pf, 'landmarks', {}), "right_ankle")
            la_y.append(la[1] if la is not None else None)
            ra_y.append(ra[1] if ra is not None else None)

        return self._count_crossings(la_y, ra_y)

    def _count_crossings(self, left_y, right_y, min_segment=3):
        segments = []
        curr_l, curr_r = [], []
        for l, r in zip(left_y, right_y):
            if l is not None and r is not None:
                curr_l.append(l)
                curr_r.append(r)
            else:
                if len(curr_l) >= min_segment:
                    segments.append((curr_l, curr_r))
                curr_l, curr_r = [], []
        if len(curr_l) >= min_segment:
            segments.append((curr_l, curr_r))

        total = 0
        for l_seg, r_seg in segments:
            diff = np.array(l_seg) - np.array(r_seg)
            if len(diff) < min_segment:
                continue
            if len(diff) > 5:
                diff_smooth = np.convolve(diff, np.ones(max(2, len(diff) // 40)) / max(2, len(diff) // 40), mode='same')
            else:
                diff_smooth = diff
            cooldown = 0
            for i in range(1, len(diff_smooth)):
                if cooldown > 0:
                    cooldown -= 1
                    continue
                if diff_smooth[i - 1] * diff_smooth[i] < 0:
                    total += 1
                    cooldown = max(2, len(diff_smooth) // 30)
        return total

    def _estimate_underwater_distance(self, pose_frames, events, race_duration):
        if events.dive_entry is None or events.dive_surface is None:
            return None
        entry_xs, surface_xs = [], []
        for pf in pose_frames:
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            ts = get_timestamp(pf)
            if lm is None:
                continue
            lh = get_lm(lm, "left_hip")
            rh = get_lm(lm, "right_hip")
            mid = midpoint(lh, rh)
            if mid is None or mid[0] < 0 or mid[0] > 1:
                continue
            if abs(ts - events.dive_entry) < 0.3:
                entry_xs.append(mid[0])
            if abs(ts - events.dive_surface) < 0.3:
                surface_xs.append(mid[0])

        entry_x = float(np.median(entry_xs)) if entry_xs else None
        surface_x = float(np.median(surface_xs)) if surface_xs else None

        if entry_x is not None and surface_x is not None:
            px_per_m = self._estimate_pixel_per_meter(pose_frames, events)
            if px_per_m > 0.001:
                dist = abs(surface_x - entry_x) / px_per_m
                if 1.0 < dist < 25.0:
                    return round(dist, 2)

        uw_time = events.dive_surface - events.dive_entry
        if race_duration > 0:
            avg_speed = self.race_distance / race_duration if hasattr(self, 'race_distance') else 0
            if avg_speed > 0:
                return round(avg_speed * uw_time * 1.8, 2)
        return None

    def _estimate_pixel_per_meter(self, pose_frames, events):
        start = events.signal_time or events.dive_start or 0
        end = events.race_end or float('inf')
        first_half_ts_x = []
        for pf in pose_frames:
            ts = get_timestamp(pf)
            if ts < start or ts > end:
                continue
            if events.turn_touch and ts > events.turn_touch:
                break
            lh = get_lm(pf.get("landmarks", {}) if isinstance(pf, dict) else getattr(pf, 'landmarks', {}), "left_hip")
            rh = get_lm(pf.get("landmarks", {}) if isinstance(pf, dict) else getattr(pf, 'landmarks', {}), "right_hip")
            mid = midpoint(lh, rh)
            if mid is not None and 0 < mid[0] < 1 and mid[1] < 0.9:
                first_half_ts_x.append(mid[0])
        if len(first_half_ts_x) < 10:
            return 0.01
        x_arr = np.array(first_half_ts_x)
        q1, q3 = np.percentile(x_arr, [25, 75])
        iqr = q3 - q1
        x_arr = x_arr[(x_arr >= q1 - 1.5 * iqr) & (x_arr <= q3 + 1.5 * iqr)]
        if len(x_arr) < 10:
            return 0.01
        x_range = float(x_arr.max() - x_arr.min())
        if x_range < 0.01:
            return 0.01
        return x_range / 50