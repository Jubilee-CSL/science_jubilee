from flask import Flask, request, jsonify
from gpiozero import Motor
import serial
import time

app = Flask(__name__)

# ==========================================
# 1. CONFIGURATION DU MATÉRIEL
# ==========================================
print("Initialisation du matériel...")

try:
    moteur = Motor(forward=23, backward=24, enable=12)
    print("✅ Moteur prêt.")
except Exception as e:
    print(f"❌ Erreur Moteur : {e}")
    moteur = None

try:
    arduino = serial.Serial('/dev/ttyACM1', 9600, timeout=1)
    # --- LA CORRECTION EST ICI ---
    print("⏳ Attente de 2 secondes pour le réveil de l'Arduino...")
    time.sleep(2.0) 
    arduino.reset_input_buffer()
    print("✅ Arduino connecté et réveillé sur /dev/ttyACM1.")
except Exception as e:
    print(f"❌ Erreur Arduino : {e}")
    arduino = None

# ==========================================
# 2. LES ROUTES
# ==========================================

@app.route('/moteur', methods=['POST'])
def controler_moteur():
    if moteur is None:
        return jsonify({"erreur": "Moteur non initialisé"}), 500
        
    data = request.json
    action = data.get('action')
    vitesse = data.get('speed', 1.0)
    
    if action == 'forward':
        moteur.forward(speed=vitesse)
    elif action == 'backward':
        moteur.backward(speed=vitesse)
    elif action == 'stop':
        moteur.stop()
        
    return jsonify({"status": "ok", "action": action, "speed": vitesse})


@app.route('/capteur', methods=['GET'])
def lire_capteur():
    if arduino is None:
        return jsonify({"erreur": "Arduino non connecté", "tension": 0.0}), 500
        
    try:
        arduino.reset_input_buffer()
        
        # --- LA CORRECTION EST ICI ---
        # On laisse à l'Arduino le temps (50ms) d'envoyer sa nouvelle valeur
        time.sleep(0.05)
        
        ligne = arduino.readline().decode('utf-8', errors='ignore').rstrip()
        
        if ligne:
            valeur_brute = int(ligne)
            tension = (valeur_brute * 5.0) / 1023.0 
            return jsonify({"tension": tension, "brute": valeur_brute})
        else:
            return jsonify({"erreur": "L'Arduino n'a rien envoyé à temps", "tension": 0.0}), 500
            
    except ValueError:
        return jsonify({"erreur": "Donnée illisible", "tension": 0.0}), 500
    except Exception as e:
        return jsonify({"erreur": str(e), "tension": 0.0}), 500


if __name__ == '__main__':
    print("🚀 Serveur matériel démarré ! En attente des ordres de Jubilee...")
    app.run(host='0.0.0.0', port=5001) # (Remettez 5001 ici si vous aviez changé !)