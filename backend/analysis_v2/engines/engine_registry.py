import logging
import time
from typing import Dict, Any, List, Optional

import numpy as np

from .engine_protocol import EngineProtocol, EngineResult

logger = logging.getLogger(__name__)


class EngineRegistry:
    def __init__(self):
        self._engines: Dict[str, List[EngineProtocol]] = {}
        self._availability: Dict[str, Dict[str, bool]] = {}
        self._evaluation_records: List[Dict[str, Any]] = []

    def register(self, module_name: str, engine: EngineProtocol) -> None:
        if module_name not in self._engines:
            self._engines[module_name] = []
        self._engines[module_name].append(engine)
        self._engines[module_name].sort(key=lambda e: e.priority)
        available = engine.is_available()
        if module_name not in self._availability:
            self._availability[module_name] = {}
        self._availability[module_name][engine.name] = available
        if not available:
            deps = engine.get_dependencies()
            logger.warning(f"引擎{engine.name}不可用（依赖库{deps}未安装或不可用），已跳过")

    def get_engines(self, module_name: str) -> List[EngineProtocol]:
        return self._engines.get(module_name, [])

    def run_with_fallback(
        self, module_name: str, signal: np.ndarray, params: Dict[str, Any], context: Dict[str, Any]
    ) -> EngineResult:
        engines = self.get_engines(module_name)
        engines_tried = []
        for engine in engines:
            if not self._availability.get(module_name, {}).get(engine.name, False):
                engines_tried.append(engine.name)
                continue
            engines_tried.append(engine.name)
            try:
                start_time = time.time()
                result = engine.detect(signal, params, context)
                elapsed_ms = (time.time() - start_time) * 1000
                result.latency_ms = round(elapsed_ms, 1)
                result.engine_name = engine.name
                self._record_evaluation(module_name, engine.name, result)
                if result.success:
                    logger.info(f"模块{module_name}引擎{engine.name}检测成功(conf={result.confidence:.2f}, {elapsed_ms:.0f}ms)")
                    result.data["engines_tried"] = engines_tried
                    return result
                else:
                    logger.debug(f"模块{module_name}引擎{engine.name}检测失败")
            except Exception as e:
                logger.warning(f"模块{module_name}引擎{engine.name}运行异常: {e}")
                self._record_evaluation(module_name, engine.name, EngineResult(
                    success=False, engine_name=engine.name, confidence=0.0
                ))

        return EngineResult(
            success=False,
            data={"engines_tried": engines_tried},
            engine_name="",
            confidence=0.0,
        )

    def check_availability(self, module_name: str = None) -> Dict[str, Dict[str, bool]]:
        if module_name:
            engines = self.get_engines(module_name)
            result = {}
            for engine in engines:
                available = engine.is_available()
                result[engine.name] = available
                self._availability.setdefault(module_name, {})[engine.name] = available
                if not available:
                    logger.warning(f"引擎{engine.name}不可用（依赖库{engine.get_dependencies()}未安装或不可用），已跳过")
            return {module_name: result}

        for mod_name, engines in self._engines.items():
            for engine in engines:
                available = engine.is_available()
                self._availability.setdefault(mod_name, {})[engine.name] = available
                if not available:
                    logger.warning(f"引擎{engine.name}不可用（依赖库{engine.get_dependencies()}未安装或不可用），已跳过")
        return dict(self._availability)

    def _record_evaluation(self, module_name: str, engine_name: str, result: EngineResult) -> None:
        self._evaluation_records.append({
            "module_name": module_name,
            "engine_name": engine_name,
            "timestamp": time.time(),
            "success": result.success,
            "confidence": result.confidence,
            "latency_ms": result.latency_ms,
        })

    def should_promote_engine(self, module_name: str, engine_name: str, min_samples: int = 10, threshold: float = 0.6) -> bool:
        records = [r for r in self._evaluation_records
                    if r["module_name"] == module_name and r["engine_name"] == engine_name and r["success"]]
        if len(records) < min_samples:
            return False
        success_rate = sum(1 for r in records if r["success"]) / len(records)
        return success_rate >= threshold

    def get_availability_report(self) -> str:
        lines = ["=== 引擎可用性报告 ==="]
        for mod_name, engines in self._engines.items():
            lines.append(f"\n[{mod_name}]")
            for engine in engines:
                available = self._availability.get(mod_name, {}).get(engine.name, False)
                status = "✓ 可用" if available else "✗ 不可用"
                deps = ", ".join(engine.get_dependencies()) if engine.get_dependencies() else "无额外依赖"
                lines.append(f"  {engine.name} (优先级{engine.priority}): {status} [依赖: {deps}]")
        return "\n".join(lines)