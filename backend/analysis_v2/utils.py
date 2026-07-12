import numpy as np
from typing import Optional, List, Dict, Any


def get_lm(landmarks: dict, name: str) -> Optional[np.ndarray]:
    if landmarks is None or name not in landmarks:
        return None
    val = landmarks[name]
    if isinstance(val, np.ndarray):
        return val[:3]
    return None


def midpoint(p1, p2) -> Optional[np.ndarray]:
    if p1 is None or p2 is None:
        return None
    return (p1 + p2) / 2.0


def smooth(data, window: int):
    if len(data) < window:
        return data
    kernel = np.ones(window) / window
    return np.convolve(data, kernel, mode='same')


def detect_water_surface(pose_frames: list) -> float:
    all_y = []
    for pf in pose_frames:
        lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
        if lm is None:
            continue
        for name in ["left_shoulder", "right_shoulder"]:
            p = get_lm(lm, name)
            if p is not None and 0.15 <= p[1] <= 0.75:
                all_y.append(p[1])
    if all_y:
        return float(np.percentile(all_y, 20))
    all_y2 = []
    for pf in pose_frames:
        lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
        if lm is None:
            continue
        for name in ["left_shoulder", "right_shoulder"]:
            p = get_lm(lm, name)
            if p is not None:
                all_y2.append(p[1])
    return float(np.percentile(all_y2, 15)) if all_y2 else 0.5


def get_swimmer_x_range(pose_frames: list, race_start, swimmer_position: int = 1):
    all_hip_x = []
    for pf in pose_frames:
        ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
        lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
        if lm is None:
            continue
        lh = get_lm(lm, "left_hip")
        rh = get_lm(lm, "right_hip")
        mid = midpoint(lh, rh)
        if mid is not None and mid[1] < 0.7:
            all_hip_x.append(mid[0])

    if len(all_hip_x) < 10:
        return None, None

    x_arr = np.array(all_hip_x)
    q1, q99 = np.percentile(x_arr, [5, 95])
    iqr = q99 - q1
    x_arr = x_arr[(x_arr >= q1 - 1.5 * iqr) & (x_arr <= q99 + 1.5 * iqr)]
    if len(x_arr) < 10:
        return None, None
    n_swimmers = min(9, max(2, int((x_arr.max() - x_arr.min()) / 0.15) + 1))

    if n_swimmers <= 2:
        return None, None

    n_bins = n_swimmers * 5
    hist, bin_edges = np.histogram(x_arr, bins=n_bins)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    peak_indices = np.argsort(hist)[::-1]
    peak_bins = []
    for idx in peak_indices:
        if len(peak_bins) >= n_swimmers:
            break
        center = bin_centers[idx]
        too_close = any(abs(center - pb) < 0.08 for pb in peak_bins)
        if not too_close:
            peak_bins.append(center)

    if len(peak_bins) == 0:
        return None, None

    peak_bins.sort()
    pos = min(swimmer_position, len(peak_bins))
    target_center = peak_bins[pos - 1]

    target_x = x_arr[np.abs(x_arr - target_center) < 0.10]
    if len(target_x) < 3:
        target_x = x_arr[np.abs(x_arr - target_center) < 0.15]
    if len(target_x) < 3:
        return None, None

    x_min = float(np.percentile(target_x, 5)) - 0.03
    x_max = float(np.percentile(target_x, 95)) + 0.03
    return x_min, x_max


def get_swimmer_x_range_dive(pose_frames: list, dive_start, swimmer_position: int = 1):
    on_block_x = []
    for pf in pose_frames:
        ts = pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp
        lm = pf.get("landmarks") if isinstance(pf, dict) else getattr(pf, 'landmarks', None)
        if lm is None:
            continue
        if ts > dive_start + 2.0:
            break
        lh = get_lm(lm, "left_hip")
        rh = get_lm(lm, "right_hip")
        mid = midpoint(lh, rh)
        if mid is not None and mid[1] > 0.8:
            on_block_x.append(mid[0])

    if len(on_block_x) < 5:
        return None, None

    x_arr = np.array(on_block_x)
    q1, q99 = np.percentile(x_arr, [5, 95])
    iqr = q99 - q1
    x_arr = x_arr[(x_arr >= q1 - 1.5 * iqr) & (x_arr <= q99 + 1.5 * iqr)]
    if len(x_arr) < 5:
        return None, None
    n_swimmers = min(9, max(2, int((x_arr.max() - x_arr.min()) / 0.10) + 1))

    if n_swimmers <= 2:
        return None, None

    n_bins = n_swimmers * 5
    hist, bin_edges = np.histogram(x_arr, bins=n_bins)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    peak_indices = np.argsort(hist)[::-1]
    peak_bins = []
    for idx in peak_indices:
        if len(peak_bins) >= n_swimmers:
            break
        center = bin_centers[idx]
        too_close = any(abs(center - pb) < 0.06 for pb in peak_bins)
        if not too_close:
            peak_bins.append(center)

    if len(peak_bins) == 0:
        return None, None

    peak_bins.sort()
    pos = min(swimmer_position, len(peak_bins))
    target_center = peak_bins[pos - 1]

    target_x = x_arr[np.abs(x_arr - target_center) < 0.08]
    if len(target_x) < 3:
        target_x = x_arr[np.abs(x_arr - target_center) < 0.12]
    if len(target_x) < 3:
        return None, None

    x_min = float(np.percentile(target_x, 5)) - 0.05
    x_max = float(np.percentile(target_x, 95)) + 0.05
    return x_min, x_max


def get_timestamp(pf) -> float:
    return pf.get("timestamp") if isinstance(pf, dict) else pf.timestamp


def get_landmark_from_pf(pf, name: str, landmarks_key: str = "landmarks") -> Optional[np.ndarray]:
    lm = pf.get(landmarks_key) if isinstance(pf, dict) else getattr(pf, landmarks_key, None)
    return get_lm(lm, name)


def interpolate_gaps(data):
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


def format_race_time(seconds: float) -> str:
    if seconds < 0:
        return "0.00秒"
    if seconds < 60:
        return f"{seconds:.2f}秒"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}分{s:05.2f}秒"