# Documentation du package `src/science_jubilee`

Ce document décrit l'architecture, les couches, les dépendances et les responsabilités du code contenu dans `src/science_jubilee`.
Il est conçu pour aider à comprendre le projet Jubilee et faciliter les évolutions futures.

## 1. Vue d'ensemble

Le package `science_jubilee` est structuré autour de plusieurs couches logicielles :

- `hal` : abstraction bas niveau du matériel, transport G-code, homing et mouvement.
- `decks` : représentation du plateau physique et de ses emplacements.
- `labware` : définition des contenants et puits, géométrie et positions.
- `navigation` : déplacements à partir des données géométriques du plateau.
- `tools` : modèle d'outils et contrôleurs d'instruments de la machine.
- `calibration` : génération de macros et outils de calibration.
- `utils` : utilitaires généraux, gestion des environnements et notifications.

## 2. Graphe de dépendances

### 2.1. Vue générale

- `hal.transport.base` : interface commune pour tous les transports.
- `hal.transport.http` / `hal.transport.mock` / `hal.transport.recording` : implémentations du transport.
- `hal.motion_driver` : utilise un transport pour gérer les axes et les mouvements.
- `hal.tool_changer` : utilise un transport pour gérer la sélection et le parking des outils.
- `decks.Deck` : charge les définitions de plateau et crée des `Slot`.
- `labware.Labware` : charge les définitions de labware et calcule les positions des puits.
- `navigation.DeckNavigator` : combine `Deck`, `Labware` et `MotionDriver` pour des mouvements sûrs.
- `navigation.FreeNavigator` : permet des déplacements libres et des opérations d'outil sans géométrie de plateau.
- `tools.Tool` et `tools.unique_tools` : structure des outils métiers.
- `tools.Observer` : exemple d'intégration d'acquisition d'image et de traitement - à developper.
- `calibration.tool_gfiles` : génère et télécharge des fichiers G-code de gestion d'outils.
- `utils.*` : fonctions utilitaires transverses.

### 2.2. Dépendances internes principales

- `science_jubilee.decks.Deck` dépend de `science_jubilee.labware.Labware`
- `science_jubilee.navigation.deck_navigation` dépend de `science_jubilee.decks.Deck`, `science_jubilee.hal.motion_driver`, `science_jubilee.labware.Labware`
- `science_jubilee.navigation.free_navigation` dépend de `science_jubilee.hal.motion_driver`, `science_jubilee.hal.tool_changer`, `science_jubilee.tools.Tool`
- `science_jubilee.hal.tool_changer` dépend de `science_jubilee.tools.Tool`
- `science_jubilee.calibration.tool_gfiles` dépend de `science_jubilee.hal.transport.http`
- `science_jubilee.utils.duet_upload` et `science_jubilee.utils.duet_download` dépendent de `science_jubilee.hal.transport.http`
- `science_jubilee.hal.transport.http`, `science_jubilee.hal.transport.mock`, `science_jubilee.hal.transport.recording` étendent `science_jubilee.hal.transport.base`
- `tools.unique_tools.*` dépend de `science_jubilee.tools.Tool` et souvent de `science_jubilee.labware.Labware`

## 3. Explication des couches

### 3.1. Couche d'abstraction matérielle (HAL)

Objectif : découpler l'accès matériel du reste de l'application.

- `hal.transport.base.BaseTransport` : définit l'API commune de tous les transports G-code.
- `hal.transport.http.HTTPTransport` : implémentation pour machine Duet/RRF via HTTP.
- `hal.transport.mock.MockTransport` : simulateur local pour tests et développement sans machine.
- `hal.transport.recording.RecordingTransport` : wrapper qui journalise les commandes G-code et développe les macros.
- `hal.motion_driver.MotionDriver` : gère les axes, normalise les commandes, vérifie les limites, impose des gardes de sécurité (ex: Z uniquement si le plateau est dégagé).
- `hal.tool_changer.ToolChanger` : gère la sélection et le parking des outils et synchronise l'état local avec le transport.

