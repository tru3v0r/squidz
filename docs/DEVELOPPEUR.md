# squidz — Documentation développeur

## Architecture
- `core/models.py` : modèle typé, validation, priorité global → application → domaine le plus spécifique.
- `core/controllers.py` : découverte SDL GameController, lecture à 60 Hz, détection d'appui long, déplacement et défilement.
- `infra/windows.py` : couche Windows (injection clavier/souris, magnétisme des zones d'interaction, processus actif).
- `infra/browser.py` : serveur HTTP loopback authentifié par jeton, état URL avec expiration de 5 s.
- `infra/storage.py` : persistance JSON atomique, `%APPDATA%\squidz\settings.json`.
- `infra/startup.py` : inscription/suppression de l’application dans la clé de démarrage Windows de l’utilisateur.
- `ui/windows.py` : fenêtres Qt, édition de profils, sélecteurs de manettes, icône de notification.
- `main.py` : composition des composants et cycle de vie.
- `browser-extension/` : extension MV3 Brave / Firefox (chargement temporaire sur Firefox).

## Démarrage développement
`powershell -ExecutionPolicy Bypass -File scripts\run-windows.ps1`

## Tests
`python -m pip install -e '.[test]'` puis `python -m pytest`.

## Build
`powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1`

Le build PyInstaller doit être exécuté **sur Windows**, car PyInstaller ne produit pas de binaire Windows depuis Linux. Il construit `dist\squidz\squidz.exe` et copie documentation, exemples et extension. La distribution est de type `onedir` (ne déplacez pas uniquement le `.exe`).

## Configuration
Schéma `schema_version=1`. `profiles` associe un nom à ses règles ; `assignments` associe une clé `GUID#occurrence` au nom du profil. `known_devices` mémorise les manettes découvertes. `browser_token` est généré au premier lancement. Ne pas publier le fichier utilisateur contenant ce jeton.

## Sécurité / limites techniques
- Aucune commande shell arbitraire depuis un raccourci ; `key_combo` n'accepte que les touches autorisées.
- API HTTP accessible uniquement sur `127.0.0.1`, protégée par jeton, taille de requête limitée.
- L'extension reçoit l'URL complète de l'onglet actif, envoyée localement ; seul le domaine est utilisé pour le routage. Les URL ne sont pas persistées.
- Identité des manettes : GUID SDL + rang d'occurrence. Pour deux manettes strictement identiques, leur rang peut changer à la reconnexion. Une amélioration future devrait utiliser un identifiant matériel stable lorsqu'il existe.
- Le clavier virtuel dépend de UI Automation ; la détection de texte web n'est pas exhaustive.
- Les mappings SDL varient selon le contrôleur et le pilote. Les axes utilisés sont `LEFTX`, `LEFTY`, `RIGHTY` (indices 0,1,3).
- L'application n'est pas un service Windows et ne fonctionne pas sur l'écran de connexion ou les fenêtres sécurisées UAC.

## Évolutions recommandées
Introduire un adaptateur d'identité matériel stable, un navigateur de processus Windows basé sur les applications installées, un pont navigateur par fenêtre, un moteur de règles avec modificateurs/chords et une CI Windows qui publie les artefacts signés.
