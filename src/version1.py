import sqlite3
from flask import Flask, render_template_string, request, session, jsonify, redirect, url_for
from waitress import serve
import requests
from datetime import datetime
import threading
import time
import webbrowser
from functools import wraps
import os
import tkinter as tk
from tkinter import messagebox, simpledialog
import sys

app = Flask(__name__)
app.secret_key = 'yeti_secret_key'

# Configuration de session stricte
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600

@app.after_request
def add_header(response):
    """Empêche le navigateur de garder en cache les pages protégées"""
    # Pour TOUTES les pages sauf les fichiers statiques
    if request.endpoint not in ['static']:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
    return response

def get_app_dir():
    app_name = "Yetilogs"

    if getattr(sys, 'frozen', False):
        base_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            app_name
        )
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(base_dir, exist_ok=True)
    return base_dir


# Config globale
APP_DIR = get_app_dir()
DB_FILE = os.path.join(APP_DIR, "yeti_energie.db")
yeti_ip_detected = None
is_connected = False

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Simple : si pas de username dans session, déconnecter
        if 'username' not in session:
            session.clear()
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

LOGIN_HTML = """
<!DOCTYPE html>
<html><head><title>Login - Smart Battery Insights</title>
<meta charset="UTF-8">
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background: linear-gradient(135deg, #0a1628 0%, #1a2332 100%);
        color: #e0e6ed;
        min-height: 100vh;
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 20px;
    }
    .login-container {
        max-width: 400px;
        width: 100%;
        background: rgba(26, 35, 50, 0.9);
        border-radius: 20px;
        padding: 40px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .logo {
        text-align: center;
        margin-bottom: 30px;
    }
    .logo-icon {
        font-size: 60px;
        margin-bottom: 10px;
    }
    h1 {
        color: #00d9ff;
        font-size: 28px;
        text-align: center;
        margin-bottom: 10px;
        text-shadow: 0 0 20px rgba(0, 217, 255, 0.5);
    }
    .subtitle {
        text-align: center;
        color: #a0aec0;
        font-size: 14px;
        margin-bottom: 30px;
    }
    .form-group {
        margin-bottom: 20px;
    }
    label {
        display: block;
        color: #a0aec0;
        font-size: 14px;
        margin-bottom: 8px;
        font-weight: 500;
    }
    input[type="text"], input[type="password"] {
        width: 100%;
        padding: 12px 15px;
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 8px;
        color: #e0e6ed;
        font-size: 14px;
        transition: all 0.3s ease;
    }
    input[type="text"]:focus, input[type="password"]:focus {
        outline: none;
        border-color: #00d9ff;
        box-shadow: 0 0 10px rgba(0, 217, 255, 0.3);
    }
    .btn-login {
        width: 100%;
        padding: 15px;
        background: linear-gradient(135deg, #00d9ff 0%, #0099cc 100%);
        border: none;
        border-radius: 10px;
        color: white;
        font-size: 16px;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 10px;
    }
    .btn-login:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 20px rgba(0, 217, 255, 0.4);
    }
    .error-message {
        background: rgba(255, 85, 85, 0.2);
        border: 1px solid rgba(255, 85, 85, 0.5);
        color: #ff5555;
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 20px;
        text-align: center;
        font-size: 14px;
    }

</style>
<script>
// 🔒 EMPÊCHE DE REVENIR EN ARRIÈRE VERS LE DASHBOARD APRÈS DÉCONNEXION
(function() {
    window.history.forward();
    function noBack() {
        window.history.forward();
    }
    window.onload = noBack;
    window.onpageshow = function(evt) { if (evt.persisted) noBack(); };
    window.onunload = function() { void(0); };
})();
</script>
</head><body>
<div class="login-container">
    <div class="logo">
        <div class="logo-icon">🔋</div>
        <h1>Smart Battery</h1>
        <div class="subtitle">Système de connexion</div>
    </div>
    
    {% if error %}
    <div class="error-message">
        ⚠️ {{ error }}
    </div>
    {% endif %}
    
    <form method="POST">
        <div class="form-group">
            <label for="username">👤 Nom d'utilisateur</label>
            <input type="text" id="username" name="username" required autofocus>
        </div>
        
        <div class="form-group">
            <label for="password">🔒 Mot de passe</label>
            <input type="password" id="password" name="password" required>
        </div>
        
        <button type="submit" class="btn-login">🔐 Se connecter</button>
    </form>
    
</div>
</body></html>
"""

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Nettoyer toute session existante au chargement de la page login
    if request.method == 'GET':
        session.clear()
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT password, role FROM users WHERE username = ?", (username,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            stored_pwd = user_data[0]
            role = user_data[1]
            
            if stored_pwd == password:
                session.clear()  # Nettoyer complètement avant de créer nouvelle session
                session['username'] = username
                session['role'] = role
                return redirect(url_for('dashboard'))
            else:
                error = "Identifiants incorrects"
        else:
            error = "Identifiants incorrects"
        
        return render_template_string(LOGIN_HTML, error=error)
    
    return render_template_string(LOGIN_HTML, error=None)

@app.route('/logout')
def logout():
    session.clear()
    response = redirect(url_for('login'))
    # Empêche TOTALEMENT le cache pour empêcher retour/avancer
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

def detect_yeti_ip():
    possible_ips = [
        '10.1.1.1',
        '192.168.137.54',
        '192.168.1.100',
        '192.168.0.100',
    ]
    
    print("🔍 Détection automatique de l'IP du Yeti...")
    for ip in possible_ips:
        try:
            print(f"   Test de {ip}...", end=" ")
            response = requests.get(f"http://{ip}/state", timeout=2)
            if response.status_code == 200:
                print(f"✅ Trouvé!")
                return ip, True
            else:
                print("❌")
        except:
            print("❌")
    
    print("⚠️  Aucune IP détectée")
    return None, False

def show_config_dialog():
    auto_ip, connected = detect_yeti_ip()
    
    root = tk.Tk()
    root.withdraw()
    
    result_ip = None
    result_mode = None
    result_connected = connected
    
    try:
        if auto_ip:
            result = messagebox.askyesno(
                "Connexion détectée",
                f"Yeti détecté sur {auto_ip}\n\nUtiliser cette connexion ?",
                parent=root
            )
            if result:
                result_ip = auto_ip
                result_mode = "Auto-détecté"
            else:
                choice = messagebox.askquestion(
                    "Configuration Yeti",
                    "Choisir le mode de connexion:\n\n"
                    "OUI = Hotspot Yeti (10.1.1.1)\n"
                    "NON = Réseau domestique (IP personnalisée)",
                    icon='question',
                    parent=root
                )
                
                if choice == 'yes':
                    result_ip = '10.1.1.1'
                    result_mode = 'Hotspot'
                    result_connected = False
                else:
                    ip = simpledialog.askstring(
                        "IP Réseau",
                        "Entrez l'adresse IP du Yeti sur votre réseau:\n(ex: 192.168.1.100)",
                        parent=root
                    )
                    if ip and ip.strip():
                        result_ip = ip.strip()
                        result_mode = 'Réseau'
                        result_connected = False
                    else:
                        result_ip = '10.1.1.1'
                        result_mode = 'Hotspot'
                        result_connected = False
        else:
            choice = messagebox.askquestion(
                "Configuration Yeti",
                "Aucun Yeti détecté.\n\nChoisir le mode de connexion:\n\n"
                "OUI = Hotspot Yeti (10.1.1.1)\n"
                "NON = Réseau domestique (IP personnalisée)",
                icon='question',
                parent=root
            )
            
            if choice == 'yes':
                result_ip = '10.1.1.1'
                result_mode = 'Hotspot'
                result_connected = False
            else:
                ip = simpledialog.askstring(
                    "IP Réseau",
                    "Entrez l'adresse IP du Yeti sur votre réseau:\n(ex: 192.168.1.100)",
                    parent=root
                )
                if ip and ip.strip():
                    result_ip = ip.strip()
                    result_mode = 'Réseau'
                    result_connected = False
                else:
                    result_ip = '10.1.1.1'
                    result_mode = 'Hotspot'
                    result_connected = False
    
    finally:
        root.quit()
        root.destroy()
        try:
            import gc
            gc.collect()
        except:
            pass
    
    return result_ip, result_mode, result_connected

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_heure TEXT,
            whOut REAL, whStored REAL, socPercent REAL,
            wattsOut REAL, ampsOut REAL, wattsIn REAL, ampsIn REAL,
            temperature REAL, timeToEmptyFull REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'guest'
        )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_users = [
            ('admin', 'admin123', 'admin'),
            ('guest', 'guest123', 'guest')
        ]
        cursor.executemany("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", default_users)
        print("✅ Users par défaut insérés dans la DB.")
    
    conn.commit()
    conn.close()
    print(f"DB '{DB_FILE}' initialisée.")

