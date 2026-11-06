# squidz — Guide utilisateur

## Prérequis
- Windows 10 ou 11 (64 bits), Python 3.11 pour lancer/produire l'exécutable.
- Manette compatible **SDL GameController** connectée en USB ou Bluetooth (Nintendo Pro Controller selon le pilote et la configuration SDL).

## Installation
1. Extraire le ZIP dans votre dépôt.
2. Dans PowerShell à la racine : `powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1`.
3. Lancer `dist\squidz\squidz.exe`. Le dossier `dist\squidz` est **portable** : conservez l'ensemble des fichiers à côté de l'exécutable.
4. Le programme reste actif dans la zone de notification ; double-cliquez sur son icône pour ouvrir la configuration. Le menu « Quitter » l'arrête.
- La police Inter est incluse. Pour afficher le titre avec Super Water, cette police doit être installée dans Windows.

## Configuration
- Les emplacements affichent les manettes connectées et les manettes déjà connues mais déconnectées.
- Seules les manettes connectées ou déjà connues sont affichées. Si leur nombre dépasse la largeur disponible, utilisez les flèches latérales pour parcourir la liste.
- La couronne indique la manette principale (administratrice). Avec une seule manette connectée, elle devient principale automatiquement. Avec plusieurs manettes, cliquez sur « SET PRIMARY » sous celle qui doit devenir principale.
- Le niveau de batterie et le profil associé sont affichés sous chaque manette connectée. Les valeurs de batterie marquées `~` sont des estimations : SDL ne fournit qu'un niveau approximatif (faible, moyen, plein), pas un pourcentage précis.
- « Manage profiles » permet de choisir un profil à modifier ou d'en créer un. « Settings » ouvre les réglages du profil associé à la manette principale.
- Choisissez « By default » pour qu'une manette utilise le premier profil par défaut.
- Les sections « Général », « Programme » et « Site web » ont des priorités croissantes.
- « Ajouter un programme » ouvre la boîte de sélection des `.exe` (y compris applications portables).
- « Ajouter un site web » demande un domaine, par exemple `youtube.com`.
- Le bouton HOME (central) court ouvre le menu Démarrer ; maintenu **0,8 seconde** par la manette principale ouvre squidz.

## Commandes initiales
| Contrôle | Action |
|---|---|
| Stick gauche | Déplacer le pointeur |
| A / B | Clic gauche / droit |
| Stick droit vertical | Défilement |
| Clic stick droit | Clic molette |
| L / R | Ctrl+Tab / Tab (général) |
| L / R dans Firefox ou Brave | Onglet précédent / suivant |
| X / Y sur YouTube dans Firefox ou Brave | Lecture/pause (`K`) / plein écran (`F`) |
| - / + | Volume - / + |
| HOME | Touche Windows |
| HOME maintenu | Fenêtre de configuration |

Le clavier visuel Windows ne se lance pas automatiquement. Pour l'ouvrir manuellement, utilisez le raccourci Windows `Win` + `Ctrl` + `O`.

## Intégration YouTube
La détection du site actif nécessite l'extension fournie dans `browser-extension/`.
1. Ouvrir `%APPDATA%\squidz\settings.json`, copier la valeur `browser_token`.
2. Brave : `brave://extensions` → mode développeur → « Charger l'extension non empaquetée » → sélectionner `browser-extension`.
3. Firefox : `about:debugging#/runtime/this-firefox` → « Charger un module complémentaire temporaire » → choisir `manifest.json`. Le chargement temporaire doit être renouvelé après redémarrage ; pour une installation permanente, signer l'extension.
4. Dans les options de l'extension, coller le jeton et enregistrer.
5. Conserver squidz en cours d'exécution. L'extension n'envoie l'URL active qu'au service local `127.0.0.1:8765`.

**Limites connues** : la détection du domaine suit le dernier onglet actif signalé par le navigateur ; plusieurs fenêtres/profils simultanés du même navigateur peuvent provoquer un contexte erroné. Les raccourcis `K` et `F` de YouTube supposent que la page traite les raccourcis (et qu'aucun champ de saisie ne capte les touches). Le jeu de boutons et les axes dépendent du mapping SDL ; une manette non reconnue comme GameController nécessite un mapping SDL adapté. Les applications administrateur peuvent ignorer les entrées injectées par une application non élevée.
