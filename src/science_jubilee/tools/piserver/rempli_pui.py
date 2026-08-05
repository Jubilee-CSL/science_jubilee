import board
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn
from adafruit_ads1x15 import ads1x15 
from gpiozero import Motor
from time import sleep, time

# ==========================================
# 1. CONFIGURATION DU MATÉRIEL
# ==========================================

# Initialisation de l'I2C et du module
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115(i2c)

# --- NOUVELLE SYNTAXE POUR LA BROCHE ---
capteur = AnalogIn(ads, ads1x15.Pin.A0)

# Initialisation du moteur
moteur = Motor(forward=23, backward=24, enable=12)

# ==========================================
# 2. PARAMÈTRES DE TON PROJET
# ==========================================

SEUIL_DECLENCHEMENT = 1.0
VITESSE = 1.0

print("Lancement du système...")
print(f"Le moteur va avancer jusqu'à ce que le capteur atteigne {SEUIL_DECLENCHEMENT}V.")

try:
    print("Moteur : EN AVANT")
    moteur.forward(speed=VITESSE)

    while True:
        # Lecture de la tension
        tension_actuelle = capteur.voltage
        print(f"Valeur lue : {tension_actuelle:.2f} V")
        
        # --- LA LOGIQUE ---
        if tension_actuelle >= SEUIL_DECLENCHEMENT:
            print(">>> Capteur activé ! Arrêt du moteur. <<<")
            moteur.stop()
            break 
            
        sleep(0.1)

except KeyboardInterrupt:
    print("\nArrêt manuel par l'utilisateur.")
    moteur.stop()