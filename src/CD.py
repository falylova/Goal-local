import requests
import sqlite3
import time
from datetime import datetime
import os
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog
import threading

# Configuration par défaut
DEFAULT_HOTSPOT_IP = "10.1.1.1"
DEFAULT_RESEAU_IP = "192.168.137.54"
DB_FILE = "yeti_energie.db"
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
        
    def selection_ip(self):
        """Popup pour sélectionner l'IP au démarrage"""
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        result = messagebox.askyesno(
            "Configuration IP Yeti", 
            "Voulez-vous utiliser le mode Hotspot (10.1.1.1) ?\n\n"
            "Oui = Hotspot\n"
            "Non = Réseau domestique (IP personnalisée)",
            parent=root
        )
        
        if result:
            ip = DEFAULT_HOTSPOT_IP
            mode = "Hotspot"
        else:
            ip = simpledialog.askstring(
                "IP Réseau", 
                f"Entrez l'IP du Yeti sur le réseau domestique\n(défaut: {DEFAULT_RESEAU_IP}):",
                initialvalue=DEFAULT_RESEAU_IP,
                parent=root
            )
            if not ip:
                ip = DEFAULT_RESEAU_IP
            mode = "Réseau domestique"
        
        root.destroy()
        return ip, mode
    
    def verifier_connexion_initiale(self):
        """Vérifie la connexion et affiche un popup de confirmation"""
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        try:
            response = requests.get(f"http://{self.yeti_ip}/state", timeout=10)
            data = response.json()
            
            if data:
                self.connected = True
                self.erreurs_consecutives = 0
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
    
    def init_db(self):
        """Initialiser la DB et la table"""
        if not os.path.exists(DB_FILE):
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    {', '.join([f"{champ} {'TEXT' if champ == 'date_heure' else 'REAL'}" for champ in CHAMPS])}
                )
            """)
            conn.commit()
            conn.close()
            print(f"🗄️ Base de données '{DB_FILE}' créée.")
    
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