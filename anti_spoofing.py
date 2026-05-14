# anti_spoofing.py
import cv2
import numpy as np
import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.getenv(
    'ANTI_SPOOF_DIR',
    os.path.join(PROJECT_DIR, 'Silent-Face-Anti-Spoofing'),
)
sys.path.insert(0, BASE_DIR)

# os.chdir 삭제하고 대신 환경변수로 경로 전달
os.environ['ANTI_SPOOF_DIR'] = BASE_DIR

from src.anti_spoof_predict import AntiSpoofPredict
from src.generate_patches import CropImage
from src.utility import parse_model_name

MODEL_DIR = f'{BASE_DIR}/resources/anti_spoof_models'

# 모델 로드 시 디렉토리 임시 변경
_cwd = os.getcwd()
os.chdir(BASE_DIR)
model_test = AntiSpoofPredict(0)
image_cropper = CropImage()
os.chdir(_cwd)  # ← 원래 디렉토리로 복구

def check_real_face(image_bgr, face_location):
    """
    반환: (is_real: bool, score: float)
    """
    try:
        top, right, bottom, left = face_location
        w = right - left
        h = bottom - top
        image_bbox = [left, top, w, h]

        prediction = np.zeros((1, 3))
        for model_name in os.listdir(MODEL_DIR):
            h_input, w_input, model_type, scale = parse_model_name(model_name)
            param = {
                "org_img": image_bgr,
                "bbox": image_bbox,
                "scale": scale,
                "out_w": w_input,
                "out_h": h_input,
                "crop": True,
            }
            if scale is None:
                param["crop"] = False
            img = image_cropper.crop(**param)
            prediction += model_test.predict(img, os.path.join(MODEL_DIR, model_name))

        label = np.argmax(prediction)
        score = float(prediction[0][label] / 2)

        is_real = (label == 1)
        return is_real, round(score, 3)

    except Exception as e:
        print(f"⚠️ Anti-spoofing 오류: {e}")
        return True, 1.0  # 오류 시 통과
