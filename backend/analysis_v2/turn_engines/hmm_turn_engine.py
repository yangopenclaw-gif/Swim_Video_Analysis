import logging
import numpy as np
from typing import Dict, Any, List

from ..engines.engine_protocol import EngineProtocol, EngineResult

logger = logging.getLogger(__name__)


class HMMTurnEngine(EngineProtocol):
    @property
    def name(self) -> str:
        return "HMM状态转移"

    @property
    def priority(self) -> int:
        return 3

    def is_available(self) -> bool:
        try:
            from hmmlearn import hmm
            return True
        except ImportError:
            return False

    def get_dependencies(self) -> List[str]:
        return ["hmmlearn"]

    def detect(self, signal: np.ndarray, params: Dict[str, Any], context: Dict[str, Any]) -> EngineResult:
        try:
            from hmmlearn import hmm
        except ImportError:
            return EngineResult(success=False, engine_name=self.name)

        hip_x_series = context.get("hip_x_series")
        if hip_x_series is None or len(hip_x_series) < 10:
            return EngineResult(success=False, engine_name=self.name)

        signal_time = context.get("signal_time")
        race_end = context.get("race_end")
        if signal_time is None or race_end is None:
            return EngineResult(success=False, engine_name=self.name)

        race_dur = race_end - signal_time
        if race_dur <= 0:
            return EngineResult(success=False, engine_name=self.name)

        n_states = params.get("hmm_turn_n_states", 5)
        n_iter = params.get("hmm_turn_n_iter", 50)

        ts_arr = np.array([t for t, _ in hip_x_series])
        x_arr = np.array([v for _, v in hip_x_series])

        dx = np.diff(x_arr)
        dt = np.diff(ts_arr)
        dt[dt == 0] = 1e-6
        vx = dx / dt

        obs_len = min(len(vx), len(x_arr) - 1)
        obs = np.column_stack([
            x_arr[:obs_len],
            vx[:obs_len],
        ])

        obs = obs.astype(np.float64)
        obs = np.nan_to_num(obs, nan=0.0, posinf=0.0, neginf=0.0)

        std_x = np.std(obs[:, 0]) if np.std(obs[:, 0]) > 0 else 1.0
        std_v = np.std(obs[:, 1]) if np.std(obs[:, 1]) > 0 else 1.0
        obs[:, 0] /= std_x
        obs[:, 1] /= std_v

        try:
            model = hmm.GaussianHMM(
                n_components=n_states,
                covariance_type="full",
                n_iter=n_iter,
                random_state=42,
            )
            model.fit(obs)
            _, state_seq = model.decode(obs)
        except Exception as e:
            logger.warning(f"HMM fitting failed: {e}")
            return EngineResult(success=False, engine_name=self.name)

        min_time = signal_time + race_dur * 0.2
        max_time = signal_time + race_dur * 0.8
        expected_turn = signal_time + race_dur / 2.0

        transition_points = []
        for i in range(1, len(state_seq)):
            if state_seq[i] != state_seq[i - 1]:
                ts = ts_arr[min(i, len(ts_arr) - 1)]
                if min_time <= ts <= max_time:
                    proximity = 1.0 - abs(ts - expected_turn) / (race_dur / 2.0)
                    transition_points.append((ts, state_seq[i - 1], state_seq[i], proximity))

        if not transition_points:
            return EngineResult(success=False, engine_name=self.name)

        transition_points.sort(key=lambda p: -p[3])
        best_ts = transition_points[0][0]

        confidence = 0.5
        if len(transition_points) > 1:
            consistency = sum(1 for _, s1, s2, _ in transition_points[:5]
                             if s1 == transition_points[0][1] and s2 == transition_points[0][2])
            confidence = min(0.9, 0.3 + consistency * 0.1)

        return EngineResult(
            success=True,
            data={"turn_time": float(best_ts), "n_states": n_states,
                  "state_transition": f"{transition_points[0][1]}→{transition_points[0][2]}"},
            engine_name=self.name,
            confidence=confidence,
        )