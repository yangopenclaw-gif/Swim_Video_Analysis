import logging
from typing import Optional, Dict, Any
from .base_module import AnalysisModule
from .shared import AnalysisContext, ModuleResult, AccuracyInfo

class SpeedCalculator(AnalysisModule):
    VERSION = "4.0.0"
    
    @property
    def name(self) -> str:
        return "速度计算"
    
    def analyze(self, context: AnalysisContext) -> ModuleResult:
        events = context.events
        is_50m_50pool = context.is_50m_50pool
        pool_length = context.pool_length
        race_distance = context.race_distance
        half_distance = pool_length
        
        metrics = {}
        
        if is_50m_50pool:
            race_duration = context.race_duration
            if race_duration > 0:
                speed = round(race_distance / race_duration, 2)
                metrics["途中游速度"] = f"{speed:.2f} 米/秒"
            else:
                metrics["途中游速度"] = "未检测到"
        else:
            turn_touch = events.turn_touch
            signal_time = events.signal_time
            dive_start = events.dive_start
            race_end = events.race_end
            
            start_time = signal_time if signal_time is not None else dive_start
            
            if turn_touch is not None and start_time is not None:
                first_dur = turn_touch - start_time
                if first_dur > 0:
                    metrics["前程途中游速度"] = f"{half_distance / first_dur:.2f} 米/秒"
                else:
                    metrics["前程途中游速度"] = "未检测到"
            else:
                metrics["前程途中游速度"] = "未检测到"
            
            if turn_touch is not None and race_end is not None:
                second_dur = race_end - turn_touch
                if second_dur > 0:
                    metrics["后程途中游速度"] = f"{half_distance / second_dur:.2f} 米/秒"
                else:
                    metrics["后程途中游速度"] = "未检测到"
            else:
                metrics["后程途中游速度"] = "未检测到"
        
        confidence = 1.0 if context.race_duration > 0 or events.race_end is not None else 0.0
        accuracy = AccuracyInfo(
            confidence=round(confidence, 3), coverage=1.0,
            quality="高" if confidence >= 0.7 else "低",
            low_confidence=confidence < 0.3, warnings=[],
        )
        
        return ModuleResult(
            module_name=self.name, metrics=metrics, module_events={},
            accuracy=accuracy, detection_method="距离/时间",
        )