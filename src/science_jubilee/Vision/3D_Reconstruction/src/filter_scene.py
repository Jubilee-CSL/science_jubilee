import argparse
import json
import os
import sys
from pathlib import Path
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"  # Allows using Cuda (necessary)
import cv2
import numpy as np
from PIL import Image
from ultralytics import SAM
from torchvision import transforms
from transformers import AutoModelForImageSegmentation
import torch


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


model = SAM("sam2.1_b.pt")


def find_rough_plant_bboxes(image_bgr, min_area=400):
    """
    Étape 1 : Trouve de multiples bounding boxes pour les plantes (Vert) et les pots (Marron),
    tout en ignorant le fond et le papier blanc.
    """
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

    # 1. MASQUE VERT (La Plante)
    # Saturation minimale à 40 : ignore automatiquement le blanc, le gris et le noir.
    lower_green = np.array([40, 25, 25])
    upper_green = np.array([80, 200, 200])
    green_mask = cv2.inRange(hsv, lower_green, upper_green)

    # 2. MASQUE MARRON (Le Pot / Vase)
    # Le marron en HSV est un "orange sombre". Teinte entre 10 et 25.
    # Saturation > 50 ignore le blanc. Value < 200 ignore les reflets lumineux forts.
    lower_brown = np.array([10, 50, 20])
    upper_brown = np.array([25, 255, 200])
    brown_mask = cv2.inRange(hsv, lower_brown, upper_brown)

    #3. Masque Blanc(La feuille de papier blanche)
    lower_white = np.array([0, 0, 80])
    upper_white = np.array([179, 40, 255])
    
    white_mask = cv2.inRange(hsv, lower_white, upper_white)

    # 3. FUSION DES MASQUES
    # On combine les pixels verts et les pixels marrons.
    # Le papier blanc (Saturation proche de 0) est ici totalement invisible/ignoré.
    #combined_mask = cv2.bitwise_or(green_mask, brown_mask)
    combined_mask = cv2.bitwise_and(green_mask,cv2.bitwise_not(white_mask))
    # 4. NETTOYAGE
    kernel_open = np.ones((5, 5), np.uint8)
    kernel_close = np.ones((15, 15), np.uint8) # Kernel plus grand pour fusionner la plante et son pot s'il y a un petit trou
    
    mask_clean = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel_open)
    mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_CLOSE, kernel_close)

    # 5. TROUVER DE MULTIPLES CONTOURS
    contours, _ = cv2.findContours(
        mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    bboxes = []
    for cnt in contours:
        if cv2.contourArea(cnt) > min_area:
            x, y, w, h = cv2.boundingRect(cnt)
            # Format attendu par SAM : [x1, y1, x2, y2]
            bboxes.append([x, y, x + w, y + h])

    return bboxes


def segment_plants_fast(image_bgr, device="cuda"):
    """
    Étape 2 : Découpe les plantes et leurs pots détectés à l'aide des bboxes.
    """
    # Récupère la liste complète des bounding boxes
    bboxes = find_rough_plant_bboxes(image_bgr)

    # Si rien n'est détecté, on retourne un masque noir vide
    if not bboxes:
        return np.zeros(image_bgr.shape[:2], dtype=np.uint8)

    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    # FastSAM / SAM 2 accepte nativement une liste de bboxes : [[x,y,x,y], [x,y,x,y]]
    results = model(
        image_rgb,
        bboxes=bboxes,
        device=device,
        retina_masks=True,
        verbose=False,
    )

    h, w = image_bgr.shape[:2]
    final_mask = np.zeros((h, w), dtype=np.uint8)

    if results and results[0].masks is not None:
        masks = results[0].masks.data.cpu().numpy()

        for m in masks:
            # Ajoute le calque de chaque plante/pot au masque principal
            plant_layer = (m > 0.5).astype(np.uint8) * 255
            final_mask = cv2.bitwise_or(final_mask, plant_layer)
            
    #3. Masque Blanc(La feuille de papier blanche)
    lower_white = np.array([0, 0, 80])
    upper_white = np.array([179, 40, 255])
        
    white_mask = cv2.inRange(hsv, lower_white, upper_white)

    final_mask= cv2.bitwise_and(final_mask,cv2.bitwise_not(white_mask))

    return final_mask
      
def segment_plant_mask(image: np.ndarray,birefnet,transform_image, use_ai: bool = True) -> np.ndarray:
    if use_ai == True:
        try:
            image_rgb = image
            pil_image = Image.fromarray(image_rgb)
            
            # 2. Préparer le tenseur pour la carte graphique
            input_tensor = transform_image(pil_image).unsqueeze(0).to("cuda")
            
            # 3. Inférence (Calcul IA)
            with torch.no_grad():
                preds = birefnet(input_tensor)[-1].sigmoid().cpu()
            
            # 4. Convertir le tenseur de sortie en image
            pred = preds[0].squeeze()
            mask_pil = transforms.ToPILImage()(pred)
            
            # 5. Redimensionner le masque à la taille originale de votre photo
            h, w = image_rgb.shape[:2]
            mask_pil = mask_pil.resize((w, h), resample=Image.BILINEAR)
            
            # 6. Transformer en masque binaire net (0 ou 255)
            mask_np = np.array(mask_pil)
            final_mask = (mask_np > 127).astype(np.uint8) * 255
    
        except Exception as exc:  # model runtime may fail
            print(f"[!] AI segmentation failed ({exc}), falling back to a HSV-based mask")

    # Fallback HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_green = np.array([35, 40, 40], dtype=np.uint8)
    upper_green = np.array([95, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_green, upper_green)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return cv2.bitwise_or(mask,final_mask)


def segment_cube_mask(image: np.ndarray) -> np.ndarray:
    """Segmentation du petit cube bleu de référence"""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_blue = np.array([100, 100, 50], dtype=np.uint8)
    upper_blue = np.array([140, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask

def segment_vase_plant(image:np.ndarray):
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # 2. MASQUE MARRON (Le Pot / Vase)
        # Le marron en HSV est un "orange sombre". Teinte entre 10 et 25.
        # Saturation > 50 ignore le blanc. Value < 200 ignore les reflets lumineux forts.
        lower_brown = np.array([10, 70, 20])
        upper_brown = np.array([25, 255, 170])
        brown_mask = cv2.inRange(hsv, lower_brown, upper_brown)
        return brown_mask
def segment_tray_mask(image: np.ndarray, margin_padding_px=20) -> tuple[np.ndarray, np.ndarray]:
    """
    Détecte les codes ArUco et retourne deux masques :
    1. tray_mask : La zone délimitée par les codes (le plateau complet).
    2. aruco_mask : Uniquement l'emplacement exact des codes (avec padding).
    """
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters() 
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(gray)

    H, W = image.shape[:2]
    tray_mask = np.zeros((H, W), dtype=np.uint8)
    aruco_mask = np.zeros((H, W), dtype=np.uint8)

    if ids is None or len(corners) == 0:
        print("Aucun code ArUco détecté.")
        tray_mask = np.ones((H, W), dtype=np.uint8)*255
        return tray_mask, aruco_mask

    # 1. Construction du masque des codes ArUco (avec padding)
    all_pts = []
    for marker_corners in corners:
        pts = np.int32(marker_corners[0]) 
        all_pts.extend(pts) # On stocke tous les points pour la géométrie du plateau
        cv2.drawContours(aruco_mask, [pts], 0, 255, thickness=cv2.FILLED)

    if margin_padding_px > 0:
        kernel = np.ones((margin_padding_px, margin_padding_px), np.uint8)
        aruco_mask = cv2.dilate(aruco_mask, kernel, iterations=1)

    # 2. Construction du masque d'acceptation du plateau (Tray Mask)
    all_pts = np.array(all_pts)
    x_min, y_min = np.min(all_pts, axis=0)
    x_max, y_max = np.max(all_pts, axis=0)
    
    # Centre de gravité des codes détectés
    cx = (x_min + x_max) / 2
    cy = (y_min + y_max) / 2
    
    num_markers = len(corners)

    # RÈGLE 1 : 3 ou 4 codes -> On relie tous les codes pour former un polygone (Convex Hull)
    if num_markers >= 3:
        width_span = x_max - x_min
        height_span = y_max - y_min
        cv2.rectangle(tray_mask, (int(x_min), int(y_min)), (int(x_max), int(y_max)), 255, cv2.FILLED)

    # RÈGLE 2 : 2 codes -> On détermine s'ils forment un axe vertical ou horizontal, et on l'étend
    elif num_markers == 2:
        width_span = x_max - x_min
        height_span = y_max - y_min
        
        if width_span < height_span:
            # Alignement vertical (ex: les deux codes sont sur le bord gauche)
            if cx < W / 2:
                x_max = W  # Étendre vers la droite
            else:
                x_min = 0  # Étendre vers la gauche
        else:
            # Alignement horizontal (ex: les deux codes sont sur le bord haut)
            if cy < H / 2:
                y_max = H  # Étendre vers le bas
            else:
                y_min = 0  # Étendre vers le haut
                
        cv2.rectangle(tray_mask, (int(x_min), int(y_min)), (int(x_max), int(y_max)), 255, cv2.FILLED)

    # RÈGLE 3 : 1 code -> On étend dans les directions opposées à son cadran
    elif num_markers == 1:
        if cx < W / 2:
            x_max = W  # Le code est à gauche, on étend jusqu'à droite
        else:
            x_min = 0  # Le code est à droite, on étend jusqu'à gauche
            
        if cy < H / 2:
            y_max = H  # Le code est en haut, on étend jusqu'en bas
        else:
            y_min = 0  # Le code est en bas, on étend jusqu'en haut
            
        cv2.rectangle(tray_mask, (int(x_min), int(y_min)), (int(x_max), int(y_max)), 255, cv2.FILLED)

    return tray_mask, aruco_mask


def main(images_path, use_ai=True):
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
    images_path = Path(images_path)
    if not images_path.exists():
        raise FileNotFoundError(images_path)

    for image_file in images_path.glob("*.jpg"):
        print(f"Processing {image_file}...")
        image = cv2.imread(str(image_file))
        
        if image is None:
            print(f"Erreur de lecture de l'image {image_file}")
            continue

        # 1. Générer les 3 masques
        plant_mask = segment_plant_mask(image,birefnet, transform_image, use_ai=use_ai)
        #plant_mask = segment_plants_fast(image, device="cuda")
        cube_mask = segment_cube_mask(image)
        vase_mask= segment_vase_plant(image)
        tray_mask,aruco_mask = segment_tray_mask(image)

        safe_mask=(plant_mask | vase_mask) & tray_mask
        final_mask = safe_mask  | aruco_mask

        # 3. Créer l'image RGBA (avec transparence pour 3DGS)
        # Convertir BGR en BGRA (ajoute le canal Alpha)
        rgba_image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
        # Appliquer notre masque combiné sur le canal Alpha (indice 3)
        rgba_image[:, :, 3] = final_mask

        # 4. Sauvegarder en .png
        output_file = image_file.with_suffix(".png")
        cv2.imwrite(str(output_file), rgba_image)
        print(f"Sauvegardé avec transparence : {output_file}")
        
        try:
            image_file.unlink()
            print(f"Fichier original supprimé : {image_file}")
        except Exception as e:
            print(f"Impossible de supprimer {image_file} : {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Segmenter la plante, le cube et les codes ArUco.")
    parser.add_argument("--images_path", type=str, required=True, help="Chemin vers le dossier contenant les images .jpg")
    parser.add_argument("--no_ai", action="store_true", help="Désactiver rembg (utilise HSV pour la plante)")
    
    args = parser.parse_args()
    
    main(args.images_path, use_ai=not args.no_ai)