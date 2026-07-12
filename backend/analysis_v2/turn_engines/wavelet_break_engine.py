import logging
import numpy as np
from typing import Dict, Any, List

from ..engines.engine_protocol import EngineProtocol, EngineResult

logger = logging.getLogger(__name__)


class WaveletBreakEngine(EngineProtocol):
    @property
    def name(self) -> str:
        return "小波变换周期性断裂"

    @property
    def priority(self) -> int:
        return 4

    def is_available(self) -> bool:
        try:
            import pywt
            return True
        except ImportError:
            return False

    def get_dependencies(self) -> List[str]:
        return ["pywt"]

    def detect(self, signal: np.ndarray, params: Dict[str, Any], context: Dict[str, Any]) -> EngineResult:
        try:
            import pywt
        except ImportError:
            return EngineResult(success=False, engine_name=self.name)

        hip_x_series = context.get("hip_x_series")
        if hip_x_series is None or len(hip_x_series) < 20:
            return EngineResult(success=False, engine_name=self.name)

        signal_time = context.get("signal_time")
        race_end = context.get("race_end")
        if signal_time is None or race_end is None:
            return EngineResult(success=False, engine_name=self.name)

        race_dur = race_end - signal_time
        if race_dur <= 0:
            return EngineResult(success=False, engine_name=self.name)

        wavelet_name = params.get("wavelet_break_wavelet", "db4")
        level = params.get("wavelet_break_level", 4)

        ts_arr = np.array([t for t, _ in hip_x_series])
        x_arr = np.array([v for _, v in hip_x_series])

        if len(x_arr) < 2 ** level:
            level = max(1, int(np.log2(len(x_arr))) - 1)

        try:
            coeffs = pywt.wavedec(x_arr, wavelet_name, level=level)
        except Exception as e:
            logger.warning(f"Wavelet decomposition failed: {e}")
            return EngineResult(success=False, engine_name=self.name)

        detail_levels = coeffs[1:] if len(coeffs) > 1 else coeffs
        target_level_idx = min(len(detail_levels) - 1, max(0, len(detail_levels) // 2))
        detail_coeffs = detail_levels[target_level_idx]

        window_size = max(3, len(detail_coeffs) // 20)
        energy = np.array([
            np.sum(detail_coeffs[max(0, i - window_size):i + window_size + 1] ** 2)
            for i in range(len(detail_coeffs))
        ])

        energy_diff = np.abs(np.diff(energy))
        if len(energy_diff) == 0:
            return EngineResult(success=False, engine_name=self.name)

        threshold = np.mean(energy_diff) + 2 * np.std(energy_diff)
        break_indices = np.where(energy_diff > threshold)[0]

        if len(break_indices) == 0:
            threshold = np.mean(energy_diff) + np.std(energy_diff)
            break_indices = np.where(energy_diff > threshold)[0]

        if len(break_indices) == 0:
            return EngineResult(success=False, engine_name=self.name)

        min_time = signal_time + race_dur * 0.2
        max_time = signal_time + race_dur * 0.8
        expected_turn = signal_time + race_dur / 2.0

        candidates = []
        for idx in break_indices:
            ts_idx = int(idx * len(ts_arr) / len(detail_coeffs))
            ts_idx = min(ts_idx, len(ts_arr) - 1)
            ts = ts_arr[ts_idx]

            if min_time <= ts <= max_time:
                proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                significance = energy_diff[idx] / max(threshold, 1e-10)
                candidates.append((ts, significance * max(0, proximity)))

        if not candidates:
            return EngineResult(success=False, engine_name=self.name)

        candidates.sort(key=lambda c: -c[1])
        best_ts = candidates[0][0]

        confidence = min(0.9, 0.3 + candidates[0][1] * 0.2)

        return EngineResult(
            success=True,
            data={"turn_time": float(best_ts), "wavelet": wavelet_name,
                  "level": level, "break_significance": float(candidates[0][1])},
            engine_name=self.name,
            confidence=confidence,
        )