### 3.2. Couche plateau et labware

Objectif : représenter la machine physique, le plateau et les contenants.

- `decks.Deck.Deck` : charge un fichier de définition de plateau JSON, crée des `Slot` et charge les labwares configurés.
- `decks.Deck.Slot` / `SlotSet` : représentent une position de plateau et son contenu.
- `labware.Labware.Labware` : charge un fichier de définition de labware, génère `Well`, `Row`, `Column` et calcule les coordonnées.
- `labware.Labware.Well` : modèle de puits avec position, forme, volume, offsets, états de pointe de pipette.

### 3.3. Couche navigation

Objectif : traduire les positions de labware en mouvements physiques sûrs.

- `navigation.DeckNavigator` : propose des méthodes pour se rendre dans un puits, s'élever en Z, et déplacer l'outil en toute sécurité via le plateau et le labware.
- `navigation.FreeNavigator` : propose des commandes de mobilité directe (jog, move_to) et des actions d'outil sans dépendre du plateau.

### 3.4. Couche des outils

Objectif : encapsuler les capacités métier des instruments.

- `tools.Tool.Tool` : classe de base pour tous les outils, avec cycle de vie et état actif.
- `tools.Tool.requires_active_tool` : décorateur garantissant qu'une action est réalisée par l'outil actif.
- `tools.unique_tools` : implémentations spécialisées pour des instruments comme pipettes, seringues, caméra, pompes, spectromètre, etc.
- `tools.Observer` : implémente l'acquisition d'images (OpenCV, requêtes HTTP) et des outils d'analyse d'images sur la machine.

### 3.5. Couche calibration

Objectif : générer les macros d'outils et lever les points de configuration.

- `calibration.tool_gfiles` : rend des templates Jinja2 en fichiers G-code `tpreN.g`, `tpostN.g`, `tfreeN.g` et peut les téléverser sur la Duet.
- Les notebooks dans `calibration/` décrivent des tests et procédures de calibration.

### 3.6. Couche utilitaire

Objectif : fonctions transverses, configuration et intégration externe.

- `utils.env.load_env_file` / `ensure_env_from_file` : chargent des variables d'environnement à partir de fichiers `.env`.
- `utils.duet_upload.upload_gcode_file` : télécharge un fichier G-code sur la Duet.
- `utils.duet_download.download_gcode_file` : lit un fichier depuis une Duet.
- `utils.Handlers.SlackInputHandler` : envoie une notification Slack sur crash et attend la validation utilisateur.

## 4. Documentation des fichiers clés

### 4.1. `src/science_jubilee/__init__.py`
- Détermine la version du package à partir du metadata de distribution.
- Fournit `__version__` et implémente un fallback si le paquet n'est pas installé.

### 4.2. `src/science_jubilee/decks/Deck.py`
- `Slot` : représente un emplacement sur le plateau.
- `SlotSet` : collection de slots et fabriques d'accès.
- `Deck` : charge un plateau JSON, instancie les slots, charge des labwares et maintient la sécurité Z.
- Fonctions importantes : `load_labware`, `unload_labware`, `update_safe_z`, `get_slot`, `get_well`.

### 4.3. `src/science_jubilee/labware/Labware.py`
- `Point` : vecteur 3D simple.
- `Location` : associe un `Point` à un objet `Well` ou `Labware`.
- `Well` : contient géométrie, profondeur, volume, forme, et aide à calculer des positions sûres.
- `Well.safe_move`, `Well.random_point`, `Well.in_usable_space` : fonctions de sécurité pour mouvements à l'intérieur d'un puits.
- `WellSet`, `Row`, `Column` : regroupements de puits.
- `Labware` : charge et organise le labware JSON, crée lignes et colonnes, et expose des helpers d'ordre de puits.
- Fonctions importantes de `Labware` : `apply_offset`, `add_slot`, `with_well_order`, `_create_rows_and_columns`, `nominal_coordinates`.
- Fonctions importantes de `Well` :  `safe_move`, `in_usable_space`, `random_point`

