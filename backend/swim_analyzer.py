import cv2
import numpy as np
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core import base_options
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple, Callable
import logging
import os


logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "pose_landmarker_heavy.task")

NOSE = 0
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28
LEFT_HEEL = 29
RIGHT_HEEL = 30
LEFT_FOOT_INDEX = 31
RIGHT_FOOT_INDEX = 32
LEFT_EAR = 7
RIGHT_EAR = 8
LEFT_PINKY = 17
RIGHT_PINKY = 18
LEFT_INDEX = 19
RIGHT_INDEX = 20
LEFT_THUMB = 21
RIGHT_THUMB = 22

MAX_PERSONS = 9

REACTION_TIME_MIN = 0.3
REACTION_TIME_MAX = 2.0
FREE_50M_TIME_MIN = 22.0
FREE_50M_TIME_MAX = 45.0
FREE_100M_TIME_MIN = 50.0
FREE_100M_TIME_MAX = 100.0
UNDERWATER_TIME_MAX = 15.0
STROKE_RATE_MIN = 15
STROKE_RATE_MAX = 60
KICK_RATE_MIN = 40
KICK_RATE_MAX = 180


@dataclass
class SwimAnalysisResult:
    dive_reaction_time: Optional[float] = None
    dive_underwater_time: Optional[float] = None
    dive_underwater_distance: Optional[float] = None
    underwater_kick_count: Optional[int] = None
    first_half_stroke_count: Optional[int] = None
    first_half_kick_count: Optional[int] = None
    first_half_breath_count: Optional[int] = None
    first_half_speed: Optional[float] = None
    first_half_time: Optional[float] = None
    turn_touch_time: Optional[float] = None
    turn_surface_time_val: Optional[float] = None
    turn_surface_distance: Optional[float] = None
    turn_underwater_kick_count: Optional[int] = None
    second_half_stroke_count: Optional[int] = None
    second_half_kick_count: Optional[int] = None
    second_half_breath_count: Optional[int] = None
    second_half_speed: Optional[float] = None
    finish_time: Optional[float] = None
    stroke_count: Optional[int] = None
    kick_count: Optional[int] = None
    breath_count: Optional[int] = None
    mid_course_speed: Optional[float] = None
    race_start_time: Optional[float] = None
    race_end_time: Optional[float] = None


def _MpImageFromNumpy(numpy_image):
    from mediapipe import Image
    from mediapipe import ImageFormat
    return Image(image_format=ImageFormat.SRGB, data=numpy_image)


def _format_race_time(seconds: float) -> str:
    if seconds < 0:
        return "0.00秒"
    if seconds < 60:
        return f"{seconds:.2f}秒"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}分{s:05.2f}秒"


def _lowpass_filter(data, cutoff_hz, fs, order=4):
    if len(data) < order * 3 + 1:
        return np.array(data)
    nyq = 0.5 * fs
    if cutoff_hz >= nyq:
        return np.array(data)
    alpha = 1.0 - np.exp(-2.0 * np.pi * cutoff_hz / fs)
    result = np.zeros(len(data))
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    for _ in range(order - 1):
        prev = result.copy()
        for i in range(1, len(data)):
            result[i] = alpha * prev[i] + (1 - alpha) * result[i - 1]
    return result


def _bandpass_filter(data, low_hz, high_hz, fs, order=3):
    if len(data) < order * 3 + 1:
        return np.array(data)
    high_passed = np.zeros(len(data))
    alpha_h = 1.0 / (1.0 + 2.0 * np.pi * high_hz / fs)
    high_passed[0] = data[0]
    for i in range(1, len(data)):
        high_passed[i] = alpha_h * (high_passed[i - 1] + data[i] - data[i - 1])
    result = np.zeros(len(data))
    alpha_l = 1.0 - np.exp(-2.0 * np.pi * low_hz / fs)
    result[0] = high_passed[0]
    for i in range(1, len(data)):
        result[i] = alpha_l * high_passed[i] + (1 - alpha_l) * result[i - 1]
    return result


def _find_peaks_simple(data, min_height=0.0, min_distance=1, min_prominence=0.0):
    peaks = []
    for i in range(1, len(data) - 1):
        if data[i] > data[i - 1] and data[i] > data[i + 1]:
            if data[i] >= min_height:
                if not peaks or i - peaks[-1] >= min_distance:
                    if min_prominence > 0:
                        left_min = min(data[max(0, i - min_distance):i])
                        right_min = min(data[i + 1:min(len(data), i + min_distance + 1)])
                        prominence = data[i] - max(left_min, right_min)
                        if prominence < min_prominence:
                            continue
                    peaks.append(i)
    return np.array(peaks)


def _interpolate_gaps(data):
    result = list(data)
    i = 0
    while i < len(result):
        if result[i] is None:
            start = i
            while i < len(result) and result[i] is None:
                i += 1
            end = i
            before = result[start - 1] if start > 0 and result[start - 1] is not None else None
            after = result[end] if end < len(result) and result[end] is not None else None
            if before is not None and after is not None:
                for j in range(start, end):
                    alpha = (j - start + 1) / (end - start + 1)
                    result[j] = before * (1 - alpha) + after * alpha
            elif before is not None:
                for j in range(start, end):
                    result[j] = before
            elif after is not None:
                for j in range(start, end):
                    result[j] = after
        else:
            i += 1
    return [x if x is not None else 0.0 for x in result]


