# Création d'un nouvel outil (dossier tools)

Ce document décrit la procédure recommandée pour ajouter un nouvel outil physique à la machine Jubilee et l'intégrer dans le code (dossier tools/unique_tools). Il rassemble les étapes matérielles (parking slot, impression), les étapes de configuration Duet (fichiers G), la détermination des offsets.

---

## Avant-propos

Remarque de bonne pratique : utiliser au maximum le matériel et les emplacements déjà présents sur la machine (ports, slots, supports) pour minimiser les modifications physiques. Documenter toute impression ou modification mécanique (STL, paramètres d'impression, orientation).

## 1. Choisir (ou créer) un parking slot pour l'outil

1. Inspecter les emplacements assignés aux outils pour identifier un emplacement libre et adapté (espace, fixation, alimentation électrique si nécessaire).
2. Si un parking slot adapté existe et n'est pas occupé : passer à l'étape 3.
3. Si aucun slot n'existe :
   - Conception / impression : imprimer le support (fichier STL) nécessaire pour fixer l'outil.
   - Installer mécaniquement le support sur la machine à l'emplacement physique choisi.
   - Exécuter le notebook `SetToolParkingPositions` (ou son équivalent) pour :
     - enregistrer la position dans un fichier de macro (G-code) pour la Duet,
     - générer les trois fichiers d'outil liés au parking : `tfreeN.g`, `tpostN.g`, `tpreN.g` (où N est le numéro du parking/tool index choisi sur la Duet).

> Remarque : les noms exacts des fichiers macro d'outil sont habituellement `tfreeN.g`, `tpreN.g`, `tpostN.g` (templates générés par `calibration/tool_gfiles`). S'assurer que N ne rentre pas en conflit avec un outil déjà défini sur la Duet.

### 1.1. Télécharger / installer les macros sur la Duet

- Utiliser l'utilitaire `utils.duet_upload.upload_gcode_file` ou la console Web de la Duet pour téléverser les fichiers :
  - `tfreeN.g` (mouvements libres pour l'outil)
  - `tpreN.g` (pré-actions lors du `Tn`)
  - `tpostN.g` (post-actions après sélection)

- Vérifier sur la Duet (interface Web) que les fichiers apparaissent dans la racine et qu'ils correspondent au numéro N choisi.

## 2. Déterminer l'offset de l'outil (Tool alignment XY)

1. Pour la précision XY/Z, utiliser le notebook `Tool alignment XY` (ou une méthode équivalente) :
   - Mettre l'outil en position de mesure (ex: pointer vers un repère bien connu sur le plateau).
   - Effectuer la procédure d'alignement pour obtenir le décalage (offset) par rapport au centre de l'outil de référence.
2. Résultat attendu : un vecteur d'offset (ex: X = 12.3, Y = 4.8, Z = - 12) exprimé dans les unités de la machine (mm).
3. Enregistrer ce décalage :
   - Ajouter l'offset au fichier `toffset.g` contenant l'offset associé au outils.
   - Exemple :
     - "G10 P0 X0.0 Y16.0 Z-67.0" ; déclaration pour l'outil placé dans l'emplacement 0

> Remarque : la manière exacte d'écrire l'offset dépend de votre politique Duet (G10, G92, ou macros personnalisées). L'idée principale : le fichier d'offset stocke la compensation à appliquer lors de l'activation de l'outil.

## 3. Créer la définition de l'outil dans `config.g` de la Duet

1. Éditer `config.g` (sur la Duet, généralement via l'interface Web ou upload) et ajouter en bas :
   - la déclaration du nouvel outil (indice N) et son nom. Idéalement, le `name` doit correspondre au nom du fichier Python du tool pour garder la cohérence (ex: `MyPipette` -> `mypipette.py`).
   - la déclaration pointera vers les macros `tpreN.g`, `tpostN.g`, `tfreeN.g` et `toffset.g`.

2. Exemple :
   - Définir nom et index selon la configuration existante (veillez à ne pas réutiliser un index déjà affecté).
   - `M563 P1 S"Pipette"`

3. Redémarrer/recharger la configuration Duet ou exécuter `M999` / `RESTART` si nécessaire pour prendre en compte les nouvelles macros.

## 4. Intégrer l'outil côté Python (dossier tools/unique_tools)

1. Créer un nouveau fichier Python `src/science_jubilee/tools/unique_tools/<tool_name>.py` (nom sans espace, de préférence en snake_case) contenant :
   - une classe qui hérite de `tools.Tool` (ex: `class MyTool(Tool):`).
   - méthodes clés : `post_load(self)`, et les commandes métier (`pick`, `dispense`, `capture`, etc.).
   - définir les métadonnées d'outil : `tool_name`, `preferred_parking_slot`, `tool_index` (N), `default_offsets` (fallback si Duet non disponible).
   - pour réaliser des test mock de l'outil choisie, modifier le mock

2. Ajouter (si existe) une entrée de configuration JSON dans `tools/configs/<tool_name>.json` avec :
   - `parking_slot`: identifiant du slot choisi
   - `duet_tool_index`: N
   - `default_offset`: {x, y, z}
   - `notes`: chemin du STL et instructions d'installation

## 5. Vérifications et tests

1. En mode Mock (local) : implémenter un test unitaire minimal dans `tests/` qui vérifie :
   - l'instanciation de la classe outil,
   - l'appel de `post_load`, `activate` et `deactivate`,

2. En mode Hardware :
   - Tester la commande `park_tool` et `pickup_tool` via `FreeNavigator` ou `ToolChanger`.
   - Vérifier le comportement des macros : `Tn` déclenche bien `tpreN.g` et `tpostN.g` et que `tfreeN.g` correspond aux mouvements libres.
   - Valider l'offset en effectuant un mouvement connu et en inspectant la position réelle.

3. G-code logging : utiliser `RecordingTransport` pour capturer la séquence G-code et la stocker sous `gcode_logs/{test_name}.gcode` pour revue.

## 6. Checklist rapide (à suivre pour chaque nouvel outil)

- [ ] Choisir ou imprimer un parking slot et l'installer mécaniquement
- [ ] Générer/upload `tfreeN.g`, `tpreN.g`, `tpostN.g` via `SetToolParkingPositions` notebook
- [ ] Déterminer l'offset XY(Z) via `Tool alignment XY` notebook
- [ ] Ajouter l'offset dans `toffset.g` et uploader sur la Duet
- [ ] Modifier `config.g` (en bas) pour créer la définition `Tool N` et lui associer un nom (idem que le fichier python si possible)
- [ ] Créer la classe Python dans `tools/unique_tools/` et un fichier de config dans `tools/configs/`
- [ ] Ajouter tests Mock et Hardware et vérifier les G-code logs
- [ ] Documenter la mécanique (STL, orientation) et la procédure

## 7. Bonnes pratiques et recommandations

- Réutiliser les slots existants et le matériel présent pour réduire la maintenance.
- Versionner les macros G-code et les STLs dans le dépôt et joindre des photos de l'installation.
- Nommer l'outil Python et le nom Duet de façon cohérente (par ex. `camera_front` -> `camera_front.py`).
- Centraliser la configuration de l'outil dans `tools/configs` pour faciliter l'automatisation et les tests.
- Ajouter des tests `@pytest.mark.invasive` pour les tests hardware et `@pytest.mark.primary/secondary` pour les validations non invasives.
