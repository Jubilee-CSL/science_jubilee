# Guide des tests pour Science Jubilee

Ce document décrit la structure, les catégories et les approches de test du projet Science Jubilee. 
Il aide à comprendre les tests existants et à encourager le développement de nouveaux tests de sécurité et d'expériences.

---

## 1. Vue d'ensemble des tests

Les tests sont organisés en trois catégories :

1. **Tests de validation** : vérifient que les couches logicielles fonctionnent correctement avec mock et hardware.
2. **Tests d'expérimentation** : testent des scénarios métier complets (ex: capture d'images, localisation).
3. **Tests de sécurité** : vérifient les gardes-fou et les comportements d'erreur (à développer avec le jumeau numérique).

### Fichier de configuration central

- **`tests/conftest.py`** : définit les fixtures pytest et la logique de sélection du profil.
  - Charge les env files (`.env.mock`, `.env.hardware`)
  - Fournit les fixtures : `transport`, `motion`, `tool_changer`, `navigator`
  - Gère les options CLI : `--jubilee-env` et `--jubilee-address`

---

## 2. Structure des tests

### 2.1. Marqueurs pytest

Tous les tests sont marqués pour faciliter la sélection et l'exécution ciblée :

- **`@pytest.mark.primary`** : tests critiques de connectivité (ex: import, HTTP)
  - Pas de modification d'état machine
  - À exécuter en premier pour vérifier la configuration
  
- **`@pytest.mark.secondary`** : tests d'informations (ex: axes disponibles)
  - Lisent l'état mais n'effectuent pas d'action invasive
  - À exécuter après validation de la connectivité
  
- **`@pytest.mark.invasive`** : tests de mouvement et de changement d'outil
  - Modifient l'état de la machine (mouvements, sélection d'outil)
  - À exécuter seulement si la machine est prête et le plateau dégagé
  - Nécessitent une intervention utilisateur en mode hardware

### 2.2. Profils d'exécution

Tests exécutables en deux modes :

#### Mode Mock (par défaut)
```powershell
pytest -q --jubilee-env mock
```
- Utilise `MockTransport` : simulateur en mémoire déterministe
- Pas de matériel requis
- Rapide, reproductible, idéal pour développement

#### Mode Hardware
```powershell
pytest -q --jubilee-env hardware --jubilee-address 192.168.1.2
```
- Utilise `HTTPTransport` : communication réelle avec la Duet
- Matériel requis
- Plus lent, peut nécessiter intervention utilisateur (confirmations)

### 2.3. Enregistrement G-code

Tous les tests bénéficient d'un wrapper `RecordingTransport` automatique :
- Journalise chaque commande G-code envoyée
- Développe les macros `Tn` et `M98` pour inspection
- Génère deux fichiers :
  - `gcode_logs/latest.gcode` : dernier log
  - `gcode_logs/{test_name}.gcode` : log du test spécifique

Utile pour :
- Déboguer les mouvements
- Documenter les séquences
- Rejouer manuellement sur la machine réelle

---

## 3. Catalogue des tests existants

### 3.1. Tests de validation fondamentaux

| Fichier | Marqueur | Description |
|---------|----------|-------------|
| `test_import.py` | `primary` | Import du package `science_jubilee` |
| `test_requests_http.py` | `primary` | Connectivité HTTP (M115) vers Duet |
| `test_connect.py` | `primary` | Vérification du ping matériel |
| `test_available_axes.py` | `secondary` | Axes disponibles sur la machine |
| `test_positions.py` | `secondary` | Lecture des positions (M114) |
| `test_machine_summary.py` | `secondary` | Résumé complet de l'état machine |

**Exécution rapide :**
```powershell
pytest -q -m "primary or secondary"
```

### 3.2. Tests de transport et navigation

| Fichier | Marqueur | Description |
|---------|----------|-------------|
| `test_homing.py` | `invasive` | Homing de tous les axes (XYU puis Z) |
| `test_navigation_deck.py` | `invasive` | Déplacement vers puits individuels et tous les puits |
| `test_macro_expansion.py` | (générique) | Expansion des macros T{n}, M98 dans RecordingTransport |
| `test_recording_transport.py` | (générique) | Vérification des fichiers de log G-code |

