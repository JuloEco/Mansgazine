# Mans&Co Magazine

Site de magazine en ligne complet : **Flask + SQLite + frontend HTML/CSS/JS**,
sans framework CSS (design maison sobre : encre marine, papier crème, or brossé,
typographieserif *Playfair Display* + *Inter*, icônes Font Awesome).

## Lancer le site

```bash
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Ouvrez http://127.0.0.1:5000

## Premier lancement

Au premier démarrage, la base `magazine.db` est créée automatiquement avec
quelques articles d'exemple, et le site **redirige vers `/setup`** pour définir
le mot de passe du compte admin **« Mans&Co »** (8 caractères minimum, stocké
haché, jamais en clair). Le fichier `secret.key` (clé de session) est généré
automatiquement — ne le commitez pas.

Connexion admin : page **Admin** (footer ou menu), identifiant `Mans&Co`.

## Fonctionnalités

- **Espace public** : page d'accueil avec article à la une, recherche plein
  texte dans les articles, filtres par rubrique, pagination, compteur de vues,
  temps de lecture estimé, bouton « j'aime » (1 par visiteur), article 404.
- **Commentaires** : les lecteurs commentent les articles ; embargo admin :
  suppression depuis l'article ou le tableau de bord.
- **Newsletter** : inscription d'adresses e-mail (anti-doublon).
- **Espace admin « Mans&Co »** :
  - tableau de bord avec statistiques (articles, vues, likes, commentaires,
    abonnés) et top des articles les plus lus ;
  - créer / modifier / supprimer chaque article ;
  - publier / dépublier un article (brouillon invisible pour les visiteurs) ;
  - mettre un article **à la une** ;
  - rubriques ; gérer l'URL d'une image d'illustration par article.
- **Sécurité** : mot de passe haché (scrypt via Werkzeug), sessions signées,
  requêtes SQL paramétrées, échappement Jinja par défaut, `MAX_CONTENT_LENGTH`.

## Structure

```
app.py            application Flask (routes, base de données, seeds)
templates/        pages HTML (base, accueil, article, rubrique, admin…)
static/css/       style.css — design maison, responsive
static/js/        main.js — menu mobile, bouton j'aime (fetch)
magazine.db       base SQLite (créée au 1er lancement)
secret.key        clé de sessions (créée au 1er lancement)
```

## Notes techniques

- SQLite en mode WAL non requis : écritures sérialisées par un verrou
  applicatif — suffisant pour un petit magazine.
- Déploiement production : `pip install gunicorn` puis
  `gunicorn -w 2 -b 127.0.0.1:8000 app:app` derrière un reverse proxy.
