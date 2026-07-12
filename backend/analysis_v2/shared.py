from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class RaceEvents:
    signal_time: Optional[float] = None
    signal_type: Optional[str] = None
    signal_confidence: float = 0.0
    dive_start: Optional[float] = None
    dive_entry: Optional[float] = None
    dive_surface: Optional[float] = None
    turn_touch: Optional[float] = None
    turn_surface: Optional[float] = None
    turn_touch_confidence: Optional[float] = None
    turn_touch_method: Optional[str] = None
    turn_diagnosis: Optional[str] = None
    race_end: Optional[float] = None
    reaction_time: Optional[float] = None

    def merge(self, events_dict: Dict[str, Any]) -> "RaceEvents":
        updates = {}
        for k, v in events_dict.items():
            if hasattr(self, k) and v is not None:
                current = getattr(self, k)
                if current is None:
                    updates[k] = v
        return RaceEvents(
            signal_time=updates.get("signal_time", self.signal_time),
            signal_type=updates.get("signal_type", self.signal_type),
            signal_confidence=updates.get("signal_confidence", self.signal_confidence),
            dive_start=updates.get("dive_start", self.dive_start),
            dive_entry=updates.get("dive_entry", self.dive_entry),
            dive_surface=updates.get("dive_surface", self.dive_surface),
            turn_touch=updates.get("turn_touch", self.turn_touch),
            turn_surface=updates.get("turn_surface", self.turn_surface),
            turn_touch_confidence=updates.get("turn_touch_confidence", self.turn_touch_confidence),
            turn_touch_method=updates.get("turn_touch_method", self.turn_touch_method),
            turn_diagnosis=updates.get("turn_diagnosis", self.turn_diagnosis),
            race_end=updates.get("race_end", self.race_end),
            reaction_time=updates.get("reaction_time", self.reaction_time),
        )


@dataclass(frozen=True)
class AccuracyInfo:
    confidence: float = 0.0
    coverage: float = 0.0
    quality: str = "低"
    low_confidence: bool = False
    warnings: List[str] = field(default_factory=list)


@dataclass
class EngineSwitchRecord:
    metric_name: str
    primary_engine: str
    primary_result: Any = None
    primary_success: bool = False
    backup_engines_tried: List[Dict[str, Any]] = field(default_factory=list)
    final_engine: str = ""
    final_result: Any = None


@dataclass
class RetryRecord:
    attempt: int
    success: bool
    strategy_name: str
    result: Any = None
    confidence: float = 0.0


@dataclass
class EngineResult:
    success: bool
    data: Dict[str, Any]
    engine_name: str
    confidence: float = 0.0


@dataclass
class ModuleResult:
    module_name: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    module_events: Dict[str, Any] = field(default_factory=dict)
    accuracy: AccuracyInfo = field(default_factory=AccuracyInfo)
    engine_switch_records: List[EngineSwitchRecord] = field(default_factory=list)
    retry_records: List[RetryRecord] = field(default_factory=list)
    detection_method: str = ""