### 4.4. `src/science_jubilee/hal/motion_driver.py`
- `MotionDriver` : interface de mouvement de l'axe à partir d'un transport.
- Normalise les axes, valide les limites, impose la sécurité Z selon le statut du plateau.
- Commandes : `move_to`, `move`, `home`, `home_all`, `home_in_place`, `get_positions`, `get_available_axes`, `get_axis_limits`.
- Cache l'état de plateau dégagé (`deck_is_clear`) pour réduire les appels transport.

### 4.5. `src/science_jubilee/hal/tool_changer.py`
- `ToolChanger` : gère l'état de chaque outil et les transitions de chariot.
- Fonctions : `pickup_tool`, `park_tool`, `tool_lock`, `tool_unlock`, `get_active_tool`, `get_tool_offsets`, `get_tools`.
- Vérifie la configuration de l'outil avant changement et synchronise l'état actif.

### 4.6. `src/science_jubilee/hal/transport/base.py`
- Base abstraite du transport G-code.
- Définit `send_gcode`, `connect`, `deck_is_clear`, `get_available_axes`, `get_axis_limits`, `get_positions`.
- Propose des méthodes communes `move_axes`, `send_gcode_json`, homing, file locking et résumé machine.

### 4.7. `src/science_jubilee/hal/transport/http.py`
- Transport HTTP pour Duet / RepRapFirmware.
- Implémente l'envoi de commandes via `/machine/code` ou query en cas d'échec.
- Fournit des méthodes spécifiques pour :
  - connecter et vérifier le firmware,
  - lire l'état de plate-forme dégagée,
  - déterminer axes, limites et positions,
  - gérer les outils Duet (T, outils, offsets),
  - téléverser et lire des fichiers sur la Duet.
- Prend en charge `crash_detection` et des `crash_handler` externes.

### 4.8. `src/science_jubilee/hal/transport/mock.py`
- Transport de simulation en mémoire.
- Simule les modes G90/G91, G28, G92, G0/G1, M114, M409 et d'autres commandes Duet.
- Utilisé pour tester la logique sans machine réelle.

### 4.9. `src/science_jubilee/hal/transport/recording.py`
- Wrapper de transport qui journalise chaque commande G-code.
- Étend les appels de macro `Tn` et `M98` en lisant les fichiers de macro locaux.
- Conserve un journal de session et un fichier de log principal pour analyse.

### 4.10. `src/science_jubilee/navigation/deck_navigation.py`
- `DeckNavigator` : gestion des déplacements structurés sur le plateau.
- Méthodes principales : `move_to_safe_z`, `move_to_well`, `move_inside_well`, `random_move_inside_well`, `get_labware_in_slot`, `get_well`, `get_wells_in_slot`.
- Séquence standard : lever en Z, se déplacer en XY, redescendre au-dessus du puits.

### 4.11. `src/science_jubilee/navigation/free_navigation.py`
- `FreeNavigator` : contrôles manuels et opération d'outils sans référence de labware.
- Offre : `move_to`, `jog`, `home_all`, `home`, `tool_lock`, `tool_unlock`, `pickup_tool`, `park_tool`, `get_position`, `list_tools`.

### 4.12. `src/science_jubilee/tools/Tool.py`
- Classe de base `Tool` pour tous les outils métier.
- Cycle de vie : `post_load`, `activate`, `deactivate`.
- Décorateur `requires_active_tool` : protège les actions dépendant d'un outil actif.
- Exceptions : `ToolStateError`, `ToolConfigurationError`.

### 4.13. `src/science_jubilee/tools/Observer.py`
- Intègre la capture d'images via OctoPi / webcam et le traitement OpenCV.
- Gère des acquisitions multilight, le stockage d'images, la segmentation ExG et la localisation.
- Exemples de fonctions : `get_image`, `save_image`, `get_multi_lighting_img`, `get_clean_image`, `get_img_contour`, `detect_isolated_duckweed`, `get_lens_coordinate`.

