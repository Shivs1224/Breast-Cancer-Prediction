import os

import cv2
import numpy as np


def cv2_imread(path):
    path = os.path.normpath(path)
    img = cv2.imread(path)
    if img is not None:
        return img
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def cv2_imwrite(path, image, ext=".png"):
    path = os.path.normpath(path)
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    ok, buf = cv2.imencode(ext, image)
    if not ok:
        return False
    buf.tofile(path)
    return True
