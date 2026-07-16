# Framework d'expériences - Dossier `experiment`

## Vue d'ensemble

Le dossier `experiment` propose une **architecture complète pour construire, configurer et exécuter des expériences répétables** sur la machine Jubilee. L'objectif final est de permettre la création d'expériences via une **interface graphique de type Scratch** (drag-and-drop de blocs d'actions).

Ce framework sépare trois concepts clés :
1. **Description** : définition déclarative d'une expérience (JSON)
2. **Compilation** : conversion en plan d'exécution (mock et complet)
3. **Exécution** : lancement sur la machine réelle ou en simulation

---

## 1. Concepts fondamentaux

### 1.1. Action

Une **Action** est une **description immutable** d'une opération élémentaire. Elle ne contient **aucune logique d'exécution**—elle enregistre juste ce qui doit être fait.

**Caractéristiques :**
- Immutable (frozen dataclass)
- Contient les paramètres nécessaires à l'exécution
- Peut être simulable (`simulate=True`) ou non (`simulate=False`)
- Possède une méthode `compile()` qui contient la logique réelle
- Enregistrée dans le Registry via `@Registry.register("identifier")`

**Types d'Actions :**

| Type | Simulable ? | Exemple | Description |
|------|-----------|---------|-------------|
| **MotionAction** | ✓ Oui | MoveToWell, MoveToSafeZ | Déplacements du chariot |
| **ToolAction** | ✓ Oui | PickupTool, ParkTool | Sélection/changement d'outils |
| **AcquisitionAction** | ✗ Non | CaptureImage, AcquireSpectrum | Mesures (images, spectro, etc.) |
| **FlowAction** | ✗ Non | Pause, Wait, UserConfirmation | Contrôle de flux |
| **EnvAction** | ✗ Non | PixelOn, AllPixelOff | Actions environnementales (LED, etc.) |

**Exemple (action.py) :**
```python
@Registry.register("move_to_well")
@dataclass(frozen=True)
class MoveToWell(MotionAction):
    well_name: str
    slot_id: str
    speed_xy: float = None
    speed_z: float = None
    margin: float = None
    random: bool = False

    def compile(self):
        well = self.nav.get_well(slot_id=self.slot_id, well_id=self.well_name)
        self.nav.move_to_target(well=well, speed_xy=self.speed_xy, speed_z=self.speed_z, ...)
```

### 1.2. Task

Une **Task** est une **opération métier** composée de plusieurs Actions. Elle représente une étape logique complète (ex: "Réaliser un déplacement a partir du traitement d'une image acquise pendant ou avant le mouvement"). Une Task rassemble des Actions non simulable et simulable sous un nom général et des paramètres simplifiés.

**Caractéristiques :**
- Méthode `compile()` ajoute les Actions au plan d'exécution
- Déclare les ressources requises (`required_tools`, `required_observers`, `required_modules`)
- Enregistrée dans le Registry via `@Registry.register("identifier")`

**Exemple (task.py) :**
Transfert de lentille à l'aide d'une détection par ordinateur
Déplacement qui permettront l'acquisition d'image - simulable
Acquisition, traitement de l'image et obtention des coordonnées de la lentille - non simulable
Récupération et transfert de la lentille du réservoir vers un puit - simulable
Déplacement qui permettront une acquisition d'image - simulable
Confirmation du dépot de la lentille par acquisition et traitement d'image - non simulable

Paramètres à definir par l'utilisateur : Réservoir, puits de destination
Paramètres par défaut - défini par le développeur : vitesse de récupération et de déplacement, marge de sécurité du déplacement, spécification de la méthode de récupération, paramètres d'acquisition, vitesse d'acquisition, conservation de l'acquisition, ...



### 1.3. Experience (Expérience)

Une **Experience** est une **séquence ordonnée de Tasks et d'Actions**. Elle ne contient aucune logique d'exécution—c'est juste la description de ce qui doit arriver.

**Caractéristiques :**
- Contient métadonnées : `name`, `description`, `author`, `version`, `parameters`
- Contient une liste `sequence` de Tasks et Actions
- Méthode `compile()` génère deux plans : complet et mock

**Exemple (experience.py) :**
```python
@dataclass
class Experience:
    name: str
    description: str = ""
    author: str = ""
    version: str = "1.0"
    parameters: dict = field(default_factory=dict)
    sequence: list[ExperimentNode] = field(default_factory=list)

    def add(self, node: ExperimentNode):
        self.sequence.append(node)

    def compile(self) -> tuple[ExecutionPlan, ExecutionPlan]:
        compiler = ExperimentCompiler()
        return compiler.compile(self)  # Retourne (plan_complet, plan_mock)
```

### 1.4. ExecutionPlan

Un **ExecutionPlan** est une liste ordonnée d'Actions prête à être exécutée.

**Deux plans sont générés :**
1. **complete** : toutes les actions (y compris non-simulables)
2. **mock** : uniquement les actions avec `simulate=True`

**Bénéfice :** tester une expérience rapidement en mock avant de la lancer sur la machine réelle.

---

## 2. Architecture : Flux de données

```
┌─────────────────-┐
│  experience.json │  Configuration déclarative
└────────┬────────-┘
         │
         ▼
┌──────────────────┐
│ ExperimentLoader │  Charge et valide le JSON
└────────┬─────────┘
         │
         ▼
┌─────────────────┐
│  Experience     │  Séquence de Tasks/Actions
│  (en mémoire)   │
└────────┬────────┘
         │
         ▼
┌───────────────────┐
│ ExperimentCompiler│ Génère deux plans
└────────┬──────────┘
         │
         ├──────────────────┬───────────────────┐
         ▼                  ▼                   ▼
    ┌────────────┐   ┌────────────┐   ┌──────────────┐
    │ plan_mock  │   │plan_complete│  │ plan_metadata│
    └────────────┘   └────────────┘   └──────────────┘
         │            
         ▼            
    ┌──────────────┐  
    │ MockExecutor │  
    └──────────────┘  
         │                  
         ▼                  
    ┌──────────────┐
    │ Validation   │
    │ Digital Twin │  ───> Echec demande une intervention humaine
    └──────────────┘
         │
         ▼       
    ┌────────────────┐
    │HardwareExecutor│ Exécute le plan complet
    └────────────────┘
         │                 
         ▼ 
    ┌───────────────────┐
    │ Expérience Réel   │ Enregistre les acquisitions d'expériences
    └───────────────────┘
         

```

---

## 3. Structure des fichiers

### 3.1. `action.py`

**Rôle** : Définir toutes les actions élémentaires disponibles.

**Contient :**
- Classe de base `ExperimentNode` et `Action`
- Sous-classes spécialisées : `MotionAction`, `ToolAction`, `AcquisitionAction`, `FlowAction`, `EnvAction`
- Implémentations concrètes des actions :
  - **Motion** : `HomeAll`, `MoveToWell`, `MoveToSafeZ`, `MoveInsideWell`
  - **Tools** : `PickupTool`, `ParkTool`
  - **Acquisition** : `CaptureImage`, `AcquireSpectrum`
  - **Flow** : `Pause`, `Wait`, `UserConfirmation`
  - **Environment** : `PixelOn`, `PixelOff`, `AllPixelOn`, `AllPixelOff`

**Points à améliorer :**
- Ajouter plus d'actions pour les outils existants (Pipette, Syringe, Spectrometer, etc.)
- Créer une action abstraite pour les actions utilisateur/confirmation
- Ajouter actions pour les lumières et les futurs capteurs

### 3.2. `task.py`

**Rôle** : Définir les opérations métier (composées d'actions).

**Contient :**
- Classe de base `Task`
- Implémentations d'exemple :
  - `TransferLens` : transférer un échantillon via un outil d'inoculation et une validation avec une vision par ordinateur
    
**Points à améliorer :**
- Développer les tasks réelles pour les protocoles scientifiques (culture, Etude de fluorescence, etc.)
- Gérer les tâches composées (boucles, conditions) de façon plus robuste
- Valider les dépendances (`required_tools`, etc.) avant compilation

### 3.3. `registry.py`

**Rôle** : Enregistrer et découvrir les Actions et Tasks disponibles.

**API :**
```python
@Registry.register("my_action")
class MyAction(Action):
    ...

# Récupérer une action enregistrée
MyActionClass = Registry.action("my_action")
node = Registry.create("my_action", param1=value1, param2=value2)
```

**Points à améliorer :**
- Ajouter des registres spécialisés pour les outils (`register_tool`, `register_observer`)
- Valider les dépendances entre Actions

### 3.4. `experience.py`

**Rôle** : Modèle d'une expérience complète.

**Classe principale :**
- `Experience` : conteneur de métadonnées + séquence de Tasks/Actions

**Points à améliorer :**
- Ajouter validation des dépendances (ressources requises)

### 3.5. `plan.py`

**Rôle** : Représenter un plan d'exécution prêt à être lancé.

**Classes :**
- `ExecutionPlan` : liste ordonnée d'Actions
- `ExecutionBundle` : pair (plan_complete, plan_mock)

### 3.6. `run.py`

**Rôle** : Compiler, valider et exécuter une expérience.

**Classes principales :**

| Classe | Rôle |
|--------|------|
| `ExperimentCompiler` | Transforme Experience → ExecutionBundle |
| `MockExecutor` | Exécute le plan_mock (simulation) |
| `HardwareExecutor` | Exécute le plan_complete (vraie machine) |
| `DigitalTwin` | Valide le plan contre un simulateur (non implémenté) |
| `ExperimentRun` | Représente une exécution : état, résultats, artifacts |

**Points à améliorer :**
- Implémenter `DigitalTwin.validate()` pour valider avant exécution hardware
- Ajouter gestion des erreurs et retry

### 3.7. `loader.py`

**Rôle** : Charger une expérience depuis un fichier JSON.

**API :**
```python
experience, deck = ExperimentLoader.load(
    experience_file="configs/experiment.json",
    deck_file="configs/deck.json"
)
```

**Format JSON attendu :**
```json
{
    "name": "Transfer lens",
    "description": "Simple demonstration",
    "author": "Pierre",
    "version": "1.0",
    "sequence": [
        {
            "id": "home"
        },
        {
            "id": "transfer_lens",
            "parameters": {
                "source": "Plate1:A1",
                "destination": "Plate2"
            }
        },
        {
            "id": "wait",
            "parameters": {
                "duration": 2
            }
        }
    ]
}
```

**Points à améliorer :**
- Supporter MongoDB pour chargement d'expériences versionnées
- Supporter Altar (expérience registry)
- Ajouter validation de schéma JSON au chargement


### 3.8. `launcher.py`

**Rôle** : Point d'entrée pour exécuter une expérience end-to-end avec logging.

**Utilise :**
- **Sacred** : gestion des métadonnées, tracking des résultats, logging
- **MongoDB** : persistance des exécutions passées

**Flux :**
1. Charger config (fichiers JSON)
2. Compiler l'expérience
3. Exécuter en mock (validation)
4. Valider avec DigitalTwin (non implémenté)
5. Exécuter sur hardware
6. Logger les résultats dans MongoDB

**Points à améliorer :**
- Implémenter la validation DigitalTwin
- Ajouter interface graphique pour paramétrage avant exécution


### 3.9. Fichiers de configuration

#### `config/experiment.json`
Définition déclarative d'une expérience.

#### `config/deck.json`
Configuration du plateau (emplacement des labwares, slots utilisés, etc.).

---

## 4. Améliorations proposées

### 4.1. Améliorations court terme

1. **Enrichir les Actions** :
   - Ajouter actions pour tous les outils existants (Pipette, outil de Fluorescence, Camera, etc.)
   - Ajouter actions pour paramètres d'environnement 

2. **Développer les Tasks métier** :
   - Culture/croissance (boucles temporelles)
   - Imagerie
   - Acquisition de la Fluorescence

3. **Validation et sécurité** :
   - Implémenter `DigitalTwin.validate()` pour simuler avant hardware
   - Ajouter logs de G-code complets (via `RecordingTransport`)
   - Ajouter retry/rollback en cas d'erreur

4. **Intégration avec Jubilee** :
   - Remplacer imports MockTransport par vrais transports
   - Intégrer avec `DeckNavigator`, `ToolChanger`, `Tool` réels
   
### 4.2. Améliorations moyen terme

1. **Interface graphique (Scratch-like)** :
   - Drag-and-drop de blocs d'Actions/Tasks
   - Paramétrage visuel
   - Génération automatique de JSON
   - Export/import d'expériences

2. **Gestion de base de données** :
   - MongoDB pour versionning d'expériences
   - Historique complet des exécutions (résultats, temps, états)
   - Comparaison d'exécutions

---

## 5. Comment utiliser le framework

### 5.1. Créer une nouvelle Action

```python
# Dans action.py
@Registry.register("my_custom_action")
@dataclass(frozen=True)
class MyCustomAction(MotionAction):  # ou autre type
    param1: str
    param2: float = 10.0

    def compile(self):
        # Logique réelle : appeler les vrais objets Jubilee
        result = self.nav.do_something(param1=self.param1, param2=self.param2)
        return result
```

### 5.2. Créer une nouvelle Task

```python
# Dans task.py
@Registry.register("my_workflow")
@dataclass
class MyWorkflow(Task):
    required_tools = ["ToolName"]
    required_modules = ["DeckNavigator"]

    def compile(self, plan: ExecutionPlan):
        plan.add(ActionA(...))
        plan.add(ActionB(...))
        plan.add(ActionC(...))
```

### 5.3. Créer une expérience en JSON

```json
{
    "name": "My Experiment",
    "description": "Testing my workflow",
    "author": "Me",
    "version": "1.0",
    "sequence": [
        {"id": "home_all"},
        {
            "id": "my_workflow",
            "parameters": {
                "param1": "value1"
            }
        },
        {"id": "capture_image", "parameters": {"camera": "Top"}}
    ]
}
```

### 5.4. Exécuter une expérience

```python
# En Python
from experiment.loader import ExperimentLoader
from experiment.run import ExperimentCompiler, MockExecutor, HardwareExecutor

experience, deck = ExperimentLoader.load("my_experiment.json", "deck_config.json")
compiler = ExperimentCompiler()
bundle = compiler.compile(experience)

# Test en mock
mock = MockExecutor()
mock.execute(bundle.mock)

# Exécution réelle
hardware = HardwareExecutor()
hardware.execute(bundle.complete)
```

---

## 6. État actuel et limitations

### 6.1. Ce qui fonctionne

✅ Architecture générale de base  
✅ Système de Registry  
✅ Compilation Actions → Plans  
✅ Exécution mock vs hardware  
✅ Chargement JSON  
✅ Exemple de Task (TransferLens)  

### 6.2. Ce qui manque ou est incomplet

❌ **Intégration avec code source réel** :
- Les imports dans `action.py` pointent vers mocktransport, pas vers vrais modules
- `DeckNavigator`, `ToolChanger`, `Tool` ne sont pas correctement intégrés

❌ **Actions/Tasks métier** :
- Seul TransferLens est implémenté et incomplet
- Beaucoup d'actions possibles manquent (pipette, fluorescence, etc.)

❌ **Validation/sécurité** :
- `DigitalTwin.validate()` n'est pas implémentée
- Pas de vérification de dépendances (`required_tools`, etc.)

❌ **Gestion d'erreurs** :
- Pas de retry/rollback

❌ **Interface utilisateur** :
- Interface Scratch n'existe pas (c'est la vision)
- Seulement JSON en entrée

❌ **Persistance** :
- MongoDB n'est pas configuré
- Pas d'historique d'exécutions

---

## 7. Recommandations pour les améliorations

### Phase 1 : Fondations
1. **Intégrer avec code réel** : remplacer imports mocktransport par vrais modules
3. **Documenter protocoles** : identifier protocoles scientifiques à implémenter

### Phase 2 : Enrichissement
1. **Créer Actions/Tasks métier** :  culture, imagerie, fluo
2. **Implémenter validation** : DigitalTwin, G-code logging
3. **Rendre opérationnel MongoDB** : tracking et historique

### Phase 3 : Interface utilisateur
1. **Prototype interface Scratch** : drag-and-drop, paramétrage visuel
2. **Générateur JSON** : depuis interface → JSON
3. **Visualisation** : timeline, logs en temps réel

---

## 8. Conclusion

Le framework `experiment` propose une **architecture déclarative et extensible** pour construire des expériences répétables. Même si le code actuel n'est pas totalement intégré avec science_jubilee, **l'idée centrale est recherché robuste** et peut être améliorée progressivement.

L'objectif final—une interface Scratch-like pour construire des expériences—est réaliste et souhaitable. Le chemin vers cet objectif passe par l'intégration progressive du code, l'enrichissement des Actions/Tasks, et finalement l'ajout d'une interface graphique.
