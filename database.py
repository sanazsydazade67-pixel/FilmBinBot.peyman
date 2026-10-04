import sqlite3
import json
from datetime import datetime
import os


# =========================
# DATABASE PATH
# =========================

# Railway Volume
# Volume باید روی /data متصل شده باشد.
DB_DIR = "/data"

# اگر /data در دسترس نبود، برای جلوگیری از Crash
# از مسیر فعلی برنامه استفاده می‌کنیم.
if not os.path.exists(DB_DIR):
    DB_DIR = "."

DB_NAME = os.path.join(DB_DIR, "film_bin.db")


# =========================
# DATABASE CONNECTION
# =========================

def get_db():
    conn = sqlite3.connect(
        DB_NAME,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================
# INIT DATABASE
# =========================

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        original_title TEXT,
        category TEXT,
        imdb TEXT,
        country TEXT,
        director TEXT,
        stars TEXT,
        synopsis TEXT,
        subtitle TEXT,
        poster_file_id TEXT,
        trailer_file_id TEXT,
        trailer_type TEXT,
        status TEXT DEFAULT 'pending',
        channel_message_ids TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movie_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        quality TEXT NOT NULL,
        file_id TEXT NOT NULL,
        file_type TEXT NOT NULL,
        UNIQUE(movie_id, quality)
    )
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_seen TEXT,
        last_seen TEXT
    )
    """)
    
       # اضافه کردن وضعیت اعلان برای کاربران قدیمی و جدید
    try:
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN notifications_enabled INTEGER DEFAULT 1
        """)
    except Exception:
        pass 
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS downloads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        movie_id INTEGER,
        quality TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        movie_id INTEGER NOT NULL,
        created_at TEXT,
        UNIQUE(user_id, movie_id)
    )
    """)

    conn.commit()
    conn.close()
    
# =========================
# USERS
# =========================

def add_user(user_id):
    conn = get_db()

    now = datetime.utcnow().isoformat()

    conn.execute("""
    INSERT INTO users(
        user_id,
        first_seen,
        last_seen
    )
    VALUES (?, ?, ?)
    ON CONFLICT(user_id)
    DO UPDATE SET last_seen=excluded.last_seen
    """, (
        user_id,
        now,
        now
    ))

    conn.commit()
    conn.close()


# =========================
# MOVIES
# =========================

def add_movie(data):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO movies (
        code,
        title,
        original_title,
        category,
        imdb,
        country,
        director,
        stars,
        synopsis,
        subtitle,
        poster_file_id,
        trailer_file_id,
        trailer_type,
        status,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["code"],
        data["title"],
        data.get("original_title"),
        data.get("category"),
        data.get("imdb"),
        data.get("country"),
        data.get("director"),
        data.get("stars"),
        data.get("synopsis"),
        data.get("subtitle"),
        data.get("poster_file_id"),
        data.get("trailer_file_id"),
        data.get("trailer_type"),
        "pending",
        datetime.utcnow().isoformat()
    ))

    movie_id = cur.lastrowid

    conn.commit()
    conn.close()

    return movie_id


def get_movie(movie_id):
    conn = get_db()

    movie = conn.execute(
        "SELECT * FROM movies WHERE id=?",
        (movie_id,)
    ).fetchone()

    conn.close()

    return movie

# =========================================================
# علاقه‌مندی‌ها
# =========================================================

def add_favorite(user_id, movie_id):

    conn = get_db()

    conn.execute("""
        INSERT OR IGNORE INTO favorites
        (
            user_id,
            movie_id,
            created_at
        )
        VALUES (?, ?, datetime('now'))
    """, (
        user_id,
        movie_id
    ))

    conn.commit()
    conn.close()


def remove_favorite(user_id, movie_id):

    conn = get_db()

    conn.execute("""
        DELETE FROM favorites
        WHERE user_id=?
        AND movie_id=?
    """, (
        user_id,
        movie_id
    ))

    conn.commit()
    conn.close()


def is_favorite(user_id, movie_id):

    conn = get_db()

    row = conn.execute("""
        SELECT id
        FROM favorites
        WHERE user_id=?
        AND movie_id=?
    """, (
        user_id,
        movie_id
    )).fetchone()

    conn.close()

    return row is not None


def get_user_favorites(user_id):

    conn = get_db()

    rows = conn.execute("""
        SELECT movies.*
        FROM favorites
        JOIN movies
        ON favorites.movie_id = movies.id
        WHERE favorites.user_id=?
        ORDER BY favorites.id DESC
    """, (
        user_id,
    )).fetchall()

    conn.close()

    return rows
    
def get_movie_by_code(code):
    conn = get_db()

    code = str(code).strip()

    # جستجوی مستقیم کد فیلم
    movie = conn.execute(
        "SELECT * FROM movies WHERE code=?",
        (code,)
    ).fetchone()

    # اگر لینک شامل کیفیت بود،
    # کیفیت را از انتهای کد حذف می‌کنیم
    if not movie:

        for quality in (
            "_360p",
            "_480p",
            "_720p",
            "_1080p",
        ):

            if code.endswith(quality):

                base_code = code[:-len(quality)]

                movie = conn.execute(
                    "SELECT * FROM movies WHERE code=?",
                    (base_code,)
                ).fetchone()

                if movie:
                    break

    conn.close()

    return movie


def get_all_movies():
    conn = get_db()

    rows = conn.execute("""
    SELECT * FROM movies
    ORDER BY id DESC
    """).fetchall()

    conn.close()

    return rows


def set_movie_status(movie_id, status):
    conn = get_db()

    conn.execute(
        "UPDATE movies SET status=? WHERE id=?",
        (status, movie_id)
    )

    conn.commit()
    conn.close()
    
# =========================================================
# وضعیت اعلان‌ها
# =========================================================

def get_notifications_status(user_id):

    conn = get_db()

    row = conn.execute("""
        SELECT notifications_enabled
        FROM users
        WHERE user_id=?
    """, (
        user_id,
    )).fetchone()

    conn.close()

    if not row:
        return True

    return bool(
        row["notifications_enabled"]
    )
    
# =========================================================
# تغییر وضعیت اعلان‌ها
# =========================================================

def set_notifications_status(user_id, enabled):

    conn = get_db()

    conn.execute("""
        UPDATE users
        SET notifications_enabled=?
        WHERE user_id=?
    """, (
        1 if enabled else 0,
        user_id,
    ))

    conn.commit()
    conn.close()
    
# =========================================================
# کاربران فعال برای دریافت اعلان
# =========================================================

def get_notification_users():

    conn = get_db()

    rows = conn.execute("""
        SELECT user_id
        FROM users
        WHERE notifications_enabled=1
    """).fetchall()

    conn.close()

    return [
        row["user_id"]
        for row in rows
    ]


# =========================
# MOVIE FILES
# =========================

def add_movie_file(
    movie_id,
    quality,
    file_id,
    file_type
):
    conn = get_db()

    conn.execute("""
    INSERT OR REPLACE INTO movie_files
    (
        movie_id,
        quality,
        file_id,
        file_type
    )
    VALUES (?, ?, ?, ?)
    """, (
        movie_id,
        quality,
        file_id,
        file_type
    ))

    conn.commit()
    conn.close()


def get_movie_files(movie_id):
    conn = get_db()

    rows = conn.execute("""
    SELECT * FROM movie_files
    WHERE movie_id=?
    ORDER BY
        CASE quality
        WHEN '360p' THEN 1
        WHEN '480p' THEN 2
        WHEN '720p' THEN 3
        WHEN '1080p' THEN 4
        ELSE 5
        END
    """, (
        movie_id,
    )).fetchall()

    conn.close()

    return rows


# =========================
# SEARCH
# =========================

def search_movies(query):
    conn = get_db()

    q = f"%{query}%"

    rows = conn.execute("""
    SELECT * FROM movies
    WHERE status='published'
    AND (
        title LIKE ?
        OR original_title LIKE ?
        OR category LIKE ?
    )
    ORDER BY id DESC
    LIMIT 20
    """, (
        q,
        q,
        q
    )).fetchall()

    conn.close()

    return rows


def get_latest_movies(limit=30):

    conn = get_db()

    rows = conn.execute("""
        SELECT *
        FROM movies
        WHERE status='published'
        ORDER BY id DESC
        LIMIT ?
    """, (
        limit,
    )).fetchall()

    conn.close()

    return rows


# =========================
# CHANNEL MESSAGE IDS
# =========================

def save_channel_message_ids(
    movie_id,
    message_ids
):
    conn = get_db()

    conn.execute(
        "UPDATE movies SET channel_message_ids=? WHERE id=?",
        (
            json.dumps(message_ids),
            movie_id
        )
    )

    conn.commit()
    conn.close()


def get_channel_message_ids(movie_id):
    movie = get_movie(movie_id)

    if not movie:
        return []

    if not movie["channel_message_ids"]:
        return []

    try:
        return json.loads(
            movie["channel_message_ids"]
        )

    except Exception:
        return []


# =========================
# DOWNLOADS
# =========================

def record_download(
    user_id,
    movie_id,
    quality
):
    conn = get_db()

    conn.execute("""
    INSERT INTO downloads(
        user_id,
        movie_id,
        quality,
        created_at
    )
    VALUES (?, ?, ?, ?)
    """, (
        user_id,
        movie_id,
        quality,
        datetime.utcnow().isoformat()
    ))

    conn.commit()
    conn.close()


# =========================
# STATISTICS
# =========================

def get_stats():
    conn = get_db()

    users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    movies = conn.execute(
        "SELECT COUNT(*) FROM movies"
    ).fetchone()[0]

    published = conn.execute(
        "SELECT COUNT(*) FROM movies WHERE status='published'"
    ).fetchone()[0]

    files = conn.execute(
        "SELECT COUNT(*) FROM movie_files"
    ).fetchone()[0]

    downloads = conn.execute(
        "SELECT COUNT(*) FROM downloads"
    ).fetchone()[0]

    conn.close()

    return {
        "users": users,
        "movies": movies,
        "published": published,
        "files": files,
        "downloads": downloads
    }


# =========================
# DELETE MOVIE
# =========================

def delete_movie(movie_id):
    conn = get_db()

    # حذف فایل‌های فیلم
    conn.execute(
        "DELETE FROM movie_files WHERE movie_id=?",
        (movie_id,)
    )

    # حذف دانلودهای مربوط به فیلم
    conn.execute(
        "DELETE FROM downloads WHERE movie_id=?",
        (movie_id,)
    )

    # حذف خود فیلم
    conn.execute(
        "DELETE FROM movies WHERE id=?",
        (movie_id,)
    )

    conn.commit()
    conn.close()
