from science_jubilee.tools.Observer import Camera
import requests
import time
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


LED_SERVER = "http://10.0.9.55:5001"
def test_imag():
    """requests.get(f"{LED_SERVER}/led/255/255/255")"""
    cam = Camera()
    """
    img = cam.get_clean_image(save_dir= Path("dataset_clean"), nb_image_used= 8)
    #img = cam.get_latest_image(folder = Path("dataset_clean"))
    
    contour = cam.get_img_contour(img = img,max_area_px= 100, min_area_px= 10, debug=True)
    logger.info(contour)

    isolated_lens = cam.detect_isolated_duckweed(valid_contours= contour)
    logger.info(isolated_lens)"""
    cam.save_image()