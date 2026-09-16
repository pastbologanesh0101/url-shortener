import os
import sqlite3
import string
import random
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import Flask, g, request, redirect, jsonify, render_template, abort

ALPHABET = string.ascii_letters + string.digits  # base62
CODE_LENGTH = 6


def is_valid_url(url):
    """A URL is considered valid if it has both a scheme and a netloc."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return bool(parsed.scheme) and bool(parsed.netloc)


def generate_short_code(length=CODE_LENGTH):
    return "".join(random.choice(ALPHABET) for _ in range(length))


def create_app(testing=False, db_path=None):
    app = Flask(__name__, template_folder="templates")
    app.config["TESTING"] = testing

    if db_path is not None:
        app.config["DATABASE"] = db_path
    elif testing:
        app.config["DATABASE"] = ":memory:"
    else:
        instance_dir = os.path.join(app.root_path, "..", "instance")
        os.makedirs(instance_dir, exist_ok=True)
        app.config["DATABASE"] = os.path.join(instance_dir, "urls.db")

    # For in-memory DBs we need a single persistent connection shared across
    # the app context, otherwise each connection would see an empty DB.
    if app.config["DATABASE"] == ":memory:":
        app._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
        app._memory_conn.row_factory = sqlite3.Row

    def _get_db():
        if app.config["DATABASE"] == ":memory:":
            return app._memory_conn
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(exception=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db():
        conn = _get_db()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS link (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                long_url TEXT NOT NULL,
                short_code TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                click_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()

    with app.app_context():
        init_db()

    def code_exists(conn, code):
        row = conn.execute(
            "SELECT 1 FROM link WHERE short_code = ?", (code,)
        ).fetchone()
        return row is not None

    @app.route("/", methods=["GET"])
    def index():
        conn = _get_db()
        rows = conn.execute(
            "SELECT long_url, short_code, created_at, click_count "
            "FROM link ORDER BY id DESC"
        ).fetchall()
        links = [dict(r) for r in rows]
        return render_template("index.html", links=links)

    @app.route("/api/links", methods=["POST"])
    def create_link():
        data = request.get_json(silent=True) or request.form
        long_url = (data.get("long_url") or "").strip()
        custom_alias = (data.get("custom_alias") or "").strip() or None

        if not is_valid_url(long_url):
            return jsonify({"error": "Invalid URL. Must include scheme and domain, e.g. https://example.com"}), 400

        conn = _get_db()

        if custom_alias:
            if not all(c in ALPHABET for c in custom_alias):
                return jsonify({"error": "Custom alias may only contain letters and digits"}), 400
            if code_exists(conn, custom_alias):
                return jsonify({"error": f"Alias '{custom_alias}' is already taken"}), 409
            short_code = custom_alias
        else:
            short_code = generate_short_code()
            attempts = 0
            while code_exists(conn, short_code):
                short_code = generate_short_code()
                attempts += 1
                if attempts > 20:
                    return jsonify({"error": "Could not generate a unique short code, try again"}), 500

        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO link (long_url, short_code, created_at, click_count) "
            "VALUES (?, ?, ?, 0)",
            (long_url, short_code, created_at),
        )
        conn.commit()

        short_url = request.host_url.rstrip("/") + "/" + short_code
        return jsonify({
            "long_url": long_url,
            "short_code": short_code,
            "short_url": short_url,
            "created_at": created_at,
            "click_count": 0,
        }), 201

    @app.route("/<short_code>", methods=["GET"])
    def follow_link(short_code):
        conn = _get_db()
        row = conn.execute(
            "SELECT long_url FROM link WHERE short_code = ?", (short_code,)
        ).fetchone()
        if row is None:
            abort(404)
        conn.execute(
            "UPDATE link SET click_count = click_count + 1 WHERE short_code = ?",
            (short_code,),
        )
        conn.commit()
        return redirect(row["long_url"])

    @app.route("/api/stats/<short_code>", methods=["GET"])
    def stats(short_code):
        conn = _get_db()
        row = conn.execute(
            "SELECT long_url, short_code, created_at, click_count "
            "FROM link WHERE short_code = ?",
            (short_code,),
        ).fetchone()
        if row is None:
            abort(404)
        return jsonify(dict(row))

    return app