@app.route('/api/current_stats')
@login_required
def current_stats():
    global is_connected
    
    yeti_ip = session.get('yeti_ip', yeti_ip_detected or '10.1.1.1')
    try:
        response = requests.get(f"http://{yeti_ip}/state", timeout=3)
        is_connected = response.status_code == 200
    except:
        is_connected = False
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT socPercent, wattsOut, wattsIn, temperature, whStored
        FROM logs 
        ORDER BY date_heure DESC
        LIMIT 1
    """)
    current = cursor.fetchone()
    conn.close()
    
    if current:
        return jsonify({
            'soc': current[0],
            'watts_out': current[1],
            'watts_in': current[2],
            'temp': current[3],
            'wh_stored': current[4],
            'connected': is_connected
        })
    else:
        return jsonify({
            'soc': 0,
            'watts_out': 0,
            'watts_in': 0,
            'temp': 0,
            'wh_stored': 0,
            'connected': is_connected
        })

@app.route('/config', methods=['GET', 'POST'])
@login_required
@admin_required
def config():
    global is_connected
    if request.method == 'POST':
        mode = request.form['mode']
        if mode == 'hotspot':
            session['yeti_ip'] = '10.1.1.1'
            session['mode'] = 'Hotspot'
        else:
            ip = request.form['ip']
            if ip:
                session['yeti_ip'] = ip.strip()
                session['mode'] = 'Réseau'
            else:
                session['yeti_ip'] = '192.168.1.XXX'
                session['mode'] = 'Réseau'
        
        yeti_ip = session['yeti_ip']
        try:
            response = requests.get(f"http://{yeti_ip}/state", timeout=3)
            is_connected = response.status_code == 200
        except:
            is_connected = False
        
        print(f"Mode changé : {session['mode']} avec IP {session['yeti_ip']}")
    
    yeti_ip = session.get('yeti_ip', yeti_ip_detected or '10.1.1.1')
    mode = session.get('mode', 'Auto-détecté')
    
    html = """
    <!DOCTYPE html>
    <html><head><title>Configuration - Yeti Energy</title>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0a1628 0%, #1a2332 100%);
            color: #e0e6ed;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(26, 35, 50, 0.8);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        h1 {
            color: #00d9ff;
            font-size: 32px;
            margin-bottom: 30px;
            text-align: center;
            text-shadow: 0 0 20px rgba(0, 217, 255, 0.5);
        }
        .current-config {
            background: rgba(0, 217, 255, 0.1);
            border: 1px solid rgba(0, 217, 255, 0.3);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
        }
        .radio-group {
            margin: 25px 0;
        }
        .radio-option {
            background: rgba(255, 255, 255, 0.05);
            border: 2px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 20px;
            margin: 15px 0;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .radio-option:hover {
            border-color: #00d9ff;
            background: rgba(0, 217, 255, 0.1);
        }
        .radio-option.selected {
            border-color: #00d9ff;
            background: rgba(0, 217, 255, 0.15);
        }
        .radio-option input[type="radio"] {
            margin-right: 12px;
            transform: scale(1.3);
        }
        .radio-option label {
            cursor: pointer;
            font-size: 16px;
        }
        .ip-field {
            margin-top: 15px;
            padding-left: 30px;
        }
        .ip-field input {
            width: 100%;
            padding: 12px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            color: #e0e6ed;
            font-size: 14px;
        }
        .ip-field input:focus {
            outline: none;
            border-color: #00d9ff;
            box-shadow: 0 0 10px rgba(0, 217, 255, 0.3);
        }
        .btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #00d9ff 0%, #0099cc 100%);
            border: none;
            border-radius: 10px;
            color: white;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 20px;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 217, 255, 0.4);
        }
        .back-link {
            display: block;
            text-align: center;
            margin-top: 20px;
            color: #00d9ff;
            text-decoration: none;
            transition: all 0.3s ease;
        }
        .back-link:hover {
            text-shadow: 0 0 10px rgba(0, 217, 255, 0.8);
        }
    </style>
    </head><body>
    <div class="container">
        <h1>⚙️ Configuration Réseau</h1>
        
        <div class="current-config">
            <p><strong>Mode actuel:</strong> {{ mode }}</p>
            <p><strong>IP Yeti:</strong> {{ yeti_ip }}</p>
        </div>
        
        <form method="POST">
            <div class="radio-group">
                <div class="radio-option {% if mode == 'Hotspot' %}selected{% endif %}" onclick="selectMode(this, 'hotspot')">
                    <input type="radio" name="mode" value="hotspot" id="hotspot" {% if mode == 'Hotspot' %}checked{% endif %}>
                    <label for="hotspot">📡 Hotspot Yeti (10.1.1.1)</label>
                </div>
                
                <div class="radio-option {% if mode == 'Réseau' %}selected{% endif %}" onclick="selectMode(this, 'network')">
                    <input type="radio" name="mode" value="network" id="network" {% if mode == 'Réseau' %}checked{% endif %}>
                    <label for="network">🌐 Réseau domestique</label>
                    <div class="ip-field" id="ip_field" style="display: {% if mode == 'Réseau' %}block{% else %}none{% endif %};">
                        <input type="text" name="ip" value="{% if mode == 'Réseau' %}{{ yeti_ip }}{% endif %}" placeholder="ex: 192.168.1.100">
                    </div>
                </div>
            </div>
            
            <button type="submit" class="btn">💾 Sauvegarder & Redémarrer</button>
        </form>
        
        <a href="/" class="back-link">← Retour </a>
    </div>
    
    <script>
        function selectMode(element, mode) {
            document.querySelectorAll('.radio-option').forEach(el => el.classList.remove('selected'));
            element.classList.add('selected');
            document.getElementById(mode === 'hotspot' ? 'hotspot' : 'network').checked = true;
            document.getElementById('ip_field').style.display = mode === 'network' ? 'block' : 'none';
        }
    </script>
    </body></html>
    """
    return render_template_string(html, mode=mode, yeti_ip=yeti_ip)

@app.route('/users', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_users():
    error = None
    success = None
    
    if request.method == 'POST':
        username_to_edit = request.form.get('username_to_edit')
        new_username = request.form.get('new_username')
        new_password = request.form.get('new_password')
        
        if username_to_edit and new_username and new_password:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            try:
                cursor.execute("SELECT id FROM users WHERE username = ? AND username != ?", (new_username, username_to_edit))
                if cursor.fetchone():
                    error = "Ce nom d'utilisateur existe déjà !"
                else:
                    cursor.execute("UPDATE users SET username = ?, password = ? WHERE username = ?", 
                                   (new_username, new_password, username_to_edit))
                    if cursor.rowcount > 0:
                        success = f"User '{username_to_edit}' mis à jour en '{new_username}'."
                        if username_to_edit == session['username']:
                            session['username'] = new_username
                    else:
                        error = "Erreur lors de la mise à jour."
                conn.commit()
            except sqlite3.IntegrityError as e:
                error = f"Erreur: {e} (username dupliqué ?)"
            finally:
                conn.close()
        else:
            error = "Tous les champs sont requis."
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username, role FROM users ORDER BY role DESC")
    users_list = cursor.fetchall()
    conn.close()
    
    if len(users_list) != 2:
        error = "Erreur: Seulement 2 users attendus. Vérifiez la DB."
    
    html = """
    <!DOCTYPE html>
    <html><head><title>Gestion Users</title>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #0a1628 0%, #1a2332 100%); color: #e0e6ed; min-height: 100vh; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: rgba(26, 35, 50, 0.8); border-radius: 20px; padding: 40px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4); border: 1px solid rgba(255, 255, 255, 0.1); }
        h1 { color: #00d9ff; font-size: 32px; margin-bottom: 30px; text-align: center; text-shadow: 0 0 20px rgba(0, 217, 255, 0.5); }
        .user-item { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 20px; margin: 15px 0; }
        .user-info { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .user-role { color: #ffd700; font-weight: bold; }
        .edit-btn { background: #00d9ff; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; transition: all 0.3s; }
        .edit-btn:hover { background: #0099cc; transform: translateY(-1px); }
        .edit-form { display: none; margin-top: 15px; }
        .edit-form.show { display: block; }
        .form-group { margin-bottom: 10px; }
        .form-group label { display: block; color: #a0aec0; font-size: 14px; margin-bottom: 5px; }
        .form-group input { width: 100%; padding: 10px; background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 5px; color: #e0e6ed; }
        .form-group input:focus { outline: none; border-color: #00d9ff; box-shadow: 0 0 5px rgba(0, 217, 255, 0.3); }
        button[type="submit"] { width: 100%; padding: 12px; background: linear-gradient(135deg, #00d9ff 0%, #0099cc 100%); border: none; border-radius: 8px; color: white; font-weight: bold; cursor: pointer; margin-top: 10px; }
        button[type="submit"]:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0, 217, 255, 0.4); }
        .error { background: rgba(255, 85, 85, 0.2); border: 1px solid #ff5555; color: #ff5555; padding: 10px; border-radius: 8px; margin-bottom: 20px; text-align: center; }
        .success { background: rgba(0, 255, 136, 0.2); border: 1px solid #00ff88; color: #00ff88; padding: 10px; border-radius: 8px; margin-bottom: 20px; text-align: center; }
        .back-link { display: block; text-align: center; margin-top: 20px; color: #00d9ff; text-decoration: none; transition: all 0.3s; }
        .back-link:hover { text-shadow: 0 0 10px rgba(0, 217, 255, 0.8); }
    </style>
    </head><body>
    <div class="container">
        <h1>👥 Gestion des Utilisateurs</h1>
        
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        {% if success %}
        <div class="success">{{ success }}</div>
        {% endif %}
        
        {% for user in users_list %}
        <div class="user-item">
            <div class="user-info">
                <div>
                    <strong>{{ user[0] }}</strong> 
                    <span class="user-role">({{ user[1] }})</span>
                </div>
                <button class="edit-btn" onclick="toggleEdit('edit-{{ user[0] }}')">Modifier</button>
            </div>
            
            <form class="edit-form" id="edit-{{ user[0] }}" method="POST" onsubmit="return confirm('Confirmer les changements pour {{ user[0] }} ?')">
                <input type="hidden" name="username_to_edit" value="{{ user[0] }}">
                <div class="form-group">
                    <label>Nouveau Nom d'Utilisateur</label>
                    <input type="text" name="new_username" value="{{ user[0] }}" required>
                </div>
                <div class="form-group">
                    <label>Nouveau Mot de Passe</label>
                    <input type="password" name="new_password" placeholder="Nouveau password" required>
                </div>
                <button type="submit">💾 Mettre à Jour</button>
                <button type="button" class="edit-btn" onclick="toggleEdit('edit-{{ user[0] }}')">Annuler</button>
            </form>
        </div>
        {% endfor %}
        
        <a href="/" class="back-link">← Retour </a>
    </div>
    
    <script>
        function toggleEdit(formId) {
            const form = document.getElementById(formId);
            form.classList.toggle('show');
        }
    </script>
    </body></html>
    """
    return render_template_string(html, users_list=users_list, error=error, success=success)

@app.route('/api/ports_state')
@login_required
def ports_state():
    yeti_ip = session.get('yeti_ip', '10.1.1.1')

    try:
        r = requests.get(f"http://{yeti_ip}/state", timeout=3)
        data = r.json()

        return jsonify({
            "ac": data.get("acPortStatus", 0),
            "usb": data.get("usbPortStatus", 0),
            "12v": data.get("v12PortStatus", 0)
        })
    except Exception as e:
        print(f"Ports state error: {e}")
        return jsonify({"error": "Yeti unreachable"}), 503

@app.route('/api/set_port', methods=['POST'])
@login_required
@admin_required
def set_port():
    payload = request.json
    port = payload["port"]
    enable = payload["enable"]
    yeti_ip = session.get('yeti_ip', '10.1.1.1')
    value = 1 if enable else 0
    key_map = {
        "ac": "acPortStatus",
        "usb": "usbPortStatus",
        "12v": "v12PortStatus"
    }
    try:
        response_data = {key_map[port]: value}
        r = requests.post(
            f"http://{yeti_ip}/state",
            json=response_data,
            headers={'Content-Type': 'application/json'},
            timeout=3
        )
        success = r.status_code < 400
        print(f"SET {key_map[port]}={value} HTTP {r.status_code} Response: {r.text}")
        return jsonify({"success": success})
    except Exception as e:
        print(f"SET ERROR: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/delete_logs', methods=['POST'])
@login_required
@admin_required
def delete_logs():
    data = request.json
    period = data.get('period')
    value = data.get('value')

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # 🕘 HEURE : "2026-01-23 09"
        if period == 'hour':
            cursor.execute("""
                DELETE FROM logs
                WHERE strftime('%Y-%m-%d %H', date_heure) = ?
            """, (value,))

        # 📅 JOUR : "2026-01-23"
        elif period == 'day':
            cursor.execute("""
                DELETE FROM logs
                WHERE strftime('%Y-%m-%d', date_heure) = ?
            """, (value,))

        # 📆 MOIS : "2026-01"
        elif period == 'month':
            cursor.execute("""
                DELETE FROM logs
                WHERE strftime('%Y-%m', date_heure) = ?
            """, (value,))

        conn.commit()
        deleted = cursor.rowcount

        print("DELETE OK =>", period, value, "=>", deleted)

        return jsonify({
            "success": True,
            "deleted": deleted
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        conn.close()




@app.route('/')
def index():
    """Route racine - redirige toujours vers login"""
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    period = request.args.get('period', 'hour')
    view_type = request.args.get('view', 'table')
    selected_date = request.args.get('date', '')
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT strftime('%Y-%m-%d', date_heure) as date FROM logs ORDER BY date DESC")
    available_dates = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("""
    SELECT DISTINCT 
        strftime('%Y-W%W', date_heure) as week,
        MIN(date(date_heure)) as week_start
    FROM logs 
    GROUP BY strftime('%Y-W%W', date_heure)
    ORDER BY week DESC
    """)
    available_weeks = cursor.fetchall()
    
    cursor.execute("SELECT DISTINCT strftime('%Y-%m', date_heure) as month FROM logs ORDER BY month DESC LIMIT 6")
    available_months = [row[0] for row in cursor.fetchall()]
    
    data = []
    minmax_data = None
    title = "Par défaut"
    chart_labels = []
    chart_conso = []
    chart_temps = []
    chart_watts_in = []
    chart_rows = []

    
    if period == 'hour':
        if selected_date:
            query = """
                SELECT 
                    strftime('%H:00', date_heure) as periode,
                    AVG(wattsOut) as total_conso_wh,
                    AVG(temperature) as avg_temp,
                    AVG(wattsIn) as avg_watts_in
                FROM logs 
                WHERE strftime('%Y-%m-%d', date_heure) = ?
                GROUP BY strftime('%H', date_heure)
                ORDER BY periode ASC
            """
            cursor.execute(query, (selected_date,))
            data = cursor.fetchall()
            minmax_query = """
                SELECT 
                    MIN(wattsIn) as min_watts_in,
                    MAX(wattsIn) as max_watts_in,
                    MIN(wattsOut) as min_conso,
                    MAX(wattsOut) as max_conso
                FROM logs 
                WHERE strftime('%Y-%m-%d', date_heure) = ?
            """
            cursor.execute(minmax_query, (selected_date,))
            minmax_data = cursor.fetchone()
            title = f"Par heure - {selected_date}"
        else:
            query = """
                SELECT 
                    strftime('%Y-%m-%d %H:00', date_heure) as periode,
                    AVG(wattsOut) as total_conso_wh,
                    AVG(temperature) as avg_temp,
                    AVG(wattsIn) as avg_watts_in
                FROM logs 
                WHERE date_heure >= datetime('now', '-24 hours')
                GROUP BY strftime('%Y-%m-%d %H', date_heure)
                ORDER BY periode ASC
            """
            cursor.execute(query)
            data = cursor.fetchall()
            minmax_query = """
                SELECT 
                    MIN(wattsIn) as min_watts_in,
                    MAX(wattsIn) as max_watts_in,
                    MIN(wattsOut) as min_conso,
                    MAX(wattsOut) as max_conso
                FROM logs 
                WHERE date_heure >= datetime('now', '-24 hours')
            """
            cursor.execute(minmax_query)
            minmax_data = cursor.fetchone()
            title = "Par heure - Dernières 24h"
            
    elif period == 'day':
        if selected_date:
            year, week_num = selected_date.split('-W')
            week_filter = f"{year}-W{week_num}"
            query = """
                SELECT 
                    strftime('%Y-%m-%d', date_heure) as periode,
                    AVG(wattsOut) as total_conso_wh,
                    AVG(temperature) as avg_temp,
                    AVG(wattsIn) as avg_watts_in
                FROM logs 
                WHERE strftime('%Y-W%W', date_heure) = ?
                GROUP BY strftime('%Y-%m-%d', date_heure)
                ORDER BY periode ASC
            """
            cursor.execute(query, (week_filter,))
            data = cursor.fetchall()
            minmax_query = """
                SELECT 
                    MIN(hourly_min_watts_in) as min_watts_in,
                    MAX(hourly_max_watts_in) as max_watts_in,
                    MIN(hourly_min_conso) as min_conso,
                    MAX(hourly_max_conso) as max_conso
                FROM (
                    SELECT 
                        MIN(wattsIn) as hourly_min_watts_in,
                        MAX(wattsIn) as hourly_max_watts_in,
                        MIN(wattsOut) as hourly_min_conso,
                        MAX(wattsOut) as hourly_max_conso
                    FROM logs 
                    WHERE strftime('%Y-W%W', date_heure) = ?
                    GROUP BY strftime('%Y-%m-%d %H', date_heure)
                )
            """
            cursor.execute(minmax_query, (week_filter,))
            minmax_data = cursor.fetchone()
            title = f"Par jour - Semaine {week_num}/{year}"
        else:
            query = """
                SELECT 
                    strftime('%Y-%m-%d', date_heure) as periode,
                    AVG(wattsOut) as total_conso_wh,
                    AVG(temperature) as avg_temp,
                    AVG(wattsIn) as avg_watts_in
                FROM logs 
                WHERE date_heure >= datetime('now', '-7 days')
                GROUP BY strftime('%Y-%m-%d', date_heure)
                ORDER BY periode ASC
            """
            cursor.execute(query)
            data = cursor.fetchall()
            minmax_query = """
                SELECT 
                    MIN(hourly_min_watts_in) as min_watts_in,
                    MAX(hourly_max_watts_in) as max_watts_in,
                    MIN(hourly_min_conso) as min_conso,
                    MAX(hourly_max_conso) as max_conso
                FROM (
                    SELECT 
                        MIN(wattsIn) as hourly_min_watts_in,
                        MAX(wattsIn) as hourly_max_watts_in,
                        MIN(wattsOut) as hourly_min_conso,
                        MAX(wattsOut) as hourly_max_conso
                    FROM logs 
                    WHERE date_heure >= datetime('now', '-7 days')
                    GROUP BY strftime('%Y-%m-%d %H', date_heure)
                )
            """
            cursor.execute(minmax_query)
            minmax_data = cursor.fetchone()
            title = "Par jour - 7 derniers jours"
    else:
        if selected_date:
            months_list = selected_date.split(',')
            placeholders = ','.join(['?' for _ in months_list])
            query = f"""
                SELECT 
                    strftime('%m/%Y', date_heure) as periode,
                    AVG(wattsOut) as total_conso_wh,
                    AVG(temperature) as avg_temp,
                    AVG(wattsIn) as avg_watts_in
                FROM logs 
                WHERE strftime('%Y-%m', date_heure) IN ({placeholders})
                GROUP BY strftime('%Y-%m', date_heure)
                ORDER BY periode ASC
            """
            cursor.execute(query, months_list)
            data = cursor.fetchall()
            minmax_query = f"""
                SELECT 
                    MIN(daily_min_watts_in) as min_watts_in,
                    MAX(daily_max_watts_in) as max_watts_in,
                    MIN(daily_min_conso) as min_conso,
                    MAX(daily_max_conso) as max_conso
                FROM (
                    SELECT 
                        MIN(wattsIn) as daily_min_watts_in,
                        MAX(wattsIn) as daily_max_watts_in,
                        MIN(wattsOut) as daily_min_conso,
                        MAX(wattsOut) as daily_max_conso
                    FROM logs 
                    WHERE strftime('%Y-%m', date_heure) IN ({placeholders})
                    GROUP BY strftime('%Y-%m-%d', date_heure)
                )
            """
            cursor.execute(minmax_query, months_list)
            minmax_data = cursor.fetchone()
            title = "Par mois - Sélection personnalisée"
        else:
            query = """
                SELECT 
                    strftime('%m/%Y', date_heure) as periode,
                    AVG(wattsOut) as total_conso_wh,
                    AVG(temperature) as avg_temp,
                    AVG(wattsIn) as avg_watts_in
                FROM logs 
                WHERE date_heure >= datetime('now', '-6 months')
                GROUP BY strftime('%Y-%m', date_heure)
                ORDER BY periode ASC
            """
            cursor.execute(query)
            data = cursor.fetchall()
            minmax_query = """
                SELECT 
                    MIN(daily_min_watts_in) as min_watts_in,
                    MAX(daily_max_watts_in) as max_watts_in,
                    MIN(daily_min_conso) as min_conso,
                    MAX(daily_max_conso) as max_conso
                FROM (
                    SELECT 
                        MIN(wattsIn) as daily_min_watts_in,
                        MAX(wattsIn) as daily_max_watts_in,
                        MIN(wattsOut) as daily_min_conso,
                        MAX(wattsOut) as daily_max_conso
                    FROM logs 
                    WHERE date_heure >= datetime('now', '-6 months')
                    GROUP BY strftime('%Y-%m-%d', date_heure)
                )
            """
            cursor.execute(minmax_query)
            minmax_data = cursor.fetchone()
            title = "Par mois - 6 derniers mois"

    if data:
        watts_in_values = [row[3] for row in data if row[3] is not None]
        avg_watts_in = sum(watts_in_values) / len(watts_in_values) if watts_in_values else 0
        
        conso_values = [row[1] for row in data if row[1] is not None]
        avg_conso_wh = sum(conso_values) / len(conso_values) if conso_values else 0
        
        if minmax_data:
            min_watts_in = minmax_data[0] if minmax_data[0] is not None else 0
            max_watts_in = minmax_data[1] if minmax_data[1] is not None else 0
            min_conso_wh = minmax_data[2] if minmax_data[2] is not None else 0
            max_conso_wh = minmax_data[3] if minmax_data[3] is not None else 0
        else:
            min_watts_in = max_watts_in = min_conso_wh = max_conso_wh = 0
    else:
        avg_watts_in = min_watts_in = max_watts_in = 0
        avg_conso_wh = min_conso_wh = max_conso_wh = 0

    cursor.execute("""
        SELECT socPercent, wattsOut, wattsIn, temperature, whStored
        FROM logs 
        ORDER BY date_heure DESC
        LIMIT 1
    """)
    current = cursor.fetchone()
    conn.close()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if period == 'hour':
        if selected_date:
            cursor.execute("""
                SELECT date_heure, wattsOut, temperature, wattsIn
                FROM logs
                WHERE strftime('%Y-%m-%d', date_heure) = ?
                ORDER BY date_heure ASC
            """, (selected_date,))
        else:
            cursor.execute("""
                SELECT date_heure, wattsOut, temperature, wattsIn
                FROM logs
                WHERE date_heure >= datetime('now', '-24 hours')
                ORDER BY date_heure ASC
            """)

    elif period == 'day':
        if selected_date and '-W' in selected_date:
            year, week_num = selected_date.split('-W')
            week_filter = f"{year}-W{week_num}"
            cursor.execute("""
                SELECT date_heure, wattsOut, temperature, wattsIn
                FROM logs
                WHERE strftime('%Y-W%W', date_heure) = ?
                ORDER BY date_heure ASC
            """, (week_filter,))
        else:
            cursor.execute("""
                SELECT date_heure, wattsOut, temperature, wattsIn
                FROM logs
                WHERE date_heure >= datetime('now', '-7 days')
                ORDER BY date_heure ASC
            """)

    else:
        if selected_date:
            months_list = selected_date.split(',')
            placeholders = ','.join(['?' for _ in months_list])
            query = f"""
                SELECT date_heure, wattsOut, temperature, wattsIn
                FROM logs
                WHERE strftime('%Y-%m', date_heure) IN ({placeholders})
                ORDER BY date_heure ASC
            """
            cursor.execute(query, months_list)
        else:
            cursor.execute("""
                SELECT date_heure, wattsOut, temperature, wattsIn
                FROM logs
                WHERE date_heure >= datetime('now', '-6 months')
                ORDER BY date_heure ASC
            """)

    chart_rows = cursor.fetchall()
    conn.close()

    chart_labels = []
    chart_conso = []
    chart_temps = []
    chart_watts_in = []

    from datetime import datetime

    for row in chart_rows:
        date_str = row[0]

        if date_str is None:
            label = "???"
        else:
            try:
                dt = datetime.fromisoformat(date_str)
                if period == 'hour':
                    label = dt.strftime('%H:%M')
                elif period == 'day':
                    label = dt.strftime('%d/%m %H:%M')
                else:
                    label = dt.strftime('%d/%m')
            except ValueError:
                label = date_str[:19]

        chart_labels.append(label)
        chart_conso.append(row[1] if row[1] is not None else 0)
        chart_temps.append(row[2] if row[2] is not None else 0)
        chart_watts_in.append(row[3] if row[3] is not None else 0)

    if not chart_labels:
        chart_labels = chart_conso = chart_temps = chart_watts_in = []
    
    soc = current[0] if current else 0
    watts_out = current[1] if current else 0
    watts_in = current[2] if current else 0
    temp = current[3] if current else 0
    wh_stored = current[4] if current else 0
    
    yeti_ip = session.get('yeti_ip', yeti_ip_detected or '10.1.1.1')
    mode = session.get('mode', 'Auto-détecté')
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard - Smart Battery Insights</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                background: linear-gradient(135deg, #0a1628 0%, #1a2332 100%);
                color: #e0e6ed;
                min-height: 100vh;
                padding: 20px;
            }
            
            /* Header */
            .header { 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                max-width: 1400px;
                margin: 0 auto 30px;
                padding: 25px 0;
                position: relative;
            }
            .header::after {
                content: '';
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                height: 2px;
                background: linear-gradient(90deg, transparent, rgba(0, 217, 255, 0.8) 50%, transparent);
            }
            .logo { display: flex; align-items: center; gap: 15px; }
            .logo-icon { font-size: 48px; }
            .device-name { font-size: 24px; font-weight: bold; color: #ffffff; }
            .status { font-size: 14px; font-weight: 500; }
            .status.connected { color: #00ff88; }
            .status.disconnected { color: #ff5555; }
            
            /* Menu */
            .menu-container { position: relative; }
            .menu-btn {
                background: rgba(0, 217, 255, 0.2);
                border: 1px solid #00d9ff;
                color: #00d9ff;
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 14px;
                font-weight: 500;
            }
            .menu-btn:hover { background: rgba(0, 217, 255, 0.3); }
            .menu-dropdown {
                display: none;
                position: absolute;
                top: 100%;
                right: 0;
                margin-top: 10px;
                background: rgba(26, 35, 50, 0.95);
                border: 1px solid rgba(0, 217, 255, 0.3);
                border-radius: 10px;
                min-width: 200px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
                z-index: 1000;
            }
            .menu-dropdown.show { display: block; }
            .menu-item {
                padding: 12px 20px;
                color: #e0e6ed;
                text-decoration: none;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .menu-item:hover { background: rgba(0, 217, 255, 0.1); color: #00d9ff; }
            .menu-item.logout:hover { background: rgba(255, 85, 85, 0.1); }
            
            /* 4 jauges alignées – sans cadre extérieur */
            .gauges-row {
                display: flex;
                justify-content: center;
                gap: 40px;
                flex-wrap: wrap;
                margin: 0 auto 50px;
                max-width: 1400px;
            }
            .gauge-card {
                display: flex;
                flex-direction: column;
                align-items: center;
                min-width: 220px;
            }
            .gauge-wrapper {
                position: relative;
                width: 220px;
                height: 220px;
            }
            .gauge-svg {
                width: 100%;
                height: 100%;
                transform: rotate(-90deg);
            }
            .gauge-bg {
                fill: none;
                stroke: #2a374a;
                stroke-width: 16;
            }
            .gauge-fill {
                fill: none;
                stroke-width: 16;
                stroke-linecap: round;
            }
            .gauge-fill.cyan   { stroke: #00d9ff; }
            .gauge-fill.orange { stroke: #ff9500; }
            .gauge-fill.green  { stroke: #00ff88; }
            .gauge-fill.purple { stroke: #9d4edd; }

            .gauge-text {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-size: 48px;
                font-weight: 700;
                color: #ffffff;
                text-align: center;
                line-height: 1;
            }
            .gauge-text .unit {
                font-size: 22px;
                opacity: 0.75;
                margin-left: 4px;
            }
            .gauge-icon {
                position: absolute;
                bottom: 38px;           /* icônes plus basses */
                left: 50%;
                transform: translateX(-50%);
                font-size: 38px;
                opacity: 0.9;
            }
            .gauge-label {
                margin-top: 14px;
                font-size: 14px;
                color: #a0aec0;
                text-transform: uppercase;
                letter-spacing: 0.6px;
                text-align: center;
            }
            
            /* Responsive jauges */
            @media (max-width: 1100px) {
                .gauges-row { gap: 30px; }
                .gauge-wrapper { width: 200px; height: 200px; }
                .gauge-text { font-size: 42px; }
                .gauge-icon { font-size: 34px; bottom: 35px; }
            }
            @media (max-width: 820px) {
                .gauges-row { flex-direction: column; align-items: center; gap: 55px; }
            }
            
            /* Carte principale */
            .main-card {
                background: rgba(26, 35, 50, 0.6);
                border-radius: 20px;
                padding: 30px;
                margin: 0 auto 30px;
                max-width: 1400px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            .card-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 25px;
                padding-bottom: 20px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                flex-wrap: wrap;
                gap: 15px;
            }
            .card-title-section {
                flex: 1;
            }
            .card-title {
                color: #e0e6ed;
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 5px;
            }
            .card-subtitle {
                color: #a0aec0;
                font-size: 14px;
            }
            .filters-inline {
                display: flex;
                gap: 15px;
                align-items: center;
                flex-wrap: wrap;
            }
            .filter-group {
                display: flex;
                flex-direction: column;
                gap: 5px;
            }
            .filter-label-mini {
                color: #a0aec0;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            select {
                padding: 10px 35px 10px 12px;
                background: rgba(26, 35, 50, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                color: #e0e6ed;
                font-size: 13px;
                cursor: pointer;
                appearance: none;
                background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2300d9ff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
                background-repeat: no-repeat;
                background-position: right 8px center;
                background-size: 18px;
                min-width: 140px;
            }
            select:focus {
                outline: none;
                border-color: #00d9ff;
                box-shadow: 0 0 10px rgba(0, 217, 255, 0.3);
            }
            select option {
                background: rgba(26, 35, 50, 0.98);
                color: #e0e6ed;
                padding: 8px;
            }
            .ok-btn {
                padding: 10px 18px;
                background: linear-gradient(135deg, #00d9ff 0%, #0099cc 100%);
                border: none;
                border-radius: 8px;
                color: white;
                font-weight: bold;
                cursor: pointer;
                margin-top: 18px;
                font-size: 13px;
            }
            .ok-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0, 217, 255, 0.4);
            }
            
            /* Tableau (exactement le même qu'avant) */
            .data-table { width: 100%; border-collapse: collapse; }
            .data-table thead { 
                background: rgba(0, 217, 255, 0.1); 
                position: sticky; 
                top: 0; 
                z-index: 10; 
            }
            .data-table th { 
                padding: 15px; 
                text-align: center; 
                font-weight: bold; 
                color: #e0e6ed; 
                border-bottom: 2px solid rgba(0, 217, 255, 0.3); 
            }
            .data-table tbody tr { 
                border-bottom: 1px solid rgba(255, 255, 255, 0.05); 
                transition: all 0.2s ease; 
            }
            .data-table tbody tr:hover { 
                background: rgba(0, 217, 255, 0.05); 
            }
            .data-table td { 
                padding: 12px 15px; 
                color: #e0e6ed; 
                text-align: center; 
            }
            
            /* Stats moyennes */
            .data-grid { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
                gap: 20px; 
                margin: 20px auto; 
                max-width: 1400px; 
            }
            .data-section { 
                background: rgba(26, 35, 50, 0.6); 
                border-radius: 20px; 
                padding: 30px; 
                border: 1px solid rgba(255, 255, 255, 0.1); 
            }
            .data-section h3 { 
                color: #00d9ff; 
                margin-bottom: 20px; 
                font-size: 18px; 
                text-transform: uppercase; 
                letter-spacing: 1px; 
                text-align: center; 
            }
            .data-row { 
                display: flex; 
                justify-content: space-between; 
                padding: 12px 0; 
                border-bottom: 1px solid rgba(255, 255, 255, 0.05); 
            }
            .data-row:last-child { border-bottom: none; }
            .data-label { color: #a0aec0; }
            .data-value { color: #e0e6ed; font-weight: bold; }
            
            /* Ports alignés avec les autres sections */
            .output-ports {
                background: rgba(26, 35, 50, 0.6);
                border-radius: 20px;
                padding: 30px;
                margin: 0 auto 30px;
                max-width: 1400px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            .output-ports h3 { 
                color: #00d9ff; 
                text-align: center; 
                margin-bottom: 20px; 
                font-size: 18px; 
                text-transform: uppercase; 
            }
            .port-item { 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                padding: 15px; 
                background: rgba(255, 255, 255, 0.05); 
                margin-bottom: 15px; 
                border-radius: 10px; 
            }
            .port-info { display: flex; align-items: center; gap: 15px; }
            .port-icon { font-size: 24px; }
            .port-name { font-weight: bold; color: #e0e6ed; }
            .port-status { font-size: 12px; color: #a0aec0; }
            .port-status.on { color: #00ff88; }
            .port-status.off { color: #ff5555; }
            .toggle-switch { 
                position: relative; 
                width: 60px; 
                height: 30px; 
                background: #ccc; 
                border-radius: 15px; 
                cursor: pointer; 
                transition: background 0.3s; 
            }
            .toggle-switch.active { background: #00ff88; }
            .toggle-slider { 
                position: absolute; 
                top: 3px; 
                left: 3px; 
                width: 24px; 
                height: 24px; 
                background: white; 
                border-radius: 50%; 
                transition: transform 0.3s; 
            }
            .toggle-switch.active .toggle-slider { transform: translateX(30px); }
            .toggle-switch.disabled { opacity: 0.5; cursor: not-allowed; }
            .access-denied { 
                text-align: center; 
                padding: 15px; 
                background: rgba(255, 215, 0, 0.1); 
                border: 1px solid rgba(255, 215, 0, 0.3); 
                border-radius: 10px; 
                margin-bottom: 20px; 
                color: #ffd700; 
            }
            
            @media (max-width: 768px) { 
                .filters-inline { flex-direction: column; align-items: stretch; }
                .card-header { flex-direction: column; align-items: stretch; }
                .gauges-row { gap: 30px; }
                .gauge-wrapper { width: 220px; height: 220px; }
                .gauge-text { font-size: 48px; }
            }
        </style>
    </head>
    <body>
    
    <div class="header">
        <div class="logo">
            <div class="logo-icon">🔋</div>
            <div>
                <div class="device-name">Yeti 1500X (120V)</div>
                <div class="status {{ 'connected' if is_connected else 'disconnected' }}" id="connection-status">
                    {{ '🟢 Connecté' if is_connected else '🔴 Non Connecté' }}
                </div>
            </div>
        </div>
        
        <div class="menu-container">
            <button class="menu-btn" onclick="document.getElementById('menuDropdown').classList.toggle('show')">
                ⚙ Menu
            </button>
            <div class="menu-dropdown" id="menuDropdown">
                {% if user_role == 'admin' %}
                <a href="/config" class="menu-item">
                    <span>⚙️</span> Configuration
                </a>
                <a href="/users" class="menu-item">
                    <span>👥</span> Utilisateurs
                </a>
                {% endif %}
                <a href="/logout" class="menu-item logout">
                    <span>🚪</span> Déconnexion
                </a>
            </div>
        </div>
    </div>
    
    <!-- 4 jauges alignées horizontalement -->
    <div class="gauges-row">
        <div class="gauge-card">
            <div class="gauge-wrapper">
                <svg class="gauge-svg" viewBox="0 0 220 220">
                    <circle class="gauge-bg" cx="110" cy="110" r="95"/>
                    <circle class="gauge-fill cyan" cx="110" cy="110" r="95"
                            stroke-dasharray="596" stroke-dashoffset="{{ (596 * (100 - soc)) / 100 | round(1) }}"></circle>
                </svg>
                <div class="gauge-text">{{ soc|round(0)|int }}<span class="unit">%</span></div>
                <div class="gauge-icon">🔋</div>
            </div>
            <div class="gauge-label">Charge Batterie</div>
        </div>
        
        <div class="gauge-card">
            <div class="gauge-wrapper">
                <svg class="gauge-svg" viewBox="0 0 220 220">
                    <circle class="gauge-bg" cx="110" cy="110" r="95"/>
                    <circle class="gauge-fill orange" cx="110" cy="110" r="95"
                            stroke-dasharray="596" stroke-dashoffset="{{ (596 * (2000 - watts_out)) / 2000 | round(1) if watts_out <= 2000 else 0 }}"></circle>
                </svg>
                <div class="gauge-text">{{ watts_out|round(0)|int }}<span class="unit">W</span></div>
                <div class="gauge-icon">⚡</div>
            </div>
            <div class="gauge-label">Consommation</div>
        </div>
        
        <div class="gauge-card">
            <div class="gauge-wrapper">
                <svg class="gauge-svg" viewBox="0 0 220 220">
                    <circle class="gauge-bg" cx="110" cy="110" r="95"/>
                    <circle class="gauge-fill green" cx="110" cy="110" r="95"
                            stroke-dasharray="596" stroke-dashoffset="{{ (596 * (1500 - watts_in)) / 1500 | round(1) if watts_in <= 1500 else 0 }}"></circle>
                </svg>
                <div class="gauge-text">{{ watts_in|round(0)|int }}<span class="unit">W</span></div>
                <div class="gauge-icon">🔌</div>
            </div>
            <div class="gauge-label">Charge Entrante</div>
        </div>
        
        <div class="gauge-card">
            <div class="gauge-wrapper">
                <svg class="gauge-svg" viewBox="0 0 220 220">
                    <circle class="gauge-bg" cx="110" cy="110" r="95"/>
                    <circle class="gauge-fill purple" cx="110" cy="110" r="95"
                            stroke-dasharray="596" stroke-dashoffset="{{ (596 * (60 - temp)) / 60 | round(1) if temp <= 60 else 0 }}"></circle>
                </svg>
                <div class="gauge-text">{{ temp|round(1) }}<span class="unit">°C</span></div>
                <div class="gauge-icon">🌡️</div>
            </div>
            <div class="gauge-label">Température</div>
        </div>
    </div>

    <!-- Carte historique + filtres (exactement comme avant) -->
    <div class="main-card">
        <div class="card-header">
            <div class="card-title-section">
                <div class="card-title">HISTORIQUE ÉNERGÉTIQUE</div>
                <div class="card-subtitle">{{ title }}</div>
            </div>
            
            <div class="filters-inline">
                <div class="filter-group">
                    <div class="filter-label-mini">Période</div>
                    <select id="periodSelect" onchange="changePeriod()">
                        <option value="hour" {% if period=='hour' %}selected{% endif %}>Heure</option>
                        <option value="day" {% if period=='day' %}selected{% endif %}>Jour</option>
                        <option value="month" {% if period=='month' %}selected{% endif %}>Mois</option>
                    </select>
                </div>
                
                <div class="filter-group">
                    <div class="filter-label-mini">Filtre</div>
                    {% if period == 'hour' %}
                        <select id="dateFilter" onchange="applyFilter()">
                            <option value="">24 heures</option>
                            {% for date in available_dates %}
                                <option value="{{ date }}" {% if selected_date == date %}selected{% endif %}>{{ date }}</option>
                            {% endfor %}
                        </select>
                    {% elif period == 'day' %}
                        <select id="weekFilter" onchange="applyFilter()">
                            <option value="">7 jours</option>
                            {% for week, week_start in available_weeks %}
                                <option value="{{ week }}" {% if selected_date == week %}selected{% endif %}>
                                    Sem. {{ week_start }}
                                </option>
                            {% endfor %}
                        </select>
                    {% elif period == 'month' %}
                        <select id="monthFilter" multiple size="1">
                            {% for month in available_months %}
                                <option value="{{ month }}" {% if selected_date and month in selected_date.split(',') %}selected{% endif %}>{{ month }}</option>
                            {% endfor %}
                        </select>
                        <button class="ok-btn" onclick="applyMonthFilter()">OK</button>
                    {% endif %}
                </div>
                
                <div class="filter-group">
                    <div class="filter-label-mini">Affichage</div>
                    <select id="viewSelect" onchange="changeView()">
                        <option value="table" {% if view_type=='table' %}selected{% endif %}>Tableau</option>
                        <option value="chart" {% if view_type=='chart' %}selected{% endif %}>Graphique</option>
                    </select>
                </div>
            </div>
        </div>
        
        {% if data|length == 0 %}
            <div class="no-data">
                <div class="no-data-icon">📭</div>
                <p>Aucune donnée disponible pour cette période</p>
            </div>
        {% else %}
            {% if view_type == 'table' %}
                <div style="max-height: 500px; overflow-y: auto;">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Période</th>
                                <th style="color: #00ff88;">Charge (W)</th>
                                <th style="color: #00d9ff;">Conso (Wh)</th>
                                <th style="color: #9d4edd;">Temp (°C)</th>
                                {% if user_role == 'admin' %}
                                <th>❌</th>
                                {% endif %}
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in data %}
                            <tr>
                                <td><strong>{{ row[0] }}</strong></td>
                                <td style="color: #00ff88;">{{ row[3]|round(1) if row[3] else 0 }}</td>
                                <td style="color: #00d9ff;">{{ row[1]|round(1) if row[1] else 0 }}</td>
                                <td style="color: #9d4edd;">{{ row[2]|round(1) if row[2] else 0 }}</td>
                                {% if user_role == 'admin' %}
                                <td>
                                    <button onclick="deleteRow('{{ row[0] }}')">❌</button>
                                </td>
                                {% endif %}
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            {% else %}
                <div style="position: relative; height: 450px;">
                    <canvas id="energyChart"></canvas>
                </div>
            {% endif %}
        {% endif %}
    </div>

    <div class="data-grid">
        <div class="data-section">
            <h3>🔌 Charge Entrante</h3>
            <div class="data-row">
                <span class="data-label">Moyenne:</span>
                <span class="data-value" style="color: #00ff88;">{{ avg_watts_in|round(2) }} W</span>
            </div>
            <div class="data-row">
                <span class="data-label">Minimum:</span>
                <span class="data-value" style="color: #00ff88;">{{ min_watts_in|round(2) }} W</span>
            </div>
            <div class="data-row">
                <span class="data-label">Maximum:</span>
                <span class="data-value" style="color: #00ff88;">{{ max_watts_in|round(2) }} W</span>
            </div>
        </div>
        
        <div class="data-section">
            <h3>⚡ Consommation</h3>
            <div class="data-row">
                <span class="data-label">Moyenne:</span>
                <span class="data-value" style="color: #00d9ff;">{{ avg_conso_wh|round(2) }} Wh</span>
            </div>
            <div class="data-row">
                <span class="data-label">Minimum:</span>
                <span class="data-value" style="color: #00d9ff;">{{ min_conso_wh|round(2) }} Wh</span>
            </div>
            <div class="data-row">
                <span class="data-label">Maximum:</span>
                <span class="data-value" style="color: #00d9ff;">{{ max_conso_wh|round(2) }} Wh</span>
            </div>
        </div>
    </div>
    
    <!-- Ports alignés comme les autres sections -->
    <div class="output-ports">
        <h3>⚡ CONTRÔLE DES PORTS DE SORTIE</h3>
        
        {% if user_role != 'admin' %}
        <div class="access-denied">
            ⚠️ Vous êtes en mode lecture seule. Seuls les administrateurs peuvent modifier les ports.
        </div>
        {% endif %}
        
        <div class="port-item">
            <div class="port-info">
                <div class="port-icon">🔌</div>
                <div class="port-details">
                    <div class="port-name">12V DC</div>
                    <div class="port-status off" id="status-12v">Status: Off</div>
                </div>
            </div>
            <div class="toggle-switch {% if user_role != 'admin' %}disabled{% endif %}" id="toggle-12v" onclick="{% if user_role == 'admin' %}togglePort('12v'){% else %}showAccessDenied(){% endif %}">
                <div class="toggle-slider"></div>
            </div>
        </div>
        
        <div class="port-item">
            <div class="port-info">
                <div class="port-icon">📱</div>
                <div class="port-details">
                    <div class="port-name">USB</div>
                    <div class="port-status off" id="status-usb">Status: Off</div>
                </div>
            </div>
            <div class="toggle-switch {% if user_role != 'admin' %}disabled{% endif %}" id="toggle-usb" onclick="{% if user_role == 'admin' %}togglePort('usb'){% else %}showAccessDenied(){% endif %}">
                <div class="toggle-slider"></div>
            </div>
        </div>
        
        <div class="port-item">
            <div class="port-info">
                <div class="port-icon">🏠</div>
                <div class="port-details">
                    <div class="port-name">AC 120V</div>
                    <div class="port-status off" id="status-ac">Status: Off</div>
                </div>
            </div>
            <div class="toggle-switch {% if user_role != 'admin' %}disabled{% endif %}" id="toggle-ac" onclick="{% if user_role == 'admin' %}togglePort('ac'){% else %}showAccessDenied(){% endif %}">
                <div class="toggle-slider"></div>
            </div>
        </div>
    </div>

    <script>
        // 🚫 DÉCONNEXION FORCÉE SI RETOUR ARRIÈRE
        (function() {
            // Détecte si l'utilisateur clique sur retour
            window.addEventListener('pageshow', function(event) {
                if (event.persisted || (window.performance && window.performance.navigation.type === 2)) {
                    // Page chargée depuis le cache (retour arrière) -> DÉCONNEXION
                    window.location.href = '/logout';
                }
            });
            
            // Empêche complètement l'historique de navigation
            if (typeof history.pushState === "function") {
                history.pushState(null, null, window.location.href);
                window.onpopstate = function() {
                    // Si l'utilisateur essaie de faire retour -> DÉCONNEXION IMMÉDIATE
                    window.location.replace('/logout');
                };
            }
        })();
        
        const userRole = '{{ user_role }}';
        const portStates = { '12v': false, 'usb': false, 'ac': false };
        
        function toggleMenu() {
            document.getElementById('menuDropdown').classList.toggle('show');
        }
        
        window.onclick = function(event) {
            if (!event.target.matches('.menu-btn')) {
                var dropdowns = document.getElementsByClassName("menu-dropdown");
                for (var i = 0; i < dropdowns.length; i++) {
                    var openDropdown = dropdowns[i];
                    if (openDropdown.classList.contains('show')) {
                        openDropdown.classList.remove('show');
                    }
                }
            }
        }
        
        function showAccessDenied() {
            alert('⚠️ Accès refusé\\n\\nSeuls les administrateurs peuvent modifier les ports.');
        }
        
        function changePeriod() {
            const period = document.getElementById('periodSelect').value;
            const view = '{{ view_type }}';
            window.location.href = `?period=${period}&view=${view}&date=`;
        }
        
        function changeView() {
            const view = document.getElementById('viewSelect').value;
            const period = '{{ period }}';
            const date = '{{ selected_date }}';
            window.location.href = `?period=${period}&view=${view}&date=${date}`;
        }
        
function deleteRow(value) {
    if (!confirm("Supprimer toutes les données associées ?")) return;

    let period = "{{ period }}";
    let sendValue = value;

    // 🔥 HEURE : "09:00" → "2026-01-09 09"
    if (period === "hour") {
        let selectedDate = document.getElementById("dateFilter")?.value;
        if (!selectedDate) {
            alert("Sélectionne une date d'abord");
            return;
        }
        let hour = value.substring(0, 2);
        sendValue = selectedDate + " " + hour;
    }

    // 🔥 JOUR : rien à changer (YYYY-MM-DD)
    if (period === "day") {
        sendValue = value;
    }

    // 🔥 MOIS : "01/2026" ou "2026-01" → "2026-01"
    if (period === "month") {
        if (value.includes("/")) {
            let parts = value.split("/");
            sendValue = parts[1] + "-" + parts[0];
        }
    }

    fetch('/api/delete_logs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            period: period,
            value: sendValue
        })
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            alert("Suppression OK : " + res.deleted + " lignes");
            location.reload(); // 🔄 rafraîchit l'affichage
        } else {
            alert("Erreur suppression");
        }
    });
}

        function togglePort(port) {
            if (userRole !== 'admin') {
                showAccessDenied();
                return;
            }
            const enable = !portStates[port];
            fetch('/api/set_port', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ port: port, enable: enable })
            })
            .then(r => r.json())
            .then(res => {
                if (res.success) {
                    portStates[port] = enable;
                    updatePortUI(port);
                } else {
                    alert('Erreur lors du changement de port');
                }
            })
            .catch(err => {
                console.error(err);
                alert('Erreur de connexion au Yeti');
            });
        }
        
        function refreshPorts() {
            fetch('/api/ports_state')
                .then(r => r.json())
                .then(data => {
                    portStates['12v'] = !!data['12v'];
                    portStates.usb = !!data.usb;
                    portStates.ac = !!data.ac;
                    updatePortUI('12v');
                    updatePortUI('usb');
                    updatePortUI('ac');
                });
        }
        
        function updatePortUI(port) {
            const toggle = document.getElementById(`toggle-${port}`);
            const status = document.getElementById(`status-${port}`);
            if (portStates[port]) {
                toggle.classList.add('active');
                status.textContent = 'Status: On';
                status.classList.add('on');
                status.classList.remove('off');
            } else {
                toggle.classList.remove('active');
                status.textContent = 'Status: Off';
                status.classList.add('off');
                status.classList.remove('on');
            }
        }
        
        setInterval(refreshPorts, 30000);
        refreshPorts();
        
        function updateStats() {
            fetch('/api/current_stats')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('stat-watts-out').textContent = Math.round(data.watts_out) + 'W';
                    document.getElementById('stat-watts-in').textContent = Math.round(data.watts_in) + 'W';
                    document.getElementById('stat-temp').textContent = data.temp.toFixed(1) + '°C';
                    const statusEl = document.getElementById('connection-status');
                    statusEl.textContent = data.connected ? '🟢 Connecté' : '🔴 Non Connecté';
                    statusEl.className = `status ${data.connected ? 'connected' : 'disconnected'}`;
                });
        }
        setInterval(updateStats, 60000);
        updateStats();
        
        // 🔄 Auto-refresh complet du dashboard toutes les 5 minutes (300000 ms)
        setInterval(function() {
            location.reload();
        }, 300000);
        
        function applyFilter() {
            const period = '{{ period }}';
            const view = '{{ view_type }}';
            let filter = '';
            if (period === 'hour') filter = document.getElementById('dateFilter').value;
            if (period === 'day') filter = document.getElementById('weekFilter').value;
            window.location.href = `?period=${period}&view=${view}&date=${filter}`;
        }
        
        function applyMonthFilter() {
            const period = 'month';
            const view = '{{ view_type }}';
            const select = document.getElementById('monthFilter');
            const selected = Array.from(select.selectedOptions).map(opt => opt.value).join(',');
            window.location.href = `?period=${period}&view=${view}&date=${selected}`;
        }
        
        {% if view_type == 'chart' and data|length > 0 %}
        const ctx = document.getElementById('energyChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: {{ chart_labels|tojson }},
                datasets: [
                    {
                        label: 'Charge Entrante (W)',
                        data: {{ chart_watts_in|tojson }},
                        borderColor: 'rgba(0, 255, 136, 1)',
                        backgroundColor: 'rgba(0, 255, 136, 0.1)',
                        borderWidth: 3,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 2,
                        pointHoverRadius: 5
                    },
                    {
                        label: 'Consommation (Wh)',
                        data: {{ chart_conso|tojson }},
                        borderColor: 'rgba(0, 217, 255, 1)',
                        backgroundColor: 'rgba(0, 217, 255, 0.1)',
                        borderWidth: 3,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 2,
                        pointHoverRadius: 5
                    },
                    {
                        label: 'Température (°C)',
                        data: {{ chart_temps|tojson }},
                        borderColor: 'rgba(157, 78, 221, 1)',
                        backgroundColor: 'rgba(157, 78, 221, 0.1)',
                        borderWidth: 3,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 2,
                        pointHoverRadius: 5
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { beginAtZero: true } },
                plugins: {
                    legend: { labels: { color: '#e0e6ed' } },
                    tooltip: { backgroundColor: 'rgba(26, 35, 50, 0.95)' }
                }
            }
        });
        {% endif %}
    </script>
    </body>
    </html>
    """
    return render_template_string(html, 
                                 period=period, view_type=view_type, selected_date=selected_date, title=title, data=data,
                                 available_dates=available_dates, available_weeks=available_weeks, available_months=available_months,
                                 is_connected=is_connected, soc=soc, watts_out=watts_out, watts_in=watts_in, temp=temp, wh_stored=wh_stored,
                                 avg_watts_in=avg_watts_in, min_watts_in=min_watts_in, max_watts_in=max_watts_in,
                                 avg_conso_wh=avg_conso_wh, min_conso_wh=min_conso_wh, max_conso_wh=max_conso_wh,
                                 chart_labels=chart_labels, chart_watts_in=chart_watts_in, chart_conso=chart_conso, chart_temps=chart_temps,
                                 user_role=session.get('role', 'guest'), username=session.get('username', 'Unknown'))

if __name__ == '__main__':
    print("=" * 60)
    print("🔋 SMART BATTERY INSIGHTS - Initialisation Sécurisée")
    print("=" * 60)
    
    init_db()
    
    yeti_ip_detected, mode_detected, is_connected = show_config_dialog()
    
    time.sleep(0.5)
    
    print(f"✅ Configuration: {mode_detected}")
    print(f"✅ IP sélectionnée: {yeti_ip_detected}")
    print(f"✅ Connexion: {'Établie' if is_connected else 'Non établie'}")
    
    # Note: yeti_ip et mode sont déjà stockés globalement, pas besoin de session ici
    
    print("=" * 60)
    print("🚀 Serveur lancé avec succès!")
    print("📊 Login: http://localhost:5002/login")
    print("⚙️  Config: http://localhost:5002/config (admin only)")
    print(f"🔌 IP configurée: {yeti_ip_detected}")
    print("=" * 60)
    
    def open_browser():
        time.sleep(5)
        site_url = "http://localhost:5002/login"
        try:
            webbrowser.open(site_url)
            print(f"\n🌐 Navigateur ouvert sur {site_url}")
        except Exception as e:
            print(f"\n⚠️ Impossible d'ouvrir le navigateur: {e}")
            print(f"📌 Ouvrez manuellement: {site_url}")

    browser_thread = threading.Thread(target=open_browser)
    browser_thread.start()

    try:
        serve(app, host="127.0.0.1", port=5002)
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du serveur...")
        print("✅ Serveur arrêté proprement")
    except Exception as e:
        print(f"\n❌ Erreur serveur: {e}")