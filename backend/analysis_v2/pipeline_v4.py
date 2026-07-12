import logging
import os
import gc
from typing import List, Optional, Callable, Dict, Any

from .shared import AnalysisContext, ModuleResult, RaceEvents, DetectionParamsConfig
from .utils import detect_water_surface, format_race_time

logger = logging.getLogger(__name__)

ANALYSIS_VERSION = "4.0.0"

TASK_DEFINITIONS = [
    {"name": "出发信号检测", "weight": 5, "task_id": "signal"},
    {"name": "逐帧泳者检测与姿态估计", "weight": 50, "task_id": "pose"},
    {"name": "起跳反应时间", "weight": 5, "task_id": "reaction"},
    {"name": "水下阶段", "weight": 5, "task_id": "underwater"},
    {"name": "划水计数", "weight": 6, "task_id": "stroke"},
    {"name": "打腿计数", "weight": 5, "task_id": "kick"},
    {"name": "换气计数", "weight": 5, "task_id": "breath"},
    {"name": "速度计算", "weight": 3, "task_id": "speed"},
    {"name": "转身检测", "weight": 5, "task_id": "turn"},
    {"name": "终点检测", "weight": 5, "task_id": "finish"},
    {"name": "比赛用时计算", "weight": 3, "task_id": "duration"},
]

OPTION_TO_TASK_IDS = {
    "起跳反应时间": ["reaction"],
    "出发后潜水时间": ["underwater"],
    "出发后潜水距离": ["underwater"],
    "水下腿次数": ["underwater"],
    "左臂划水次数": ["stroke"],
    "右臂划水次数": ["stroke"],
    "前程左臂划水次数": ["stroke"],
    "前程右臂划水次数": ["stroke"],
    "后程左臂划水次数": ["stroke"],
    "后程右臂划水次数": ["stroke"],
    "打腿次数(单腿)": ["kick"],
    "水面交替打腿次数": ["kick"],
    "前程打腿次数(单腿)": ["kick"],
    "后程打腿次数(单腿)": ["kick"],
    "总换气次数": ["breath"],
    "前程总换气次数": ["breath"],
    "后程总换气次数": ["breath"],
    "途中游速度": ["speed"],
    "前程途中游速度": ["speed"],
    "后程途中游速度": ["speed"],
    "半程触壁转身时刻": ["turn"],
    "转身后出水用时": ["turn"],
    "转身出水距离": ["turn"],
    "转身水下腿次数": ["turn"],
    "前程整体用时": ["turn", "finish", "duration"],
    "后程整体用时": ["turn", "finish", "duration"],
    "触壁终点用时": ["finish", "duration"],
    "用时标注": ["finish", "duration"],
}

ALWAYS_REQUIRED_TASK_IDS = {"signal", "pose"}

TOTAL_TASKS = len(TASK_DEFINITIONS)


