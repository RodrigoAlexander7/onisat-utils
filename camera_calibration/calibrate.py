"""
Fisheye dual-camera calibration (first pass).
Input : side-by-side JPG images (2560x720) in camera_test/
Output: calibration.npz  (K_L, D_L, K_R, D_R, img_size)

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

    obj_pts_l, pts_l = [], []
    obj_pts_r, pts_r = [], []

    for path in images:
        img = cv2.imread(path)
        if img is None:
            print(f"  skip (unreadable): {os.path.basename(path)}")
            continue

        gray_l = cv2.cvtColor(img[:, :HALF_W], cv2.COLOR_BGR2GRAY)
        gray_r = cv2.cvtColor(img[:, HALF_W:], cv2.COLOR_BGR2GRAY)

        ok_l, cl = cv2.findChessboardCorners(gray_l, BOARD_SIZE, None)
        ok_r, cr = cv2.findChessboardCorners(gray_r, BOARD_SIZE, None)

        if ok_l:
            cl = cv2.cornerSubPix(gray_l, cl, (11, 11), (-1, -1), subpix_criteria)
            obj_pts_l.append(objp)
            pts_l.append(cl.reshape(-1, 1, 2))
            
        if ok_r:
            cr = cv2.cornerSubPix(gray_r, cr, (11, 11), (-1, -1), subpix_criteria)
            obj_pts_r.append(objp)
            pts_r.append(cr.reshape(-1, 1, 2))

        print(f"  [{'L' if ok_l else '-'}{'R' if ok_r else '-'}] {os.path.basename(path)}")

    return obj_pts_l, pts_l, obj_pts_r, pts_r


def calibrate_fisheye(all_obj, all_img, img_size, label=""):
    """Calibrate one fisheye lens, dropping ill-conditioned images automatically.
    Returns (rms, K, D, kept_indices).
    """
    flags = (
        cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC
        + cv2.fisheye.CALIB_FIX_SKEW
        + cv2.fisheye.CALIB_USE_INTRINSIC_GUESS
    )
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6)

    indices = list(range(len(all_obj)))

    while len(indices) >= 6:
        obj = [all_obj[i] for i in indices]
        img = [all_img[i] for i in indices]
        
        # Initial guess for K
        focal_length = img_size[0] / 2.0  # rough guess for fisheye
        cx = img_size[0] / 2.0
        cy = img_size[1] / 2.0
        K = np.array([
            [focal_length, 0, cx],
            [0, focal_length, cy],
            [0, 0, 1]
        ], dtype=np.float64)
        
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
                # If OpenCV assertions trigger but it doesn't give the view index (e.g., InitExtrinsics),
                # we hunt for the bad image by testing a subset or popping backwards.
                print(f"  [{label}] Calibration failed with unknown view error: {e}. Searching for problematic view...")
                found_bad = False
                # Test leaving one out to see if it fixes it
                for test_idx in range(len(indices)):
                    test_obj = obj[:test_idx] + obj[test_idx+1:]
                    test_img = img[:test_idx] + img[test_idx+1:]
                    test_K = K.copy()
                    test_D = np.zeros((4, 1))
                    try:
                        cv2.fisheye.calibrate(test_obj, test_img, img_size, test_K, test_D, flags=flags, criteria=criteria)
                        print(f"  [{label}] View local idx {test_idx} is the culprit. Dropping global idx {indices[test_idx]}.")
                        indices.pop(test_idx)
                        found_bad = True
                        break
                    except:
                        pass
                
                if not found_bad:
                    # If leaving one out didn't fix it, drop the last frame and hope we get closer to a usable set
                    print(f"  [{label}] Could not isolate a single bad view. Dropping the last view (global idx {indices[-1]}) and retrying.")
                    indices.pop()

    raise RuntimeError(f"[{label}] not enough valid images after filtering")


def main():
    images = sorted(
        glob.glob(os.path.join(IMAGES_DIR, "*.jpg"))
        + glob.glob(os.path.join(IMAGES_DIR, "*.JPG"))
    )
    print(f"Found {len(images)} images\n")

    obj_pts_l, pts_l, obj_pts_r, pts_r = find_corners(images)
    print(f"\nValid images: L={len(obj_pts_l)}, R={len(obj_pts_r)}\n")

    if len(obj_pts_l) < 6 and len(obj_pts_r) < 6:
        print("Not enough valid images for either camera (need at least 6). Aborting.")
        return

    img_size = (HALF_W, IMG_H)
    save_dict = {'img_size': np.array(img_size)}

    if len(obj_pts_l) >= 6:
        print("Calibrating left camera ...")
        rms_l, K_L, D_L, idx_l = calibrate_fisheye(obj_pts_l, pts_l, img_size, "L")
        print(f"  RMS = {rms_l:.4f}  ({len(idx_l)} images used)")
        print(f"  K_L:\n{K_L}")
        print(f"  D_L: {D_L.T}")
        save_dict['K_L'] = K_L
        save_dict['D_L'] = D_L
    else:
        print("Not enough valid images for left camera.")

    if len(obj_pts_r) >= 6:
        print("\nCalibrating right camera ...")
        rms_r, K_R, D_R, idx_r = calibrate_fisheye(obj_pts_r, pts_r, img_size, "R")
        print(f"  RMS = {rms_r:.4f}  ({len(idx_r)} images used)")
        print(f"  K_R:\n{K_R}")
        print(f"  D_R: {D_R.T}")
        save_dict['K_R'] = K_R
        save_dict['D_R'] = D_R
    else:
        print("\nNot enough valid images for right camera.")

    np.savez(OUTPUT_FILE, **save_dict)
    print(f"\nSaved → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