class SwimVideoAnalyzer:
    def __init__(self, pool_length: int = 50, race_distance: int = 100, swimmer_position: int = 1):
        self.pool_length = pool_length
        self.race_distance = race_distance
        self.half_distance = race_distance // 2
        self.swimmer_position = max(1, min(swimmer_position, MAX_PERSONS))
        self.progress_callback: Optional[Callable[[int, str], None]] = None
        self._target_anchor: Optional[np.ndarray] = None

        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"PoseLandmarker model not found at {MODEL_PATH}")

        options = vision.PoseLandmarkerOptions(
            base_options=base_options.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            num_poses=MAX_PERSONS,
            output_segmentation_masks=False,
        )
        self.landmarker = vision.PoseLandmarker.create_from_options(options)

    def _report_progress(self, percent: int, message: str):
        if self.progress_callback:
            self.progress_callback(percent, message)

    def _get_landmark(self, landmarks, idx):
        if landmarks is None or idx >= len(landmarks):
            return None
        lm = landmarks[idx]
        return np.array([lm.x, lm.y, lm.z])

    def _midpoint(self, p1, p2):
        if p1 is None or p2 is None:
            return None
        return (p1 + p2) / 2.0

    def _get_person_center_x(self, landmarks) -> Optional[float]:
        if landmarks is None:
            return None
        xs = []
        for idx in [LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP]:
            p = self._get_landmark(landmarks, idx)
            if p is not None:
                xs.append(p[0])
        if not xs:
            nose = self._get_landmark(landmarks, NOSE)
            if nose is not None:
                return nose[0]
            return None
        return float(np.mean(xs))

    def _get_pose_anchor(self, landmarks) -> Optional[np.ndarray]:
        if landmarks is None:
            return None
        pts = []
        for idx in [LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP]:
            p = self._get_landmark(landmarks, idx)
            if p is not None:
                pts.append(p[0])
                pts.append(p[1])
        if len(pts) < 4:
            return None
        return np.array(pts)

    def _select_target_person(self, all_poses) -> int:
        if not all_poses:
            return -1
        if len(all_poses) == 1:
            self._target_anchor = self._get_pose_anchor(all_poses[0])
            return 0

        if self._target_anchor is not None:
            best_idx = -1
            best_dist = float('inf')
            for idx, pose in enumerate(all_poses):
                anchor = self._get_pose_anchor(pose)
                if anchor is not None and len(anchor) == len(self._target_anchor):
                    dist = np.linalg.norm(anchor - self._target_anchor)
                    if dist < best_dist:
                        best_dist = dist
                        best_idx = idx
            if best_idx >= 0 and best_dist < 0.3:
                self._target_anchor = self._get_pose_anchor(all_poses[best_idx])
                return best_idx

        persons_with_x = []
        for idx, pose in enumerate(all_poses):
            cx = self._get_person_center_x(pose)
            if cx is not None:
                persons_with_x.append((cx, idx))
        persons_with_x.sort(key=lambda item: item[0])
        target_idx = self.swimmer_position - 1
        if target_idx >= len(persons_with_x):
            target_idx = len(persons_with_x) - 1
        selected = persons_with_x[target_idx][1]
        self._target_anchor = self._get_pose_anchor(all_poses[selected])
        return selected

    def _detect_water_surface_y(self, frames_landmarks):
        all_y = []
        for lm_list in frames_landmarks:
            if lm_list is not None:
                for idx in [LEFT_SHOULDER, RIGHT_SHOULDER]:
                    p = self._get_landmark(lm_list, idx)
                    if p is not None:
                        all_y.append(p[1])
        if not all_y:
            return 0.5
        return float(np.percentile(all_y, 15))

    def _is_underwater(self, landmarks, water_y):
        if landmarks is None:
            return False
        nose = self._get_landmark(landmarks, NOSE)
        if nose is None:
            shoulder_mid = self._midpoint(
                self._get_landmark(landmarks, LEFT_SHOULDER),
                self._get_landmark(landmarks, RIGHT_SHOULDER)
            )
            if shoulder_mid is None:
                return False
            return shoulder_mid[1] > water_y + 0.08
        return nose[1] > water_y + 0.08

    def _detect_race_start(self, frames_data) -> Tuple[float, float]:
        if len(frames_data) < 10:
            ts0 = frames_data[0][0] if frames_data else 0.0
            return ts0, 0.0

        hip_y_series = []
        hip_x_series = []
        for ts, lm in frames_data:
            if lm is not None:
                lh = self._get_landmark(lm, LEFT_HIP)
                rh = self._get_landmark(lm, RIGHT_HIP)
                mid = self._midpoint(lh, rh)
                if mid is not None:
                    hip_y_series.append((ts, mid[1]))
                    hip_x_series.append((ts, mid[0]))

        if len(hip_y_series) < 10:
            ts0 = frames_data[0][0] if frames_data else 0.0
            return ts0, 0.0

        timestamps_y = [t for t, _ in hip_y_series]
        y_vals = [v for _, v in hip_y_series]
        timestamps_x = [t for t, _ in hip_x_series]
        x_vals = [v for _, v in hip_x_series]

        fs_y = 1.0 / np.mean(np.diff(timestamps_y)) if len(timestamps_y) > 1 else 15.0
        fs_x = 1.0 / np.mean(np.diff(timestamps_x)) if len(timestamps_x) > 1 else 15.0

        y_smooth = _lowpass_filter(y_vals, 3.0, fs_y)
        x_smooth = _lowpass_filter(x_vals, 2.0, fs_x)

        dy = np.gradient(y_smooth, timestamps_y)
        dy_smooth = _lowpass_filter(dy, 3.0, fs_y)

        dx = np.gradient(x_smooth, timestamps_x)
        dx_smooth = _lowpass_filter(dx, 2.0, fs_x)

        speed = np.sqrt(dx_smooth ** 2 + dy_smooth ** 2)
        speed_smooth = _lowpass_filter(speed, 2.0, fs_x)

        baseline_end = max(5, len(speed_smooth) // 10)
        baseline_speed = np.median(speed_smooth[:baseline_end])
        baseline_dy = np.median(np.abs(dy_smooth[:baseline_end]))

        dive_start = None
        for i in range(baseline_end, len(timestamps_y)):
            if dy_smooth[i] < -0.15 and speed_smooth[i] > baseline_speed + 0.1:
                window_before = dy_smooth[max(0, i - 8):i]
                if np.median(np.abs(window_before)) < 0.05:
                    dive_start = timestamps_y[i]
                    break

        if dive_start is None:
            for i in range(baseline_end, len(speed_smooth)):
                if speed_smooth[i] > baseline_speed * 3 + 0.05:
                    dive_start = timestamps_x[i]
                    break

        if dive_start is None:
            for i in range(baseline_end, len(dx_smooth)):
                if abs(dx_smooth[i]) > 0.1:
                    dive_start = timestamps_x[i]
                    break

        if dive_start is not None:
            still_before = [(ts, lm) for ts, lm in frames_data if ts < dive_start and lm is not None]
            if still_before:
                command_time = still_before[0][0]
                reaction_time = dive_start - command_time
                if REACTION_TIME_MIN <= reaction_time <= REACTION_TIME_MAX:
                    logger.info(f"Dive start (vertical): t={dive_start:.2f}s, reaction={reaction_time:.2f}s")
                    return dive_start, round(reaction_time, 2)
                elif reaction_time > REACTION_TIME_MAX:
                    for i in range(len(timestamps_y) - 1, -1, -1):
                        if timestamps_y[i] < dive_start:
                            dt_gap = dive_start - timestamps_y[i]
                            if 0.3 <= dt_gap <= REACTION_TIME_MAX:
                                reaction_time = dt_gap
                                logger.info(f"Dive start (corrected): t={dive_start:.2f}s, reaction={reaction_time:.2f}s")
                                return dive_start, round(reaction_time, 2)
                            break
                    logger.info(f"Dive start: t={dive_start:.2f}s, reaction clamped from {reaction_time:.2f}s")
                    return dive_start, round(min(reaction_time, REACTION_TIME_MAX), 2)
            return dive_start, 0.0

        logger.info("No clear dive detected, using first significant motion")
        for i in range(baseline_end, len(speed_smooth)):
            if speed_smooth[i] > 0.08:
                ts = timestamps_x[i]
                still_before = [(t, lm) for t, lm in frames_data if t < ts and lm is not None]
                command_time = still_before[0][0] if still_before else frames_data[0][0]
                reaction_time = ts - command_time
                return ts, round(max(0, min(reaction_time, REACTION_TIME_MAX)), 2)

        for ts, lm in frames_data:
            if lm is not None:
                return ts, 0.0
        return frames_data[0][0], 0.0

    def _detect_race_end(self, frames_data, race_start: float, water_y: float) -> Optional[float]:
        if len(frames_data) < 10:
            return frames_data[-1][0] if frames_data else 0.0

        min_race_time = max(5.0, self.race_distance / 3.0)

        wrist_data = []
        for ts, lm in frames_data:
            if ts < race_start or ts - race_start < min_race_time:
                continue
            if lm is None:
                continue
            lw = self._get_landmark(lm, LEFT_WRIST)
            rw = self._get_landmark(lm, RIGHT_WRIST)
            ls = self._get_landmark(lm, LEFT_SHOULDER)
            rs = self._get_landmark(lm, RIGHT_SHOULDER)

            if lw is not None and ls is not None:
                wrist_data.append((ts, lw[0], lw[1], ls[0], ls[1], 'left'))
            if rw is not None and rs is not None:
                wrist_data.append((ts, rw[0], rw[1], rs[0], rs[1], 'right'))

        if len(wrist_data) > 10:
            for i in range(2, len(wrist_data)):
                ts = wrist_data[i][0]
                dt = ts - wrist_data[i - 1][0]
                if dt > 0.5:
                    continue

                curr_wy = wrist_data[i][2]
                prev_wy = wrist_data[i - 1][2]
                curr_wx = wrist_data[i][1]
                curr_sx = wrist_data[i][3]

                x_advance = curr_wx - curr_sx

                if prev_wy - curr_wy > 0.03 and x_advance > 0.02:
                    next_pts = [(wrist_data[j][0], wrist_data[j][2])
                                for j in range(i, min(i + 10, len(wrist_data)))
                                if wrist_data[j][0] - ts < 1.0]
                    if len(next_pts) >= 2:
                        min_y = min(p[1] for p in next_pts)
                        if min_y < curr_wy - 0.02:
                            speed_before = []
                            for j in range(max(0, i - 6), i):
                                dt_j = wrist_data[j + 1][0] - wrist_data[j][0]
                                if dt_j > 0:
                                    speed_before.append(abs(wrist_data[j + 1][1] - wrist_data[j][1]) / dt_j)
                            if speed_before and np.mean(speed_before) > 0.01:
                                logger.info(f"Race end (wall touch) at t={ts:.2f}s")
                                return ts

        hip_xs = []
        for ts, lm in frames_data:
            if ts < race_start:
                continue
            if lm is not None:
                lh = self._get_landmark(lm, LEFT_HIP)
                rh = self._get_landmark(lm, RIGHT_HIP)
                mid = self._midpoint(lh, rh)
                if mid is not None:
                    hip_xs.append((ts, mid[0]))

        if len(hip_xs) > 20:
            timestamps = [t for t, _ in hip_xs]
            x_vals = [x for _, x in hip_xs]
            fs = 1.0 / np.mean(np.diff(timestamps)) if len(timestamps) > 1 else 15.0
            x_smooth = _lowpass_filter(x_vals, 2.0, fs)
            dx = np.gradient(x_smooth, timestamps)
            dx_smooth = _lowpass_filter(dx, 2.0, fs)

            window = max(5, len(dx_smooth) // 10)
            for i in range(window, len(dx_smooth)):
                ts = timestamps[i]
                if ts - race_start < min_race_time:
                    continue
                prev_speeds = dx_smooth[max(0, i - window):i]
                curr_speeds = dx_smooth[i:min(i + window, len(dx_smooth))]
                if len(prev_speeds) > 0 and len(curr_speeds) > 0:
                    if np.mean(np.abs(prev_speeds)) > 0.02 and np.mean(np.abs(curr_speeds)) < 0.003:
                        logger.info(f"Race end (motion stop) at t={ts:.2f}s")
                        return ts

        logger.info("No clear race end detected, using last frame with pose")
        for ts, lm in reversed(frames_data):
            if lm is not None:
                return ts
        return frames_data[-1][0]

    def _detect_dive_entry(self, frames_data, race_start: float, water_y: float) -> Tuple[Optional[float], Optional[float]]:
        first_underwater = None
        first_surface_after = None

        for ts, lm in frames_data:
            if ts < race_start - 1.0:
                continue
            if lm is None:
                continue
            if first_underwater is None:
                if self._is_underwater(lm, water_y):
                    first_underwater = ts
            elif first_surface_after is None:
                if not self._is_underwater(lm, water_y):
                    first_surface_after = ts
                    break

        return first_underwater, first_surface_after

    def _detect_stroke_cycles_advanced(self, wrist_y_list, shoulder_y, frame_ts, side='left'):
        if len(wrist_y_list) < 5:
            return 0

        filled = _interpolate_gaps(wrist_y_list)
        if len(filled) < 5:
            return 0

        fs = 1.0 / np.mean(np.diff(frame_ts)) if len(frame_ts) > 1 else 15.0
        filtered = _bandpass_filter(filled, 0.3, 3.0, fs)

        relative = [v - shoulder_y for v in filtered]

        peaks = _find_peaks_simple(relative, min_height=0.01,
                                    min_distance=max(2, int(fs * 0.4)),
                                    min_prominence=0.01)

        valid_strokes = 0
        for peak_idx in peaks:
            if peak_idx < 2 or peak_idx >= len(relative) - 2:
                continue
            left_val = relative[peak_idx - 2]
            right_val = relative[peak_idx + 2]
            if left_val < relative[peak_idx] - 0.005 or right_val < relative[peak_idx] - 0.005:
                valid_strokes += 1

        return valid_strokes

    def _detect_kick_cycles_advanced(self, left_ankle_y_list, right_ankle_y_list, frame_ts):
        left_filled = _interpolate_gaps(left_ankle_y_list)
        right_filled = _interpolate_gaps(right_ankle_y_list)

        if len(left_filled) < 5 or len(right_filled) < 5:
            return 0

        fs = 1.0 / np.mean(np.diff(frame_ts)) if len(frame_ts) > 1 else 15.0

        left_filtered = _bandpass_filter(left_filled, 0.5, 5.0, fs)
        right_filtered = _bandpass_filter(right_filled, 0.5, 5.0, fs)

        diff = left_filtered - right_filtered
        diff_filtered = _lowpass_filter(diff, 5.0, fs)

        zero_crossings = []
        for i in range(1, len(diff_filtered)):
            if diff_filtered[i - 1] * diff_filtered[i] < 0:
                if abs(diff_filtered[i - 1]) > 0.003 or abs(diff_filtered[i]) > 0.003:
                    zero_crossings.append(i)

        kick_count = len(zero_crossings) // 2
        return max(1, kick_count)

    def _detect_breath_cycles_advanced(self, nose_positions, ear_positions, frame_ts):
        if len(nose_positions) < 5:
            return 0

        nose_x = [p[0] if p is not None else None for p in nose_positions]
        nose_y = [p[1] if p is not None else None for p in nose_positions]
        ear_x = [p[0] if p is not None else None for p in ear_positions]
        ear_y = [p[1] if p is not None else None for p in ear_positions]

        nose_x_filled = _interpolate_gaps(nose_x)
        nose_y_filled = _interpolate_gaps(nose_y)
        ear_x_filled = _interpolate_gaps(ear_x)
        ear_y_filled = _interpolate_gaps(ear_y)

        if len(nose_x_filled) < 5:
            return 0

        dx = np.array(nose_x_filled) - np.array(ear_x_filled)
        dy = np.array(nose_y_filled) - np.array(ear_y_filled)
        angles = np.arctan2(dy, dx)

        fs = 1.0 / np.mean(np.diff(frame_ts)) if len(frame_ts) > 1 else 15.0
        angles_filtered = _lowpass_filter(angles, 2.0, fs)

        d_angle = np.gradient(angles_filtered, frame_ts)
        d_angle_filtered = _lowpass_filter(d_angle, 2.0, fs)

        baseline = np.median(np.abs(d_angle_filtered[:max(5, len(d_angle_filtered) // 10)]))
        threshold = max(baseline * 3, 0.3)

        breath_count = 0
        cooldown_frames = 0
        min_cooldown = max(3, int(fs * 0.8))

        for i in range(1, len(d_angle_filtered)):
            if cooldown_frames > 0:
                cooldown_frames -= 1
                continue

            if abs(d_angle_filtered[i]) > threshold:
                if (d_angle_filtered[i - 1] * d_angle_filtered[i] <= 0 or
                        abs(d_angle_filtered[i]) > threshold * 1.5):
                    breath_count += 1
                    cooldown_frames = min_cooldown

        return breath_count

    def _estimate_pixel_per_meter(self, frames_data, race_start: float, race_end: float):
        hip_xs = []
        for ts, lm in frames_data:
            if race_start <= ts <= race_end and lm is not None:
                lh = self._get_landmark(lm, LEFT_HIP)
                rh = self._get_landmark(lm, RIGHT_HIP)
                mid = self._midpoint(lh, rh)
                if mid is not None:
                    hip_xs.append((ts, mid[0]))

        if len(hip_xs) < 20:
            return 0.01

        total_x_range = max(x for _, x in hip_xs) - min(x for _, x in hip_xs)
        if total_x_range < 0.01:
            return 0.01

        laps = max(1, self.race_distance // self.pool_length)
        pixels_per_meter = total_x_range / (self.pool_length * laps * 0.8)
        return max(0.001, pixels_per_meter)

    def _validate_results(self, result: SwimAnalysisResult, race_duration: float):
        if result.dive_reaction_time is not None:
            if result.dive_reaction_time > REACTION_TIME_MAX:
                logger.warning(f"Reaction time {result.dive_reaction_time}s too high, clamping to {REACTION_TIME_MAX}s")
                result.dive_reaction_time = REACTION_TIME_MAX
            if result.dive_reaction_time < REACTION_TIME_MIN and result.dive_reaction_time > 0:
                logger.warning(f"Reaction time {result.dive_reaction_time}s too low, setting to {REACTION_TIME_MIN}s")
                result.dive_reaction_time = REACTION_TIME_MIN

        if race_duration > 0:
            time_min = FREE_50M_TIME_MIN if self.race_distance <= 50 else FREE_100M_TIME_MIN
            time_max = FREE_50M_TIME_MAX if self.race_distance <= 50 else FREE_100M_TIME_MAX
            if race_duration < time_min:
                logger.warning(f"Race duration {race_duration:.2f}s suspiciously short for {self.race_distance}m")
            if race_duration > time_max:
                logger.warning(f"Race duration {race_duration:.2f}s suspiciously long for {self.race_distance}m")

        if result.dive_underwater_time is not None and result.dive_underwater_time > UNDERWATER_TIME_MAX:
            logger.warning(f"Underwater time {result.dive_underwater_time}s too high, capping")
            result.dive_underwater_time = UNDERWATER_TIME_MAX

        if result.finish_time is not None and result.finish_time > 0:
            total_strokes = (result.stroke_count or 0) + (result.first_half_stroke_count or 0) + (result.second_half_stroke_count or 0)
            if total_strokes > 0:
                stroke_rate = total_strokes / (result.finish_time / 60.0)
                if stroke_rate > STROKE_RATE_MAX:
                    logger.warning(f"Stroke rate {stroke_rate:.0f}/min too high")
                if stroke_rate < STROKE_RATE_MIN and result.finish_time > 10:
                    logger.warning(f"Stroke rate {stroke_rate:.0f}/min too low")

    def analyze_video(self, video_path: str, analysis_options: List[str]) -> Dict[str, Any]:
        logger.info(f"Starting analysis of {video_path}, swimmer_position={self.swimmer_position}")
        self._target_anchor = None
        self._report_progress(0, "正在打开视频文件...")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / fps

        logger.info(f"Video: {total_frames} frames, {fps:.1f} fps, {video_duration:.1f}s")

        self._report_progress(5, "正在提取视频帧并检测人体姿态...")
        frames_data = []
        frame_idx = 0
        sample_rate = max(1, int(fps / 15))
        person_count_samples = []
        total_sampled = total_frames // sample_rate

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % sample_rate == 0:
                ts_ms = int(frame_idx * 1000 / fps)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = _MpImageFromNumpy(rgb)
                try:
                    result = self.landmarker.detect_for_video(mp_image, ts_ms)
                    if result.pose_landmarks and len(result.pose_landmarks) > 0:
                        person_count_samples.append(len(result.pose_landmarks))
                        target_idx = self._select_target_person(result.pose_landmarks)
                        if 0 <= target_idx < len(result.pose_landmarks):
                            frames_data.append((frame_idx / fps, result.pose_landmarks[target_idx]))
                        else:
                            frames_data.append((frame_idx / fps, result.pose_landmarks[0]))
                    else:
                        person_count_samples.append(0)
                        frames_data.append((frame_idx / fps, None))
                except Exception as e:
                    logger.warning(f"Frame {frame_idx} detection failed: {e}")
                    frames_data.append((frame_idx / fps, None))

                processed = len(frames_data)
                if processed % 20 == 0:
                    pct = 5 + int(50 * processed / max(total_sampled, 1))
                    self._report_progress(min(pct, 55), f"正在分析帧 {processed}/{total_sampled}...")
            frame_idx += 1
        cap.release()

        max_persons = max(person_count_samples) if person_count_samples else 0
        logger.info(f"Processed {len(frames_data)} sampled frames, max persons: {max_persons}")
        self._report_progress(55, "正在检测水面位置...")

        water_y = self._detect_water_surface_y([fd[1] for fd in frames_data])
        logger.info(f"Water surface Y: {water_y:.3f}")

        self._report_progress(58, "正在检测比赛起止时刻...")
        race_start, reaction_time = self._detect_race_start(frames_data)
        race_end = self._detect_race_end(frames_data, race_start, water_y)
        race_duration = race_end - race_start if race_end and race_start else video_duration

        logger.info(f"Race: start={race_start:.2f}s, end={race_end:.2f}s, duration={race_duration:.2f}s, reaction={reaction_time:.2f}s")

        self._report_progress(62, "正在分析出发入水阶段...")
        dive_entry, dive_surface = self._detect_dive_entry(frames_data, race_start, water_y)

        dive_underwater_time = None
        dive_underwater_distance = None
        if dive_entry is not None and dive_surface is not None:
            dive_underwater_time = round(dive_surface - dive_entry, 2)
            px_per_m = self._estimate_pixel_per_meter(frames_data, race_start, race_end)
            dive_x_start = None
            dive_x_end = None
            for ts, lm in frames_data:
                if lm is None:
                    continue
                if abs(ts - dive_entry) < 0.2:
                    lh = self._get_landmark(lm, LEFT_HIP)
                    rh = self._get_landmark(lm, RIGHT_HIP)
                    mid = self._midpoint(lh, rh)
                    if mid is not None and dive_x_start is None:
                        dive_x_start = mid[0]
                if abs(ts - dive_surface) < 0.2:
                    lh = self._get_landmark(lm, LEFT_HIP)
                    rh = self._get_landmark(lm, RIGHT_HIP)
                    mid = self._midpoint(lh, rh)
                    if mid is not None and dive_x_end is None:
                        dive_x_end = mid[0]
            if dive_x_start is not None and dive_x_end is not None and px_per_m > 0:
                dive_underwater_distance = round(abs(dive_x_end - dive_x_start) / px_per_m, 2)
            else:
                avg_speed = self.race_distance / max(race_duration, 1.0)
                dive_underwater_distance = round(avg_speed * dive_underwater_time, 2)

        self._report_progress(68, "正在识别划水、打腿、呼吸动作...")

        is_50m_50pool = (self.pool_length == 50 and self.race_distance == 50)

        if is_50m_50pool:
            half_time = race_end
        elif self.race_distance == 100 and self.pool_length == 25:
            half_time = race_start + race_duration / 4.0
        else:
            half_time = race_start + race_duration / 2.0

        race_frames = [(ts, lm) for ts, lm in frames_data if ts >= race_start]

        left_wrist_y = []
        right_wrist_y = []
        left_ankle_y = []
        right_ankle_y = []
        nose_positions = []
        ear_positions = []
        frame_ts = []

        for ts, lm in race_frames:
            frame_ts.append(ts)
            if lm is None:
                left_wrist_y.append(None)
                right_wrist_y.append(None)
                left_ankle_y.append(None)
                right_ankle_y.append(None)
                nose_positions.append(None)
                ear_positions.append(None)
                continue
            lw = self._get_landmark(lm, LEFT_WRIST)
            rw = self._get_landmark(lm, RIGHT_WRIST)
            la = self._get_landmark(lm, LEFT_ANKLE)
            ra = self._get_landmark(lm, RIGHT_ANKLE)
            n = self._get_landmark(lm, NOSE)
            le = self._get_landmark(lm, LEFT_EAR)
            re = self._get_landmark(lm, RIGHT_EAR)

            left_wrist_y.append(lw[1] if lw is not None else None)
            right_wrist_y.append(rw[1] if rw is not None else None)
            left_ankle_y.append(la[1] if la is not None else None)
            right_ankle_y.append(ra[1] if ra is not None else None)
            nose_positions.append(n if n is not None else None)
            ear_positions.append(le if le is not None else (re if re is not None else None))

        shoulder_y_vals = []
        for ts, lm in race_frames:
            if lm is not None:
                ls = self._get_landmark(lm, LEFT_SHOULDER)
                rs = self._get_landmark(lm, RIGHT_SHOULDER)
                mid = self._midpoint(ls, rs)
                if mid is not None:
                    shoulder_y_vals.append(mid[1])
        avg_shoulder_y = float(np.median(shoulder_y_vals)) if shoulder_y_vals else 0.5

        half_idx = 0
        for i, ts in enumerate(frame_ts):
            if ts >= half_time:
                half_idx = i
                break

        stroke_count_first = self._detect_stroke_cycles_advanced(
            left_wrist_y[:half_idx], avg_shoulder_y, frame_ts[:half_idx], 'left') + \
            self._detect_stroke_cycles_advanced(
            right_wrist_y[:half_idx], avg_shoulder_y, frame_ts[:half_idx], 'right')
        stroke_count_second = self._detect_stroke_cycles_advanced(
            left_wrist_y[half_idx:], avg_shoulder_y, frame_ts[half_idx:], 'left') + \
            self._detect_stroke_cycles_advanced(
            right_wrist_y[half_idx:], avg_shoulder_y, frame_ts[half_idx:], 'right')
        total_stroke_count = stroke_count_first + stroke_count_second

        kick_count_first = self._detect_kick_cycles_advanced(
            left_ankle_y[:half_idx], right_ankle_y[:half_idx], frame_ts[:half_idx])
        kick_count_second = self._detect_kick_cycles_advanced(
            left_ankle_y[half_idx:], right_ankle_y[half_idx:], frame_ts[half_idx:])
        total_kick_count = kick_count_first + kick_count_second

        breath_count_first = self._detect_breath_cycles_advanced(
            nose_positions[:half_idx], ear_positions[:half_idx], frame_ts[:half_idx])
        breath_count_second = self._detect_breath_cycles_advanced(
            nose_positions[half_idx:], ear_positions[half_idx:], frame_ts[half_idx:])
        total_breath_count = breath_count_first + breath_count_second

        self._report_progress(85, "正在分析水下腿次数...")

        underwater_kick_count = 0
        if dive_entry is not None and dive_surface is not None:
            uw_left_ankle = []
            uw_right_ankle = []
            uw_ts = []
            for ts, lm in frames_data:
                if dive_entry <= ts <= dive_surface and lm is not None:
                    la = self._get_landmark(lm, LEFT_ANKLE)
                    ra = self._get_landmark(lm, RIGHT_ANKLE)
                    uw_left_ankle.append(la[1] if la is not None else None)
                    uw_right_ankle.append(ra[1] if ra is not None else None)
                    uw_ts.append(ts)
            if len(uw_ts) > 2:
                underwater_kick_count = self._detect_kick_cycles_advanced(uw_left_ankle, uw_right_ankle, uw_ts)

        self._report_progress(90, "正在分析转身数据...")

        turn_underwater_kick_count = 0
        turn_touch_time = None
        turn_surface_time = None
        if self.race_distance > self.pool_length:
            mid_ts = race_start + race_duration / 2.0
            underwater_after_mid = []
            surface_after_mid = []
            for ts, lm in frames_data:
                if ts >= mid_ts - 3.0:
                    if self._is_underwater(lm, water_y):
                        underwater_after_mid.append(ts)
                    else:
                        surface_after_mid.append(ts)

            if underwater_after_mid:
                turn_start = underwater_after_mid[0]
                for ts in surface_after_mid:
                    if ts > turn_start:
                        turn_surface_time = ts
                        break
                turn_touch_time = turn_start

                if turn_surface_time:
                    tuw_la = []
                    tuw_ra = []
                    tuw_ts = []
                    for ts, lm in frames_data:
                        if turn_start <= ts <= turn_surface_time and lm is not None:
                            la = self._get_landmark(lm, LEFT_ANKLE)
                            ra = self._get_landmark(lm, RIGHT_ANKLE)
                            tuw_la.append(la[1] if la is not None else None)
                            tuw_ra.append(ra[1] if ra is not None else None)
                            tuw_ts.append(ts)
                    if len(tuw_ts) > 2:
                        turn_underwater_kick_count = self._detect_kick_cycles_advanced(tuw_la, tuw_ra, tuw_ts)

        self._report_progress(96, "正在汇总分析结果...")

        result = SwimAnalysisResult()
        result.race_start_time = round(race_start, 2)
        result.race_end_time = round(race_end, 2)

        result.dive_reaction_time = round(reaction_time, 2) if reaction_time > 0 else 0.00

        if dive_underwater_time is not None:
            result.dive_underwater_time = dive_underwater_time
        if dive_underwater_distance is not None:
            result.dive_underwater_distance = dive_underwater_distance

        result.underwater_kick_count = underwater_kick_count

        if is_50m_50pool:
            result.stroke_count = total_stroke_count
            result.kick_count = total_kick_count
            result.breath_count = total_breath_count
            if race_duration > 0:
                result.mid_course_speed = round(self.race_distance / race_duration, 2)
            result.finish_time = round(race_duration, 2)
        else:
            first_half_dur = half_time - race_start
            second_half_dur = race_end - half_time

            result.first_half_stroke_count = stroke_count_first
            result.first_half_kick_count = kick_count_first
            result.first_half_breath_count = breath_count_first
            result.first_half_time = round(first_half_dur, 2)
            if first_half_dur > 0:
                result.first_half_speed = round(self.half_distance / first_half_dur, 2)

            result.second_half_stroke_count = stroke_count_second
            result.second_half_kick_count = kick_count_second
            result.second_half_breath_count = breath_count_second
            if second_half_dur > 0:
                result.second_half_speed = round(self.half_distance / second_half_dur, 2)

            result.turn_touch_time = round(turn_touch_time - race_start, 2) if turn_touch_time is not None else None
            if turn_touch_time is not None and turn_surface_time is not None:
                result.turn_surface_time_val = round(turn_surface_time - turn_touch_time, 2)
                px_per_m = self._estimate_pixel_per_meter(frames_data, race_start, race_end)
                turn_x_start = None
                turn_x_end = None
                for ts, lm in frames_data:
                    if lm is None:
                        continue
                    if abs(ts - turn_touch_time) < 0.2:
                        lh = self._get_landmark(lm, LEFT_HIP)
                        rh = self._get_landmark(lm, RIGHT_HIP)
                        mid = self._midpoint(lh, rh)
                        if mid is not None and turn_x_start is None:
                            turn_x_start = mid[0]
                    if abs(ts - turn_surface_time) < 0.2:
                        lh = self._get_landmark(lm, LEFT_HIP)
                        rh = self._get_landmark(lm, RIGHT_HIP)
                        mid = self._midpoint(lh, rh)
                        if mid is not None and turn_x_end is None:
                            turn_x_end = mid[0]
                if turn_x_start is not None and turn_x_end is not None and px_per_m > 0:
                    result.turn_surface_distance = round(abs(turn_x_end - turn_x_start) / px_per_m, 2)
                else:
                    avg_speed = self.race_distance / max(race_duration, 1.0)
                    turn_uw_dur = turn_surface_time - turn_touch_time
                    result.turn_surface_distance = round(avg_speed * turn_uw_dur, 2)
            result.turn_underwater_kick_count = turn_underwater_kick_count

            result.finish_time = round(race_duration, 2)

        self._validate_results(result, race_duration)

        filtered = self._filter_by_options(result, analysis_options)
        filtered["_meta"] = {
            "max_persons_detected": max_persons,
            "swimmer_position": self.swimmer_position,
            "video_duration": round(video_duration, 2),
            "race_start": round(race_start, 2),
            "race_end": round(race_end, 2),
            "race_duration": round(race_duration, 2),
        }

        self._report_progress(100, "分析完成")
        return filtered

    def _filter_by_options(self, result: SwimAnalysisResult, options: List[str]) -> Dict[str, Any]:
        option_map = {
            "起跳反应时间": ("dive_reaction_time", "秒", False),
            "出发后潜水时间": ("dive_underwater_time", "秒", False),
            "出发后潜水距离": ("dive_underwater_distance", "米", False),
            "水下腿次数": ("underwater_kick_count", "次", False),
            "前程途中游速度": ("first_half_speed", "米/秒", False),
            "前程总划水次数": ("first_half_stroke_count", "次", False),
            "前程水面交替打腿次数": ("first_half_kick_count", "次", False),
            "前程总呼吸次数": ("first_half_breath_count", "次", False),
            "半程触壁转身时刻": ("turn_touch_time", "秒", False),
            "前程整体用时": ("first_half_time", "秒", True),
            "转身后出水用时": ("turn_surface_time_val", "秒", False),
            "转身出水距离": ("turn_surface_distance", "米", False),
            "转身水下腿次数": ("turn_underwater_kick_count", "次", False),
            "后程途中游速度": ("second_half_speed", "米/秒", False),
            "后程总划水次数": ("second_half_stroke_count", "次", False),
            "后程水面交替打腿次数": ("second_half_kick_count", "次", False),
            "后程总呼吸次数": ("second_half_breath_count", "次", False),
            "触壁终点用时": ("finish_time", "秒", True),
            "途中游速度": ("mid_course_speed", "米/秒", False),
            "途中游划水次数": ("stroke_count", "次", False),
            "水面交替打腿次数": ("kick_count", "次", False),
            "总呼吸次数": ("breath_count", "次", False),
        }

        output = {}
        for opt in options:
            if opt in option_map:
                attr_name, unit, is_race_time = option_map[opt]
                val = getattr(result, attr_name, None)
                if val is not None:
                    if is_race_time and isinstance(val, (int, float)):
                        output[opt] = _format_race_time(val)
                    elif isinstance(val, float):
                        output[opt] = f"{val:.2f} {unit}"
                    else:
                        output[opt] = f"{val} {unit}"
                else:
                    output[opt] = "未检测到"
        return output
