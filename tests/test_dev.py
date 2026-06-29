import requests
from science_jubilee.tools.Observer import Camera
from pathlib import Path

LED_SERVER = "http://10.0.9.55:5001"
"""
Pour mettre en valeur les lentilles on peux les éclairer en vert, longueur d'onde 500-650, rgb : 0,255,0
Pour permttre la croissance des lentilles éclairage, longueur d'onde 400-500, rgb, 10,0,255 ou 255,0,255

"""

"""def test_image_sans_ombre():
    
    requests.get(f"{LED_SERVER}/led/255/255/255")

    
    #cam.image_sans_ombre()
"""

def test_imag():
    cam = Camera()
    img = cam.get_latest_image(folder = Path("dataset_brut"))
    
    contour = cam.get_img_contour(img = img)

    print(contour)