**Exécution sécurisée :**
```powershell
# En mock d'abord
pytest -q --jubilee-env mock -m invasive

# Puis en hardware 
pytest -q --jubilee-env hardware -m invasive --maxfail=1
```

### 3.3. Tests d'outils et expériences

| Fichier | Marqueur | Type | Description |
|---------|----------|------|-------------|
| `test_tools_api.py` | (générique) | Validation | API de base des outils |
| `test_tools_inoculator.py` | (générique) | Validation | Inoculator (tool index 0) |
| `test_tools_blender_connection.py` | (générique) | Validation | Connexion blender |
| `test_snake.py` | (commenté) | Expérience | Mouvement serpentin pour exploration du plateau |
| `test_observer.py` | (commenté) | Expérience | Acquisition et traitement d'image (hardware only) |

**Note :** `test_snake.py` et `test_observer.py` contiennent du code commenté correspondant à des expériences temporaires.

### 3.4. Tests d'upload/download

| Fichier | Marqueur | Description |
|---------|----------|-------------|
| `test_upload_http.py` | `primary` | Upload de fichier G-code via DWC2 ou rr_upload |

---

## 4. Fixtures pytest partagées

Toutes les fixtures sont définies dans `conftest.py` et disponibles pour tous les tests :

### `jubilee_env` (fixture)
Retourne le profil sélectionné : `"mock"` ou `"hardware"`

```python
def test_example(jubilee_env):
    if jubilee_env == "mock":
        # comportement spécifique mock
    else:
        # comportement hardware
```

### `transport` (fixture)
Fournit un transport enrobé dans `RecordingTransport` :
- Mock : `RecordingTransport(MockTransport())`
- Hardware : `RecordingTransport(HTTPTransport(address))`

```python
def test_send_command(transport):
    response = transport.send_gcode("M114")
    assert "X:" in response
```

### `motion` (fixture)
Fournit un `MotionDriver` pré-configuré :

```python
def test_move(motion):
    motion.move_to({"X": 100, "Y": 100})
    pos = motion.get_positions()
    assert pos["X"] == pytest.approx(100.0, rel=1e-3)
```

### `tool_changer` (fixture)
Fournit un `ToolChanger` pré-configuré :

```python
def test_pickup_tool(tool_changer):
    success = tool_changer.pickup_tool(0)
    assert success
    assert tool_changer.get_active_tool_index() == 0
```

### `navigator` (fixture)
Fournit un `DeckNavigator` pré-configuré avec plateau et labware :

```python
def test_navigate_to_well(navigator):
    well = navigator.get_well("0", "A1")
    navigator.move_to_well(well)
    pos = navigator.driver.get_positions()
    # vérifier les positions
```

---

## 5. Exemples d'exécution lire le ReadMe
 
### Exécution complète en mock (recommandée pour développement)
```powershell
pytest -q --jubilee-env mock -v
```

### Tests critiques uniquement
```powershell
pytest -q -m primary --maxfail=1
```

### Tests de navigation (invasive) en mock
```powershell
pytest -q --jubilee-env mock -m invasive -k "navigation"
```

### Tests sur hardware avec arrêt sur première erreur
```powershell
pytest -q --jubilee-env hardware --jubilee-address 192.168.1.2 -m primary --maxfail=1
```

### Générer des logs G-code détaillés
```powershell
pytest -q --jubilee-env mock -m invasive -v
# Consultez gcode_logs/latest.gcode et gcode_logs/{test_name}.gcode
```

---

## 6. Tests existants : expériences temporaires

### 6.1. test_snake.py

**Objectif :** explorer le plateau avec un mouvement serpentin, utile pour acquisition de dataset.

**Paramètres d'exemple :**
- Point de départ : (60, 60, 320)
- Point d'arrivée visé : (310, 310, 320)
- Pas de jogging : 20 mm

