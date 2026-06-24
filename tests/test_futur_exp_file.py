import requests
import subprocess
from science_jubilee.tools.Observer import Camera

LED_SERVER = "http://10.0.9.55:5001"

def test_image_sans_ombre():
    """
    subprocess.run([
        "ssh",
        "jubilee@10.0.9.55",
        "python3 led_server.py"
    ])
    """
    requests.get(f"{LED_SERVER}/led/255/255/255")

    
    #cam.image_sans_ombre()
    

