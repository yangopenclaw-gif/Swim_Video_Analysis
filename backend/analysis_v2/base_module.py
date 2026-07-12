import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from .shared import (
    AnalysisContext, ModuleResult, EngineResult, EngineSwitchRecord,
    RetryRecord, AccuracyInfo,
)

logger = logging.getLogger(__name__)


class AnalysisModule(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def analyze(self, context: AnalysisContext) -> ModuleResult:
        pass

    def _should_retry(self, result: EngineResult, coverage: float = 0.0) -> bool:
        if not result.success:
            return True
        if coverage < 0.05:
            return True
        data = result.data
        for key, val in data.items():
            if isinstance(val, (int, float)) and val == 0:
                return True
            if isinstance(val, str) and "未检测到" in val:
                return True
        return False

    def _get_backup_engines(self) -> List[str]:
        return []

    def _execute_primary_engine(self, context: AnalysisContext) -> EngineResult:
        raise NotImplementedError

    def _execute_backup_engine(self, engine_name: str, context: AnalysisContext) -> EngineResult:
        raise NotImplementedError

    def _execute_with_engine_switch(self, context: AnalysisContext) -> tuple:
        primary_result = self._execute_primary_engine(context)
        switch_record = EngineSwitchRecord(
            metric_name=self.name,
            primary_engine="primary",
            primary_result=primary_result.data if primary_result else None,
            primary_success=primary_result.success if primary_result else False,
            final_engine="primary" if primary_result and primary_result.success else "",
            final_result=primary_result.data if primary_result and primary_result.success else None,
        )

        if primary_result and primary_result.success:
            return primary_result, switch_record

        backup_engines = self._get_backup_engines()
        for engine_name in backup_engines:
            try:
                backup_result = self._execute_backup_engine(engine_name, context)
                switch_record.backup_engines_tried.append({
                    "engine": engine_name,
                    "success": backup_result.success,
                    "confidence": backup_result.confidence,
                })
                if backup_result.success:
                    switch_record.final_engine = engine_name
                    switch_record.final_result = backup_result.data
                    logger.info(f"[{self.name}] Switched to backup engine: {engine_name}")
                    return backup_result, switch_record
            except Exception as e:
                logger.warning(f"[{self.name}] Backup engine {engine_name} failed: {e}")
                switch_record.backup_engines_tried.append({
                    "engine": engine_name,
                    "success": False,
                    "error": str(e),
                })

        if not switch_record.final_engine:
            switch_record.final_engine = "none"
            switch_record.final_result = None

        return primary_result, switch_record

    def _assess_accuracy(self, result: ModuleResult, context: AnalysisContext,
                         coverage: float = 0.0, signal_confidence: float = 0.0,
                         consistency: float = 0.0) -> AccuracyInfo:
        confidence = (
            coverage * 0.4
            + signal_confidence * 0.3
            + consistency * 0.2
            + (0.1 if not result.engine_switch_records else 0.05) * 1.0
        )
        confidence = min(max(confidence, 0.0), 1.0)

        if confidence >= 0.7:
            quality = "高"
        elif confidence >= 0.4:
            quality = "中"
        else:
            quality = "低"

        low_confidence = confidence < 0.3
        warnings = []
        if low_confidence:
            warnings.append("低置信度")
        if coverage < 0.1:
            warnings.append("关键点覆盖率极低")
        if result.engine_switch_records:
            for sr in result.engine_switch_records:
                if sr.backup_engines_tried:
                    warnings.append(f"主引擎失败，已切换至{sr.final_engine}")

        return AccuracyInfo(
            confidence=round(confidence, 3),
            coverage=round(coverage, 3),
            quality=quality,
            low_confidence=low_confidence,
            warnings=warnings,
        )