import argparse
import os
import struct

import yaml

# Dictionnaire de correspondance des modèles de caméra COLMAP
# ID de modèle -> Nom du modèle, nombre de paramètres, et indices des paramètres (fx, fy, cx, cy)
CAMERA_MODELS = {
    0: {
        "name": "SIMPLE_PINHOLE",
        "num_params": 3,
        "mapping": lambda p: (p[0], p[0], p[1], p[2]),
    },
    1: {
        "name": "PINHOLE",
        "num_params": 4,
        "mapping": lambda p: (p[0], p[1], p[2], p[3]),
    },
    2: {
        "name": "SIMPLE_RADIAL",
        "num_params": 4,
        "mapping": lambda p: (p[0], p[0], p[1], p[2]),
    },
    3: {
        "name": "RADIAL",
        "num_params": 5,
        "mapping": lambda p: (p[0], p[0], p[1], p[2]),
    },
    4: {
        "name": "OPENCV",
        "num_params": 8,
        "mapping": lambda p: (p[0], p[1], p[2], p[3]),
    },
}


def parse_cameras_txt(file_path):
    """
    Lit le fichier texte cameras.txt de COLMAP.
    """
    print(f"[+] Lecture du fichier texte COLMAP : {file_path}")
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Format d'une ligne : CAMERA_ID MODEL WIDTH HEIGHT PARAMS[]
            elems = line.split()
            int(elems[0])
            model_name = elems[1]
            width = int(elems[2])
            height = int(elems[3])
            params = [float(x) for x in elems[4:]]

            # Recherche du modèle de caméra correspondant
            matched_model = None
            for model_id, m_info in CAMERA_MODELS.items():
                if m_info["name"] == model_name:
                    matched_model = m_info
                    break

            if matched_model:
                fx, fy, cx, cy = matched_model["mapping"](params)
                return fx, fy, cx, cy, width, height

    return None


def parse_cameras_bin(file_path):
    """
    Lit le fichier binaire cameras.bin de COLMAP.
    """
    print(f"[+] Lecture du fichier binaire COLMAP : {file_path}")
    with open(file_path, "rb") as fid:
        # COLMAP stocke d'abord le nombre de caméras sous forme d'un uint64 (8 octets)
        num_cameras = struct.unpack("<Q", fid.read(8))[0]

        for _ in range(num_cameras):
            # ID de la caméra (uint32, 4 octets)
            struct.unpack("<I", fid.read(4))[0]
            # ID du modèle (int32, 4 octets)
            model_id = struct.unpack("<i", fid.read(4))[0]
            # Largeur et Hauteur (uint64, 8 octets chacun)
            width = struct.unpack("<Q", fid.read(8))[0]
            height = struct.unpack("<Q", fid.read(8))[0]

            if model_id in CAMERA_MODELS:
                model_info = CAMERA_MODELS[model_id]
                num_params = model_info["num_params"]
                # Chaque paramètre est stocké en float double précision (double, 8 octets)
                params = struct.unpack(f"<{num_params}d", fid.read(num_params * 8))

                fx, fy, cx, cy = model_info["mapping"](params)
                return fx, fy, cx, cy, width, height

    return None


def update_config_yaml(fx, fy, cx, cy, config_path="config.yaml"):
    """
    Met à jour ou crée le fichier config.yaml avec les nouveaux paramètres.
    """
    config_data = {}
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f) or {}

    if "camera" not in config_data:
        config_data["camera"] = {}

    config_data["camera"]["fx"] = round(float(fx), 2)
    config_data["camera"]["fy"] = round(float(fy), 2)
    config_data["camera"]["cx"] = round(float(cx), 2)
    config_data["camera"]["cy"] = round(float(cy), 2)

    with open(config_path, "w") as f:
        yaml.safe_dump(config_data, f, default_flow_style=False)
    print(f"[+] Fichier {config_path} mis à jour avec succès !")


def main():
    parser = argparse.ArgumentParser(
        description="Extracteur de paramètres de caméra depuis les exports COLMAP."
    )
    parser.add_argument(
        "--path", required=True, help="Chemin vers le fichier cameras.txt/.bin"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Chemin vers le fichier de configuration de destination",
    )
    args = parser.parse_args()

    # Résolution intelligente du chemin
    file_path = args.path
    if os.path.isdir(file_path):
        txt_attempt = os.path.join(file_path, "cameras.txt")
        bin_attempt = os.path.join(file_path, "cameras.bin")
        if os.path.exists(txt_attempt):
            file_path = txt_attempt
        elif os.path.exists(bin_attempt):
            file_path = bin_attempt
        else:
            print(
                "[-] Erreur : Aucun fichier 'cameras.txt' ou 'cameras.bin' trouvé dans ce dossier."
            )
            return

    # Parsing selon le type de fichier
    result = None
    if file_path.endswith(".txt"):
        result = parse_cameras_txt(file_path)
    elif file_path.endswith(".bin"):
        result = parse_cameras_bin(file_path)
    else:
        print(
            "[-] Erreur : Format de fichier non supporté. Fournissez un fichier .txt ou .bin."
        )
        return

    if result:
        fx, fy, cx, cy, w, h = result
        print("\n================ PARAMÈTRES DETECTÉS ================")
        print(f"  Focale X (fx) : {fx:.2f} px")
        print(f"  Focale Y (fy) : {fy:.2f} px")
        print(f"  Centre X (cx) : {cx:.2f} px")
        print(f"  Centre Y (cy) : {cy:.2f} px")
        print(f"  Résolution    : {w}x{h} px")
        print("=====================================================")

        update_config_yaml(fx, fy, cx, cy, args.config)
    else:
        print("[-] Erreur lors de l'extraction des paramètres.")


if __name__ == "__main__":
    main()
