import requests
import sqlite3
import time
from datetime import datetime
import os
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog
import threading

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

# Configuration par défaut
DEFAULT_HOTSPOT_IP = "10.1.1.1"
DEFAULT_RESEAU_IP = "192.168.137.54"
INTERVALLE = 300  # Toutes les 5 min
STATS_INTERVALLE = 3600  # Stats toutes les heures
TIMEOUT_RECONNEXION = 3  # Tentatives avant popup d'erreur

# Colonnes pour la table
CHAMPS = ["date_heure", "whOut", "whStored", "socPercent", "wattsOut", "ampsOut", 
          "wattsIn", "ampsIn", "temperature", "timeToEmptyFull"]


class YetiLogger:
    def __init__(self):
        self.yeti_ip = None
        self.mode = None
        self.running = False
        self.connected = False
        self.erreurs_consecutives = 0
        self.dernier_stats = time.time()
        self.thread = None
        
    def init_db(self):
        """Initialiser la DB avec exactement 2 lignes fixes (1=hotspot, 2=reseau)"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Table des logs (existante)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {', '.join([f"{champ} {'TEXT' if champ == 'date_heure' else 'REAL'}" for champ in CHAMPS])}
            )
        """)
        
        # Table de configuration réseau Yeti - exactement 2 lignes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS yeti_network_config (
                id INTEGER PRIMARY KEY CHECK (id IN (1, 2)),
                mode TEXT NOT NULL,          -- 'hotspot' ou 'reseau'
                ip TEXT NOT NULL,
                is_active INTEGER DEFAULT 0, -- 1 = actuellement utilisé, 0 = pas utilisé
                last_tested_success INTEGER DEFAULT 0,
                last_updated TEXT
            )
        """)
        
        # Insérer les 2 configurations fixes si elles n'existent pas encore
        cursor.execute("SELECT COUNT(*) FROM yeti_network_config")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Créer les 2 lignes fixes
            default_configs = [
                (1, 'hotspot', DEFAULT_HOTSPOT_IP, 0, 0, datetime.now().isoformat()),
                (2, 'reseau', DEFAULT_RESEAU_IP, 0, 0, datetime.now().isoformat())
            ]
            cursor.executemany("""
                INSERT INTO yeti_network_config 
                (id, mode, ip, is_active, last_tested_success, last_updated) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, default_configs)
            print("✅ Configurations réseau initialisées (Hotspot + Réseau).")
        
        conn.commit()
        conn.close()
        print(f"🗄️ Base de données '{DB_FILE}' initialisée.")
    
    def get_config_by_id(self, config_id):
        """Récupère une config par son ID (1 ou 2)"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT mode, ip, is_active, last_tested_success 
            FROM yeti_network_config 
            WHERE id = ?
        """, (config_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    
    def get_active_config(self):
        """Récupère la configuration active (celle avec is_active=1)"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, mode, ip FROM yeti_network_config 
            WHERE is_active = 1 LIMIT 1
        """)
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0], result[1], result[2]  # id, mode, ip
        return None, None, None
    
    def set_active_config(self, config_id, success=True):
        """Active une config (1 ou 2) et désactive l'autre"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Désactiver toutes
        cursor.execute("UPDATE yeti_network_config SET is_active = 0")
        
        # Activer celle choisie
        cursor.execute("""
            UPDATE yeti_network_config 
            SET is_active = 1, last_tested_success = ?, last_updated = ?
            WHERE id = ?
        """, (1 if success else 0, datetime.now().isoformat(), config_id))
        
        conn.commit()
        conn.close()
        
        # Récupérer les infos pour l'affichage
        config = self.get_config_by_id(config_id)
        if config:
            print(f"💾 Configuration active: ID {config_id} ({config[0]}) - {config[1]}")
    
    def update_reseau_ip(self, new_ip):
        """Met à jour l'IP du mode réseau (ID=2) - remplace l'ancienne"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # UPDATE sur ID 2 uniquement, jamais d'INSERT
        cursor.execute("""
            UPDATE yeti_network_config 
            SET ip = ?, last_updated = ?
            WHERE id = 2
        """, (new_ip, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        print(f"🔄 IP Réseau mise à jour: {new_ip} (remplace l'ancienne)")
    
    def selection_ip(self):
        """Popup pour sélectionner l'IP - utilise les 2 lignes fixes"""
        # Vérifier s'il y a une config active
        active_id, active_mode, active_ip = self.get_active_config()
        
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        # Proposer d'utiliser la dernière config active si elle existe
        if active_id and active_mode and active_ip:
            use_saved = messagebox.askyesno(
                "Configuration existante",
                f"Configuration précédente trouvée:\n"
                f"Mode: {active_mode}\n"
                f"IP: {active_ip}\n\n"
                f"Utiliser cette configuration?",
                parent=root
            )
            if use_saved:
                root.destroy()
                return active_ip, active_mode
        
        # Sinon, demander la configuration
        result = messagebox.askyesno(
            "Configuration IP Yeti", 
            "Voulez-vous utiliser le mode Hotspot (10.1.1.1) ?\n\n"
            "Oui = Hotspot\n"
            "Non = Réseau domestique (IP personnalisée)",
            parent=root
        )
        
        if result:
            # Mode Hotspot - ID 1
            ip = DEFAULT_HOTSPOT_IP
            mode = "hotspot"
            self.set_active_config(1, success=False)
        else:
            # Mode Réseau - ID 2
            # Récupérer l'IP actuelle du réseau
            config = self.get_config_by_id(2)
            current_reseau_ip = config[1] if config else DEFAULT_RESEAU_IP
            
            # Demander la nouvelle IP
            new_ip = simpledialog.askstring(
                "IP Réseau", 
                f"Entrez l'IP du Yeti sur le réseau domestique\n(actuelle: {current_reseau_ip}):",
                initialvalue=current_reseau_ip,
                parent=root
            )
            
            if not new_ip:
                new_ip = current_reseau_ip
            
            # Si nouvelle IP différente, mettre à jour (UPDATE, pas INSERT)
            if new_ip != current_reseau_ip:
                self.update_reseau_ip(new_ip)
            
            ip = new_ip
            mode = "reseau"
            self.set_active_config(2, success=False)
        
        root.destroy()
        return ip, mode
    
    def verifier_connexion_initiale(self):
        """Vérifie la connexion et met à jour le statut"""
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        try:
            response = requests.get(f"http://{self.yeti_ip}/state", timeout=10)
            data = response.json()
            
            if data:
                self.connected = True
                self.erreurs_consecutives = 0
                
                # Déterminer l'ID selon le mode et marquer comme succès
                config_id = 1 if self.mode == "hotspot" else 2
                self.set_active_config(config_id, success=True)
                
                messagebox.showinfo(
                    "✅ Connexion Réussie",
                    f"Connexion établie avec le Yeti ({self.mode})\n"
                    f"IP: {self.yeti_ip}\n\n"
                    f"Charge actuelle: {data.get('socPercent', 0)}%\n"
                    f"Énergie stockée: {data.get('whStored', 0)} Wh\n\n"
                    f"Le logger tourne maintenant en arrière-plan.",
                    parent=root
                )
                root.destroy()
                return True
        except Exception as e:
            # Marquer comme échec
            config_id = 1 if self.mode == "hotspot" else 2
            self.set_active_config(config_id, success=False)
            
            messagebox.showerror(
                "❌ Erreur de Connexion",
                f"Impossible de se connecter au Yeti\n"
                f"IP: {self.yeti_ip}\n"
                f"Erreur: {str(e)}\n\n"
                f"Vérifiez:\n"
                f"- Que le Yeti est allumé\n"
                f"- Votre connexion WiFi\n"
                f"- L'adresse IP",
                parent=root
            )
            root.destroy()
            return False
    
    def afficher_erreur_reconnexion(self):
        """Affiche un popup d'erreur et redemande l'IP"""
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        retry = messagebox.askretrycancel(
            "⚠️ Perte de Connexion",
            f"La connexion avec le Yeti a été perdue!\n"
            f"IP actuelle: {self.yeti_ip}\n\n"
            f"Tentatives échouées: {self.erreurs_consecutives}\n\n"
            f"Voulez-vous:\n"
            f"• Réessayer = Continuer avec la même IP\n"
            f"• Annuler = Reconfigurer l'IP",
            parent=root
        )
        
        root.destroy()
        
        if not retry:
            # Redemander l'IP
            self.yeti_ip, self.mode = self.selection_ip()
            self.erreurs_consecutives = 0
            print(f"🔄 Nouvelle IP configurée: {self.yeti_ip} ({self.mode})")
    
    def afficher_donnees_utiles(self, data):
        """Afficher les données dans la console"""
        print("\n" + "="*50)
        print(f"🚀 DONNÉES YETI ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        print("="*50)
        print(f"📊 Énergie sortie cumulée: {data.get('whOut', 0)} Wh")
        print(f"🔋 Énergie stockée: {data.get('whStored', 0)} Wh")
        print(f"⚡ Charge: {data.get('socPercent', 0)} %")
        print(f"🔌 Sortie: {data.get('wattsOut', 0)} W / {data.get('ampsOut', 0)} A")
        print(f"🔋 Entrée: {data.get('wattsIn', 0)} W / {data.get('ampsIn', 0)} A")
        print(f"🌡️ Température: {data.get('temperature', 0)} °C")
        print("="*50 + "\n")
    
    def inserer_en_db(self, ligne):
        """Insérer les données en DB"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT INTO logs ({', '.join(CHAMPS)}) 
            VALUES ({', '.join('?' * len(CHAMPS))})
        """, list(ligne.values()))
        conn.commit()
        conn.close()
        print(f"💾 Données insérées en DB.\n")
    
    def calculer_stats(self):
        """Calculer et afficher les statistiques"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                AVG(wattsOut) as moyenne_conso,
                MAX(wattsOut) as pic_conso,
                MIN(wattsOut) as min_conso,
                AVG(socPercent) as moyenne_charge,
                SUM(ABS(whOut)) as total_energie_sortie,
                COUNT(*) as nb_logs
            FROM logs 
            WHERE date_heure >= datetime('now', '-1 day')
        """)
        stats = cursor.fetchone()
        
        if stats and stats[5] > 0:
            print("\n" + "#" * 50)
            print("📈 STATISTIQUES (24h)")
            print("#" * 50)
            print(f"📊 Moyenne conso: {stats[0]:.2f} W")
            print(f"🔥 Pic conso: {stats[1]:.2f} W")
            print(f"😴 Conso min: {stats[2]:.2f} W")
            print(f"⚡ Moyenne charge: {stats[3]:.2f} %")
            print(f"💡 Total sortie: {stats[4]:.0f} Wh")
            print(f"📋 Logs: {stats[5]}")
            print("#" * 50 + "\n")
        
        conn.close()
    
    def logger_iteration(self):
        """Une itération du logger"""
        endpoint = f"http://{self.yeti_ip}/state"
        try:
            response = requests.get(endpoint, timeout=10)
            data = response.json()
            
            # Connexion réussie
            if not self.connected:
                print("✅ Connexion rétablie!")
                self.connected = True
                config_id = 1 if self.mode == "hotspot" else 2
                self.set_active_config(config_id, success=True)
            self.erreurs_consecutives = 0
            
            # Afficher et sauvegarder
            self.afficher_donnees_utiles(data)
            
            ligne = {
                "date_heure": datetime.now().isoformat(),
                "whOut": data.get("whOut", 0),
                "whStored": data.get("whStored", 0),
                "socPercent": data.get("socPercent", 0),
                "wattsOut": data.get("wattsOut", 0),
                "ampsOut": data.get("ampsOut", 0),
                "wattsIn": data.get("wattsIn", 0),
                "ampsIn": data.get("ampsIn", 0),
                "temperature": data.get("temperature", 0),
                "timeToEmptyFull": data.get("timeToEmptyFull", 0)
            }
            
            self.inserer_en_db(ligne)
            
        except Exception as e:
            self.erreurs_consecutives += 1
            print(f"❌ Erreur ({self.erreurs_consecutives}/{TIMEOUT_RECONNEXION}): {e}")
            
            # Si trop d'erreurs consécutives
            if self.erreurs_consecutives >= TIMEOUT_RECONNEXION:
                self.connected = False
                config_id = 1 if self.mode == "hotspot" else 2
                self.set_active_config(config_id, success=False)
                self.afficher_erreur_reconnexion()
    
    def run_loop(self):
        """Boucle principale en arrière-plan"""
        while self.running:
            self.logger_iteration()
            
            # Stats périodiques
            if STATS_INTERVALLE > 0 and (time.time() - self.dernier_stats) >= STATS_INTERVALLE:
                self.calculer_stats()
                self.dernier_stats = time.time()
            
            print(f"😴 Pause {INTERVALLE}s...\n")
            time.sleep(INTERVALLE)
    
    def start(self):
        """Démarrer le service"""
        # Afficher info système
        print(f"🐍 Python: {sys.version.split()[0]}")
        print(f"📂 Script: {os.path.abspath(__file__)}\n")
        
        # Initialiser DB
        self.init_db()
        
        # Sélectionner IP
        self.yeti_ip, self.mode = self.selection_ip()
        print(f"🚀 Configuration: {self.yeti_ip} ({self.mode})")
        
        # Vérifier connexion initiale
        if not self.verifier_connexion_initiale():
            # Redemander si échec
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            retry = messagebox.askyesno(
                "Réessayer?",
                "Voulez-vous reconfigurer l'IP?",
                parent=root
            )
            root.destroy()
            
            if retry:
                return self.start()  # Recommencer
            else:
                sys.exit(0)
        
        # Démarrer le thread en arrière-plan
        self.running = True
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()
        
        print(f"✅ Logger démarré en arrière-plan sur {self.yeti_ip}")
        print(f"📝 Logs toutes les {INTERVALLE}s, stats toutes les {STATS_INTERVALLE}s")
        print(f"🛑 Ctrl+C pour arrêter\n")
        
        # Garder le programme actif
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Arrêt du logger...")
            self.running = False
            self.thread.join(timeout=2)
            print("👋 Logger arrêté proprement.")


# Point d'entrée
if __name__ == "__main__":
    logger = YetiLogger()
    logger.start()