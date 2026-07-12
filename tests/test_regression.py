import json
import os
import sys
import re

ANNOTATIONS_DIR = os.path.join(os.path.dirname(__file__), "data", "annotations")
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")


def parse_numeric(value_str: str) -> float | None:
    if not value_str or value_str == "未检测到":
        return None
    match = re.search(r'[\d.]+', value_str)
    if match:
        return float(match.group())
    return None


def load_annotations(annotations_dir: str) -> list:
    annotations = []
    if not os.path.exists(annotations_dir):
        print(f"Annotations directory not found: {annotations_dir}")
        return annotations
    for fname in os.listdir(annotations_dir):
        if not fname.endswith('.json'):
            continue
        fpath = os.path.join(annotations_dir, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        annotations.append(data)
    return annotations


def find_video(video_filename: str) -> str | None:
    if not os.path.exists(UPLOADS_DIR):
        return None
    for fname in os.listdir(UPLOADS_DIR):
        if fname.startswith('.'):
            continue
        name_without_ext = os.path.splitext(fname)[0]
        if video_filename in fname or fname in video_filename:
            return os.path.join(UPLOADS_DIR, fname)
    return None


def run_regression_test(annotation: dict) -> dict:
    from backend.analysis_v2.pipeline import AnalysisPipeline

    video_filename = annotation.get("video_filename", "")
    pool_length = annotation.get("pool_length", 50)
    race_distance = annotation.get("race_distance", 100)
    expected = annotation.get("annotations", {})
    tolerance = annotation.get("tolerance", {})

    video_path = find_video(video_filename)
    if not video_path:
        return {
            "video": video_filename,
            "status": "skipped",
            "message": f"Video file not found: {video_filename}",
        }

    pipeline = AnalysisPipeline(
        pool_length=pool_length,
        race_distance=race_distance,
    )
    result = pipeline.analyze(video_path, [])

    report = {"video": video_filename, "status": "passed", "details": []}
    for key, expected_val_str in expected.items():
        expected_num = parse_numeric(expected_val_str)
        actual_val = result.get(key)
        actual_num = parse_numeric(str(actual_val)) if actual_val else None
        tol = tolerance.get(key, 0)

        detail = {
            "metric": key,
            "expected": expected_val_str,
            "actual": actual_val,
            "expected_num": expected_num,
            "actual_num": actual_num,
            "tolerance": tol,
        }

        if expected_num is not None and actual_num is not None:
            error = abs(actual_num - expected_num)
            detail["error"] = round(error, 4)
            if error > tol:
                detail["status"] = "FAIL"
                report["status"] = "failed"
            else:
                detail["status"] = "PASS"
        elif expected_num is None and actual_num is None:
            detail["status"] = "PASS"
        else:
            detail["status"] = "SKIP"

        report["details"].append(detail)

    return report


def main():
    annotations = load_annotations(ANNOTATIONS_DIR)
    if not annotations:
        print("No annotation files found. Please add JSON files to tests/data/annotations/")
        return 1

    all_passed = True
    for ann in annotations:
        print(f"\n{'='*60}")
        print(f"Testing: {ann.get('video_filename', 'unknown')}")
        print(f"Pool: {ann.get('pool_length')}m, Distance: {ann.get('race_distance')}m")
        print(f"{'='*60}")

        report = run_regression_test(ann)
        if report["status"] == "skipped":
            print(f"  SKIPPED: {report['message']}")
            continue

        for detail in report["details"]:
            status_icon = "✓" if detail["status"] == "PASS" else ("✗" if detail["status"] == "FAIL" else "?")
            line = f"  {status_icon} {detail['metric']}: expected={detail['expected']}, actual={detail['actual']}"
            if "error" in detail:
                line += f", error={detail['error']}, tol={detail['tolerance']}"
            print(line)

        if report["status"] == "failed":
            all_passed = False
            print(f"\n  Result: FAILED")
        else:
            print(f"\n  Result: PASSED")

    print(f"\n{'='*60}")
    if all_passed:
        print("All regression tests PASSED")
        return 0
    else:
        print("Some regression tests FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())