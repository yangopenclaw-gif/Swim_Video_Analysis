import logging
import numpy as np
from typing import Optional, Dict, Any
from .base_module import AnalysisModule
from .shared import AnalysisContext, ModuleResult, AccuracyInfo
from .utils import get_lm, midpoint, get_timestamp, get_swimmer_x_range, smooth

class FinishDetector(AnalysisModule):
    VERSION = "4.0.0"
    
    @property
    def name(self) -> str:
        return "终点检测"
    
    def analyze(self, context: AnalysisContext) -> ModuleResult:
        pose_frames = list(context.pose_frames)
        events = context.events
        params = context.detection_params.finish_detection
        
        race_end = events.race_end
        if race_end is None:
            race_end = self._detect_race_end(pose_frames, events, params, context.video_duration)
        
        metrics = {}
        module_events = {}
        
        if race_end is not None:
            module_events["race_end"] = race_end
        
        confidence = 1.0 if race_end is not None else 0.0
        accuracy = AccuracyInfo(
            confidence=round(confidence, 3), coverage=1.0 if race_end is not None else 0.0,
            quality="高" if confidence >= 0.7 else "低",
            low_confidence=confidence < 0.3, warnings=[] if confidence >= 0.3 else ["终点检测置信度低"],
        )
        
        return ModuleResult(
            module_name=self.name, metrics=metrics, module_events=module_events,
            accuracy=accuracy, detection_method="姿态变化+运动停止融合",
        )
    
    def _detect_race_end(self, pose_frames, events, params, video_duration):
        hip_y_standing = params.get("hip_y_standing_threshold", 0.85)
        hip_y_swimming = params.get("hip_y_swimming_threshold", 0.7)
        movement_threshold = params.get("movement_threshold", 0.002)
        min_race_time_factor = params.get("min_race_time_factor", 3.0)
        
        race_start = events.signal_time or events.dive_start or 0
        min_race_time = max(5.0, min_race_time_factor)
        
        target_x_min, target_x_max = get_swimmer_x_range(pose_frames, race_start, 1)
        
        last_swimming_ts = None
        first_standing_after_swim = None
        
        for pf in pose_frames:
            ts = get_timestamp(pf)
            if ts < race_start or ts - race_start < min_race_time:
                continue
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = get_lm(lm, "left_hip")
            rh = get_lm(lm, "right_hip")
            mid = midpoint(lh, rh)
            if mid is None:
                continue
            if target_x_min is not None and target_x_max is not None:
                if mid[0] < target_x_min or mid[0] > target_x_max:
                    continue
            if mid[1] < hip_y_swimming:
                last_swimming_ts = ts
            elif mid[1] > hip_y_standing and last_swimming_ts is not None and first_standing_after_swim is None:
                if ts - last_swimming_ts < 3.0:
                    first_standing_after_swim = ts
        
        if last_swimming_ts is not None:
            return float(last_swimming_ts)
        
        return self._detect_by_movement(pose_frames, race_start, min_race_time, video_duration, movement_threshold)
    
    def _detect_by_movement(self, pose_frames, race_start, min_race_time, video_duration, movement_threshold):
        hip_x_data = []
        for pf in pose_frames:
            ts = get_timestamp(pf)
            if ts < race_start or ts - race_start < min_race_time:
                continue
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = get_lm(lm, "left_hip")
            rh = get_lm(lm, "right_hip")
            mid = midpoint(lh, rh)
            if mid is not None:
                hip_x_data.append((ts, mid[0]))
        
        if len(hip_x_data) > 20:
            ts_arr = np.array([t for t, _ in hip_x_data])
            x_arr = np.array([v for _, v in hip_x_data])
            window = max(5, len(x_arr) // 10)
            dx = np.gradient(x_arr, ts_arr)
            dx_smooth = smooth(dx, window)
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
                    if prev_movement > movement_threshold and curr_movement < movement_threshold:
                        if i + movement_window < len(ts_arr):
                            return float(ts_arr[min(i + movement_window // 2, len(ts_arr) - 1)])
        
        for pf in reversed(pose_frames):
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is not None:
                ts = get_timestamp(pf)
                if ts > race_start + min_race_time:
                    return ts
        
        return video_duration