@dataclass(frozen=True)
class DetectionParamsNamespace:
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DetectionParamsConfig:
    pose_estimation: Dict[str, Any] = field(default_factory=dict)
    signal_detection: Dict[str, Any] = field(default_factory=dict)
    reaction_time: Dict[str, Any] = field(default_factory=dict)
    underwater_phase: Dict[str, Any] = field(default_factory=dict)
    stroke_detection: Dict[str, Any] = field(default_factory=dict)
    kick_detection: Dict[str, Any] = field(default_factory=dict)
    breath_detection: Dict[str, Any] = field(default_factory=dict)
    turn_detection: Dict[str, Any] = field(default_factory=dict)
    finish_detection: Dict[str, Any] = field(default_factory=dict)
    engine_config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "DetectionParamsConfig":
        return cls(
            pose_estimation={
                "detection_confidence": 0.5,
                "presence_confidence": 0.5,
                "tracking_confidence": 0.5,
                "yolo_confidence": 0.3,
                "num_poses": 6,
                "coverage_retry_threshold": 0.3,
                "max_coverage_retries": 3,
                "retry_confidence_steps": [0.3, 0.2, 0.1],
                "retry_yolo_confidence_steps": [0.3, 0.15, 0.15],
                "retry_hip_visibility_steps": [0.1, 0.1, 0.05],
                "aggressive_supplementary_threshold": 0.5,
                "aggressive_supplementary_confidence": 0.3,
                "aggressive_supplementary_num_poses": 4,
            },
            signal_detection={
                "silence_threshold_offset": 10,
                "confidence_threshold": 0.4,
                "search_window_seconds": 10.0,
                "max_retries": 3,
                "retry_silence_offset_step": 4,
                "retry_confidence_step": 0.1,
                "retry_window_step": 5.0,
            },
            reaction_time={
                "min_reaction_time": 0.30,
                "max_reaction_time": 1.50,
                "velocity_threshold": 0.01,
            },
            underwater_phase={
                "max_underwater_time": 15.0,
                "surface_threshold_offset": 0.03,
            },
            stroke_detection={
                "peak_height_factor": 0.15,
                "min_distance_seconds": 0.3,
                "min_prominence_factor": 0.1,
                "baseline_window_seconds": 2.0,
                "coverage_threshold": 0.05,
            },
            kick_detection={
                "min_amplitude": 0.005,
                "cooldown_factor": 1.0,
                "coverage_threshold": 0.05,
            },
            breath_detection={
                "deviation_factor": 0.3,
                "min_deviation": 0.002,
                "min_nose_x_deviation": 0.01,
                "cooldown_seconds": 0.8,
                "baseline_window_seconds": 2.0,
                "coverage_threshold": 0.05,
            },
            turn_detection={
                "direction_change_threshold": 0.003,
                "min_turn_time_range": 0.3,
                "max_turn_time_range": 0.7,
                "sparse_mode_threshold": 50,
                "sparse_min_data_points": 10,
                "sparse_before_after_frames": 3,
                "sparse_min_time_range": 0.2,
                "sparse_max_time_range": 0.8,
                "sparse_direction_change_factor": 0.3,
                "sparse_min_direction_change": 0.001,
                "interpolation_gap_threshold": 0.5,
                "retry1_min_time_range": 0.15,
                "retry1_max_time_range": 0.85,
                "retry1_threshold_factor": 0.5,
                "position_clustering_window": 0.5,
                "position_clustering_threshold": 0.15,
                "velocity_direction_time_range": 0.2,
                "hmm_turn_enabled": False,
                "hmm_turn_n_states": 5,
                "hmm_turn_n_iter": 50,
                "wavelet_break_enabled": False,
                "wavelet_break_wavelet": "db4",
                "wavelet_break_level": 4,
                "y_motion_slope_window": 1.0,
                "y_motion_min_change": 0.001,
                "y_motion_change_factor": 0.3,
                "y_motion_persistence_window": 2.0,
                "y_motion_dive_exclusion": 8.0,
                "y_extrema_min_window": 3.0,
                "y_motion_pattern_enabled": True,
                "visibility_smooth_window": 5,
                "visibility_change_threshold": 0.2,
                "visibility_change_enabled": True,
                "velocity_smooth_window": 0.5,
                "velocity_angle_change_threshold": 60.0,
                "velocity_2d_enabled": True,
                "hmm_multi_obs_n_states": 5,
                "hmm_multi_obs_n_iter": 100,
                "hmm_multi_obs_enabled": True,
                "wavelet_multi_signal_wavelet": "db4",
                "wavelet_multi_signal_level": 4,
                "wavelet_cluster_window": 1.0,
                "wavelet_multi_signal_enabled": True,
                "multi_keypoint_2d_fusion_enabled": True,
                "turn_consistency_window": 5.0,
            },
            finish_detection={
                "hip_y_standing_threshold": 0.85,
                "hip_y_swimming_threshold": 0.7,
                "movement_threshold": 0.002,
                "min_race_time_factor": 3.0,
            },
            engine_config={
                "engine_deployment_stage": "backup",
                "parallel_evaluation_enabled": False,
                "evaluation_min_samples": 10,
                "promotion_threshold": 0.6,
                "max_latency_multiplier": 3.0,
                "max_memory_increment_gb": 2.0,
            },
        )


@dataclass(frozen=True)
class AnalysisContext:
    pose_frames: tuple = ()
    events: RaceEvents = field(default_factory=RaceEvents)
    water_y: float = 0.5
    race_duration: float = 0.0
    is_50m_50pool: bool = False
    pool_length: int = 50
    race_distance: int = 100
    video_duration: float = 0.0
    video_path: str = ""
    swimmer_position: int = 1
    detection_params: DetectionParamsConfig = field(default_factory=DetectionParamsConfig.default)
    previous_results: Dict[str, ModuleResult] = field(default_factory=dict)

    def with_events(self, new_events: RaceEvents) -> "AnalysisContext":
        return AnalysisContext(
            pose_frames=self.pose_frames,
            events=new_events,
            water_y=self.water_y,
            race_duration=self.race_duration,
            is_50m_50pool=self.is_50m_50pool,
            pool_length=self.pool_length,
            race_distance=self.race_distance,
            video_duration=self.video_duration,
            video_path=self.video_path,
            swimmer_position=self.swimmer_position,
            detection_params=self.detection_params,
            previous_results=self.previous_results,
        )

    def with_previous_result(self, module_name: str, result: ModuleResult) -> "AnalysisContext":
        new_prev = dict(self.previous_results)
        new_prev[module_name] = result
        return AnalysisContext(
            pose_frames=self.pose_frames,
            events=self.events,
            water_y=self.water_y,
            race_duration=self.race_duration,
            is_50m_50pool=self.is_50m_50pool,
            pool_length=self.pool_length,
            race_distance=self.race_distance,
            video_duration=self.video_duration,
            video_path=self.video_path,
            swimmer_position=self.swimmer_position,
            detection_params=self.detection_params,
            previous_results=new_prev,
        )