from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List

import numpy as np


@dataclass
class EngineResult:
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    engine_name: str = ""
    confidence: float = 0.0
    latency_ms: float = 0.0


class EngineProtocol(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def detect(self, signal: np.ndarray, params: Dict[str, Any], context: Dict[str, Any]) -> EngineResult:
        pass

    @abstractmethod
    def get_dependencies(self) -> List[str]:
        pass