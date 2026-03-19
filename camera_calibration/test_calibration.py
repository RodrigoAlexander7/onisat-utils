"""
Test the fisheye dual-camera calibration.
Loads calibration.npz, undistorts the left and right halves of each side-by-side image.

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
    
    K_L = d["K_L"] if "K_L" in d else d["K"] if "K" in d else None
    D_L = d["D_L"] if "D_L" in d else d["D"] if "D" in d else None
    K_R = d["K_R"] if "K_R" in d else None
    D_R = d["D_R"] if "D_R" in d else None
    
    return K_L, D_L, K_R, D_R, img_size


def build_undistort_map(K, D, img_size):
    if K is None or D is None:
        return None, None
    K_new = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
        K, D, img_size, np.eye(3), balance=0.0
    )
    map1, map2 = cv2.fisheye.initUndistortRectifyMap(
        K, D, np.eye(3), K_new, img_size, cv2.CV_16SC2
    )
    return map1, map2


def process(path, map1_l, map2_l, map1_r, map2_r, show=True):
    img = cv2.imread(path)
    if img is None:
        print(f"Cannot read: {path}")
        return True

    left = img[:, :HALF_W]
    right = img[:, HALF_W:]
    
    row_l, row_r = None, None

    if map1_l is not None:
        undistorted_l = cv2.remap(left, map1_l, map2_l, cv2.INTER_LINEAR)
        row_l = np.hstack([left, undistorted_l])
        
    if map1_r is not None:
        undistorted_r = cv2.remap(right, map1_r, map2_r, cv2.INTER_LINEAR)
        row_r = np.hstack([right, undistorted_r])

    if row_l is not None and row_r is not None:
        combined = np.vstack([row_l, row_r])
    elif row_l is not None:
        combined = row_l
    elif row_r is not None:
        combined = row_r
    else:
        return True

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, os.path.basename(path))
    cv2.imwrite(out_path, combined)
    print(f"Saved → {out_path}")

    if show:
        # Resize if combined is too large, it might not fit on standard screens
        scale = 0.5
        display_img = cv2.resize(combined, (int(combined.shape[1] * scale), int(combined.shape[0] * scale)))
        cv2.imshow("Original | Undistorted (Top: L, Bottom: R) (any key = next, q = quit)", display_img)
        key = cv2.waitKey(0) & 0xFF
        cv2.destroyAllWindows()
        return key != ord("q")
    return True


def main():
    if not os.path.exists(CALIBRATION_FILE):
        print(f"Calibration file not found: {CALIBRATION_FILE}")
        print("Run calibrate.py first.")
        return

    K_L, D_L, K_R, D_R, img_size = load_calibration()
    map1_l, map2_l = build_undistort_map(K_L, D_L, img_size)
    map1_r, map2_r = build_undistort_map(K_R, D_R, img_size)

    if K_L is not None:
        print(f"K_L:\n{K_L}")
        print(f"D_L: {D_L.T}\n")
    if K_R is not None:
        print(f"K_R:\n{K_R}")
        print(f"D_R: {D_R.T}\n")

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
        if not process(path, map1_l, map2_l, map1_r, map2_r):
            break


if __name__ == "__main__":
    main()
