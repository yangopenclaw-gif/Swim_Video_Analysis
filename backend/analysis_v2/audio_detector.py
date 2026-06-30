import logging
import numpy as np

logger = logging.getLogger(__name__)


class AudioDetector:
    VERSION = "3.0.0"

    def __init__(self, sample_rate=22050):
        self.sample_rate = sample_rate

    def extract_audio(self, video_path: str) -> tuple:
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

    def detect_start_signal(self, video_path: str) -> dict:
        result = {"signal_time": None, "signal_type": None, "confidence": 0.0}

        y, sr = self.extract_audio(video_path)
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
        silence_threshold = baseline + 10

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
            if rms_db[i] > baseline + 10 and rms_db[i - 1] <= baseline + 10:
                t_sec = i * hop_length / sr
                if t_sec > 10.0:
                    break
                onset_candidates.append(i)

        ramp_candidates = []
        window = 10
        for i in range(window, len(rms_db)):
            t_sec = i * hop_length / sr
            if t_sec > 10.0:
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
                logger.info(f"Pre-splash ramp at t={t_sec:.3f}s, ramp={ramp:.1f}dB")

        if not pre_splash:
            for frame_idx, t_sec, ramp, _, _ in ramp_candidates[:3]:
                if frame_idx not in onset_candidates:
                    onset_candidates.append(frame_idx)
                    logger.info(f"Ramp onset at t={t_sec:.3f}s, ramp={ramp:.1f}dB")

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

            if score > 0.4 and (best_signal is None or t_sec < best_signal[0]):
                best_signal = (t_sec, score, is_tonal)

        if best_signal is not None:
            result["signal_time"] = round(best_signal[0], 3)
            result["signal_type"] = "buzzer" if best_signal[2] else "beep"
            result["confidence"] = min(best_signal[1], 1.0)
            logger.info(f"Start signal: t={best_signal[0]:.3f}s, type={result['signal_type']}, conf={best_signal[1]:.2f}")
            return result

        logger.info("No clear start signal detected in audio (all candidates below threshold)")
        return result
