import board
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn
from adafruit_ads1x15 import ads1x15 
from gpiozero import Motor
from time import sleep, time

# ==========================================
# CONFIGURATION MATÉRIELLE
# ==========================================
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115(i2c)
capteur = AnalogIn(ads, ads1x15.Pin.A0)

moteur = Motor(forward=23, backward=24, enable=12)

# ==========================================
# PARAMÈTRES DE LA SERINGUE
# ==========================================
# Tension à laquelle la seringue est considérée comme "pleine"
TENSION_MAX = 2.50  

# Vitesse de remplissage (entre 0.0 et 1.0). 
# Conseil : Reste lent (0.3 ou 0.4) pour le premier test !
VITESSE = 1.0  

TEMPS_MAX = 10.0

print("--- PROGRAMME DE REMPLISSAGE DE LA SERINGUE ---")
print(f"Objectif : Arrêt automatique à {TENSION_MAX} V")
print("Appuyez sur Ctrl+C à tout moment pour un ARRÊT D'URGENCE.")
sleep(2) # Petite pause pour te laisser le temps de lire

try:
    # On lance le moteur. 
    # NOTE: Selon ton câblage, "backward" tire peut-être le piston. 
    # Si le moteur pousse au lieu de tirer, change 'backward' par 'forward'.
    print("Actionnement du moteur (Remplissage en cours...)")
    #moteur.forward(speed=VITESSE)
    #sleep(10)
    #moteur.backward(speed=VITESSE)
    #tension_actuelle >= TENSION_MAX
    heure_debut = time()
    
    print("on vide l'air")
    while time() - heure_debut <= 4:
        
        moteur.forward(speed=VITESSE)
        # Capteur
        tension_actuelle = capteur.voltage
        print(f"Niveau actuel : {tension_actuelle:.2f} V")
        sleep(0.1)
    
    print("Remplissage")
    heure_debut = time()
    while time() - heure_debut <= 10:
        
        moteur.backward(speed=VITESSE)
        # Capteur
        tension_actuelle = capteur.voltage
        print(f"Niveau actuel : {tension_actuelle:.2f} V")
        sleep(0.1)


except KeyboardInterrupt:
    # L'arrêt d'urgence sécurisé
    print("\n[ALARM] Arrêt d'urgence déclenché par l'utilisateur !")
    moteur.stop()

finally:
    # Cette ligne s'exécute TOUJOURS à la fin, quoi qu'il arrive, 
    # pour garantir que le moteur ne reste pas allumé par erreur.
    moteur.stop()