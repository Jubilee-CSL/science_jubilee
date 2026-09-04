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
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    lower_green = np.array([35, 40, 40], dtype=np.uint8)
    upper_green = np.array([95, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_green, upper_green)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return cv2.bitwise_or(mask,final_mask)


def segment_cube_mask(image: np.ndarray) -> np.ndarray:
    """Segmentation du petit cube bleu de référence"""
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    lower_blue = np.array([100, 100, 50], dtype=np.uint8)
    upper_blue = np.array([140, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask

def segment_vase_plant(image:np.ndarray):
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    # 2. MASQUE MARRON (Le Pot / Vase)
        # Le marron en HSV est un "orange sombre". Teinte entre 10 et 25.
        # Saturation > 50 ignore le blanc. Value < 200 ignore les reflets lumineux forts.
        lower_brown = np.array([10, 70, 20])
        upper_brown = np.array([25, 255, 170])
        brown_mask = cv2.inRange(hsv, lower_brown, upper_brown)
        return brown_mask

def segment_tray_mask(image: np.ndarray, margin_padding_px=20) -> tuple[np.ndarray, np.ndarray]:
    """
    Détecte les codes ArUco (0=Haut-Gauche, 1=Haut-Droite, 2=Bas-Gauche, 3=Bas-Droite).
    Utilise l'orientation interne des codes pour déduire la géométrie du plateau, 
    même si la caméra est à l'envers ou tournée.
    """
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters() 
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    # Note: cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) car votre image semble déjà être en RGB d'après votre main()
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    corners, ids, rejected = detector.detectMarkers(gray)

    H, W = image.shape[:2]
    tray_mask = np.zeros((H, W), dtype=np.uint8)
    aruco_mask = np.zeros((H, W), dtype=np.uint8)

    # 1. Vérification basique
    if ids is None or len(corners) == 0:
        print("Aucun code ArUco détecté. On conserve toute l'image.")
        tray_mask = np.ones((H, W), dtype=np.uint8) * 255
        return tray_mask, aruco_mask

    # 2. Filtrer pour ne garder QUE les codes du plateau (0, 1, 2, 3)
    ids = ids.flatten()
    valid_indices = [i for i, x in enumerate(ids) if x in [0, 1, 2, 3]]
    
    if not valid_indices:
        print("Aucun code ArUco du plateau (0-3) détecté. On conserve l'image.")
        tray_mask = np.ones((H, W), dtype=np.uint8) * 255
        return tray_mask, aruco_mask

    valid_corners = [corners[i] for i in valid_indices]
    valid_ids = [ids[i] for i in valid_indices]

    # 3. Dessiner le masque des ArUcos
    all_pts = []
    vx, vy = np.array([0.0, 0.0]), np.array([0.0, 0.0])

    for pts in valid_corners:
        points = pts[0]
        all_pts.extend(points)
        cv2.drawContours(aruco_mask, [np.int32(points)], 0, 255, thickness=cv2.FILLED)
        
        # Extraire les vecteurs d'orientation du code ArUco actuel
        # p0=Top-Left, p1=Top-Right, p2=Bottom-Right, p3=Bottom-Left du code
        p0, p1, p2, p3 = points
        
        # Vecteur X (vers la droite du plateau) et Vecteur Y (vers le bas du plateau)
        vx += (p1 - p0) + (p2 - p3)
        vy += (p3 - p0) + (p2 - p1)

    if margin_padding_px > 0:
        kernel = np.ones((margin_padding_px, margin_padding_px), np.uint8)
        aruco_mask = cv2.dilate(aruco_mask, kernel, iterations=1)

    # 4. Normaliser les vecteurs directeurs du plateau (Axes X et Y locaux)
    vx = vx / np.linalg.norm(vx)
    vy = vy / np.linalg.norm(vy)

    # 5. Calculer le centre de gravité des points détectés
    all_pts = np.array(all_pts)
    center = np.mean(all_pts, axis=0)

    # 6. Projeter les points sur les axes locaux pour trouver les limites actuelles (u, v)
    rel_pts = all_pts - center
    u_vals = np.dot(rel_pts, vx)
    v_vals = np.dot(rel_pts, vy)

    u_min, u_max = np.min(u_vals), np.max(u_vals)
    v_min, v_max = np.min(v_vals), np.max(v_vals)

    # 7. Vérifier quels côtés du plateau sont présents
    has_left = (0 in valid_ids) or (2 in valid_ids)
    has_right = (1 in valid_ids) or (3 in valid_ids)
    has_top = (0 in valid_ids) or (1 in valid_ids)
    has_bottom = (2 in valid_ids) or (3 in valid_ids)

    # 8. Étendre les limites vers l'infini pour les côtés manquants
    # Une distance de 3 fois la taille de l'image est suffisante pour aller "à l'infini"
    INF = max(W, H) * 3 

    if not has_left:   u_min -= INF
    if not has_right:  u_max += INF
    if not has_top:    v_min -= INF
    if not has_bottom: v_max += INF

    # 9. Reconstruire le polygone final du plateau dans les coordonnées de l'image
    c1 = center + u_min * vx + v_min * vy
    c2 = center + u_max * vx + v_min * vy
    c3 = center + u_max * vx + v_max * vy
    c4 = center + u_min * vx + v_max * vy

    poly = np.array([c1, c2, c3, c4], dtype=np.int32)
    
    # Remplir le masque
    cv2.fillPoly(tray_mask, [poly], 255)

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
    #On suppose que colmap a pris et traité des images .jpg
    for image_file in images_path.glob("*.jpg"):
        print(f"Processing {image_file}...")
        image = cv2.imread(str(image_file))
        image=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
        if image is None:
            print(f"Erreur de lecture de l'image {image_file}")
            continue

        # 1. Générer les 3 masques
        plant_mask = segment_plant_mask(image,birefnet, transform_image, use_ai=use_ai)
        cube_mask = segment_cube_mask(image)
        vase_mask= segment_vase_plant(image)
        tray_mask,aruco_mask = segment_tray_mask(image)

        #safe_mask=(plant_mask | vase_mask) & tray_mask
        safe_mask= plant_mask& tray_mask
        final_mask = safe_mask  | aruco_mask

        # 3. Créer l'image RGBA (avec transparence pour 3DGS)
        # Convertir RGB en RGBA (ajoute le canal Alpha)
        rgba_image = cv2.cvtColor(image, cv2.COLOR_RGB2RGBA)
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