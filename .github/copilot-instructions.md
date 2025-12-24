# Instructions pour GitHub Copilot

## À propos du projet

Ce projet est une application web Django appelée **Datakult**. C'est une application de gestion de médias (films, séries, livres, etc.) avec système de notation et de suivi. Elle est développée pour une utilisation personnelle et éducative.

## Stack technique

- **Backend** : Python 3 avec Django
- **Frontend** : HTML avec HTMX pour les interactions dynamiques
- **CSS** : Tailwind CSS (via django-tailwind) et daisyUI
- **Base de données** : SQLite (développement)
- **Gestionnaire de paquets Python** : uv

## Structure du projet

- `src/` : Code source Django
  - `config/` : Configuration Django (settings, urls, wsgi, asgi)
  - `core/` : Application principale (modèles Media, vues, formulaires)
  - `accounts/` : Gestion des utilisateurs
  - `templates/` : Templates HTML
  - `static/` : Fichiers statiques (CSS, JS, images)
  - `theme/` : Configuration Tailwind CSS

## Conventions de code

### Python/Django
- Utiliser des docstrings en anglais
- Suivre PEP 8 pour le style de code
- Utiliser des vues basées sur les fonctions (FBV) sauf si une CBV est plus appropriée
- Les modèles doivent avoir une méthode `__str__` explicite

### Templates
- Utiliser les partials dans `templates/partials/` pour les composants réutilisables
- Privilégier HTMX pour les interactions dynamiques plutôt que JavaScript vanilla
- Utiliser les classes Tailwind CSS pour le styling

### JavaScript
- Garder le JavaScript minimal, préférer HTMX
- Fichiers JS dans `static/js/`

## Commandes utiles

```bash
# Démarrer le serveur de développement
uv run poe server

# Compiler Tailwind CSS en mode watch
python manage.py tailwind start

# Migrations
uv run poe makemigrations
uv run poe migrate

# Créer un superuser
python manage.py createsuperuser
```

## Préférences

- Plutôt que de proposer des solutions toutes faites, guider l'utilisateur à travers les étapes nécessaires pour atteindre son objectif. Le but est d'aider l'utilisateur à apprendre et comprendre le processus à chaque étape. Donner des explications claires sur le pourquoi de chaque étape et des liens vers les sources et la documentation officielle lorsque c'est pertinent.
- Répondre en **français**
- Fournir des explications concises
- Proposer des solutions idiomatiques Django/Python
- Utiliser HTMX plutôt que des appels AJAX JavaScript classiques
- Privilégier les solutions simples et maintenables
- Pour le CSS, utiliser les classes Tailwind/DaisyUI existantes avant d'ajouter du CSS personnalisé
