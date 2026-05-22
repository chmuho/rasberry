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

    if upper_points and not lower_points:
        return True, upper_points
    if not upper_points or not lower_points:
        return False, upper_points

    # 코/입 영역에서 피부색이 충분히 보이면 마스크 미착용으로 판단합니다.
    lower_ys = [p[1] for p in lower_points]
    lower_xs = [p[0] for p in lower_points]

    roi_top    = max(0, min(lower_ys) - 10)
    roi_bottom = min(image_rgb.shape[0], max(lower_ys) + 10)
    roi_left   = max(0, min(lower_xs) - 10)
    roi_right  = min(image_rgb.shape[1], max(lower_xs) + 10)

    lower_roi = image_rgb[roi_top:roi_bottom, roi_left:roi_right]
    if lower_roi.size == 0:
        return False, upper_points

    gray_roi = cv2.cvtColor(lower_roi, cv2.COLOR_RGB2GRAY)
    std_dev = float(np.std(gray_roi))
    ycrcb = cv2.cvtColor(lower_roi, cv2.COLOR_RGB2YCrCb)
    skin_mask = cv2.inRange(ycrcb, np.array([0, 133, 77]), np.array([255, 173, 127]))
    skin_ratio = float(np.count_nonzero(skin_mask)) / float(skin_mask.size)

    # 피부색이 거의 보이지 않고 비교적 균일할 때만 마스크 착용으로 봅니다.
    is_masked = skin_ratio < 0.12 and std_dev < 38
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
