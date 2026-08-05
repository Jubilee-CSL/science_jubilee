import serial
from time import sleep
from gpiozero import Motor

# ==========================================
# 1. CONFIGURATION DU MATÉRIEL
# ==========================================

# Configuration de la connexion USB avec l'Arduino
PORT = '/dev/ttyACM0'  # À vérifier si ça change, mais c'était bon au test !
VITESSE_SERIE = 9600

# Initialisation du moteur (les mêmes broches qu'avant)
moteur = Motor(forward=23, backward=24, enable=12)

# ==========================================
# 2. PARAMÈTRES DE TON PROJET
# ==========================================

SEUIL_DECLENCHEMENT = 1.0  # En Volts
VITESSE_MOTEUR = 1.0       # De 0.0 à 1.0

print("Lancement du système...")
print(f"Le moteur va avancer jusqu'à ce que le capteur atteigne {SEUIL_DECLENCHEMENT}V.")

try:
    # Connexion à l'Arduino
    arduino = serial.Serial(PORT, VITESSE_SERIE, timeout=1)
    arduino.reset_input_buffer()
    print("✅ Arduino connecté avec succès !")
    
    # Démarrage du moteur
    print("Moteur : EN AVANT")
    moteur.forward(speed=VITESSE_MOTEUR)

    # Boucle principale
    while True:
        if arduino.in_waiting > 0:
            # Lecture de la donnée de l'Arduino
            ligne = arduino.readline().decode('utf-8').rstrip()
            
            try:
                # L'Arduino envoie un nombre entre 0 et 1023
                valeur_brute = int(ligne)
                
                # Conversion du nombre brut en Volts (0 à 5V)
                tension_actuelle = (valeur_brute * 5.0) / 1023.0
                print(f"Valeur lue : {tension_actuelle:.2f} V  (brut: {valeur_brute})")
                
                # --- LA LOGIQUE ---
                if tension_actuelle >= SEUIL_DECLENCHEMENT:
                    print("\n>>> Capteur activé ! Arrêt du moteur. <<<")
                    moteur.stop()
                    break # On sort de la boucle, le programme se termine
                    
            except ValueError:
                # Si jamais l'Arduino envoie un bout de texte illisible, on l'ignore
                pass

except serial.SerialException:
    print(f"\n❌ ERREUR : Impossible de se connecter à l'Arduino sur {PORT}.")
    print("Assurez-vous qu'il est bien branché.")
    moteur.stop()

except KeyboardInterrupt:
    print("\n🛑 Arrêt manuel par l'utilisateur.")

finally:
    # Cette sécurité s'exécute toujours à la fin, quoi qu'il arrive,
    # pour être sûr que le moteur ne continue pas de tourner tout seul.
    moteur.stop()
    if 'arduino' in locals() and arduino.is_open:
        arduino.close()
    print("Système arrêté proprement.")