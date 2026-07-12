import logging
import numpy as np
from typing import Dict, Any, List

from ..engines.engine_protocol import EngineProtocol, EngineResult

logger = logging.getLogger(__name__)


class HMMMultiObsEngine(EngineProtocol):
    @property
    def name(self) -> str:
        return "HMM多观测变量"

    @property
    def priority(self) -> int:
        return 6

    def is_available(self) -> bool:
        try:
            from hmmlearn.hmm import GaussianHMM
            return True
        except ImportError:
            return False

    def get_dependencies(self) -> List[str]:
        return ["hmmlearn", "numpy"]

    def detect(self, signal: np.ndarray, params: Dict[str, Any], context: Dict[str, Any]) -> EngineResult:
        try:
            from hmmlearn.hmm import GaussianHMM
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

        n_states = params.get("hmm_multi_obs_n_states", 5)
        n_iter = params.get("hmm_multi_obs_n_iter", 100)
        dive_exclusion = params.get("y_motion_dive_exclusion", 8.0)

        min_time = signal_time + race_dur * 0.2
        max_time = signal_time + race_dur * 0.8
        expected_turn = signal_time + race_dur / 2.0
        dive_cutoff = signal_time + dive_exclusion

        keypoint_pairs = [
            ("hip", "hip_x", "hip_y"),
            ("shoulder", "shoulder_x", "shoulder_y"),
            ("wrist", "wrist_x", "wrist_y"),
        ]

        obs_signals = {}
        for kp_name, x_key, y_key in keypoint_pairs:
            if x_key in x_series_dict and y_key in y_series_dict:
                x_s = x_series_dict[x_key]
                y_s = y_series_dict[y_key]
                ts_x = {t: v for t, v in x_s}
                ts_y = {t: v for t, v in y_s}
                common_ts = sorted(set(ts_x.keys()) & set(ts_y.keys()))
                if len(common_ts) >= 20:
                    obs_signals[kp_name] = {
                        "ts": np.array(common_ts),
                        "x": np.array([ts_x[t] for t in common_ts]),
                        "y": np.array([ts_y[t] for t in common_ts]),
                    }

        if not obs_signals:
            return EngineResult(success=False, engine_name=self.name)

        all_candidates = []

        for kp_name, data in obs_signals.items():
            ts_arr = data["ts"]
            x_vals = data["x"]
            y_vals = data["y"]

            obs_matrix = np.column_stack([x_vals, y_vals])

            n_obs = len(obs_matrix)
            actual_n_states = min(n_states, max(2, n_obs // 10))

            try:
                model = GaussianHMM(
                    n_components=actual_n_states,
                    covariance_type="full",
                    n_iter=n_iter,
                    random_state=42,
                    tol=0.01,
                )
                model.fit(obs_matrix)
                states = model.predict(obs_matrix)
            except Exception as e:
                logger.debug(f"HMM multi-obs failed for {kp_name}: {e}")
                continue

            state_changes = []
            for i in range(1, len(states)):
                if states[i] != states[i - 1]:
                    state_changes.append((i, states[i - 1], states[i]))

            if len(state_changes) < 2:
                continue

            for i, (change_idx, prev_state, curr_state) in enumerate(state_changes):
                ts = ts_arr[change_idx]
                if ts < min_time or ts > max_time:
                    continue
                if ts < dive_cutoff:
                    continue

                before_count = sum(1 for _, ps, _ in state_changes[:i] if ps == prev_state)
                after_count = sum(1 for _, _, cs in state_changes[i:] if cs == curr_state)

                transition_significance = 1.0 / (1.0 + abs(before_count - after_count))

                proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                score = transition_significance * max(0, proximity)
                all_candidates.append((float(ts), score, kp_name, prev_state, curr_state))

        if not all_candidates:
            return EngineResult(success=False, engine_name=self.name)

        all_candidates.sort(key=lambda c: -c[1])
        best_ts = all_candidates[0][0]
        best_kp = all_candidates[0][2]

        consistency_window = 3.0
        consistent_count = sum(
            1 for c in all_candidates
            if abs(c[0] - best_ts) < consistency_window and c[2] != best_kp
        )
        consistency_bonus = min(0.15, consistent_count * 0.05)

        confidence = min(0.85, 0.3 + all_candidates[0][1] * 0.3 + consistency_bonus)

        return EngineResult(
            success=True,
            data={"turn_time": best_ts, "keypoint": best_kp,
                  "prev_state": int(all_candidates[0][3]),
                  "curr_state": int(all_candidates[0][4])},
            engine_name=self.name,
            confidence=confidence,
        )