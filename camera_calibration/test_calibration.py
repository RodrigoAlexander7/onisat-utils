"""
Test the fisheye left-camera calibration.
Loads calibration.npz, undistorts the left half of each side-by-side image.

Usage:
    python test_calibration.py                     # uses first image from camera_test/
    python test_calibration.py path/to/image.jpg   # specific image
    python test_calibration.py --all               # all images in camera_test/
"""

import cv2
import numpy as np
import glob
import os
import sys

CALIBRATION_FILE = "calibration.npz"
IMAGES_DIR       = "camera_test"
OUTPUT_DIR       = "rectified"
HALF_W           = 1280


def load_calibration():
    d = np.load(CALIBRATION_FILE)
    img_size = tuple(d["img_size"].tolist())
    return d["K"], d["D"], img_size


def build_undistort_map(K, D, img_size):
    K_new = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
        K, D, img_size, np.eye(3), balance=0.0
    )
    map1, map2 = cv2.fisheye.initUndistortRectifyMap(
        K, D, np.eye(3), K_new, img_size, cv2.CV_16SC2
    )
    return map1, map2


def process(path, map1, map2, show=True):
    img = cv2.imread(path)
    if img is None:
        print(f"Cannot read: {path}")
        return True

    left = img[:, :HALF_W]
    undistorted = cv2.remap(left, map1, map2, cv2.INTER_LINEAR)

    # side-by-side: original left | undistorted left
    combined = np.hstack([left, undistorted])

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, os.path.basename(path))
    cv2.imwrite(out_path, combined)
    print(f"Saved → {out_path}")

    if show:
        cv2.imshow("Original left | Undistorted left  (any key = next, q = quit)", combined)
        key = cv2.waitKey(0) & 0xFF
        cv2.destroyAllWindows()
        return key != ord("q")
    return True


def main():
    if not os.path.exists(CALIBRATION_FILE):
        print(f"Calibration file not found: {CALIBRATION_FILE}")
        print("Run calibrate.py first.")
        return

    K, D, img_size = load_calibration()
    map1, map2 = build_undistort_map(K, D, img_size)

    print(f"K:\n{K}")
    print(f"D: {D.T}")
    print()

    args = sys.argv[1:]

    if "--all" in args:
        images = sorted(
            glob.glob(os.path.join(IMAGES_DIR, "*.jpg"))
            + glob.glob(os.path.join(IMAGES_DIR, "*.JPG"))
        )
    elif args:
        images = args
    else:
        images = sorted(
            glob.glob(os.path.join(IMAGES_DIR, "*.jpg"))
            + glob.glob(os.path.join(IMAGES_DIR, "*.JPG"))
        )[:6]   # just the first image by default

    for path in images:
        if not process(path, map1, map2):
            break


if __name__ == "__main__":
    main()
