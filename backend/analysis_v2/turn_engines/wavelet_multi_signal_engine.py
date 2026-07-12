import logging
import numpy as np
from typing import Dict, Any, List

from ..engines.engine_protocol import EngineProtocol, EngineResult

logger = logging.getLogger(__name__)


class WaveletMultiSignalEngine(EngineProtocol):
    @property
    def name(self) -> str:
        return "小波多信号融合"

    @property
    def priority(self) -> int:
        return 7

    def is_available(self) -> bool:
        try:
            import pywt
            return True
        except ImportError:
            return False

    def get_dependencies(self) -> List[str]:
        return ["pywt", "numpy"]

    def detect(self, signal: np.ndarray, params: Dict[str, Any], context: Dict[str, Any]) -> EngineResult:
        try:
            import pywt
        except ImportError:
            return EngineResult(success=False, engine_name=self.name)

        x_series_dict = context.get("x_series", {})
        y_series_dict = context.get("y_series", {})
        signal_time = context.get("signal_time")
        race_end = context.get("race_end")

        if signal_time is None or race_end is None:
            return EngineResult(success=False, engine_name=self.name)

        race_dur = race_end - signal_time
        if race_dur <= 0:
            return EngineResult(success=False, engine_name=self.name)

        wavelet_name = params.get("wavelet_multi_signal_wavelet", "db4")
        level = params.get("wavelet_multi_signal_level", 4)
        cluster_window = params.get("wavelet_cluster_window", 1.0)
        dive_exclusion = params.get("y_motion_dive_exclusion", 8.0)

        min_time = signal_time + race_dur * 0.2
        max_time = signal_time + race_dur * 0.8
        expected_turn = signal_time + race_dur / 2.0
        dive_cutoff = signal_time + dive_exclusion

        signal_pairs = [
            ("hip_x", x_series_dict), ("hip_y", y_series_dict),
            ("shoulder_x", x_series_dict), ("shoulder_y", y_series_dict),
            ("wrist_x", x_series_dict), ("wrist_y", y_series_dict),
        ]

        all_break_points = []

        for sig_name, series_dict in signal_pairs:
            if sig_name not in series_dict:
                continue
            series = series_dict[sig_name]
            if len(series) < 20:
                continue

            ts_arr = np.array([t for t, _ in series])
            vals = np.array([v for _, v in series])

            try:
                actual_level = min(level, pywt.dwt_max_level(len(vals), wavelet_name))
                if actual_level < 1:
                    continue

                coeffs = pywt.wavedec(vals, wavelet_name, level=actual_level)

                for detail_level in range(1, len(coeffs)):
                    detail = coeffs[detail_level]
                    if len(detail) < 3:
                        continue

                    detail_std = np.std(detail)
                    if detail_std < 1e-10:
                        continue

                    threshold = detail_std * 2.0
                    large_coeffs = np.where(np.abs(detail) > threshold)[0]

                    if len(large_coeffs) == 0:
                        continue

                    for idx in large_coeffs:
                        approx_ts_idx = min(
                            int(idx * len(ts_arr) / len(detail)),
                            len(ts_arr) - 1
                        )
                        ts = ts_arr[approx_ts_idx]

                        if ts < min_time or ts > max_time:
                            continue
                        if ts < dive_cutoff:
                            continue

                        magnitude = abs(detail[idx]) / detail_std
                        all_break_points.append((float(ts), magnitude, sig_name, detail_level))

            except Exception as e:
                logger.debug(f"Wavelet failed for {sig_name}: {e}")
                continue

        if not all_break_points:
            return EngineResult(success=False, engine_name=self.name)

        clusters = []
        used = set()
        sorted_points = sorted(all_break_points, key=lambda x: x[0])

        for i, (ts_i, mag_i, sig_i, lvl_i) in enumerate(sorted_points):
            if i in used:
                continue
            cluster = [(ts_i, mag_i, sig_i, lvl_i)]
            used.add(i)
            for j, (ts_j, mag_j, sig_j, lvl_j) in enumerate(sorted_points):
                if j in used:
                    continue
                if abs(ts_j - ts_i) < cluster_window:
                    cluster.append((ts_j, mag_j, sig_j, lvl_j))
                    used.add(j)
            clusters.append(cluster)

        scored_clusters = []
        for cluster in clusters:
            total_mag = sum(m for _, m, _, _ in cluster)
            n_signals = len(set(s for _, _, s, _ in cluster))
            avg_ts = sum(t for t, _, _, _ in cluster) / len(cluster)
            proximity = 1.0 - abs(avg_ts - expected_turn) / (race_dur / 2.0)
            score = total_mag * n_signals * max(0, proximity)
            scored_clusters.append((avg_ts, score, n_signals, total_mag, cluster))

        scored_clusters.sort(key=lambda c: -c[1])

        best = scored_clusters[0]
        best_ts = best[0]
        n_signals = best[2]

        consistency_bonus = min(0.2, n_signals * 0.05)
        confidence = min(0.85, 0.25 + best[1] * 0.1 + consistency_bonus)

        return EngineResult(
            success=True,
            data={"turn_time": best_ts, "n_signals": n_signals,
                  "total_magnitude": best[3]},
            engine_name=self.name,
            confidence=confidence,
        )