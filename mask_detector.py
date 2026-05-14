import cv2
import numpy as np
import face_recognition

def detect_mask_by_landmark(image_rgb, face_location):
    """
    랜드마크 기반 마스크 감지
    반환: (is_masked: bool, upper_points: list)
    """
    landmarks_list = face_recognition.face_landmarks(image_rgb, [face_location])
    if not landmarks_list:
        return False, None

    lm = landmarks_list[0]

    upper_points = (
        lm.get("left_eyebrow", []) +
        lm.get("right_eyebrow", []) +
        lm.get("left_eye", []) +
        lm.get("right_eye", [])
    )

    lower_points = (
        lm.get("nose_tip", []) +
        lm.get("nose_bridge", []) +
        lm.get("top_lip", []) +
        lm.get("bottom_lip", [])
    )

    if not upper_points or not lower_points:
        return False, upper_points

    # 코/입 영역 크롭해서 픽셀 균일도 측정
    image_bgr = image_rgb
    lower_ys = [p[1] for p in lower_points]
    lower_xs = [p[0] for p in lower_points]

    roi_top    = max(0, min(lower_ys) - 10)
    roi_bottom = min(image_bgr.shape[0], max(lower_ys) + 10)
    roi_left   = max(0, min(lower_xs) - 10)
    roi_right  = min(image_bgr.shape[1], max(lower_xs) + 10)

    lower_roi = image_bgr[roi_top:roi_bottom, roi_left:roi_right]
    if lower_roi.size == 0:
        return False, upper_points

    gray_roi = cv2.cvtColor(lower_roi, cv2.COLOR_BGR2GRAY)
    std_dev = float(np.std(gray_roi))

    # 표준편차가 낮을수록 단색 → 마스크 착용
    is_masked = std_dev < 28
    return is_masked, upper_points


def get_upper_face_location(upper_points, image_shape):
    """
    눈/이마 랜드마크 기준으로 인코딩할 얼굴 영역 반환
    마스크 착용 시 이 영역만으로 인코딩
    """
    if not upper_points:
        return None

    ys = [p[1] for p in upper_points]
    xs = [p[0] for p in upper_points]
    pad = 30

    top    = max(0, min(ys) - pad)
    bottom = min(image_shape[0], max(ys) + pad)
    left   = max(0, min(xs) - pad)
    right  = min(image_shape[1], max(xs) + pad)

    return (top, right, bottom, left)  # dlib location 형식 유지