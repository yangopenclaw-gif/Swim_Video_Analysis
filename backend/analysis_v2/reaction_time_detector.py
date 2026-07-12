import logging
import numpy as np
from typing import Optional, Dict, Any

from .base_module import AnalysisModule
from .shared import AnalysisContext, ModuleResult, AccuracyInfo
from .utils import get_lm, midpoint, get_timestamp

logger = logging.getLogger(__name__)


class ReactionTimeDetector(AnalysisModule):
    VERSION = "4.0.0"

    @property
    def name(self) -> str:
        return "起跳反应时间"

    def analyze(self, context: AnalysisContext) -> ModuleResult:
        events = context.events
        pose_frames = list(context.pose_frames)
        params = context.detection_params.reaction_time

        signal_time = events.signal_time
        dive_start = events.dive_start

        if dive_start is None:
            dive_start = self._detect_dive_start(pose_frames, signal_time, params)

        reaction_time = None
        if signal_time is not None and dive_start is not None:
            reaction_time = dive_start - signal_time

        metrics = {}
        if reaction_time is not None:
            metrics["起跳反应时间"] = f"{reaction_time:.2f} 秒"
            min_rt = params.get("min_reaction_time", 0.30)
            max_rt = params.get("max_reaction_time", 1.50)
            if reaction_time < min_rt or reaction_time > max_rt:
                metrics["起跳反应时间"] += "（超出典型范围）"
        else:
            metrics["起跳反应时间"] = "未检测到"

        module_events = {}
        if dive_start is not None:
            module_events["dive_start"] = dive_start
        if reaction_time is not None:
            module_events["reaction_time"] = reaction_time

        confidence = 1.0 if signal_time is not None and dive_start is not None else 0.0
        accuracy = AccuracyInfo(
            confidence=round(confidence, 3),
            coverage=1.0 if dive_start is not None else 0.0,
            quality="高" if confidence >= 0.7 else ("中" if confidence >= 0.4 else "低"),
            low_confidence=confidence < 0.3,
            warnings=[] if confidence >= 0.3 else ["起跳反应时间检测置信度低"],
        )

        return ModuleResult(
            module_name=self.name,
            metrics=metrics,
            module_events=module_events,
            accuracy=accuracy,
            detection_method="信号时间-起跳时间差",
        )

    def _detect_dive_start(self, pose_frames, signal_time, params):
        if not pose_frames:
            return None

        velocity_threshold = params.get("velocity_threshold", 0.01)
        search_start = signal_time if signal_time else 0
        search_end = search_start + 3.0

        hip_y_series = []
        for pf in pose_frames:
            ts = get_timestamp(pf)
            if ts < search_start or ts > search_end:
                continue
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = get_lm(lm, "left_hip")
            rh = get_lm(lm, "right_hip")
            mid = midpoint(lh, rh)
            if mid is not None:
                hip_y_series.append((ts, mid[1]))

        if len(hip_y_series) < 5:
            return None

        ts_arr = np.array([t for t, _ in hip_y_series])
        y_arr = np.array([v for _, v in hip_y_series])

        velocity = np.gradient(y_arr, ts_arr)

        for i in range(1, len(velocity)):
            if velocity[i] < -velocity_threshold:
                return float(ts_arr[i])

        return None