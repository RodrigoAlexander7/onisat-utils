"""
Fisheye left-camera calibration (first pass).
Input : side-by-side JPG images (2560x720) in camera_test/  – only LEFT half used
Output: calibration.npz  (K, D, img_size)

Chessboard: 10x7 squares  →  9x6 inner corners
Camera    : fisheye (cv2.fisheye module)
"""

import cv2
import numpy as np
import glob
import os
import re

IMAGES_DIR  = "camera_test"
OUTPUT_FILE = "calibration.npz"
BOARD_SIZE  = (9, 6)      # inner corners (cols, rows)
SQUARE_SIZE = 3.4         # cm – measured square side
IMG_W, IMG_H = 2560, 720
HALF_W       = IMG_W // 2  # each lens: 1280 x 720


def find_corners(images):
    objp = np.zeros((BOARD_SIZE[0] * BOARD_SIZE[1], 1, 3), np.float64)
    objp[:, 0, :2] = (
        np.mgrid[0:BOARD_SIZE[0], 0:BOARD_SIZE[1]].T.reshape(-1, 2) * SQUARE_SIZE
    )

    subpix_criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    obj_pts, pts_l = [], []

    for path in images:
        img = cv2.imread(path)
        if img is None:
            print(f"  skip (unreadable): {os.path.basename(path)}")
            continue

        gray_l = cv2.cvtColor(img[:, :HALF_W], cv2.COLOR_BGR2GRAY)
        ok_l, cl = cv2.findChessboardCorners(gray_l, BOARD_SIZE, None)

        if ok_l:
            cl = cv2.cornerSubPix(gray_l, cl, (11, 11), (-1, -1), subpix_criteria)
            obj_pts.append(objp)
            pts_l.append(cl.reshape(-1, 1, 2))
            print(f"  [ok] {os.path.basename(path)}")
        else:
            print(f"  [--] {os.path.basename(path)}")

    return obj_pts, pts_l


def calibrate_fisheye(all_obj, all_img, img_size, label=""):
    """Calibrate one fisheye lens, dropping ill-conditioned images automatically.
    Returns (rms, K, D, kept_indices).
    """
    flags = (
        cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC
        + cv2.fisheye.CALIB_FIX_SKEW
    )
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6)

    indices = list(range(len(all_obj)))

    while len(indices) >= 6:
        obj = [all_obj[i] for i in indices]
        img = [all_img[i] for i in indices]
        K = np.eye(3, dtype=np.float64)
        D = np.zeros((4, 1))
        try:
            rms, K, D, _, _ = cv2.fisheye.calibrate(
                obj, img, img_size, K, D, flags=flags, criteria=criteria
            )
            return rms, K, D, indices
        except cv2.error as e:
            m = re.search(r'input array (\d+)', str(e))
            if m:
                bad = int(m.group(1))
                print(f"  [{label}] dropping ill-conditioned image (local idx {bad}, global idx {indices[bad]})")
                indices.pop(bad)
            else:
                raise

    raise RuntimeError(f"[{label}] not enough valid images after filtering")


def main():
    images = sorted(
        glob.glob(os.path.join(IMAGES_DIR, "*.jpg"))
        + glob.glob(os.path.join(IMAGES_DIR, "*.JPG"))
    )
    print(f"Found {len(images)} images\n")

    obj_pts, pts_l = find_corners(images)
    print(f"\nValid images: {len(obj_pts)}\n")

    if len(obj_pts) < 6:
        print("Not enough valid images (need at least 6). Aborting.")
        return

    img_size = (HALF_W, IMG_H)

    print("Calibrating left camera ...")
    rms, K, D, idx = calibrate_fisheye(obj_pts, pts_l, img_size, "L")
    print(f"  RMS = {rms:.4f}  ({len(idx)} images used)")
    print(f"  K:\n{K}")
    print(f"  D: {D.T}")

    np.savez(
        OUTPUT_FILE,
        K=K, D=D,
        img_size=np.array(img_size),
    )
    print(f"\nSaved → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
