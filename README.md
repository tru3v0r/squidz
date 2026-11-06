# squidz

Pilotage de Windows avec une manette : profils par appareil, raccourcis par application et domaine web, interface Qt moderne.

**Plateforme : Windows 10/11.** Archive contenant le **projet source** et les scripts de création de `squidz.exe` sur Windows ; aucun binaire Windows n'est inclus dans cette archive.

## Construire l'exécutable
Dans PowerShell, à la racine du dépôt :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```

Puis exécuter `dist\squidz\squidz.exe`.

## Documentation
- [Guide utilisateur](docs/UTILISATEUR.md)
- [Documentation développeur](docs/DEVELOPPEUR.md)

## Licence
GPL-3.0-or-later (voir `LICENSE`).

## Statut
Version **0.1.0 — prototype fonctionnel à valider sur Windows et sur les manettes cibles**. Aucune validation matérielle Windows n'a été effectuée dans l'environnement de génération.


## Compilation Windows (Python 3.12)

Installer Python 3.12 (avec le lanceur `py`), puis exécuter `powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1` à la racine du dépôt. Le script utilise `%LOCALAPPDATA%\squidz\venv-py312` pour éviter les verrous Dropbox, installe les dépendances, lance les tests et vérifie la présence de `dist\squidz\squidz.exe`. Il s’arrête sur toute erreur. Variable optionnelle : `SQUIDZ_VENV_DIR` pour personnaliser le chemin du venv.