### 4.14. `src/science_jubilee/tools/unique_tools`
- Ensemble de classes spécialisées représentant les instruments physiques.
- Chaque fichier correspond à un instrument : `Pipette`, `Syringe`, `Camera`, `AS7341`, `Sonicator`, `Spectrometer`, `PumpDispenser`, `PeristalticPumps`, `Inoculator`, `PneumaticSampleLoader`, `Loop`, `WebCamera`, etc.
- La plupart des outils reposent sur `Tool` et parfois sur `Labware` et `DeckNavigator`.

### 4.15. `src/science_jubilee/utils/duet_upload.py` et `src/science_jubilee/utils/duet_download.py`
- Fonctions d'upload / download de fichiers vers la Duet via `HTTPTransport`.

### 4.16. `src/science_jubilee/utils/env.py`
- Gestion simple de fichiers `.env` et du chargement de variables d'environnement.

### 4.17. `src/science_jubilee/utils/Handlers.py`
- Envoi de notifications Slack en cas de crash et blocage jusqu'à validation.

## 5. Fichiers ressources importants

- `decks/deck_definition/*.json` : définitions des plateaux, emplacements, offsets.
- `labware/labware_definition/*.json` : définitions des contenants, puits, volumes, formes.
- `tools/configs/*.json` : paramètres des outils et instruments.
- `calibration/templates/*.g` : templates macro pour la génération des fichiers d'outil.

## 6. Section "A faire"

- 15/07/2026
- Clarifier le rôle et la portée de `tools.Observer.py` : ce fichier mélange capture, traitement d'image et robotique, il pourrait être déplacé dans un module de vision spécialisé.

- Introduire un registre d'outils (`ToolRegistry`)
- Introduire une charge dynamique des classes de `tools/unique_tools` lors de l'initialisation de Tool_changer.

- Mettre à jour les fichiers / Notebooks de calibration qui se base encore sur l'ancienne version - dossier old

- Mettre à jour les fichiers / Notebooks de unique_tools qui se base encore sur l'ancienne version - dossier old

- Optionnel : 
  - Ajouter des tests unitaires pour :
    - `Deck.load_labware` et `Deck.unload_labware`
    - `Labware` et `Well` (offsets, commandes sûres, ordonnancement)
    - `MotionDriver` et `ToolChanger` avec `MockTransport`
    - `DeckNavigator` et `FreeNavigator`
    - `HTTPTransport` méthodes de connectivité / lecture / upload
  - Organiser les tests, en prévision d'une augmentation du nombre de ces derniers.

## 7. Proposition

- Un module Environnement pourrait centralisé les modules de vision, éclairage et potentiels capteurs.

- Standardiser la construction d'une `Machine` ou d'un orchestrateur central pour :
  - initialiser transport + driver + tool changer + deck
  - charger les outils

- Ajouter une gestion d'expérience et des données à récupérer
 - La branche Add_on_experiment dans le dossier experiment propose une version : https://github.com/Jubilee-CSL/science_jubilee/tree/Add_on_experiment/experiment
 - Pour récupérer les données et construire une base de données d'expérience potentiel utilisation de Altar qui rassemble MongoDB et Sacred
 - L'objectif proposé est d'utiliser une interface graphique pour construire une expérience comme du Scratch
  - Cette enchainement d'action "Scratch" serait envoyé sous la forme d'un fichier json à la machine pour réaliser l'expérience. 


### 7.1. Branche expérimentale recommandée

Proposition de branche expérimentale : https://github.com/Jubilee-CSL/science_jubilee/tree/Add_on_experiment

- Cette branche peut servir à regrouper les améliorations suivantes :
  - création d'un orchestrateur `Machine`
  - refactorisation de `tools.Observer` en module de vision
  - renforcement des tests de transport et navigation
  - Méthode d'expérimentation