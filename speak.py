import customtkinter as ctk
import sounddevice as sd
import queue
import json
import pyttsx3
import threading
import time
from PIL import Image, ImageTk
from vosk import Model, KaldiRecognizer
import os
from datetime import datetime
import sys
import tempfile

# Configuration générale de l'application
ctk.set_appearance_mode("System")  # Modes: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # Thèmes: "blue", "green", "dark-blue"

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    path = os.path.join(base_path, relative_path)
    
    # For PyInstaller, we might need to look in different places for different files
    if not os.path.exists(path) and hasattr(sys, '_MEIPASS'):
        # Try without joining with MEIPASS (some files might be in root)
        path = os.path.abspath(relative_path)
    
    return path
class VoiceRecognitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MultiLingual Voice Assistant")
        self.root.geometry("900x600")
        
        # Handle icon for both dev and compiled versions
        try:
            icon_path = resource_path("icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Could not load icon: {e}")
        
        # Variables d'état
        self.current_language = ctk.StringVar(value="fr")
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.history = []
        
        # Setup Vosk DLL directory for PyInstaller
        self.setup_vosk_environment()
        
        # Chargement des modèles (asynchrone pour ne pas bloquer l'interface)
        self.load_status = ctk.StringVar(value="Chargement des modèles...")
        self.model_fr = None
        self.model_en = None
        threading.Thread(target=self.load_models, daemon=True).start()
        
        # Configuration TTS
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)
        self.engine.setProperty('volume', 0.9)
        
        # Construction de l'interface
        self.setup_ui()
    
    def setup_vosk_environment(self):
        """Special handling for Vosk DLLs in PyInstaller environment"""
        if getattr(sys, 'frozen', False):
            # Create temp directory for Vosk DLLs
            temp_dir = tempfile.mkdtemp()
            vosk_dir = os.path.join(temp_dir, 'vosk')
            os.makedirs(vosk_dir, exist_ok=True)
            
            # Try to copy DLLs if they exist in MEIPASS
            try:
                dll_src = os.path.join(sys._MEIPASS, 'vosk', 'libvosk.dll')
                dll_dst = os.path.join(vosk_dir, 'libvosk.dll')
                if os.path.exists(dll_src):
                    import shutil
                    shutil.copy2(dll_src, dll_dst)
            except Exception as e:
                print(f"Could not copy Vosk DLL: {e}")
            
            # Add to DLL search path
            os.add_dll_directory(vosk_dir)

    def load_models(self):
        """Charge les modèles Vosk en arrière-plan"""
        try:
            MODEL_FR_PATH = resource_path(os.path.join("models", "vosk-model-small-fr-0.22"))
            MODEL_EN_PATH = resource_path(os.path.join("models", "vosk-model-small-en-us-0.15"))

            if not os.path.exists(MODEL_FR_PATH):
                raise FileNotFoundError(f"French model not found at: {MODEL_FR_PATH}")
            if not os.path.exists(MODEL_EN_PATH):
                raise FileNotFoundError(f"English model not found at: {MODEL_EN_PATH}")

            self.update_status("Chargement du modèle français...", "#000000")
            self.model_fr = Model(MODEL_FR_PATH)

            self.update_status("Chargement du modèle anglais...", "#000000")
            self.model_en = Model(MODEL_EN_PATH)

            self.update_status("Prêt à l'utilisation", "#4CAF50")
        except Exception as e:
            self.update_status(f"Erreur: {str(e)}", "#F44336")
            print(f"Error loading models: {e}")
            
    def update_status(self, message, color):
        """Thread-safe status updates"""
        self.root.after(0, lambda: self.load_status.set(message))
        self.root.after(0, lambda: self.status_label.configure(text_color=color))

    def update_result(self, lang, text):
        """Thread-safe result updates"""
        def _update():
            if not text:
                self.result_label.configure(text="[Aucun texte reconnu]")
                return
                
            self.result_label.configure(text=text)
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            lang_display = "🇫🇷" if lang == "fr" else "🇬🇧"
            
            history_entry = ctk.CTkFrame(self.history_frame)
            history_entry.pack(fill="x", padx=5, pady=2, ipadx=5, ipady=5)
            
            header_frame = ctk.CTkFrame(history_entry, fg_color="transparent")
            header_frame.pack(fill="x", padx=5, pady=(5, 0))
            
            time_label = ctk.CTkLabel(header_frame, text=timestamp, font=ctk.CTkFont(size=10))
            time_label.pack(side="left")
            
            lang_label = ctk.CTkLabel(header_frame, text=lang_display, font=ctk.CTkFont(size=12))
            lang_label.pack(side="right")
            
            text_label = ctk.CTkLabel(history_entry, text=text, 
                                    justify="left", anchor="w", 
                                    wraplength=400)
            text_label.pack(fill="x", padx=10, pady=5)
            
            self.history.append((lang, text))
            self.replay_button.configure(state="normal")
            self.history_frame._parent_canvas.yview_moveto(1.0)
        
        self.root.after(0, _update)
    def setup_ui(self):
        """Configure tous les éléments de l'interface"""
        # Utilisation d'un grid layout pour un meilleur contrôle
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Conteneur principal avec effet de dégradé
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Configuration du conteneur principal
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=0)  # Entête
        self.main_frame.grid_rowconfigure(1, weight=1)  # Contenu central
        self.main_frame.grid_rowconfigure(2, weight=0)  # Barre de statut
        
        # ===== ENTÊTE =====
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color=("#E0E5F1", "#2B3142"))
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        # Logo et titre
        title_label = ctk.CTkLabel(self.header_frame, text="Assistant Vocal Multilingue", 
                                  font=ctk.CTkFont(size=22, weight="bold"))
        title_label.pack(side="left", padx=10, pady=10)
        
        # Sélecteur de langue avec style élégant
        self.language_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.language_frame.pack(side="right", padx=15, pady=10)
        
        self.lang_label = ctk.CTkLabel(self.language_frame, text="Langue:")
        self.lang_label.pack(side="left", padx=(0, 5))
        
        self.fr_button = ctk.CTkButton(self.language_frame, text="FR", width=40,
                                       command=lambda: self.change_language("fr"))
        self.fr_button.pack(side="left", padx=2)
        
        self.en_button = ctk.CTkButton(self.language_frame, text="EN", width=40,
                                       command=lambda: self.change_language("en"))
        self.en_button.pack(side="left", padx=2)
        
        # ===== CONTENU CENTRAL =====
        self.content_frame = ctk.CTkFrame(self.main_frame)
        self.content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(1, weight=0)
        
        # Panneau d'historique avec défilement
        self.history_frame = ctk.CTkScrollableFrame(self.content_frame, label_text="Historique")
        self.history_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Zone de visualisation de texte reconnu
        self.result_frame = ctk.CTkFrame(self.content_frame)
        self.result_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        
        self.result_label = ctk.CTkLabel(self.result_frame, text="Texte reconnu s'affichera ici",
                                       height=100, font=ctk.CTkFont(size=16),
                                       bg_color=("#F0F2F6", "#32364A"),
                                       corner_radius=8)
        self.result_label.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Panneau de contrôle
        self.control_frame = ctk.CTkFrame(self.main_frame)
        self.control_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        
        # Visualiseur d'onde audio (simulé)
        self.visualizer_canvas = ctk.CTkCanvas(self.control_frame, height=40)
        self.visualizer_canvas.pack(fill="x", padx=10, pady=5)
        self.draw_idle_wave()
        
        # Boutons de contrôle
        self.button_frame = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        self.button_frame.pack(fill="x", padx=10, pady=5)
        
        # Bouton principal avec effet de pulsation
        self.record_button = ctk.CTkButton(self.button_frame, text="🎤 Commencer l'écoute",
                                         width=200, height=50,
                                         font=ctk.CTkFont(size=18, weight="bold"),
                                         fg_color=("#3B82F6", "#1E40AF"),
                                         hover_color=("#2563EB", "#1E3A8A"),
                                         command=self.toggle_recording)
        self.record_button.pack(side="left", padx=10, pady=10)
        
        # Boutons additionnels
        self.clear_button = ctk.CTkButton(self.button_frame, text="Effacer l'historique",
                                        width=150, 
                                        command=self.clear_history)
        self.clear_button.pack(side="right", padx=10, pady=10)
        
        self.replay_button = ctk.CTkButton(self.button_frame, text="Relire dernier texte",
                                         width=150,
                                         state="disabled",
                                         command=self.replay_last)
        self.replay_button.pack(side="right", padx=10, pady=10)
        
        # Barre de statut
        self.status_frame = ctk.CTkFrame(self.main_frame, height=25)
        self.status_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 5))
        
        self.status_label = ctk.CTkLabel(self.status_frame, textvariable=self.load_status,
                                       anchor="w", font=ctk.CTkFont(size=12))
        self.status_label.pack(side="left", padx=10, pady=5)
        
        # Démarrer l'effet de pulsation du bouton
        self.pulse_animation()
        
    def draw_idle_wave(self):
        """Dessine une onde audio statique pour l'état d'inactivité"""
        self.visualizer_canvas.delete("all")
        width = self.visualizer_canvas.winfo_width() or 800
        height = self.visualizer_canvas.winfo_height() or 40
        
        # Ligne médiane
        self.visualizer_canvas.create_line(0, height/2, width, height/2, 
                                         fill="#6B7280", width=1, dash=(4, 2))
        
        # Petites ondes statiques
        for i in range(0, width, 20):
            y = height/2 + (5 * (1 if i % 40 == 0 else -1))
            self.visualizer_canvas.create_line(i, height/2, i+10, y, 
                                             fill="#9CA3AF", width=2, smooth=True)
            self.visualizer_canvas.create_line(i+10, y, i+20, height/2, 
                                             fill="#9CA3AF", width=2, smooth=True)
    
    def draw_active_wave(self):
        """Simule une onde audio active pendant l'enregistrement"""
        if not self.is_recording:
            return
            
        self.visualizer_canvas.delete("all")
        width = self.visualizer_canvas.winfo_width() or 800
        height = self.visualizer_canvas.winfo_height() or 40
        
        points = []
        for i in range(0, width, 5):
            # Simulation d'une onde plus dynamique
            amplitude = 15 * abs(((i + time.time()*100) % 100)/100 - 0.5)
            y = height/2 + amplitude * (1 if i % 10 == 0 else -1)
            points.append(i)
            points.append(y)
        
        if len(points) >= 4:  # Au moins 2 points (x,y)
            self.visualizer_canvas.create_line(points, fill="#10B981", width=2, smooth=True)
        
        # Boucle d'animation
        if self.is_recording:
            self.root.after(50, self.draw_active_wave)
    
    def pulse_animation(self):
        """Crée un effet de pulsation sur le bouton d'enregistrement"""
        if not self.is_recording:
            current_color = self.record_button.cget("fg_color")[1]
            new_color = "#1E40AF" if current_color == "#1D4ED8" else "#1D4ED8"
            self.record_button.configure(fg_color=(new_color, new_color))
        
        self.root.after(1000, self.pulse_animation)
    
    def toggle_recording(self):
        """Démarre ou arrête l'enregistrement audio"""
        if self.model_fr is None or self.model_en is None:
            self.status_label.configure(text="Veuillez attendre le chargement des modèles...")
            return
        
        self.is_recording = not self.is_recording
        
        if self.is_recording:
            self.record_button.configure(text="⏹️ Arrêter l'écoute", 
                                       fg_color=("#DC2626", "#991B1B"),
                                       hover_color=("#B91C1C", "#7F1D1D"))
            self.status_label.configure(text="Écoute en cours...")
            
            # Démarrer l'animation de l'onde audio
            self.draw_active_wave()
            
            # Démarrer l'enregistrement dans un thread séparé
            threading.Thread(target=self.record_audio, daemon=True).start()
        else:
            self.record_button.configure(text="🎤 Commencer l'écoute",
                                       fg_color=("#3B82F6", "#1E40AF"),
                                       hover_color=("#2563EB", "#1E3A8A"))
            self.status_label.configure(text="Écoute terminée")
            self.draw_idle_wave()
    
    def record_audio(self):
        """Enregistre l'audio et le fait reconnaître"""
        if not self.is_recording:
            return
            
        def callback(indata, frames, time, status):
            if status:
                print(status)
            if self.is_recording:
                self.audio_queue.put(bytes(indata))
        
        try:
            with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                                channels=1, callback=callback):
                
                audio_data = b""
                for _ in range(8):  # ~4 secondes à 16kHz
                    if not self.is_recording:
                        break
                    try:
                        chunk = self.audio_queue.get(timeout=0.5)
                        audio_data += chunk
                    except queue.Empty:
                        continue
                
                if audio_data and self.is_recording:
                    self.root.after(0, self.toggle_recording)
                    
                    # Do recognition in this thread
                    lang, text = self.recognize_language(audio_data)
                    
                    # Schedule UI update on main thread
                    self.root.after(0, lambda: self.update_result(lang, text))
        
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"Erreur: {str(e)}", "#F44336"))
            
    def recognize_language(self, audio_data):
        """Reconnaît la langue et le texte parlé"""
        # Utiliser le modèle sélectionné
        if self.current_language.get() == "auto":
            # Mode automatique: tester les deux langues
            rec_fr = KaldiRecognizer(self.model_fr, 16000)
            rec_en = KaldiRecognizer(self.model_en, 16000)
            
            rec_fr.AcceptWaveform(audio_data)
            result_fr = json.loads(rec_fr.Result())
            text_fr = result_fr.get("text", "")
            
            rec_en.AcceptWaveform(audio_data)
            result_en = json.loads(rec_en.Result())
            text_en = result_en.get("text", "")
            
            # Sélectionner la langue avec le score de confiance le plus élevé
            conf_fr = result_fr.get("confidence", 0) if "confidence" in result_fr else len(text_fr)
            conf_en = result_en.get("confidence", 0) if "confidence" in result_en else len(text_en)
            
            if conf_fr > conf_en:
                return "fr", text_fr
            else:
                return "en", text_en
        else:
            # Mode spécifique: utiliser la langue sélectionnée
            model = self.model_fr if self.current_language.get() == "fr" else self.model_en
            recognizer = KaldiRecognizer(model, 16000)
            
            recognizer.AcceptWaveform(audio_data)
            result = json.loads(recognizer.Result())
            text = result.get("text", "")
            
            return self.current_language.get(), text
    
    def update_result(self, lang, text):
        """Met à jour l'interface avec le résultat de la reconnaissance"""
        # Si texte vide, afficher un message
        if not text:
            self.result_label.configure(text="[Aucun texte reconnu]")
            return
            
        # Afficher le résultat
        self.result_label.configure(text=text)
        
        # Ajouter à l'historique
        timestamp = datetime.now().strftime("%H:%M:%S")
        lang_display = "🇫🇷" if lang == "fr" else "🇬🇧"
        
        history_entry = ctk.CTkFrame(self.history_frame)
        history_entry.pack(fill="x", padx=5, pady=2, ipadx=5, ipady=5)
        
        header_frame = ctk.CTkFrame(history_entry, fg_color="transparent")
        header_frame.pack(fill="x", padx=5, pady=(5, 0))
        
        time_label = ctk.CTkLabel(header_frame, text=timestamp, font=ctk.CTkFont(size=10))
        time_label.pack(side="left")
        
        lang_label = ctk.CTkLabel(header_frame, text=lang_display, font=ctk.CTkFont(size=12))
        lang_label.pack(side="right")
        
        text_label = ctk.CTkLabel(history_entry, text=text, 
                                 justify="left", anchor="w", 
                                 wraplength=400)
        text_label.pack(fill="x", padx=10, pady=5)
        
        # Sauvegarder dans la liste d'historique
        self.history.append((lang, text))
        
        # Activer le bouton de relecture
        self.replay_button.configure(state="normal")
        
        # Faire défiler vers le bas
        self.history_frame._parent_canvas.yview_moveto(1.0)
        
        # Synthèse vocale
        self.speak_text(lang, text)
    
    def speak_text(self, lang, text):
        """Répond avec la synthèse vocale dans la langue détectée"""
        # Définir la voix appropriée
        voices = self.engine.getProperty('voices')
        
        for voice in voices:
            voice_name = voice.name.lower()
            if (lang == "fr" and ("french" in voice_name or "français" in voice_name)) or \
               (lang == "en" and "english" in voice_name and "french" not in voice_name):
                self.engine.setProperty('voice', voice.id)
                break
        
        # Synthèse vocale dans un thread pour ne pas bloquer l'interface
        def tts_thread():
            self.engine.say(text)
            self.engine.runAndWait()
        
        threading.Thread(target=tts_thread, daemon=True).start()
    
    def change_language(self, lang):
        """Change la langue active"""
        self.current_language.set(lang)
        
        # Mettre à jour l'apparence des boutons
        if lang == "fr":
            self.fr_button.configure(fg_color=("#2563EB", "#1E3A8A"))
            self.en_button.configure(fg_color=("#E0E7FF", "#3B4F81"))
            self.status_label.configure(text="Langue: Français")
        else:
            self.fr_button.configure(fg_color=("#E0E7FF", "#3B4F81"))
            self.en_button.configure(fg_color=("#2563EB", "#1E3A8A"))
            self.status_label.configure(text="Language: English")
    
    def clear_history(self):
        """Efface l'historique des reconnaissances"""
        # Effacer les widgets
        for widget in self.history_frame.winfo_children():
            widget.destroy()
        
        # Effacer la liste d'historique
        self.history.clear()
        
        # Désactiver le bouton de relecture
        self.replay_button.configure(state="disabled")
        
        # Réinitialiser le résultat
        self.result_label.configure(text="Historique effacé")
    
    def replay_last(self):
        """Rejoue la dernière entrée vocale"""
        if not self.history:
            return
            
        lang, text = self.history[-1]
        self.result_label.configure(text=text)
        self.speak_text(lang, text)

# Fonction principale
def main():
    root = ctk.CTk()
    app = VoiceRecognitionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()