**À activer pour :** reconnaissance visuelle, expériences de balayage

### 6.2. test_observer.py

**Objectif :** tester la capture, le traitement d'image et la localisation (hardware uniquement).

**Prérequis :**
- Caméra OctoPi connectée
- Bien visible via `/rr_webcam?action=snapshot`
- LED server optionnel pour éclairage multi-angle

**À activer pour :** tests d'acquisition d'image, localisation, interaction outil-vision

---

## 7. Section "À faire" : développement de tests de sécurité

### 7.1. Tests de sécurité recommandés

#### a) Gardes-fou du mouvement
#### b) État des outils
#### c) Robustesse du transport
#### d) Géométrie et offsets

### 7.2. Marqueur de sécurité

Ajouter à `conftest.py` :

```python
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "safety: test de sécurité (gardes-fou, limites, collision)"
    )
```

Exécution :
```powershell
pytest -q -m safety  # tous les tests de sécurité
pytest -q -m "not safety"  # tout sauf sécurité
```

### 7.3. Checklist de sécurité pour nouveaux tests

- [ ] Teste une garde-fou (limite d'axe, deck clearance, état d'outil)
- [ ] Marque avec `@pytest.mark.safety`
- [ ] Fonctionne en mock et hardware
- [ ] Docstring qui explique le risque et le scénario de test
- [ ] Inclure un cas négatif (doit échouer) et positif (doit réussir)

---

## 8. Structure proposée pour "gestion d'expérience" 
Proposition dans la branche Add_on_experiement : https://github.com/Jubilee-CSL/science_jubilee/tree/Add_on_experiment/experiment

## 9. Directives pour développer nouveaux tests

### 9.1. Checklist

- [ ] Créer le fichier `tests/test_<component>.py`
- [ ] Importer les fixtures requises (transport, motion, navigator, etc.)
- [ ] Ajouter un marqueur `@pytest.mark.primary/secondary/invasive - si developpé safety`
- [ ] Écrire docstring expliquant le scénario
- [ ] Fonctionner en mock ET hardware
- [ ] Fournir assertions claires avec messages
- [ ] Tester cas négatif ET positif si pertinent
- [ ] Consulter les logs G-code générés pour validation

### 9.2. Template minimal

```python
"""Test de [composant]."""

import pytest
import logging

logger = logging.getLogger(__name__)

@pytest.mark.secondary  # Choisir primary/secondary/invasive
def test_my_feature(navigator, tool_changer ): # choisir la fixture adaptée en paramètres
    """Vérifier que [comportement] fonctionne comme attendu.
    
    Scénario :
    1. [étape 1]
    2. [étape 2]
    3. [vérification]
    """
    # Arrange
    # Setup
    
    # Act
    # Effectuer l'action
    
    # Assert
    # Vérifier les résultats
    assert True, "Message d'erreur clair"
```

### 9.3. Bonnes pratiques

- **Mock first** : tester en mock avant hardware
- **Logging** : utiliser `logger.info()` pour tracer
- **Assertions explicites** : inclure messages
- **Cleanup** : nettoyer l'état (ex: parker les outils)
- **Répétabilité** : tests doivent être deterministe

---

## 10. Exécution rapide

### Développement local (mock)
```powershell
pytest -q --jubilee-env mock -m "primary or secondary"
```

### Avant hardware
```powershell
pytest -q -m primary --maxfail=1
pytest -q --jubilee-env mock -m invasive
```

### Validation hardware complète
```powershell
# Adapter la commande avec l'adresse adapté
pytest -q --jubilee-env hardware --jubilee-address 10.0.3.48 --maxfail=1 
```
---

## 11. Ressources

- **pytest documentation** : https://docs.pytest.org/
- **conftest.py** : configuration centralisée des fixtures et options
- **G-code logs** : consultés dans `gcode_logs/` pour tracer les mouvements
- **Marqueurs** : extendus via `pytest_configure()` dans conftest.py
