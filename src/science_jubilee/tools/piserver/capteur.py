import serial
import time

# --- CONFIGURATION ---
PORT = '/dev/ttyACM0'  # Le port de votre Arduino
BAUD_RATE = 9600       # La vitesse (doit correspondre au Serial.begin de l'Arduino)

print(f"Tentative de connexion à l'Arduino sur {PORT}...")

try:
    # Ouverture du port série
    arduino = serial.Serial(PORT, BAUD_RATE, timeout=1)
    
    # On vide la "salle d'attente" des données pour avoir du neuf
    arduino.reset_input_buffer() 
    
    print("✅ Connexion réussie !")
    print("⏳ En écoute des données du capteur... (Appuyez sur Ctrl+C pour arrêter)\n")
    print("-" * 40)

    # Boucle infinie pour lire les données en continu
    while True:
        if arduino.in_waiting > 0:
            # On lit la donnée, on la traduit en texte et on nettoie les espaces
            donnee_brute = arduino.readline().decode('utf-8').rstrip()
            
            # On récupère l'heure actuelle pour faire un beau journal (log)
            heure_actuelle = time.strftime('%H:%M:%S')
            
            # Affichage à l'écran
            print(f"[{heure_actuelle}] Valeur reçue : {donnee_brute}")

except serial.SerialException as e:
    print("\n❌ ERREUR DE CONNEXION")
    print(f"Impossible d'ouvrir le port {PORT}.")
    print("-> L'Arduino est-il bien branché en USB ?")
    print("-> Avez-vous les droits nécessaires (groupe dialout) ?")
    
except KeyboardInterrupt:
    print("\n\n🛑 Arrêt demandé par l'utilisateur.")
    
finally:
    # Cette partie s'exécute toujours à la fin, pour nettoyer
    if 'arduino' in locals() and arduino.is_open:
        arduino.close()
        print("🔌 Port série fermé proprement.")