import os
from flask import Flask, redirect, request, session, render_template, jsonify, url_for
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_key")

SCOPE = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing "
    "streaming "
    "user-read-email "
    "user-read-private"
)

def get_sp_oauth():
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:5000/callback"),
        scope=SCOPE,
        cache_path=None,
        show_dialog=True,
    )

def get_spotify():
    token_info = session.get("token_info")
    if not token_info:
        return None
    sp_oauth = get_sp_oauth()
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
        session["token_info"] = token_info
    return spotipy.Spotify(auth=token_info["access_token"])


# ── Landing page ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route("/login")
def login():
    auth_url = get_sp_oauth().get_authorize_url()
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return redirect(url_for("index"))
    token_info = get_sp_oauth().get_access_token(code)
    session["token_info"] = token_info
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/dashboard")
def dashboard():
    sp = get_spotify()
    if not sp:
        return redirect(url_for("login"))
    user = sp.current_user()
    token = session["token_info"]["access_token"]
    return render_template("dashboard.html", user=user, token=token)


# ── Player API ────────────────────────────────────────────────────────────────

@app.route("/api/now-playing")
def now_playing():
    sp = get_spotify()
    if not sp:
        return jsonify({"error": "not authenticated"}), 401
    try:
        track = sp.current_playback()
        if not track or not track.get("item"):
            return jsonify({"playing": False})
        item = track["item"]
        return jsonify({
            "playing": track["is_playing"],
            "title": item["name"],
            "artist": ", ".join(a["name"] for a in item["artists"]),
            "album_art": item["album"]["images"][0]["url"] if item["album"]["images"] else None,
            "duration_ms": item["duration_ms"],
            "progress_ms": track["progress_ms"],
            "device": track.get("device", {}).get("name", ""),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/player/<action>", methods=["POST"])
def player_action(action):
    sp = get_spotify()
    if not sp:
        return jsonify({"error": "not authenticated"}), 401
    try:
        if action == "play":
            sp.start_playback()
        elif action == "pause":
            sp.pause_playback()
        elif action == "next":
            sp.next_track()
        elif action == "previous":
            sp.previous_track()
        else:
            return jsonify({"error": "unknown action"}), 400
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
