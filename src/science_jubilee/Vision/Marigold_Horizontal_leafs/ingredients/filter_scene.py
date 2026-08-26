from sacred import Ingredient
import cv2
import numpy as np


filter_scene = Ingredient("filter_scene")


@filter_scene.config
def config():
     pass
     
@filter_scene.capture
def segment_tray_mask(image: np.ndarray, margin_padding_px=20) -> np.ndarray:
    """
    Construction of the tray mask by searching for the ArUco codes on the corners (see printable aruco_reference.pdf )
    The sheet has to be placed on the center of the jubilee tray
    """
    # Configuration of aruco code detection using its corresponding dictionary name (in this cas we use the arUco code number 0 from DICT_4X4_50 )
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = (
        cv2.aruco.DetectorParameters()
    )  # We dont need for custom parameters (real width, lenght, etc)
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(gray)

    final_mask = np.zeros(image.shape[:2], dtype=np.uint8)

    if ids is None or len(corners) == 0:
        print("Any arUco code detected")
        return final_mask

    all_corners = np.vstack(corners).reshape(-1, 2)

    # Creation of the global tray mask by using the rectangle formed by the 4 arUco Codes
    rect = cv2.minAreaRect(all_corners)
    box = cv2.boxPoints(rect)
    box = np.int32(box)

    cv2.drawContours(final_mask, [box], 0, 255, thickness=cv2.FILLED)

    # Padding added to include the real AruCo codes padding from the printed sheet
    if margin_padding_px > 0:
        kernel = np.ones((margin_padding_px, margin_padding_px), np.uint8)
        final_mask = cv2.dilate(final_mask, kernel, iterations=1)

    return final_mask

@filter_scene.capture
def segment_plant_mask(image: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_green = np.array([35, 40, 40], dtype=np.uint8)
    upper_green = np.array([95, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_green, upper_green)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


@filter_scene.capture
def run_filter_scene(image):
	image_bgr = np.asarray(image)
	tray_mask = segment_tray_mask(image_bgr)
	plant_mask = segment_plant_mask(image_bgr)
	return {
		"image": image_bgr,
		"tray_mask": tray_mask,
		"plant_mask": plant_mask,
	}