class AnalysisPipeline:
    VERSION = ANALYSIS_VERSION

    def __init__(
        self,
        pool_length: int = 50,
        race_distance: int = 100,
        swimmer_position: int = 1,
        progress_callback: Optional[Callable] = None,
        detection_params: Optional[DetectionParamsConfig] = None,
    ):
        self.pool_length = pool_length
        self.race_distance = race_distance
        self.swimmer_position = swimmer_position
        self.progress_callback = progress_callback
        self.detection_params = detection_params or DetectionParamsConfig.default()

    def _report(self, percent: int, message: str, current_task: str = "",
                tasks_completed: int = 0, total_tasks: int = TOTAL_TASKS):
        if self.progress_callback:
            self.progress_callback(percent, message, current_task, tasks_completed, total_tasks)

    def analyze(self, video_path: str, analysis_options: List[str]) -> Dict[str, Any]:
        logger.info(f"[v{self.VERSION}] Starting analysis: {video_path}")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        required_task_ids = set(ALWAYS_REQUIRED_TASK_IDS)
        for opt in analysis_options:
            if opt in OPTION_TO_TASK_IDS:
                required_task_ids.update(OPTION_TO_TASK_IDS[opt])

        required_task_indices = []
        for i, td in enumerate(TASK_DEFINITIONS):
            if td["task_id"] in required_task_ids:
                required_task_indices.append(i)

        total_selected = len(required_task_indices)
        logger.info(f"Selected options: {analysis_options}, required tasks: {required_task_ids}, count: {total_selected}")

        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / fps
        cap.release()

        is_50m_50pool = (self.pool_length == 50 and self.race_distance == 50)

        initial_context = AnalysisContext(
            video_path=video_path,
            pool_length=self.pool_length,
            race_distance=self.race_distance,
            swimmer_position=self.swimmer_position,
            video_duration=video_duration,
            is_50m_50pool=is_50m_50pool,
            detection_params=self.detection_params,
        )

        context = initial_context
        all_metrics = {}
        all_results = {}
        meta_info = {
            "analysis_version": self.VERSION,
            "swimmer_position": self.swimmer_position,
            "video_duration": round(video_duration, 2),
            "pool_length": self.pool_length,
            "race_distance": self.race_distance,
        }

        cumulative_pct = 0
        completed_count = 0

        def task_pct(task_index: int) -> tuple:
            nonlocal cumulative_pct
            start_pct = cumulative_pct
            weight = TASK_DEFINITIONS[task_index]["weight"]
            total_weight = sum(TASK_DEFINITIONS[i]["weight"] for i in required_task_indices)
            pct_share = int(weight / max(total_weight, 1) * 100)
            end_pct = min(start_pct + pct_share, 100)
            cumulative_pct = end_pct
            return start_pct, end_pct

        # Task 0: 出发信号检测
        task_idx = 0
        if task_idx in required_task_indices:
            start_pct, end_pct = task_pct(task_idx)
            completed_count += 1
            self._report(start_pct, f"任务{completed_count}/{total_selected}：出发信号检测...",
                         TASK_DEFINITIONS[task_idx]["name"], completed_count - 1, total_selected)

            from .start_signal_detector import StartSignalDetector
            signal_detector = StartSignalDetector()
            signal_result = signal_detector.analyze(context)
            all_results[signal_detector.name] = signal_result
            all_metrics.update(signal_result.metrics)

            new_events = context.events.merge(signal_result.module_events)
            context = context.with_events(new_events)
            meta_info["audio_signal_time"] = context.events.signal_time
            meta_info["audio_signal_type"] = context.events.signal_type
            meta_info["audio_confidence"] = context.events.signal_confidence

            self._report(end_pct, f"任务{completed_count}/{total_selected}：出发信号检测完成",
                         TASK_DEFINITIONS[task_idx]["name"], completed_count, total_selected)

        # Task 1: 泳者检测与姿态估计
        task_idx = 1
        if task_idx in required_task_indices:
            start_pct, end_pct = task_pct(task_idx)
            completed_count += 1
            self._report(start_pct, f"任务{completed_count}/{total_selected}：泳者检测与姿态估计...",
                         TASK_DEFINITIONS[task_idx]["name"], completed_count - 1, total_selected)

            from .swimmer_pose_detector import SwimmerPoseDetector
            pose_detector = SwimmerPoseDetector()
            pose_result = pose_detector.analyze(context)

            pose_frames = getattr(pose_result, '_pose_frames', ())
            water_y = detect_water_surface(list(pose_frames))

            race_duration = 0.0
            if context.events.race_end is not None and context.events.signal_time is not None:
                race_duration = context.events.race_end - context.events.signal_time
            elif context.events.race_end is not None and context.events.dive_start is not None:
                race_duration = context.events.race_end - context.events.dive_start

            context = AnalysisContext(
                pose_frames=pose_frames,
                events=context.events,
                water_y=water_y,
                race_duration=race_duration,
                is_50m_50pool=is_50m_50pool,
                pool_length=self.pool_length,
                race_distance=self.race_distance,
                video_duration=video_duration,
                video_path=video_path,
                swimmer_position=self.swimmer_position,
                detection_params=self.detection_params,
                previous_results=dict(context.previous_results),
            )

            all_results[pose_detector.name] = pose_result
            meta_info["detection_frames"] = pose_result.metrics.get("检测帧数", 0)
            meta_info["pose_frames"] = pose_result.metrics.get("有效姿态帧数", 0)
            retry_count = pose_result.metrics.get("覆盖率重试次数", 0)
            if retry_count > 0:
                meta_info["coverage_retries"] = retry_count

            self._report(end_pct, f"任务{completed_count}/{total_selected}：泳者检测与姿态估计完成",
                         TASK_DEFINITIONS[task_idx]["name"], completed_count, total_selected)

        # Task 2-10: 顺序执行各独立检测模块（仅执行用户选择的）
        module_classes = [
            ("起跳反应时间", "reaction_time_detector", "ReactionTimeDetector"),
            ("水下阶段", "underwater_phase_detector", "UnderwaterPhaseDetector"),
            ("划水计数", "stroke_counter", "StrokeCounter"),
            ("打腿计数", "kick_counter", "KickCounter"),
            ("换气计数", "breath_counter", "BreathCounter"),
            ("速度计算", "speed_calculator", "SpeedCalculator"),
            ("转身检测", "turn_detector", "TurnDetector"),
            ("终点检测", "finish_detector", "FinishDetector"),
            ("比赛用时计算", "race_duration_calculator", "RaceDurationCalculator"),
        ]

        import importlib

        for i, (task_name, module_file, class_name) in enumerate(module_classes):
            task_idx = 2 + i
            if task_idx not in required_task_indices:
                logger.info(f"Skipping task {task_idx}: {task_name} (not selected)")
                continue

            start_pct, end_pct = task_pct(task_idx)
            completed_count += 1
            self._report(start_pct, f"任务{completed_count}/{total_selected}：{task_name}...",
                         TASK_DEFINITIONS[task_idx]["name"], completed_count - 1, total_selected)

            try:
                mod = importlib.import_module(f".{module_file}", package="backend.analysis_v2")
                cls = getattr(mod, class_name)
                module_instance = cls()
                result = module_instance.analyze(context)

                all_results[module_instance.name] = result
                all_metrics.update(result.metrics)

                if result.module_events:
                    new_events = context.events.merge(result.module_events)
                    race_duration = 0.0
                    if new_events.race_end is not None:
                        start_t = new_events.signal_time if new_events.signal_time else new_events.dive_start
                        if start_t:
                            race_duration = new_events.race_end - start_t

                    context = AnalysisContext(
                        pose_frames=context.pose_frames,
                        events=new_events,
                        water_y=context.water_y,
                        race_duration=race_duration,
                        is_50m_50pool=context.is_50m_50pool,
                        pool_length=context.pool_length,
                        race_distance=context.race_distance,
                        video_duration=context.video_duration,
                        video_path=context.video_path,
                        swimmer_position=context.swimmer_position,
                        detection_params=context.detection_params,
                        previous_results=dict(context.previous_results),
                    )

                context = context.with_previous_result(module_instance.name, result)

                if task_name == "转身检测":
                    if new_events.turn_touch_confidence is not None:
                        meta_info["turn_touch_confidence"] = new_events.turn_touch_confidence
                    if new_events.turn_touch_method is not None:
                        meta_info["turn_touch_method"] = new_events.turn_touch_method

            except Exception as e:
                logger.error(f"Module {task_name} failed: {e}")
                all_metrics[f"{task_name}_error"] = str(e)

            self._report(end_pct, f"任务{completed_count}/{total_selected}：{task_name}完成",
                         TASK_DEFINITIONS[task_idx]["name"], completed_count, total_selected)

        result = dict(all_metrics)
        result["_meta"] = meta_info

        self._report(100, "分析完成", "分析完成", total_selected, total_selected)
        logger.info(f"[v{self.VERSION}] Analysis complete: {len(all_metrics)} metrics")
        return result