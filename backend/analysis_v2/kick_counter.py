import logging
import numpy as np
from typing import Optional, Dict, Any, Tuple
from .base_module import AnalysisModule
from .shared import AnalysisContext, ModuleResult, AccuracyInfo
from .utils import get_lm, midpoint, get_timestamp, smooth

class KickCounter(AnalysisModule):
    VERSION = "4.0.0"
    
    @property
    def name(self) -> str:
        return "打腿计数"
    
    def analyze(self, context: AnalysisContext) -> ModuleResult:
        pose_frames = list(context.pose_frames)
        events = context.events
        params = context.detection_params.kick_detection
        is_50m_50pool = context.is_50m_50pool
        half_time = self._get_half_time(events)
        
        if is_50m_50pool:
            count = self._count_kicks_phase(pose_frames, events, None, None, params)
            metrics = {"打腿次数(单腿)": f"{count} 次"}
        else:
            start_t = events.signal_time or events.dive_start or 0
            end_t = events.race_end or float('inf')
            if half_time:
                first_count = self._count_kicks_phase(pose_frames, events, start_t, half_time, params)
                second_count = self._count_kicks_phase(pose_frames, events, half_time, end_t, params)
            else:
                first_count = self._count_kicks_phase(pose_frames, events, start_t, end_t, params)
                second_count = 0
            metrics = {
                "前程打腿次数(单腿)": f"{first_count} 次",
                "后程打腿次数(单腿)": f"{second_count} 次",
            }
        
        coverage = self._estimate_coverage(pose_frames, events, half_time, is_50m_50pool)
        accuracy = AccuracyInfo(
            confidence=min(coverage * 1.1, 1.0),
            coverage=round(coverage, 3),
            quality="高" if coverage >= 0.7 else ("中" if coverage >= 0.4 else "低"),
            low_confidence=coverage < 0.3,
            warnings=[] if coverage >= 0.3 else ["打腿检测覆盖率低"],
        )
        
        return ModuleResult(
            module_name=self.name, metrics=metrics, module_events={},
            accuracy=accuracy, detection_method="过零点检测+频谱分析备选",
        )
    
    def _get_half_time(self, events):
        if events.signal_time is None:
            return None
        if events.turn_touch is not None:
            return events.turn_touch
        return None
    
    def _count_kicks_phase(self, pose_frames, events, start_t, end_t, params):
        if start_t is None:
            start_t = events.signal_time or events.dive_start or 0
        if end_t is None:
            end_t = events.race_end or float('inf')
        
        la_y, ra_y = [], []
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
            la = get_lm(lm, "left_ankle")
            ra = get_lm(lm, "right_ankle")
            la_val = la[1] if la is not None and 0 <= la[1] <= 1 else None
            ra_val = ra[1] if ra is not None and 0 <= ra[1] <= 1 else None
            la_y.append(la_val)
            ra_y.append(ra_val)
        
        crossings = self._count_crossings_in_segments(la_y, ra_y, params)
        return crossings
    
    def _count_crossings_in_segments(self, left_y, right_y, params):
        min_segment = 3
        min_amplitude = params.get("min_amplitude", 0.005)
        cooldown_factor = params.get("cooldown_factor", 1.0)
        
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
                diff_smooth = smooth(diff, max(2, len(diff) // 40))
            else:
                diff_smooth = diff
            amplitude = float(np.std(diff_smooth))
            if amplitude < min_amplitude:
                continue
            cooldown = max(2, int(len(diff_smooth) // 30 * cooldown_factor))
            cd = 0
            for i in range(1, len(diff_smooth)):
                if cd > 0:
                    cd -= 1
                    continue
                if diff_smooth[i-1] * diff_smooth[i] < 0:
                    total += 1
                    cd = cooldown
        return total
    
    def _estimate_coverage(self, pose_frames, events, half_time, is_50m_50pool):
        start_t = events.signal_time or events.dive_start or 0
        end_t = events.race_end or float('inf')
        total, valid = 0, 0
        for pf in pose_frames:
            ts = get_timestamp(pf)
            if ts < start_t or ts > end_t:
                continue
            total += 1
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is not None:
                la = get_lm(lm, "left_ankle")
                ra = get_lm(lm, "right_ankle")
                if la is not None and ra is not None:
                    valid += 1
        return valid / max(total, 1)