"""Mans&Co Magazine — site de magazine en ligne.

Flask + SQLite. Au premier lancement, la base est créée et le site propose
de définir le mot de passe du compte admin « Mans&Co » via /setup.
"""

import html as html_lib
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime
from functools import wraps

from flask import (
    Flask, abort, flash, g, redirect, render_template, request, session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "magazine.db")
SECRET_PATH = os.path.join(BASE_DIR, "secret.key")

ADMIN_USERNAME = "Mans&Co"
PER_PAGE = 6

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

_write_lock = threading.Lock()


def _load_secret_key():
    try:
        with open(SECRET_PATH, "r", encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key
    except FileNotFoundError:
        pass
    key = secrets.token_hex(32)
    with open(SECRET_PATH, "w", encoding="utf-8") as f:
        f.write(key)
    return key


app.secret_key = _load_secret_key()


# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, params=(), one=False):
    cur = get_db().execute(sql, params)
    rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, params=()):
    with _write_lock:
        db = get_db()
        cur = db.execute(sql, params)
        db.commit()
        return cur


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    excerpt     TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    image_url   TEXT NOT NULL DEFAULT '',
    published   INTEGER NOT NULL DEFAULT 0,
    featured    INTEGER NOT NULL DEFAULT 0,
    views       INTEGER NOT NULL DEFAULT 0,
    likes       INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    author     TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscribers (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);
