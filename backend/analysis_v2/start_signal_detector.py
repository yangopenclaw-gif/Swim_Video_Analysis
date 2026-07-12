import logging
import numpy as np
from typing import Optional, Dict, Any, List

from .base_module import AnalysisModule
from .shared import (
    AnalysisContext, ModuleResult, EngineResult, RetryRecord,
    AccuracyInfo, RaceEvents,
)

logger = logging.getLogger(__name__)


class StartSignalDetector(AnalysisModule):
    VERSION = "4.0.0"

    @property
    def name(self) -> str:
        return "出发信号检测"

    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate

    def analyze(self, context: AnalysisContext) -> ModuleResult:
        video_path = context.video_path
        params = context.detection_params.signal_detection

        primary_result = self._detect_start_signal(
            video_path,
            silence_offset=params.get("silence_threshold_offset", 10),
            confidence_threshold=params.get("confidence_threshold", 0.4),
            search_window=params.get("search_window_seconds", 10.0),
        )

        retry_records: List[RetryRecord] = []
        detection_method = "首次检测"
        signal_time = primary_result.get("signal_time")
        signal_type = primary_result.get("signal_type")
        signal_confidence = primary_result.get("confidence", 0.0)

        if signal_time is not None:
            retry_records.append(RetryRecord(
                attempt=0, success=True, strategy_name="首次检测(默认参数)",
                result=primary_result, confidence=signal_confidence,
            ))
        else:
            retry_records.append(RetryRecord(
                attempt=0, success=False, strategy_name="首次检测(默认参数)",
                result=primary_result, confidence=0.0,
            ))

            max_retries = params.get("max_retries", 3)
            retry_strategies = [
                {
                    "name": "降低静默阈值",
                    "silence_offset": params.get("silence_threshold_offset", 10) - params.get("retry_silence_offset_step", 4),
                    "confidence_threshold": params.get("confidence_threshold", 0.4) - params.get("retry_confidence_step", 0.1),
                    "search_window": params.get("search_window_seconds", 10.0),
                },
                {
                    "name": "扩大搜索窗口+多特征融合",
                    "silence_offset": params.get("silence_threshold_offset", 10) - params.get("retry_silence_offset_step", 4) * 2,
                    "confidence_threshold": params.get("confidence_threshold", 0.4) - params.get("retry_confidence_step", 0.1) * 2,
                    "search_window": params.get("search_window_seconds", 10.0) + params.get("retry_window_step", 5.0),
                },
                {
                    "name": "最宽松参数组合",
                    "silence_offset": 2,
                    "confidence_threshold": 0.2,
                    "search_window": 20.0,
                },
            ]

            for i in range(min(max_retries, len(retry_strategies))):
                strategy = retry_strategies[i]
                logger.info(f"出发信号重试第{i+1}次，策略：{strategy['name']}")

                retry_result = self._detect_start_signal(
                    video_path,
                    silence_offset=strategy["silence_offset"],
                    confidence_threshold=strategy["confidence_threshold"],
                    search_window=strategy["search_window"],
                )

                retry_signal_time = retry_result.get("signal_time")
                retry_confidence = retry_result.get("confidence", 0.0)

                if retry_signal_time is not None:
                    retry_records.append(RetryRecord(
                        attempt=i + 1, success=True, strategy_name=strategy["name"],
                        result=retry_result, confidence=retry_confidence,
                    ))
                    if signal_time is None or retry_confidence > signal_confidence:
                        signal_time = retry_signal_time
                        signal_type = retry_result.get("signal_type")
                        signal_confidence = retry_confidence
                        detection_method = f"第{i+1}次重试检测成功（策略：{strategy['name']}）"
                    break
                else:
                    retry_records.append(RetryRecord(
                        attempt=i + 1, success=False, strategy_name=strategy["name"],
                        result=retry_result, confidence=0.0,
                    ))

        if signal_time is None:
            detection_method = f"未检测到出发信号（已重试{len(retry_records)-1}次）"

        metrics = {
            "出发信号时间": f"{signal_time:.3f} 秒" if signal_time is not None else "未检测到",
            "出发信号类型": signal_type if signal_type else "未检测到",
            "出发信号置信度": round(signal_confidence, 2),
            "检测方式": detection_method,
        }

        module_events = {}
        if signal_time is not None:
            module_events["signal_time"] = signal_time
            module_events["signal_type"] = signal_type
            module_events["signal_confidence"] = signal_confidence

        accuracy = AccuracyInfo(
            confidence=round(signal_confidence, 3) if signal_time is not None else 0.0,
            coverage=1.0 if signal_time is not None else 0.0,
            quality="高" if signal_confidence >= 0.7 else ("中" if signal_confidence >= 0.4 else "低"),
            low_confidence=signal_time is not None and signal_confidence < 0.3,
            warnings=[] if signal_time is not None and signal_confidence >= 0.3 else ["出发信号低置信度" if signal_time is not None else "未检测到出发信号"],
        )

        return ModuleResult(
            module_name=self.name,
            metrics=metrics,
            module_events=module_events,
            accuracy=accuracy,
            retry_records=retry_records,
            detection_method=detection_method,
        )

    def _detect_start_signal(self, video_path: str, silence_offset: float = 10,
                              confidence_threshold: float = 0.4,
                              search_window: float = 10.0) -> Dict[str, Any]:
        result = {"signal_time": None, "signal_type": None, "confidence": 0.0}

        y, sr = self._extract_audio(video_path)
        if len(y) < sr:
            logger.info("Audio too short for start signal detection")
            return result

        frame_length = int(sr * 0.02)
        hop_length = frame_length // 2

        rms = np.array([
            np.sqrt(np.mean(y[i:i + frame_length] ** 2))
            for i in range(0, len(y) - frame_length, hop_length)
        ])

        if len(rms) < 10:
            return result

        rms_db = 20 * np.log10(rms + 1e-10)

        first_quarter = rms_db[:max(len(rms_db) // 4, 10)]
        baseline = np.percentile(first_quarter, 30)
        silence_threshold = baseline + silence_offset

        first_non_silent_frame = None
        for i in range(len(rms_db)):
            if rms_db[i] > silence_threshold:
                first_non_silent_frame = i
                break

        if first_non_silent_frame is None:
            logger.info("No significant audio detected in entire video")
            return result

        first_sound_time = first_non_silent_frame * hop_length / sr
        logger.info(f"First non-silent audio at t={first_sound_time:.3f}s")

        if first_sound_time > 5.0:
            logger.info(f"First sound too late ({first_sound_time:.1f}s), unlikely to be start signal")
            return result

        onset_candidates = []
        for i in range(1, len(rms_db)):
            if rms_db[i] > baseline + silence_offset and rms_db[i - 1] <= baseline + silence_offset:
                t_sec = i * hop_length / sr
                if t_sec > search_window:
                    break
                onset_candidates.append(i)

        try:
            import librosa
            onset_frames = librosa.onset.onset_detect(
                y=y[:int(sr * search_window)],
                sr=sr,
                hop_length=hop_length,
                backtrack=False,
            )
            for of in onset_frames:
                t_sec = of * hop_length / sr
                if t_sec > search_window:
                    continue
                if of not in onset_candidates:
                    onset_candidates.append(of)
                    logger.info(f"librosa.onset_detect candidate at t={t_sec:.3f}s")
        except Exception as e:
            logger.debug(f"librosa.onset_detect failed: {e}")

        ramp_candidates = []
        window = 10
        for i in range(window, len(rms_db)):
            t_sec = i * hop_length / sr
            if t_sec > search_window:
                break
            before = np.mean(rms_db[max(0, i - window):i])
            after = np.mean(rms_db[i:min(i + window, len(rms_db))])
            ramp = after - before
            if ramp > 5 and after > baseline - 5:
                ramp_candidates.append((i, t_sec, ramp, before, after))

        ramp_candidates.sort(key=lambda x: -x[2])

        early_ramps = [x for x in ramp_candidates if x[1] < 5.0]
        biggest_ramp_ts = None
        if early_ramps:
            biggest_ramp_ts = early_ramps[0][1]

        pre_splash = []
        if biggest_ramp_ts is not None:
            for i, t_sec, ramp, before, after in ramp_candidates:
                if t_sec < biggest_ramp_ts - 1.0:
                    pre_splash.append((i, t_sec, ramp))

        for frame_idx, t_sec, ramp in pre_splash[:5]:
            if frame_idx not in onset_candidates:
                onset_candidates.append(frame_idx)

        if not pre_splash:
            for frame_idx, t_sec, ramp, _, _ in ramp_candidates[:3]:
                if frame_idx not in onset_candidates:
                    onset_candidates.append(frame_idx)

        if not onset_candidates:
            logger.info("No sharp onsets found")
            return result

        best_signal = None
        best_score = 0

        for frame_idx in onset_candidates:
            t_sec = frame_idx * hop_length / sr

            start_sample = frame_idx * hop_length
            end_sample = min(start_sample + int(sr * 0.5), len(y))
            segment = y[start_sample:end_sample]

            if len(segment) < 256:
                continue

            fft = np.abs(np.fft.rfft(segment))
            freqs = np.fft.rfftfreq(len(segment), 1.0 / sr)

            high_energy = np.sum(fft[(freqs > 1500) & (freqs < 5000)])
            total_energy = np.sum(fft) + 1e-10
            high_ratio = high_energy / total_energy

            peak_freq_idx = np.argmax(fft[1:]) + 1
            peak_freq = freqs[peak_freq_idx]

            is_tonal = peak_freq > 300 and high_ratio > 0.10

            rms_onset = rms[frame_idx]
            rms_before = np.mean(rms[max(0, frame_idx - 5):frame_idx]) if frame_idx > 5 else 0
            contrast = rms_onset / (rms_before + 1e-10)

            score = 0.0
            if is_tonal:
                score += 0.5
            if contrast > 10:
                score += 0.35
            elif contrast > 5:
                score += 0.15
            elif contrast > 2:
                score += 0.05
            if high_ratio > 0.15:
                score += 0.2
            if 800 < peak_freq < 2000:
                score += 0.15

            if score > confidence_threshold and (best_signal is None or t_sec < best_signal[0]):
                best_signal = (t_sec, score, is_tonal)

        if best_signal is not None:
            result["signal_time"] = round(best_signal[0], 3)
            result["signal_type"] = "buzzer" if best_signal[2] else "beep"
            result["confidence"] = min(best_signal[1], 1.0)
            logger.info(f"Start signal: t={best_signal[0]:.3f}s, type={result['signal_type']}, conf={best_signal[1]:.2f}")
            return result

        logger.info("No clear start signal detected in audio")
        return result

    def _extract_audio(self, video_path: str) -> tuple:
        try:
            import librosa
            y, sr = librosa.load(video_path, sr=self.sample_rate, mono=True)
            return y, sr
        except Exception:
            return self._extract_via_ffmpeg(video_path)

    def _extract_via_ffmpeg(self, video_path: str) -> tuple:
        import subprocess, tempfile, os
        tmp_wav = tempfile.mktemp(suffix='.wav')
        try:
            subprocess.run([
                'ffmpeg', '-i', video_path, '-vn', '-acodec', 'pcm_s16le',
                '-ar', str(self.sample_rate), '-ac', '1', '-y', tmp_wav
            ], capture_output=True, timeout=30)
            if os.path.exists(tmp_wav) and os.path.getsize(tmp_wav) > 0:
                import soundfile as sf
                y, sr = sf.read(tmp_wav)
                return y.astype(np.float32), sr
        except Exception as e:
            logger.warning(f"ffmpeg audio extraction failed: {e}")
        finally:
            if os.path.exists(tmp_wav):
                os.unlink(tmp_wav)
        return np.array([], dtype=np.float32), self.sample_rate