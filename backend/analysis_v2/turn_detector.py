import logging
import numpy as np
from typing import Optional, Dict, Any, List, Tuple

from .base_module import AnalysisModule
from .shared import AnalysisContext, ModuleResult, AccuracyInfo, RetryRecord
from .utils import get_lm, midpoint, get_timestamp, smooth

logger = logging.getLogger(__name__)


class TurnDetector(AnalysisModule):
    VERSION = "4.1.0"

    @property
    def name(self) -> str:
        return "转身检测"

    def analyze(self, context: AnalysisContext) -> ModuleResult:
        pose_frames = list(context.pose_frames)
        events = context.events
        params = context.detection_params.turn_detection
        is_50m_50pool = context.is_50m_50pool

        if is_50m_50pool:
            return ModuleResult(module_name=self.name, metrics={}, module_events={}, accuracy=AccuracyInfo(), detection_method="50米赛无转身")

        metrics = {}
        turn_touch = events.turn_touch
        turn_surface = events.turn_surface

        retry_records: List[RetryRecord] = []
        turn_touch_method = ""
        turn_touch_confidence = 0.0
        turn_diagnosis = None

        if turn_touch is None:
            turn_touch, turn_touch_method, turn_touch_confidence, retry_records, turn_diagnosis = \
                self._detect_turn_with_retries(pose_frames, events, params, context)

        if turn_touch is not None and turn_surface is None:
            turn_surface = self._detect_turn_surface(pose_frames, turn_touch, context.water_y)

        if events.signal_time is not None and turn_touch is not None:
            metrics["半程触壁转身时刻"] = f"{turn_touch - events.signal_time:.2f} 秒"
            if turn_touch_method:
                metrics["转身检测方式"] = turn_touch_method
            if turn_touch_confidence > 0:
                metrics["转身检测置信度"] = f"{turn_touch_confidence:.2f}"
            if turn_surface is not None:
                turn_uw_time = turn_surface - turn_touch
                metrics["转身后出水用时"] = f"{turn_uw_time:.2f} 秒"
                turn_kicks = self._count_turn_kicks(pose_frames, turn_touch, turn_surface)
                metrics["转身水下腿次数"] = f"{turn_kicks} 次"
            else:
                metrics["转身后出水用时"] = "未检测到"
                metrics["转身水下腿次数"] = "未检测到"
        else:
            metrics["半程触壁转身时刻"] = "未检测到"
            metrics["转身后出水用时"] = "未检测到"
            metrics["转身水下腿次数"] = "未检测到"

        if turn_diagnosis is not None:
            metrics["转身检测诊断"] = turn_diagnosis

        module_events = {}
        if turn_touch is not None:
            module_events["turn_touch"] = turn_touch
        if turn_surface is not None:
            module_events["turn_surface"] = turn_surface
        if turn_touch_confidence > 0:
            module_events["turn_touch_confidence"] = turn_touch_confidence
        if turn_touch_method:
            module_events["turn_touch_method"] = turn_touch_method
        if turn_diagnosis is not None:
            module_events["turn_diagnosis"] = turn_diagnosis

        confidence = turn_touch_confidence if turn_touch is not None else 0.0
        accuracy = AccuracyInfo(
            confidence=round(confidence, 3),
            coverage=1.0 if turn_touch is not None else 0.0,
            quality="高" if confidence >= 0.7 else ("中" if confidence >= 0.4 else "低"),
            low_confidence=confidence < 0.3,
            warnings=[] if confidence >= 0.3 else ["转身检测置信度低"],
        )

        return ModuleResult(
            module_name=self.name,
            metrics=metrics,
            module_events=module_events,
            accuracy=accuracy,
            retry_records=retry_records,
            detection_method=turn_touch_method or "髋部x方向反转+重试+备选引擎",
        )

    def _detect_turn_with_retries(
        self, pose_frames, events, params, context
    ) -> Tuple[Optional[float], str, float, List[RetryRecord], Optional[str]]:
        retry_records: List[RetryRecord] = []
        hip_x_series = self._extract_hip_x_series(pose_frames)
        all_diagnosis_info = {}

        if len(hip_x_series) < 2:
            diagnosis = self._generate_diagnosis(hip_x_series, [], "数据完全缺失", params)
            return None, "", 0.0, retry_records, diagnosis

        sparse_mode_threshold = params.get("sparse_mode_threshold", 50)
        use_sparse = len(hip_x_series) < sparse_mode_threshold

        if use_sparse:
            hip_x_series = self._interpolate_hip_x_gaps(hip_x_series, params)

        multi_signals = self._extract_multi_keypoint_signals(pose_frames)
        multi_signal_context = self._build_multi_signal_context(multi_signals, events)

        all_strategies = []

        all_strategies.append(("主算法（x方向反转）", self._make_x_direction_strategy(hip_x_series, events, params, use_sparse), False))

        new_engine_strategies = self._get_new_engine_strategies(params, hip_x_series, events, multi_signals, multi_signal_context)
        all_strategies.extend(new_engine_strategies)

        all_strategies.extend([
            ("第1次重试（放宽窗口）", self._retry1_widened_window, False),
            ("第2次重试（位置聚类引擎）", self._detect_turn_by_position_clustering, False),
            ("第3次重试（速度方向引擎）", self._detect_turn_by_velocity_direction, False),
        ])

        all_results = []
        for attempt, item in enumerate(all_strategies):
            strategy_name = item[0]
            strategy_fn = item[1]
            is_new_engine = len(item) > 2 and item[2]

            logger.info(f"Turn detection attempt {attempt}: {strategy_name}")

            if is_new_engine:
                turn_touch, method = strategy_fn(multi_signals, events, params)
            else:
                turn_touch, method = strategy_fn(hip_x_series, events, params)

            if turn_touch is not None:
                confidence = self._calculate_turn_confidence(
                    hip_x_series, turn_touch, events, attempt, params
                )
                retry_records.append(RetryRecord(
                    attempt=attempt, success=True, strategy_name=strategy_name,
                    result=turn_touch, confidence=confidence,
                ))
                all_results.append((turn_touch, strategy_name, confidence, attempt))
            else:
                retry_records.append(RetryRecord(
                    attempt=attempt, success=False, strategy_name=strategy_name,
                    result=None, confidence=0.0,
                ))
                all_diagnosis_info[strategy_name] = "失败"

        if not all_results:
            diagnosis = self._generate_diagnosis(hip_x_series, retry_records, None, params)
            return None, "", 0.0, retry_records, diagnosis

        best_turn, best_method, best_conf = self._select_best_by_voting(
            all_results, events, params
        )
        return best_turn, best_method, best_conf, retry_records, None

    def _make_x_direction_strategy(self, hip_x_series, events, params, use_sparse):
        def wrapper(hip_x_arg, events_arg, params_arg):
            result, method = self._detect_turn_touch(hip_x_series, events, params, use_sparse)
            return result, method
        return wrapper

    def _select_best_by_voting(
        self, all_results, events, params
    ) -> Tuple[Optional[float], str, float]:
        if not all_results:
            return None, "", 0.0

        consistency_window = params.get("turn_consistency_window", 5.0)

        clusters = []
        used = set()
        for i, (ts_i, name_i, conf_i, att_i) in enumerate(all_results):
            if i in used:
                continue
            cluster = [(ts_i, name_i, conf_i, att_i)]
            used.add(i)
            for j, (ts_j, name_j, conf_j, att_j) in enumerate(all_results):
                if j in used:
                    continue
                if abs(ts_j - ts_i) < consistency_window:
                    cluster.append((ts_j, name_j, conf_j, att_j))
                    used.add(j)
            clusters.append(cluster)

        def cluster_score(c):
            n = len(c)
            total_conf = sum(conf for _, _, conf, _ in c)
            return (n, total_conf)

        clusters.sort(key=cluster_score, reverse=True)

        best_cluster = clusters[0]
        if len(best_cluster) >= 2:
            weighted_times = [(ts, conf) for ts, _, conf, _ in best_cluster]
            total_weight = sum(c for _, c in weighted_times)
            if total_weight > 0:
                voted_time = sum(t * c for t, c in weighted_times) / total_weight
            else:
                voted_time = best_cluster[0][0]

            consistency_bonus = min(0.25, len(best_cluster) * 0.06)
            best_conf = max(c for _, _, c, _ in best_cluster) + consistency_bonus
            best_conf = min(0.95, best_conf)
            method_names = [n for _, n, _, _ in best_cluster]
            best_method = f"多引擎投票({'+'.join(method_names)})"

            logger.info(f"Turn voting: {len(best_cluster)} engines agree near t={voted_time:.2f}s, "
                        f"engines={method_names}, confidence={best_conf:.3f}")
            return voted_time, best_method, best_conf
        else:
            best = max(best_cluster, key=lambda x: x[2])
            return best[0], best[1], best[2]

    def _get_new_engine_strategies(self, params, hip_x_series, events, multi_signals, multi_signal_context):
        strategies = []

        if params.get("multi_keypoint_2d_fusion_enabled", True):
            try:
                from .turn_engines.multi_keypoint_2d_fusion_engine import MultiKeypoint2DFusionEngine
                engine = MultiKeypoint2DFusionEngine()
                if engine.is_available():
                    strategies.append(("多关键点2D融合引擎", self._make_multi_engine_wrapper(engine, multi_signal_context, params), True))
            except ImportError:
                pass

        if params.get("y_motion_pattern_enabled", True):
            try:
                from .turn_engines.y_motion_engine import YMotionEngine
                engine = YMotionEngine()
                if engine.is_available():
                    strategies.append(("纵向运动模式引擎", self._make_multi_engine_wrapper(engine, multi_signal_context, params), True))
            except ImportError:
                pass

        if params.get("velocity_2d_enabled", True):
            try:
                from .turn_engines.velocity_2d_engine import Velocity2DEngine
                engine = Velocity2DEngine()
                if engine.is_available():
                    strategies.append(("2D速度向量引擎", self._make_multi_engine_wrapper(engine, multi_signal_context, params), True))
            except ImportError:
                pass

        hmm_enabled = params.get("hmm_multi_obs_enabled", True) or params.get("hmm_turn_enabled", False)
        if hmm_enabled:
            try:
                if params.get("hmm_multi_obs_enabled", True):
                    from .turn_engines.hmm_turn_engine import HMMTurnEngine
                    engine = HMMTurnEngine()
                    if engine.is_available():
                        strategies.append(("HMM状态转移引擎", self._make_multi_engine_wrapper(engine, multi_signal_context, params), True))
                elif params.get("hmm_turn_enabled", False):
                    from .turn_engines.hmm_turn_engine import HMMTurnEngine
                    engine = HMMTurnEngine()
                    if engine.is_available():
                        strategies.append(("HMM状态转移引擎", self._make_engine_wrapper(engine, hip_x_series, events, params), False))
            except ImportError:
                pass

        wavelet_enabled = params.get("wavelet_multi_signal_enabled", True) or params.get("wavelet_break_enabled", False)
        if wavelet_enabled:
            try:
                if params.get("wavelet_multi_signal_enabled", True):
                    from .turn_engines.wavelet_break_engine import WaveletBreakEngine
                    engine = WaveletBreakEngine()
                    if engine.is_available():
                        strategies.append(("小波变换周期性断裂引擎", self._make_multi_engine_wrapper(engine, multi_signal_context, params), True))
                elif params.get("wavelet_break_enabled", False):
                    from .turn_engines.wavelet_break_engine import WaveletBreakEngine
                    engine = WaveletBreakEngine()
                    if engine.is_available():
                        strategies.append(("小波变换周期性断裂引擎", self._make_engine_wrapper(engine, hip_x_series, events, params), False))
            except ImportError:
                pass

        if params.get("visibility_change_enabled", True):
            try:
                from .turn_engines.visibility_change_engine import VisibilityChangeEngine
                engine = VisibilityChangeEngine()
                if engine.is_available():
                    strategies.append(("可见度变化引擎", self._make_multi_engine_wrapper(engine, multi_signal_context, params), True))
            except ImportError:
                pass

        if params.get("hmm_multi_obs_enabled", True):
            try:
                from .turn_engines.hmm_multi_obs_engine import HMMMultiObsEngine
                engine = HMMMultiObsEngine()
                if engine.is_available():
                    strategies.append(("HMM多观测变量引擎", self._make_multi_engine_wrapper(engine, multi_signal_context, params), True))
            except ImportError:
                pass

        if params.get("wavelet_multi_signal_enabled", True):
            try:
                from .turn_engines.wavelet_multi_signal_engine import WaveletMultiSignalEngine
                engine = WaveletMultiSignalEngine()
                if engine.is_available():
                    strategies.append(("小波多信号融合引擎", self._make_multi_engine_wrapper(engine, multi_signal_context, params), True))
            except ImportError:
                pass

        return strategies

    def _make_multi_engine_wrapper(self, engine, multi_signal_context, params):
        def wrapper(multi_signals_arg, events_arg, params_arg):
            import numpy as np
            ctx = dict(multi_signal_context)
            ctx["signal_time"] = events_arg.signal_time
            ctx["race_end"] = events_arg.race_end
            hip_x = multi_signals_arg.get("x_series", {}).get("hip_x", [])
            signal = np.array([v for _, v in hip_x]) if hip_x else np.array([])
            result = engine.detect(signal, params_arg, ctx)
            if result.success:
                turn_time = result.data.get("turn_time")
                if turn_time is not None:
                    return turn_time, result.engine_name
            return None, ""
        return wrapper

    def _make_engine_wrapper(self, engine, hip_x_series, events, params):
        def wrapper(hip_x_series_arg, events_arg, params_arg):
            import numpy as np
            signal = np.array([v for _, v in hip_x_series_arg])
            context = {
                "hip_x_series": hip_x_series_arg,
                "signal_time": events_arg.signal_time,
                "race_end": events_arg.race_end,
            }
            result = engine.detect(signal, params_arg, context)
            if result.success:
                turn_time = result.data.get("turn_time")
                if turn_time is not None:
                    return turn_time, result.engine_name
            return None, ""
        return wrapper

    def _extract_multi_keypoint_signals(self, pose_frames) -> Dict[str, Any]:
        x_series = {}
        y_series = {}
        visibility_series = {}
        visibility_diff_series = {}

        keypoint_pairs = {
            "hip": ("left_hip", "right_hip"),
            "shoulder": ("left_shoulder", "right_shoulder"),
            "wrist": ("left_wrist", "right_wrist"),
        }
        single_points = {"head": ("nose",)}

        for pair_name, (left_name, right_name) in keypoint_pairs.items():
            lx, ly, rx, ry = [], [], [], []
            l_vis, r_vis = [], []
            for pf in pose_frames:
                ts = get_timestamp(pf)
                lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
                if lm is None:
                    continue
                l_pt = get_lm(lm, left_name)
                r_pt = get_lm(lm, right_name)
                mid = midpoint(l_pt, r_pt)
                if mid is not None:
                    x_series.setdefault(f"{pair_name}_x", []).append((ts, mid[0]))
                    y_series.setdefault(f"{pair_name}_y", []).append((ts, mid[1]))
                if l_pt is not None:
                    lx.append((ts, l_pt[0]))
                    ly.append((ts, l_pt[1]))
                    l_vis_val = l_pt[3] if len(l_pt) > 3 else 1.0
                    l_vis.append((ts, l_vis_val))
                if r_pt is not None:
                    rx.append((ts, r_pt[0]))
                    ry.append((ts, r_pt[1]))
                    r_vis_val = r_pt[3] if len(r_pt) > 3 else 1.0
                    r_vis.append((ts, r_vis_val))

            if l_vis and r_vis:
                common_ts = sorted(set(t for t, _ in l_vis) & set(t for t, _ in r_vis))
                if common_ts:
                    l_vis_dict = {t: v for t, v in l_vis}
                    r_vis_dict = {t: v for t, v in r_vis}
                    diff_series = [(t, l_vis_dict[t] - r_vis_dict[t]) for t in common_ts if t in l_vis_dict and t in r_vis_dict]
                    visibility_diff_series[f"{pair_name}_vis_diff"] = diff_series

            if l_vis:
                visibility_series[f"left_{pair_name}_vis"] = l_vis
            if r_vis:
                visibility_series[f"right_{pair_name}_vis"] = r_vis

        for pt_name, (key_name,) in single_points.items():
            px, py = [], []
            for pf in pose_frames:
                ts = get_timestamp(pf)
                lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
                if lm is None:
                    continue
                pt = get_lm(lm, key_name)
                if pt is not None:
                    px.append((ts, pt[0]))
                    py.append((ts, pt[1]))
            if px:
                x_series[f"{pt_name}_x"] = px
            if py:
                y_series[f"{pt_name}_y"] = py

        availability = self._assess_signal_availability(x_series, y_series, visibility_series)

        return {
            "x_series": x_series,
            "y_series": y_series,
            "visibility_series": visibility_series,
            "visibility_diff_series": visibility_diff_series,
            "availability": availability,
        }

    def _assess_signal_availability(self, x_series, y_series, visibility_series) -> Dict[str, str]:
        availability = {}
        all_signals = {}
        for k, v in x_series.items():
            all_signals[k] = v
        for k, v in y_series.items():
            all_signals[k] = v

        for sig_name, sig_data in all_signals.items():
            if len(sig_data) < 5:
                availability[sig_name] = "不可用"
                continue
            vals = np.array([v for _, v in sig_data])
            variance = np.var(vals)
            if variance < 0.0001:
                availability[sig_name] = "低质量"
                continue
            noise_est = np.mean(np.abs(np.diff(vals)))
            signal_est = np.std(vals)
            snr = signal_est / max(noise_est, 1e-10)
            if snr < 1.5:
                availability[sig_name] = "低质量"
            else:
                availability[sig_name] = "可用"

        return availability

    def _build_multi_signal_context(self, multi_signals, events) -> Dict[str, Any]:
        return {
            "hip_x_series": multi_signals.get("x_series", {}).get("hip_x", []),
            "x_series": multi_signals.get("x_series", {}),
            "y_series": multi_signals.get("y_series", {}),
            "visibility_series": multi_signals.get("visibility_series", {}),
            "visibility_diff_series": multi_signals.get("visibility_diff_series", {}),
            "availability": multi_signals.get("availability", {}),
        }

    def _extract_hip_x_series(self, pose_frames) -> List[Tuple[float, float]]:
        hip_x_series = []
        for pf in pose_frames:
            ts = get_timestamp(pf)
            lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
            if lm is None:
                continue
            lh = get_lm(lm, "left_hip")
            rh = get_lm(lm, "right_hip")
            mid = midpoint(lh, rh)
            if mid is not None:
                hip_x_series.append((ts, mid[0]))
        return hip_x_series

    def _interpolate_hip_x_gaps(
        self, hip_x_series: List[Tuple[float, float]], params
    ) -> List[Tuple[float, float]]:
        gap_threshold = params.get("interpolation_gap_threshold", 0.5)
        if len(hip_x_series) < 2:
            return hip_x_series

        interpolated = [hip_x_series[0]]
        for i in range(1, len(hip_x_series)):
            prev_ts, prev_x = hip_x_series[i - 1]
            curr_ts, curr_x = hip_x_series[i]
            gap = curr_ts - prev_ts

            if gap > gap_threshold:
                n_fill = int(gap / gap_threshold)
                for j in range(1, n_fill):
                    frac = j / n_fill
                    fill_ts = prev_ts + gap * frac
                    fill_x = prev_x + (curr_x - prev_x) * frac
                    interpolated.append((fill_ts, fill_x))

            interpolated.append((curr_ts, curr_x))

        return interpolated

    def _detect_turn_touch(
        self, hip_x_series, events, params, use_sparse: bool = False
    ) -> Tuple[Optional[float], str]:
        if events.signal_time is None or events.race_end is None:
            return None, ""

        race_dur = events.race_end - events.signal_time
        if race_dur <= 0:
            return None, ""

        if use_sparse:
            direction_change_threshold = max(
                params.get("sparse_min_direction_change", 0.001),
                np.std([x for _, x in hip_x_series]) * params.get("sparse_direction_change_factor", 0.3)
            )
            min_turn_time_range = params.get("sparse_min_time_range", 0.2)
            max_turn_time_range = params.get("sparse_max_time_range", 0.8)
            min_before_after = params.get("sparse_before_after_frames", 3)
            min_data_points = params.get("sparse_min_data_points", 10)
        else:
            direction_change_threshold = params.get("direction_change_threshold", 0.003)
            min_turn_time_range = params.get("min_turn_time_range", 0.3)
            max_turn_time_range = params.get("max_turn_time_range", 0.7)
            min_before_after = 5
            min_data_points = 20

        if len(hip_x_series) < min_data_points:
            return None, ""

        ts_arr = np.array([t for t, _ in hip_x_series])
        x_arr = np.array([v for _, v in hip_x_series])

        min_turn_time = events.signal_time + race_dur * min_turn_time_range
        max_turn_time = events.signal_time + race_dur * max_turn_time_range
        expected_turn = events.signal_time + race_dur / 2.0

        candidates = []
        for i in range(1, len(ts_arr)):
            ts = ts_arr[i]
            if ts < min_turn_time or ts > max_turn_time:
                continue
            before = [(t, x) for t, x in zip(ts_arr[:i], x_arr[:i]) if min_turn_time <= t <= ts]
            after = [(t, x) for t, x in zip(ts_arr[i:], x_arr[i:]) if ts <= t <= max_turn_time]
            if len(before) < min_before_after or len(after) < min_before_after:
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
            if abs(best_ts - expected_turn) < race_dur * 0.15:
                method = "主算法首次检测" if not use_sparse else "主算法首次检测（稀疏模式）"
                return float(best_ts), method

        return None, ""

    def _retry1_widened_window(
        self, hip_x_series, events, params
    ) -> Tuple[Optional[float], str]:
        if events.signal_time is None or events.race_end is None:
            return None, ""

        race_dur = events.race_end - events.signal_time
        min_turn_time_range = params.get("retry1_min_time_range", 0.15)
        max_turn_time_range = params.get("retry1_max_time_range", 0.85)
        threshold_factor = params.get("retry1_threshold_factor", 0.5)

        base_threshold = params.get("direction_change_threshold", 0.003)
        direction_change_threshold = base_threshold * threshold_factor

        if len(hip_x_series) < params.get("sparse_min_data_points", 10):
            return None, ""

        ts_arr = np.array([t for t, _ in hip_x_series])
        x_arr = np.array([v for _, v in hip_x_series])

        min_turn_time = events.signal_time + race_dur * min_turn_time_range
        max_turn_time = events.signal_time + race_dur * max_turn_time_range
        expected_turn = events.signal_time + race_dur / 2.0

        candidates = []
        for i in range(1, len(ts_arr)):
            ts = ts_arr[i]
            if ts < min_turn_time or ts > max_turn_time:
                continue
            before = [(t, x) for t, x in zip(ts_arr[:i], x_arr[:i]) if min_turn_time <= t <= ts]
            after = [(t, x) for t, x in zip(ts_arr[i:], x_arr[i:]) if ts <= t <= max_turn_time]
            if len(before) < 2 or len(after) < 2:
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
            return float(best_ts), "第1次重试（放宽窗口）"

        return None, ""

    def _detect_turn_by_position_clustering(
        self, hip_x_series, events, params
    ) -> Tuple[Optional[float], str]:
        if events.signal_time is None or events.race_end is None:
            return None, ""

        race_dur = events.race_end - events.signal_time
        window = params.get("position_clustering_window", 0.5)
        threshold = params.get("position_clustering_threshold", 0.15)

        ts_arr = np.array([t for t, _ in hip_x_series])
        x_arr = np.array([v for _, v in hip_x_series])

        min_time = events.signal_time + race_dur * 0.2
        max_time = events.signal_time + race_dur * 0.8
        expected_turn = events.signal_time + race_dur / 2.0

        candidates = []
        for i in range(len(ts_arr)):
            ts = ts_arr[i]
            if ts < min_time or ts > max_time:
                continue

            before_mask = (ts_arr >= ts - window) & (ts_arr <= ts)
            after_mask = (ts_arr >= ts) & (ts_arr <= ts + window)

            before_x = x_arr[before_mask]
            after_x = x_arr[after_mask]

            if len(before_x) < 1 or len(after_x) < 1:
                continue

            mean_diff = abs(np.mean(before_x) - np.mean(after_x))
            if mean_diff > threshold:
                proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                candidates.append((ts, mean_diff * max(0, proximity)))

        if candidates:
            candidates.sort(key=lambda c: -c[1])
            best_ts = candidates[0][0]
            return float(best_ts), "第2次重试（位置聚类引擎）"

        return None, ""

    def _detect_turn_by_velocity_direction(
        self, hip_x_series, events, params
    ) -> Tuple[Optional[float], str]:
        if events.signal_time is None or events.race_end is None:
            return None, ""

        race_dur = events.race_end - events.signal_time
        min_time_range = params.get("velocity_direction_time_range", 0.2)

        if len(hip_x_series) < 3:
            return None, ""

        ts_arr = np.array([t for t, _ in hip_x_series])
        x_arr = np.array([v for _, v in hip_x_series])

        min_time = events.signal_time + race_dur * min_time_range
        max_time = events.signal_time + race_dur * 0.8
        expected_turn = events.signal_time + race_dur / 2.0

        velocities = []
        for i in range(1, len(ts_arr)):
            dt = ts_arr[i] - ts_arr[i - 1]
            if dt <= 0:
                continue
            vx = (x_arr[i] - x_arr[i - 1]) / dt
            velocities.append((ts_arr[i], vx))

        if len(velocities) < 2:
            return None, ""

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
            best_ts = candidates[0][0]
            return float(best_ts), "第3次重试（速度方向引擎）"

        return None, ""

    def _calculate_turn_confidence(
        self, hip_x_series, turn_touch, events, attempt: int, params
    ) -> float:
        if events.signal_time is None or events.race_end is None:
            return 0.0

        race_dur = events.race_end - events.signal_time

        window_before = turn_touch - race_dur * 0.1
        window_after = turn_touch + race_dur * 0.1
        window_points = sum(1 for t, _ in hip_x_series if window_before <= t <= window_after)
        window_frames = max(1, int(race_dur * 0.2 * 30))
        coverage_score = min(1.0, window_points / window_frames)

        ts_arr = np.array([t for t, _ in hip_x_series])
        x_arr = np.array([v for _, v in hip_x_series])
        nearby = [(t, x) for t, x in zip(ts_arr, x_arr)
                  if turn_touch - race_dur * 0.15 <= t <= turn_touch + race_dur * 0.15]
        if len(nearby) >= 4:
            before_x = [x for t, x in nearby if t <= turn_touch]
            after_x = [x for t, x in nearby if t > turn_touch]
            if len(before_x) >= 2 and len(after_x) >= 2:
                before_dx = np.mean(np.diff(before_x))
                after_dx = np.mean(np.diff(after_x))
                change_magnitude = abs(before_dx - after_dx)
                noise_std = max(np.std(x_arr), 1e-6)
                significance_score = min(1.0, change_magnitude / (noise_std * 3))
            else:
                significance_score = 0.3
        else:
            significance_score = 0.2

        expected_turn = events.signal_time + race_dur / 2.0
        time_diff = abs(turn_touch - expected_turn) / (race_dur / 2.0)
        reasonableness_score = max(0, 1.0 - time_diff / 0.2)

        method_scores = {0: 1.0, 1: 0.7, 2: 0.5, 3: 0.3}
        method_score = method_scores.get(attempt, 0.3)

        confidence = (coverage_score * 0.4 + significance_score * 0.3 +
                      reasonableness_score * 0.2 + method_score * 0.1)

        return round(min(max(confidence, 0.0), 1.0), 3)

    def _generate_diagnosis(
        self, hip_x_series, retry_records, force_reason, params
    ) -> str:
        sparse_min = params.get("sparse_min_data_points", 10)
        direction_change_threshold = params.get("direction_change_threshold", 0.003)

        parts = []
        parts.append(f"窗口内有效髋部数据点数：{len(hip_x_series)}")

        if len(hip_x_series) > 0:
            ts_vals = [t for t, _ in hip_x_series]
            if len(ts_vals) > 1:
                coverage_pct = len(hip_x_series) / max(1, int((max(ts_vals) - min(ts_vals)) * 30))
                parts.append(f"窗口内覆盖率：{min(coverage_pct * 100, 100):.1f}%")

            x_vals = [v for _, v in hip_x_series]
            x_var = np.var(x_vals) if len(x_vals) > 1 else 0
            if x_var < 0.001:
                parts.append("x方向信号质量：低（方差极小，可能为俯视/侧面拍摄）")
            elif x_var < 0.01:
                parts.append("x方向信号质量：中")
            else:
                parts.append("x方向信号质量：高")

        for rr in retry_records:
            status = "成功" if rr.success else "失败"
            parts.append(f"{rr.strategy_name}：{status}")

        if force_reason:
            reason = force_reason
        elif len(hip_x_series) < sparse_min:
            reason = "数据不足"
        else:
            x_vals = [v for _, v in hip_x_series]
            x_var = np.var(x_vals) if len(x_vals) > 1 else 0
            if x_var < 0.001:
                reason = "x方向变化不显著（俯视/侧面视频，建议启用纵向运动检测引擎）"
            else:
                reason = "方向变化不显著"

        parts.append(f"失败原因：{reason}")

        if reason == "数据不足":
            parts.append("建议：降低姿态估计置信度阈值后重新分析")
        elif "俯视" in reason or "侧面" in reason:
            parts.append("建议：启用纵向运动模式引擎和2D速度向量引擎")
        elif reason == "方向变化不显著":
            parts.append("建议：降低转身检测方向变化阈值")
        elif reason == "数据完全缺失":
            parts.append("建议：检查视频质量或调整检测参数")

        return "；".join(parts)

    def _detect_turn_surface(self, pose_frames, turn_touch, water_y):
        if turn_touch is None or water_y == 0.5:
            from .utils import detect_water_surface
            water_y = detect_water_surface(pose_frames)

        surface_threshold = water_y + 0.03
        surface_count = 0
        min_surface_frames = 2

        for pf in pose_frames:
            ts = get_timestamp(pf)
            if ts < turn_touch + 0.3:
                continue
            if ts > turn_touch + 15.0:
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

    def _count_turn_kicks(self, pose_frames, turn_touch, turn_surface):
        if turn_touch is None or turn_surface is None:
            return 0
        la_y, ra_y = [], []
        for pf in pose_frames:
            ts = get_timestamp(pf)
            if ts < turn_touch or ts > turn_surface:
                continue
            la = get_lm(pf.get("landmarks", {}) if isinstance(pf, dict) else getattr(pf, 'landmarks', {}), "left_ankle")
            ra = get_lm(pf.get("landmarks", {}) if isinstance(pf, dict) else getattr(pf, 'landmarks', {}), "right_ankle")
            la_y.append(la[1] if la is not None else None)
            ra_y.append(ra[1] if ra is not None else None)

        total = 0
        curr_l, curr_r = [], []
        for l, r in zip(la_y, ra_y):
            if l is not None and r is not None:
                curr_l.append(l)
                curr_r.append(r)
            else:
                if len(curr_l) >= 3:
                    diff = np.array(curr_l) - np.array(curr_r)
                    cd = 0
                    for i in range(1, len(diff)):
                        if cd > 0:
                            cd -= 1
                            continue
                        if diff[i-1] * diff[i] < 0:
                            total += 1
                            cd = max(2, len(diff) // 30)
                curr_l, curr_r = [], []
        if len(curr_l) >= 3:
            diff = np.array(curr_l) - np.array(curr_r)
            cd = 0
            for i in range(1, len(diff)):
                if cd > 0:
                    cd -= 1
                    continue
                if diff[i-1] * diff[i] < 0:
                    total += 1
                    cd = max(2, len(diff) // 30)
        return total