"""

SEED_CATEGORIES = [
    ("Culture", "culture"),
    ("Technologie", "technologie"),
    ("Société", "societe"),
    ("Voyages", "voyages"),
    ("Gastronomie", "gastronomie"),
]

SEED_ARTICLES = [
    {
        "title": "Le retour du papier dans un monde tout écran",
        "cat": "culture",
        "excerpt": "Entre librairies indépendantes qui rouvrent et ventes de livres neufs en hausse, le papier semble défier les pronostics de l'ère numérique.",
        "content": (
            "On annonçait sa mort depuis vingt ans, mais le papier est toujours là. "
            "Partout, les librairies indépendantes réapprennent à vivre, portées par "
            "un public plus jeune que prévu.\n\n"
            "Ce renouveau tient à trois choses : le geste, l'objet, la patience. "
            "Lire sur papier, c'est accepter une vitesse différente, sans notifications "
            "ni tentations de bifurquer vers un autre onglet.\n\n"
            "Les éditeurs l'ont bien compris : belles éditions, dos brochés soignés, "
            "papier de droite. Le livre redevient un objet que l'on offre et que l'on "
            "garde, pas un simple conteneur de texte."
        ),
        "published": 1, "featured": 1, "views": 84, "likes": 12,
    },
    {
        "title": "Intelligence artificielle : ce qui change vraiment au travail",
        "cat": "technologie",
        "excerpt": "Au-delà des promesses et des peurs, un tour d'horizon sobre des usages qui se généralisent déjà dans les entreprises.",
        "content": (
            "Loin des grands narratifs, l'adoption se joue dans des tâches modestes : "
            "résumer des documents, préparer des comptes rendus, traduire, "
            "reformuler.\n\n"
            "Les métiers créatifs ne sont pas épargnés, mais ils transforment plutôt "
            "qu'ils ne disparaissent. Le vrai sujet est celui de la formation et de "
            "la confiance accordée aux outils.\n\n"
            "Une chose est sûre : les organisations qui prennent le temps de définir "
            "des règles claires avancent plus vite que celles qui improvisent."
        ),
        "published": 1, "featured": 0, "views": 151, "likes": 23,
    },
    {
        "title": "Villes à hauteur d'enfant : l'urbanisme qui change de regard",
        "cat": "societe",
        "excerpt": "Quand on conçoit une ville où un enfant de 8 ans peut circuler seul, on obtient une ville plus agréable pour tout le monde.",
        "content": (
            "L'idée vient des Pays-Bas et contourne le globe : penser la ville du "
            "point de vue des enfants, c'est imposer la sécurité, la lenteur et le "
            "végétal.\n\n"
            "Rues limitées à 30 km/h, élargissement de trottoirs, écoles accessibles "
            "à pied : la liste paraît banale, mais elle redessine les "
            "priorités.\n\n"
            "Les municipalités qui s'y essayent constatent un effet inattendu : les "
            "convois scolaires se réduisent, les commerces de proximité survivent et "
            "le bruit baisse."
        ),
        "published": 1, "featured": 0, "views": 63, "likes": 9,
    },
    {
        "title": "Slow travel : cinq itinéraires qui prennent leur temps",
        "cat": "voyages",
        "excerpt": "Trains de nuit, vélo, bateaux de ligne : voyager lentement n'est plus un luxe, c'est un choix d'expérience.",
        "content": (
            "Le slow travel n'est pas une mode, c'est un rapport au temps. Traverser "
            "les Alpes en train de nuit n'a pas la même saveur qu'un vol d'une heure "
            "et demie.\n\n"
            "Nos cinq itinéraires privilégient des lignes régulières, des hébergements "
            "simples et des étapes marchables.\n\n"
            "Conseil pratique : réservez les nuits en wagon-lit tôt, les places partent "
            "vite, surtout en été."
        ),
        "published": 1, "featured": 0, "views": 97, "likes": 18,
    },
    {
        "title": "La cuisine de saison, mode d'emploi",
        "cat": "gastronomie",
        "excerpt": "Manger selon les saisons sans se ruiner ni passer ses soirées en cuisine : nos repères simples et nos recettes de base.",
        "content": (
            "Cuisiner de saison, c'est d'abord un problème de **marché** : "
            "privilégier *trois légumes déjà mûrs* plutôt que quinze recettes "
            "impossibles.\n\n"
            "Avec une base de fond (ratatouille, velouté, grains, herbes), on compose "
            "en vingt minutes des assiettes différentes toute la semaine.\n\n"
            "### Les trois réflexes à installer\n\n"
            "- Un velouté express : oignon, légume de saison, bouillon\n"
            "- Des grains cuits d'avance : riz, semoule ou lentilles\n"
            "- Une sauce minute : herbes, huile, citron\n\n"
            "Manger local, ~~c'est un luxe~~, c'est souvent moins cher.\n\n"
            "Et en novembre, le *potimarron rôti au thym* reste ce qu'il y a de mieux."
        ),
        "published": 1, "featured": 0, "views": 42, "likes": 7,
    },
    {
        "title": "Brouillon : agenda des festivals du trimestre",
        "cat": "culture",
        "excerpt": "Sélection en cours de rédaction : festivals, expositions et rendez-vous à ne pas manquer ces trois prochains mois.",
        "content": (
            "Cette page reste volontairement en brouillon pour montrer le workflow "
            "éditorial : l'admin la voit sur son tableau de bord, elle n'apparaît pas "
            "pour les visiteurs.\n\n"
            "Future liste : festival du document, semaine du design, Biennale d'art "
            "contemporain."
        ),
        "published": 0, "featured": 0, "views": 0, "likes": 0,
    },
]

def _bootstrap():
    if os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    cats = {}
    for name, slug in SEED_CATEGORIES:
        cur = conn.execute(
            "INSERT INTO categories (name, slug) VALUES (?, ?)", (name, slug))
        cats[slug] = cur.lastrowid
    for a in SEED_ARTICLES:
        now = datetime.now().strftime("%d/%m/%Y à %H:%M")
        conn.execute(
            """INSERT INTO articles
               (title, slug, excerpt, content, category_id, image_url,
                published, featured, views, likes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?)""",
            (a["title"], slugify(a["title"]), a["excerpt"], a["content"],
             cats.get(a["cat"]), 1 if a["published"] else 0,
             1 if a["featured"] else 0, a["views"], a["likes"], now, now))
    conn.commit()
    conn.close()


def slugify(text):
    text = (text or "").lower()
    text = text.replace("&", " et ")
    text = re.sub(r"[éèêë]", "e", text)
    text = re.sub(r"[àâä]", "a", text)
    text = re.sub(r"[îï]", "i", text)
    text = re.sub(r"[ôö]", "o", text)
    text = re.sub(r"[ûüù]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "article"


def is_admin():
    return session.get("admin") is True


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_admin():
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def current_user():
    if "user" not in g:
        g.user = None
        uid = session.get("user_id")
        if uid is not None:
            g.user = query("SELECT * FROM users WHERE id = ?", (uid,), one=True)
            if g.user is None:
                session.clear()
    return g.user


@app.context_processor
def inject_globals():
    categories = query("SELECT * FROM categories ORDER BY name")
    return {"nav_categories": categories}


@app.template_filter("dt")
def dt_filter(value, fmt="%d/%m/%Y"):
    for pattern in ("%d/%m/%Y à %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, pattern).strftime(fmt)
        except (ValueError, TypeError):
            continue
    return value


@app.context_processor
def inject_year():
    return {"current_year": datetime.now().year}


@app.context_processor
def inject_auth():
    return {"current_user": current_user(), "is_admin": is_admin()}


# ---------------------------------------------------------------------------
# Markdown léger (italique, gras, liens, citations, listes…)
# ---------------------------------------------------------------------------

def _md_inline(text):
    text = html_lib.escape(text or "", quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\\s]+)\)",
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
        text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*\n]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", text)
    return text


@app.template_filter("md")
def md_filter(text):
    out = []
    for block in (text or "").replace("\r\n", "\n").split("\n\n"):
        lines = block.split("\n")
        stripped = [l for l in lines if l.strip()]
        if not stripped:
            continue
        if all(l.lstrip().startswith("- ") for l in stripped):
            items = "".join(
                "<li>{}</li>".format(_md_inline(l.lstrip()[2:]))
                for l in stripped)
            out.append("<ul>{}</ul>".format(items))
            continue
        if all(l.startswith("&gt; ") for l in stripped):
            quoted = "<br>".join(
                _md_inline(l[5:]) for l in stripped)
            out.append("<blockquote>{}</blockquote>".format(quoted))
            continue
        if len(stripped) == 1 and stripped[0].strip() in ("---", "***"):
            out.append("<hr>")
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", stripped[0])
        if heading and len(stripped) == 1:
            level = len(heading.group(1)) + 1
            out.append("<h{0}>{1}</h{0}>".format(
                level, _md_inline(heading.group(2))))
            continue
        out.append("<p>{}</p>".format(
            "<br>".join(_md_inline(l) for l in stripped)))
    return "\n".join(out) if out else ""


# ---------------------------------------------------------------------------
# Gestion du mot de passe admin
# ---------------------------------------------------------------------------

def password_hash_stored():
    row = query("SELECT value FROM settings WHERE key = 'admin_password_hash'",
                one=True)
    return row["value"] if row else None


def _admin_exists():
    if query("SELECT 1 FROM users WHERE is_admin = 1", one=True):
        return True
    return password_hash_stored() is not None


def _log_in(user):
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session.permanent = True
    if user["is_admin"]:
        session["admin"] = True


def _safe_next(default):
    dest = request.args.get("next") or default
    if not dest.startswith("/"):
        dest = default
    return dest


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if _admin_exists():
        flash("Le mot de passe administrateur est déjà configuré.",
              "info")
        return redirect(url_for("login"))
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if len(password) < 8:
            flash("Le mot de passe doit contenir au moins 8 caractères.",
                  "error")
        elif password != confirm:
            flash("Les deux mots de passe ne correspondent pas.", "error")
        else:
            execute(
                "INSERT INTO users (username, password_hash, is_admin, "
                "created_at) VALUES (?, ?, 1, ?)",
                (ADMIN_USERNAME, generate_password_hash(password),
                 datetime.now().strftime("%d/%m/%Y à %H:%M")))
            flash("Mot de passe administrateur enregistré. Vous pouvez vous "
                  "connecter.", "success")
            return redirect(url_for("login"))
    return render_template("setup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if not _admin_exists():
        return redirect(url_for("setup"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = query("SELECT * FROM users WHERE username = ?",
                     (username,), one=True)
        if user and check_password_hash(user["password_hash"], password):
            _log_in(user)
            session["admin"] = bool(user["is_admin"])
            flash("Bienvenue, {} !".format(user["username"]), "success")
            return redirect(_safe_next(
                url_for("dashboard") if user["is_admin"] else url_for("index")))
        flash("Identifiant ou mot de passe incorrect.", "error")
    return render_template("login.html")


USERNAME_RE = re.compile(r"^[\wÀ-ÿ][\wÀ-ÿ .&'-]{1,39}$")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        if not USERNAME_RE.match(username):
            flash("Le pseudo doit contenir 2 à 40 caractères (lettres, "
                  "chiffres, espaces ou . ' - &).", "error")
        elif username.lower() == ADMIN_USERNAME.lower():
            flash("Ce pseudo est réservé à la rédaction.", "error")
        elif query("SELECT 1 FROM users WHERE username = ?",
                   (username,), one=True):
            flash("Ce pseudo est déjà pris.", "error")
        elif len(password) < 8:
            flash("Le mot de passe doit contenir au moins 8 caractères.",
                  "error")
        elif password != confirm:
            flash("Les deux mots de passe ne correspondent pas.", "error")
        else:
            cur = execute(
                "INSERT INTO users (username, password_hash, is_admin, "
                "created_at) VALUES (?, ?, 0, ?)",
                (username, generate_password_hash(password),
                 datetime.now().strftime("%d/%m/%Y à %H:%M")))
            _log_in(dict(query(
                "SELECT * FROM users WHERE id = ?",
                (cur.lastrowid,), one=True)))
            flash("Bienvenue, {} ! Votre compte est créé : vous pouvez "
                  "désormais lire tous les articles en entier.".format(
                      username), "success")
            return redirect(_safe_next(url_for("index")))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Espace public
# ---------------------------------------------------------------------------

def _fetch_articles(page=1, search=None, category_slug=None, exclude=None,
                    per_page=PER_PAGE):
    params = []
    where = ["a.published = 1"]
    if search:
        like = "%{}%".format(search.replace("%", r"\%")
                                  .replace("_", r"\_"))
        where.append("(a.title LIKE ? ESCAPE '\\' OR a.excerpt LIKE ? "
                     "ESCAPE '\\' OR a.content LIKE ? ESCAPE '\\')")
        params += [like, like, like]
    if category_slug:
        where.append("c.slug = ?")
        params.append(category_slug)
    if exclude:
        where.append("a.id != ?")
        params.append(exclude)
    sql_where = " AND ".join(where)
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    total = query(
        "SELECT COUNT(*) AS n FROM articles a "
        "LEFT JOIN categories c ON c.id = a.category_id "
        "WHERE {}".format(sql_where), params, one=True)["n"]
    rows = query(
        "SELECT a.*, c.name AS category_name, c.slug AS category_slug "
        "FROM articles a LEFT JOIN categories c ON c.id = a.category_id "
        "WHERE {} ORDER BY a.featured DESC, a.created_at DESC "
        "LIMIT ? OFFSET ?".format(sql_where),
        params + [per_page, (page - 1) * per_page])
    return rows, total, page


def _pagination(total, page, per_page=PER_PAGE):
    pages = max(1, -(-total // per_page))
    return {"page": page, "pages": pages, "total": total,
            "has_prev": page > 1, "has_next": page < pages}


@app.route("/")
def index():
    search = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1)
    articles, total, page = _fetch_articles(page=page, search=search)
    featured = query(
        "SELECT a.*, c.name AS category_name, c.slug AS category_slug "
        "FROM articles a LEFT JOIN categories c ON c.id = a.category_id "
        "WHERE a.published = 1 AND a.featured = 1 "
        "ORDER BY a.created_at DESC LIMIT 1", one=True)
    return render_template("index.html", articles=articles,
                           pagination=_pagination(total, page),
                           search=search, featured=featured)


@app.route("/categorie/<slug>")
def category(slug):
    cat = query("SELECT * FROM categories WHERE slug = ?", (slug,), one=True)
    if cat is None:
        abort(404)
    page = request.args.get("page", 1)
    articles, total, page = _fetch_articles(page=page, category_slug=slug)
    return render_template("category.html", category=cat, articles=articles,
                           pagination=_pagination(total, page))


def _published_article(slug):
    return query(
        "SELECT a.*, c.name AS category_name, c.slug AS category_slug "
        "FROM articles a LEFT JOIN categories c ON c.id = a.category_id "
        "WHERE a.slug = ? AND a.published = 1", (slug,), one=True)


@app.route("/article/<slug>")
def article(slug):
    art = _published_article(slug)
    if art is None:
        abort(404)
    execute("UPDATE articles SET views = views + 1 WHERE id = ?",
            (art["id"],))
    related = query(
        "SELECT a.*, c.slug AS category_slug FROM articles a "
        "LEFT JOIN categories c ON c.id = a.category_id "
        "WHERE a.published = 1 AND a.id != ? "
        "ORDER BY (c.id = ?) DESC, a.created_at DESC LIMIT 3",
        (art["id"], art["category_id"] or -1))
    comments = query(
        "SELECT * FROM comments WHERE article_id = ? ORDER BY created_at DESC",
        (art["id"],))
    blocks = art["content"].replace("\r\n", "\n").split("\n\n")
    return render_template(
        "article.html", article=art, comments=comments, related=related,
        liked=session.get("likes", {}).get("liked_{}".format(art["id"]), False),
        full_access=current_user() is not None,
        content_html=md_filter(art["content"]),
        preview_html=md_filter("\n\n".join(blocks[:2])))


@app.route("/article/<slug>/comment", methods=["POST"])
def comment(slug):
    art = _published_article(slug)
    if art is None:
        abort(404)
    user = current_user()
    if user is None:
        flash("Créez un compte ou connectez-vous pour commenter.", "info")
        return redirect(url_for("register"))
    content = (request.form.get("content") or "").strip()[:2000]
    if not content:
        flash("Merci de saisir votre commentaire.", "error")
    else:
        execute(
            "INSERT INTO comments (article_id, author, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (art["id"], user["username"], content,
             datetime.now().strftime("%d/%m/%Y à %H:%M")))
        flash("Merci pour votre commentaire !", "success")
    return redirect(url_for("article", slug=slug) + "#commentaires")


@app.route("/article/<slug>/like", methods=["POST"])
def like(slug):
    art = _published_article(slug)
    if art is None:
        abort(404)
    key = "liked_%s" % art["id"]
    liked = session.setdefault("likes", {})
    if liked.get(key):
        execute("UPDATE articles SET likes = MAX(likes - 1, 0) WHERE id = ?",
                (art["id"],))
        liked[key] = False
        new_state = False
    else:
        execute("UPDATE articles SET likes = likes + 1 WHERE id = ?",
                (art["id"],))
        liked[key] = True
        new_state = True
    session.modified = True
    if request.headers.get("X-Requested-With") == "fetch":
        from flask import jsonify
        total = query("SELECT likes FROM articles WHERE id = ?",
                      (art["id"],), one=True)["likes"]
        return jsonify({"likes": total, "liked": new_state})
    return redirect(url_for("article", slug=slug))


@app.route("/newsletter", methods=["POST"])
def newsletter():
    email = (request.form.get("email") or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        flash("Adresse e-mail invalide.", "error")
    else:
        try:
            execute(
                "INSERT INTO subscribers (email, created_at) VALUES (?, ?)",
                (email, datetime.now().strftime("%d/%m/%Y à %H:%M")))
            flash("Merci ! Vous êtes inscrit à la newsletter.", "success")
        except sqlite3.IntegrityError:
            flash("Cette adresse est déjà inscrite.", "info")
    return redirect(request.referrer or url_for("index"))


@app.route("/a-propos")
def about():
    total = query("SELECT COUNT(*) AS n FROM articles WHERE published = 1",
                  one=True)["n"]
    cats = query("SELECT COUNT(*) AS n FROM categories", one=True)["n"]
    return render_template("about.html", total_articles=total,
                           total_categories=cats)


# ---------------------------------------------------------------------------
# Espace admin
# ---------------------------------------------------------------------------

@app.route("/admin")
@login_required
def dashboard():
    stats = {
        "articles": query("SELECT COUNT(*) AS n FROM articles", one=True)["n"],
        "published": query(
            "SELECT COUNT(*) AS n FROM articles WHERE published = 1",
            one=True)["n"],
        "comments": query("SELECT COUNT(*) AS n FROM comments", one=True)["n"],
        "subscribers": query("SELECT COUNT(*) AS n FROM subscribers",
                             one=True)["n"],
        "members": query("SELECT COUNT(*) AS n FROM users WHERE is_admin = 0",
                         one=True)["n"],
        "views": query("SELECT COALESCE(SUM(views), 0) AS n FROM articles",
                       one=True)["n"],
        "likes": query("SELECT COALESCE(SUM(likes), 0) AS n FROM articles",
                       one=True)["n"],
    }
    articles = query(
        "SELECT a.*, c.name AS category_name FROM articles a "
        "LEFT JOIN categories c ON c.id = a.category_id "
        "ORDER BY a.created_at DESC")
    recent_comments = query(
        "SELECT cm.*, a.title AS article_title, a.slug AS article_slug "
        "FROM comments cm JOIN articles a ON a.id = cm.article_id "
        "ORDER BY cm.created_at DESC LIMIT 5")
    top = query(
        "SELECT title, slug, views FROM articles ORDER BY views DESC LIMIT 5")
    return render_template("dashboard.html", stats=stats, articles=articles,
                           recent_comments=recent_comments, top=top)


def _flash_missing(title, content):
    missing = []
    if not title:
        missing.append("le titre")
    if not content:
        missing.append("le contenu")
    if missing:
        flash("Champ obligatoire manquant : " + ", ".join(missing) + ".",
              "error")
    return bool(missing)


@app.route("/admin/articles/nouveau", methods=["GET", "POST"])
@login_required
def article_new():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if _flash_missing(title, content):
            categories = query("SELECT * FROM categories ORDER BY name")
            return render_template("article_form.html", article=None,
                                   categories=categories, form=request.form)
        excerpt = (request.form.get("excerpt") or "").strip()
        image_url = (request.form.get("image_url") or "").strip()
        category_id = request.form.get("category_id") or None
        published = 1 if request.form.get("published") else 0
        featured = 1 if request.form.get("featured") else 0
        base = slugify(title)
        slug = base
        n = 1
        while query("SELECT 1 FROM articles WHERE slug = ?", (slug,),
                    one=True):
            n += 1
            slug = "{}-{}".format(base, n)
        now = datetime.now().strftime("%d/%m/%Y à %H:%M")
        execute(
            """INSERT INTO articles
               (title, slug, excerpt, content, category_id, image_url,
                published, featured, views, likes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)""",
            (title, slug, excerpt or (content[:180] + "…"), content,
             category_id, image_url, published, featured, now, now))
        flash("Article « {} » créé avec succès.".format(title), "success")
        return redirect(url_for("dashboard"))
    categories = query("SELECT * FROM categories ORDER BY name")
    return render_template("article_form.html", article=None,
                           categories=categories, form=None)


@app.route("/admin/articles/<int:article_id>/modifier", methods=["GET",
                                                                 "POST"])
@login_required
def article_edit(article_id):
    art = query("SELECT * FROM articles WHERE id = ?", (article_id,), one=True)
    if art is None:
        abort(404)
    categories = query("SELECT * FROM categories ORDER BY name")
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        if _flash_missing(title, content):
            return render_template("article_form.html", article=art,
                                   categories=categories,
                                   form=request.form)
        slug = art["slug"]
        new_base = slugify(title)
        if new_base != slugify(art["title"]):
            slug = new_base
            n = 1
            while query("SELECT 1 FROM articles WHERE slug = ? AND id != ?",
                        (slug, art["id"]), one=True):
                n += 1
                slug = "{}-{}".format(new_base, n)
        execute(
            """UPDATE articles SET title = ?, slug = ?, excerpt = ?,
               content = ?, category_id = ?, image_url = ?, published = ?,
               featured = ?, updated_at = ? WHERE id = ?""",
            (title, slug,
             (request.form.get("excerpt") or "").strip(),
             content, request.form.get("category_id") or None,
             (request.form.get("image_url") or "").strip(),
             1 if request.form.get("published") else 0,
             1 if request.form.get("featured") else 0,
             datetime.now().strftime("%d/%m/%Y à %H:%M"), art["id"]))
        flash("Article mis à jour.", "success")
        return redirect(url_for("dashboard"))
    return render_template("article_form.html", article=art,
                           categories=categories, form=None)


@app.route("/admin/articles/<int:article_id>/supprimer", methods=["POST"])
@login_required
def article_delete(article_id):
    execute("DELETE FROM articles WHERE id = ?", (article_id,))
    flash("Article supprimé.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/articles/<int:article_id>/publier", methods=["POST"])
@login_required
def article_toggle_publish(article_id):
    execute("UPDATE articles SET published = 1 - published, "
            "updated_at = ? WHERE id = ?",
            (datetime.now().strftime("%d/%m/%Y à %H:%M"), article_id))
    flash("Statut de publication mis à jour.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/commentaires/<int:comment_id>/supprimer", methods=["POST"])
@login_required
def comment_delete(comment_id):
    execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    flash("Commentaire supprimé.", "success")
    return redirect(request.referrer or url_for("dashboard"))


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


_bootstrap()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
