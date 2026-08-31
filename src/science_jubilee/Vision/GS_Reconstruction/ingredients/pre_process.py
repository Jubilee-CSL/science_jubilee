import os
import sys
from pathlib import Path

# Permet d'éviter certaines erreurs liées aux bibliothèques Cuda/OpenMP
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision import transforms
from transformers import AutoModelForImageSegmentation
from sacred import Ingredient

pre_process = Ingredient("pre_process")


@pre_process.config
def config():
    use_ai = True

@pre_process.capture
def segment_plant_mask(image: np.ndarray, birefnet, transform_image, use_ai: bool) -> np.ndarray:
    final_mask = np.zeros(image.shape[:2], dtype=np.uint8)
    
    if use_ai and birefnet is not None:
        try:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image_rgb)
            
            input_tensor = transform_image(pil_image).unsqueeze(0).to("cuda")
            
            with torch.no_grad():
                preds = birefnet(input_tensor)[-1].sigmoid().cpu()
            
            pred = preds[0].squeeze()
            mask_pil = transforms.ToPILImage()(pred)
            
            h, w = image.shape[:2]
            mask_pil = mask_pil.resize((w, h), resample=Image.BILINEAR)
            
            mask_np = np.array(mask_pil)
            final_mask = (mask_np > 127).astype(np.uint8) * 255
    
        except Exception as exc:
            print(f"[!] Erreur de segmentation IA ({exc}), basculement sur HSV")

    # Fallback HSV (Vert)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_green = np.array([35, 40, 40], dtype=np.uint8)
    upper_green = np.array([95, 255, 255], dtype=np.uint8)
    mask_hsv = cv2.inRange(hsv, lower_green, upper_green)
    kernel = np.ones((5, 5), np.uint8)
    mask_hsv = cv2.morphologyEx(mask_hsv, cv2.MORPH_OPEN, kernel)
    mask_hsv = cv2.morphologyEx(mask_hsv, cv2.MORPH_CLOSE, kernel)
    
    return cv2.bitwise_or(mask_hsv, final_mask)

@pre_process.capture
def segment_tray_mask(image: np.ndarray, margin_padding_px=20) -> tuple[np.ndarray, np.ndarray]:
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters() 
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(gray)

    H, W = image.shape[:2]
    tray_mask = np.zeros((H, W), dtype=np.uint8)
    aruco_mask = np.zeros((H, W), dtype=np.uint8)

    if ids is None or len(corners) == 0:
        tray_mask = np.ones((H, W), dtype=np.uint8) * 255
        return tray_mask, aruco_mask

    ids = ids.flatten()
    valid_indices = [i for i, x in enumerate(ids) if x in [0, 1, 2, 3]]
    
    if not valid_indices:
        tray_mask = np.ones((H, W), dtype=np.uint8) * 255
        return tray_mask, aruco_mask

    valid_corners = [corners[i] for i in valid_indices]
    valid_ids = [ids[i] for i in valid_indices]

    all_pts = []
    vx, vy = np.array([0.0, 0.0]), np.array([0.0, 0.0])

    for pts in valid_corners:
        points = pts[0]
        all_pts.extend(points)
        cv2.drawContours(aruco_mask, [np.int32(points)], 0, 255, thickness=cv2.FILLED)
        
        p0, p1, p2, p3 = points
        vx += (p1 - p0) + (p2 - p3)
        vy += (p3 - p0) + (p2 - p1)

    if margin_padding_px > 0:
        kernel = np.ones((margin_padding_px, margin_padding_px), np.uint8)
        aruco_mask = cv2.dilate(aruco_mask, kernel, iterations=1)

    vx = vx / np.linalg.norm(vx)
    vy = vy / np.linalg.norm(vy)

    all_pts = np.array(all_pts)
    center = np.mean(all_pts, axis=0)

    rel_pts = all_pts - center
    u_vals = np.dot(rel_pts, vx)
    v_vals = np.dot(rel_pts, vy)

    u_min, u_max = np.min(u_vals), np.max(u_vals)
    v_min, v_max = np.min(v_vals), np.max(v_vals)

    has_left = (0 in valid_ids) or (2 in valid_ids)
    has_right = (1 in valid_ids) or (3 in valid_ids)
    has_top = (0 in valid_ids) or (1 in valid_ids)
    has_bottom = (2 in valid_ids) or (3 in valid_ids)

    INF = max(W, H) * 3 

    if not has_left:   u_min -= INF
    if not has_right:  u_max += INF
    if not has_top:    v_min -= INF
    if not has_bottom: v_max += INF

    c1 = center + u_min * vx + v_min * vy
    c2 = center + u_max * vx + v_min * vy
    c3 = center + u_max * vx + v_max * vy
    c4 = center + u_min * vx + v_max * vy

    poly = np.array([c1, c2, c3, c4], dtype=np.int32)
    cv2.fillPoly(tray_mask, [poly], 255)

    return tray_mask, aruco_mask


@pre_process.capture
def run_filter_scene(images_path, use_ai,remove):
    input_path = Path(images_path)
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    birefnet = None
    transform_image = None
    
    if use_ai:
        birefnet = AutoModelForImageSegmentation.from_pretrained(
            "ZhengPeng7/BiRefNet-DIS5K", 
            trust_remote_code=True
        )
        birefnet.to("cuda")
        birefnet.eval()
        
        transform_image = transforms.Compose([
            transforms.Resize((1024, 1024)), 
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

    image_files = list(input_path.glob("*.jpg"))
    if len(image_files)==0:
        image_files = list(input_path.glob("*.png"))
    
    for image_file in image_files:
        image = cv2.imread(str(image_file))
        if image is None:
            continue

        plant_mask = segment_plant_mask(image, birefnet, transform_image, use_ai)
        tray_mask, aruco_mask = segment_tray_mask(image)
        
        safe_mask = plant_mask & tray_mask
        final_mask = safe_mask | aruco_mask
        image = cv2.bitwise_and(image, image, mask=final_mask)
        
        bgra_image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
        bgra_image[:, :, 3] = final_mask

        output_file = image_file.with_suffix(".png")
        cv2.imwrite(str(output_file), bgra_image)
        
        try:
            if remove:
             image_file.unlink()
        except Exception:
            pass

    if use_ai:
        torch.cuda.empty_cache()

    return True