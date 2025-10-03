import os
import sys
import time
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QMainWindow, QApplication, QInputDialog, QMessageBox
from PyQt5.QtCore import QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QFontDatabase, QPalette, QColor
import base64
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import QByteArray

# --- Basmapp för chatdata ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CHAT_DIR = os.path.join(BASE_DIR, "chatdata")
os.makedirs(CHAT_DIR, exist_ok=True)
CHAT_REFRESH_INTERVAL = 500  # 500ms för chat
USERS_REFRESH_INTERVAL = 3000  # 3 sekunder för användare
MENTION_CHECK_INTERVAL = 2000  # 2 sekunder för mention-kontroll
ROOM_UPDATE_INTERVAL = 5000  # 5 sekunder för rum-uppdatering

# --- Användarnamn ---
users_file = os.path.join(CHAT_DIR, "users.txt")
mentions_file = os.path.join(CHAT_DIR, "mentions.txt")  # Fil för sparade mentions

if not os.path.exists(users_file):
    open(users_file, "a", encoding="utf-8").close()
if not os.path.exists(mentions_file):
    open(mentions_file, "a", encoding="utf-8").close()

app = QApplication(sys.argv)

# Ställ in teckensnitt för hela applikationen
font = QFont("Segoe UI", 13)
app.setFont(font)

# Modern mörkt tema med professionell styling
app.setStyleSheet("""
    QMainWindow {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
    QWidget {
        background-color: #1e1e1e;
        color: #e0e0e0;
        border: none;
    }
    QComboBox {
        background-color: #2d2d30;
        color: #e0e0e0;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        padding: 8px 12px;
        min-width: 120px;
        font-size: 15px;
    }
    QComboBox:focus {
        border: 1px solid #007acc;
    }
    QTextEdit {
        background-color: #252526;
        color: #e0e0e0;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        padding: 8px;
        font-family: 'Segoe UI', sans-serif;
        font-size: 15px;
        selection-background-color: #007acc;
    }
    QLineEdit {
        background-color: #2d2d30;
        color: #e0e0e0;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        padding: 8px 12px;
        font-size: 15px;
    }
    QLineEdit:focus {
        border: 1px solid #007acc;
    }
    QPushButton {
        background-color: #0e639c;
        color: #ffffff;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: bold;
        min-width: 80px;
        font-size: 15px;
    }
    QPushButton:hover {
        background-color: #1177bb;
    }
    QLabel {
        font-size: 15px;
    }
    QSlider::groove:horizontal {
        border: 1px solid #3e3e42;
        height: 8px;
        background: #2d2d30;
        margin: 2px 0;
        border-radius: 4px;
    }
    QSlider::handle:horizontal {
        background: #0e639c;
        border: 1px solid #1177bb;
        width: 18px;
        height: 18px;
        margin: -5px 0;
        border-radius: 9px;
    }
    QSlider::handle:horizontal:hover {
        background: #1177bb;
    }
    QSlider::sub-page:horizontal {
        background: #0e639c;
        border-radius: 4px;
    }
    QListWidget {
        background-color: #2d2d30;
        border: 1px solid #3e3e42;
        border-radius: 4px;
        padding: 5px;
    }
    QListWidget::item {
        padding: 5px;
        border-bottom: 1px solid #3e3e42;
    }
    QListWidget::item:last {
        border-bottom: none;
    }
""")

# Fråga efter användarnamn
username, ok = QInputDialog.getText(None, "Vingslechat", "Ange ditt användarnamn:")
if not ok or not username:
    QMessageBox.critical(None, "Avbrutet", "Inget användarnamn angavs")
    sys.exit()

# --- Generera unikt namn ---
with open(users_file, "r+", encoding="utf-8") as f:
    users = f.read().splitlines()
    current_time = time.time()
    cleaned_users = []
    for u in users:
        try:
            name, timestamp = u.rsplit("|", 1)
            if current_time - float(timestamp) < 600:
                cleaned_users.append(u)
        except:
            cleaned_users.append(u)
    users = cleaned_users
    f.seek(0)
    f.truncate()
    f.write("\n".join(users) + "\n")

    base = username
    counter = 1
    newname = username
    existing_names = [u.split("|")[0] for u in users]
    while newname in existing_names:
        newname = f"{base}_{counter}"
        counter += 1

    users.append(f"{newname}|{current_time}")
    f.seek(0)
    f.write("\n".join(users) + "\n")

USERNAME = newname

# --- Huvudfönster ---
class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Superduper BOOM chat - {USERNAME}")
        self.resize(900, 700)
        self.setMinimumSize(700, 500)

        # Variabler för notiser
        self.notified_messages = set()
        self.unseen_mentions = set()
        self.seen_mentions = self.ladda_seen_mentions()  # Permanent lästa mentions
        self.current_room_mentions = set()
        self.previous_unseen_count = 0  # För att spåra förändringar i mentions
        self.blink_timer = QTimer()  # Timer för att blinka ikonen
        self.blink_timer.timeout.connect(self.blinka_ikon)
        self.blink_state = False
        self.normal_window_title = f"Superduper BOOM chat - {USERNAME}"
        self.is_window_active = True
        self.current_rooms = []  # Spara aktuell lista med rum

        self.current_room = "Lobby"
        self.last_seen_content = ""
        self.font_size = 15
        self.window_opacity = 0.92

        # Central widget
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        # Huvudlayout
        main_layout = QtWidgets.QHBoxLayout(central)

        # Vänster del - chatten
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setSpacing(10)
        left_layout.setContentsMargins(0, 0, 15, 0)

        # Custom title bar
        self.title_bar = self.setup_custom_titlebar()
        left_layout.addWidget(self.title_bar)

        # Header med rumval
        header_layout = QtWidgets.QHBoxLayout()
        room_selection_layout = QtWidgets.QHBoxLayout()

        room_label = QtWidgets.QLabel("Rum:")
        room_label.setStyleSheet("font-weight: bold;")
        room_selection_layout.addWidget(room_label)

        self.room_combo = QtWidgets.QComboBox()
        self.room_combo.setMinimumWidth(150)
        room_selection_layout.addWidget(self.room_combo)

        # Container för notis-indikatorer
        self.notice_container = QtWidgets.QWidget()
        self.notice_layout = QtWidgets.QHBoxLayout(self.notice_container)
        self.notice_layout.setSpacing(5)
        self.notice_layout.setContentsMargins(10, 0, 0, 0)
        room_selection_layout.addWidget(self.notice_container)

        room_selection_layout.addStretch()
        header_layout.addLayout(room_selection_layout)
        header_layout.addStretch()

        user_label = QtWidgets.QLabel(f"Användare: {USERNAME}")
        user_label.setStyleSheet("color: #569cd6; font-weight: bold;")
        header_layout.addWidget(user_label)

        left_layout.addLayout(header_layout)

        # Chatttextområde
        self.chat_text = QtWidgets.QTextEdit()
        self.chat_text.setReadOnly(True)
        self.chat_text.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        left_layout.addWidget(self.chat_text, stretch=1)

        # Inmatningsområde
        input_layout = QtWidgets.QHBoxLayout()
        self.entry = QtWidgets.QLineEdit()
        self.entry.setPlaceholderText("Skriv ditt meddelande här...")
        self.entry.returnPressed.connect(self.skicka_meddelande)
        input_layout.addWidget(self.entry, stretch=1)

        send_btn = QtWidgets.QPushButton("Skicka")
        send_btn.setFixedWidth(80)
        send_btn.clicked.connect(self.skicka_meddelande)
        input_layout.addWidget(send_btn)

        left_layout.addLayout(input_layout)

        # Knappar
        button_layout = QtWidgets.QHBoxLayout()
        add_room_btn = QtWidgets.QPushButton("Skapa Nytt Rum")
        add_room_btn.clicked.connect(self.skapa_rum)
        button_layout.addWidget(add_room_btn)
        clear_btn = QtWidgets.QPushButton("Rensa Chatt")
        clear_btn.clicked.connect(self.rensa_chatt)
        button_layout.addWidget(clear_btn)
        button_layout.addStretch()

        # Opacitetskontroller
        opacity_layout = QtWidgets.QHBoxLayout()
        opacity_label = QtWidgets.QLabel("Genomskinlighet:")
        opacity_label.setStyleSheet("font-weight: bold;")
        opacity_layout.addWidget(opacity_label)

        less_opacity_btn = QtWidgets.QPushButton("−")
        less_opacity_btn.setFixedWidth(30)
        less_opacity_btn.clicked.connect(self.minska_opacitet)
        opacity_layout.addWidget(less_opacity_btn)

        self.opacity_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.opacity_slider.setMinimum(40)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(int(self.window_opacity * 100))
        self.opacity_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.opacity_slider.setTickInterval(10)
        self.opacity_slider.valueChanged.connect(self.andrad_opacitet)
        opacity_layout.addWidget(self.opacity_slider)

        more_opacity_btn = QtWidgets.QPushButton("+")
        more_opacity_btn.setFixedWidth(30)
        more_opacity_btn.clicked.connect(self.oka_opacitet)
        opacity_layout.addWidget(more_opacity_btn)

        self.opacity_display = QtWidgets.QLabel(f"{int(self.window_opacity * 100)}%")
        self.opacity_display.setFixedWidth(50)
        self.opacity_display.setStyleSheet("font-weight: bold; color: #569cd6;")
        opacity_layout.addWidget(self.opacity_display)

        opacity_layout.addStretch()
        button_layout.addLayout(opacity_layout)
        left_layout.addLayout(button_layout)

        # Textstorlekskontroller
        font_size_layout = QtWidgets.QHBoxLayout()
        font_size_label = QtWidgets.QLabel("Textstorlek:")
        font_size_label.setStyleSheet("font-weight: bold;")
        font_size_layout.addWidget(font_size_label)

        # Mindre text-knapp
        smaller_btn = QtWidgets.QPushButton("A-")
        smaller_btn.setFixedWidth(40)
        smaller_btn.clicked.connect(self.minska_textstorlek)
        font_size_layout.addWidget(smaller_btn)

        # Slider för textstorlek
        self.font_size_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.font_size_slider.setMinimum(10)
        self.font_size_slider.setMaximum(24)
        self.font_size_slider.setValue(self.font_size)
        self.font_size_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.font_size_slider.setTickInterval(2)
        self.font_size_slider.valueChanged.connect(self.andrad_textstorlek)
        font_size_layout.addWidget(self.font_size_slider)

        # Större text-knapp
        larger_btn = QtWidgets.QPushButton("A+")
        larger_btn.setFixedWidth(40)
        larger_btn.clicked.connect(self.oka_textstorlek)
        font_size_layout.addWidget(larger_btn)

        # Visar aktuell textstorlek
        self.font_size_display = QtWidgets.QLabel(f"{self.font_size}px")
        self.font_size_display.setFixedWidth(50)
        self.font_size_display.setStyleSheet("font-weight: bold; color: #569cd6;")
        font_size_layout.addWidget(self.font_size_display)

        font_size_layout.addStretch()
        left_layout.addLayout(font_size_layout)

        # Lägg till vänster del
        main_layout.addWidget(left_widget, stretch=3)

        # Höger del - online-användare
        right_widget = QtWidgets.QWidget()
        right_widget.setMaximumWidth(200)
        right_layout = QtWidgets.QVBoxLayout(right_widget)

        online_label = QtWidgets.QLabel("Online Användare")
        online_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #569cd6; margin-bottom: 5px;")
        right_layout.addWidget(online_label)

        self.online_list = QtWidgets.QListWidget()
        right_layout.addWidget(self.online_list)
        main_layout.addWidget(right_widget, stretch=1)

        # Timer för chatuppdatering (fortfarande snabb)
        self.chat_timer = QTimer()
        self.chat_timer.timeout.connect(self.uppdatera_chatt)
        self.chat_timer.start(CHAT_REFRESH_INTERVAL)  # 500ms för chat

        # Timer för online-användare (långsammare)
        self.users_timer = QTimer()
        self.users_timer.timeout.connect(self.uppdatera_online_anvandare)
        self.users_timer.start(USERS_REFRESH_INTERVAL)  # 3 sekunder för användarlista

        # Timer för mention-kontroll
        self.mention_timer = QTimer()
        self.mention_timer.timeout.connect(self.kolla_mentions_fran_fil)
        self.mention_timer.start(MENTION_CHECK_INTERVAL)

        # Timer för rum-uppdatering
        self.room_timer = QTimer()
        self.room_timer.timeout.connect(self.kolla_nya_rum)
        self.room_timer.start(ROOM_UPDATE_INTERVAL)

        self.setWindowOpacity(self.window_opacity)
        self.ladda_rum()
        self.uppdatera_chatt()  # Uppdatera chatten direkt
        self.uppdatera_online_anvandare()  # Uppdatera användare direkt

        # Övervaka fönsteraktivitet
        self.installEventFilter(self)

    def setup_custom_titlebar(self):
        """Skapar en anpassad titelrad"""
        # Ta bort standard titelrad
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)

        # Skapa en custom title bar
        self.title_bar = QtWidgets.QWidget()
        self.title_bar.setFixedHeight(30)
        self.title_bar.setStyleSheet("""
            QWidget {
                background-color: #2d2d30;
                border-bottom: 1px solid #3e3e42;
            }
        """)

        title_layout = QtWidgets.QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 0, 5, 0)

        # Titel
        title_label = QtWidgets.QLabel(f"Superduper BOOM chat - {USERNAME}")
        title_label.setStyleSheet("color: #569cd6; font-weight: bold; font-size: 12px;")
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        # Minimize knapp
        min_btn = QtWidgets.QPushButton("−")
        min_btn.setFixedSize(25, 25)
        min_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #e0e0e0;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3e3e42;
            }
        """)
        min_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(min_btn)

        # Close knapp
        close_btn = QtWidgets.QPushButton("×")
        close_btn.setFixedSize(25, 25)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #e0e0e0;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e81123;
                color: white;
            }
        """)
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)

        return self.title_bar

    def mousePressEvent(self, event):
        """Möjliggör draggning av fönstret"""
        if event.button() == QtCore.Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Hanterar draggning av fönstret"""
        if event.buttons() == QtCore.Qt.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def eventFilter(self, obj, event):
        """Övervakar fönsterhändelser för att kolla när fönstret blir aktivt/inaktivt"""
        if event.type() == QtCore.QEvent.WindowActivate:
            self.is_window_active = True
            # Stoppa blinkning när fönstret blir aktivt
            self.stoppa_blinkande()
        elif event.type() == QtCore.QEvent.WindowDeactivate:
            self.is_window_active = False
        return super().eventFilter(obj, event)

    def blinka_ikon(self):
        """Blinkar fönsterikonen i taskbaren med riktig taskbar-blinking"""
        if self.blink_state:
            # Återställ normal ikon (göm överraskning)
            self.setWindowTitle(self.normal_window_title)
            # Återställ taskbar (ta bort överraskningsflagga)
            if hasattr(self, 'was_flashed') and self.was_flashed:
                self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized)
            self.blink_state = False
        else:
            # Visa notis-ikon (blinkande titel)
            self.setWindowTitle(f"🔔 {self.normal_window_title}")
            # Flash taskbar ikon (Windows)
            self.flash_taskbar()
            self.blink_state = True

    def flash_taskbar(self):
        """Får taskbar-ikonen att blinka (Windows)"""
        if not self.is_window_active:
            # Använd Windows-specific flash-metod
            self.setWindowState(self.windowState() | QtCore.Qt.WindowMinimized)
            self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized)
            self.was_flashed = True

    def starta_blinkande(self):
        """Startar blinkande effekten"""
        if not self.blink_timer.isActive():
            self.blink_timer.start(1000)  # Blinka varje sekund

    def stoppa_blinkande(self):
        """Stoppar blinkande effekten"""
        self.blink_timer.stop()
        self.setWindowTitle(self.normal_window_title)
        self.blink_state = False
        # Återställ taskbar om den var flashad
        if hasattr(self, 'was_flashed') and self.was_flashed:
            self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized)
            self.was_flashed = False

    def kolla_nya_rum(self):
        """Kollar efter nya rum var 5:e sekund"""
        self.ladda_rum()

    # TA BORT denna metod eftersom vi nu använder separata timers
    # def uppdatera_allt(self):
    #     """Uppdaterar chatten och online-listan"""
    #     self.uppdatera_chatt()
    #     self.uppdatera_online_anvandare()

    def ladda_seen_mentions(self):
        """Laddar permanent lästa mentions från fil"""
        seen = set()
        try:
            with open(mentions_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "|" in line:
                        user_room, message_id = line.rsplit("|", 1)
                        if user_room.startswith(USERNAME + ":"):
                            room = user_room[len(USERNAME) + 1:]
                            seen.add(f"{room}|{message_id}")
        except:
            pass
        return seen

    def spara_seen_mentions(self):
        """Sparar permanent lästa mentions till fil"""
        try:
            with open(mentions_file, "w", encoding="utf-8") as f:
                for mention in self.seen_mentions:
                    room, message_id = mention.split("|", 1)
                    user_room = f"{USERNAME}:{room}"
                    f.write(f"{user_room}|{message_id}\n")
        except Exception as e:
            print(f"Fel vid sparande av mentions: {e}")

    def markera_mention_som_last(self, room, message_id):
        """Markerar en specifik mention som permanent läst"""
        mention_id = f"{room}|{message_id}"
        self.seen_mentions.add(mention_id)
        self.spara_seen_mentions()

        # Ta bort från unseen_mentions om den finns där
        self.unseen_mentions.discard(room)
        self.uppdatera_notice_indikatorer()

    def room_file(self, room_name=None):
        """Returnerar filsökväg för ett rum"""
        if room_name is None:
            room_name = self.current_room
        path = os.path.join(CHAT_DIR, f"{room_name}.txt")
        return path

    def ladda_rum(self):
        """Laddar alla tillgängliga rum"""
        all_files = [f for f in os.listdir(CHAT_DIR) if f.endswith(".txt")]
        rooms = [f[:-4] for f in all_files if f not in ["users.txt", "mentions.txt"]]

        if not rooms:
            rooms = ["Lobby"]
            open(os.path.join(CHAT_DIR, "Lobby.txt"), "a").close()

        # Kolla om rumlistan har ändrats
        if rooms != self.current_rooms:
            current_room = self.current_room

            # Temporärt koppla bort signalen för att förhindra flera anrop (om den är ansluten)
            try:
                self.room_combo.currentIndexChanged.disconnect(self.byt_rum)
            except TypeError:
                # Signal var inte ansluten, det är ok
                pass

            self.room_combo.clear()
            for room in rooms:
                self.room_combo.addItem(room)

            # Försök behålla aktuellt rum eller välj Lobby som fallback
            index = self.room_combo.findText(current_room)
            if index >= 0:
                self.room_combo.setCurrentIndex(index)
            else:
                # Om aktuellt rum inte finns längre, välj första rummet
                self.current_room = rooms[0] if rooms else "Lobby"
                self.room_combo.setCurrentText(self.current_room)
                self.last_seen_content = ""  # Tvinga uppdatering av chatt

            # Återanslut signalen
            self.room_combo.currentIndexChanged.connect(self.byt_rum)

            self.current_rooms = rooms

    def uppdatera_notice_indikatorer(self):
        """Uppdaterar notis-indikatorerna"""
        # Rensa befintliga indikatorer
        for i in reversed(range(self.notice_layout.count())):
            widget = self.notice_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Lägg till indikatorer för rum med olästa mentions
        for room in self.unseen_mentions:
            notice_btn = QtWidgets.QPushButton(f"🔔 {room}")
            notice_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d4af37;
                    color: #000000;
                    border: none;
                    border-radius: 12px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #e6c050;
                }
            """)
            notice_btn.setFixedHeight(24)
            notice_btn.clicked.connect(lambda checked, r=room: self.hoppa_till_rum(r))
            self.notice_layout.addWidget(notice_btn)

        # Kontrollera blinkande ikon
        current_unseen_count = len(self.unseen_mentions)

        if current_unseen_count > 0 and self.previous_unseen_count == 0:
            # Nya mentions - starta blinkande
            self.starta_blinkande()
        elif current_unseen_count == 0 and self.previous_unseen_count > 0:
            # Inga mentions kvar - stoppa blinkande
            self.stoppa_blinkande()

        self.previous_unseen_count = current_unseen_count

    def hoppa_till_rum(self, room):
        """Hoppar till ett rum och markerar alla mentions i det rummet som lästa"""
        index = self.room_combo.findText(room)
        if index >= 0:
            self.room_combo.setCurrentIndex(index)

        # Markera alla mentions i detta rum som lästa
        self.markera_alla_mentions_i_rum_som_last(room)

    def markera_alla_mentions_i_rum_som_last(self, room):
        """Markerar alla mentions i ett specifikt rum som lästa"""
        try:
            # Läs mentions från fil och ta bort alla för denna användare i detta rum
            with open(mentions_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Filtrera bort mentions för denna användare i detta rum
            filtered_lines = []
            for line in lines:
                line = line.strip()
                if line and "|" in line:
                    user_room, message_id = line.rsplit("|", 1)
                    if user_room.startswith(USERNAME + ":") and user_room.endswith(":" + room):
                        # Spara som läst
                        self.seen_mentions.add(f"{room}|{message_id}")
                    else:
                        filtered_lines.append(line)

            # Spara tillbaka filtrerad lista
            with open(mentions_file, "w", encoding="utf-8") as f:
                for line in filtered_lines:
                    f.write(line + "\n")

            # Spara de lästa mentions
            self.spara_seen_mentions()

            # Uppdatera UI
            self.unseen_mentions.discard(room)
            self.uppdatera_notice_indikatorer()

        except Exception as e:
            print(f"Fel vid markering av mentions i rum {room}: {e}")

    def skapa_rum(self):
        """Skapar ett nytt rum"""
        room_name, ok = QInputDialog.getText(self, "Nytt Rum", "Ange namn på nytt rum:")
        if ok and room_name:
            room_name = "".join(c for c in room_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            if not room_name:
                QMessageBox.warning(self, "Ogiltigt Namn", "Vänligen ange ett giltigt rumnamn.")
                return

            path = self.room_file(room_name)
            # Kontrollera om rummet redan finns i vår aktuella lista
            if room_name in self.current_rooms:
                QMessageBox.information(self, "Rum Finns Redan", f"Rum '{room_name}' finns redan.")
            else:
                # Skapa rumfilen
                with open(path, "a", encoding="utf-8") as f:
                    f.write(f"Rum '{room_name}' skapades {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

                # Uppdatera rumlistan omedelbart efter att ha skapat rummet
                self.ladda_rum()
                self.room_combo.setCurrentText(room_name)
                self.last_seen_content = ""
                self.byt_rum()

    def byt_rum(self):
        """Byter till ett annat rum"""
        new_room = self.room_combo.currentText()
        if new_room != self.current_room:
            # Markera alla mentions i det nya rummet som lästa när man besöker det
            self.markera_alla_mentions_i_rum_som_last(new_room)
            self.current_room = new_room
            self.last_seen_content = ""
            self.uppdatera_chatt()

    def skicka_meddelande(self):
        """Skickar ett meddelande"""
        msg = self.entry.text().strip()
        if msg:
            # Kolla efter mentions i meddelandet
            mentioned_users = []
            words = msg.split()
            for word in words:
                if word.startswith('@') and len(word) > 1:
                    mentioned_users.append(word[1:])  # Ta bort '@'

            # Skriv meddelandet till chatten
            with open(self.room_file(), "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {USERNAME}: {msg}\n")

            # Lägg till mentions i mentions.txt för varje nämnd användare
            for mentioned_user in mentioned_users:
                # Skapa ett unikt ID för meddelandet
                timestamp = time.strftime('%H:%M:%S')
                message_id = f"{timestamp}_{hash(msg + mentioned_user) & 0xFFFFFFFF}"

                # Spara mention i filen
                with open(mentions_file, "a", encoding="utf-8") as f:
                    f.write(f"{mentioned_user}:{self.current_room}|{message_id}\n")

            self.entry.clear()
            self.uppdatera_chatt()

    def rensa_chatt(self):
        """Rensar chatthistoriken"""
        reply = QMessageBox.question(self, "Rensa Chatt",
                                    "Är du säker på att du vill rensa chatthistoriken för detta rum?",
                                    QMessageBox.Yes | QMessageBox.No,
                                    QMessageBox.No)

        if reply == QMessageBox.Yes:
            with open(self.room_file(), "w", encoding="utf-8") as f:
                f.write(f"Chatten rensades {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.uppdatera_chatt()

    # --- Textstorleksfunktioner ---
    def oka_textstorlek(self):
        """Ökar textstorleken"""
        if self.font_size < 24:
            self.font_size += 1
            self.font_size_slider.setValue(self.font_size)
            self.uppdatera_textstorlek()

    def minska_textstorlek(self):
        """Minskar textstorleken"""
        if self.font_size > 10:
            self.font_size -= 1
            self.font_size_slider.setValue(self.font_size)
            self.uppdatera_textstorlek()

    def andrad_textstorlek(self, value):
        """Hanterar ändring av textstorlek via slider"""
        self.font_size = value
        self.uppdatera_textstorlek()

    def uppdatera_textstorlek(self):
        """Uppdaterar textstorleken i gränssnittet"""
        # Uppdatera displayen
        self.font_size_display.setText(f"{self.font_size}px")

        # Uppdatera chatten med ny textstorlek
        self.uppdatera_chatt()

    # --- Opacitetsfunktioner ---
    def oka_opacitet(self):
        """Ökar opaciteten"""
        if self.window_opacity < 1.0:
            self.window_opacity = min(1.0, self.window_opacity + 0.05)
            self.opacity_slider.setValue(int(self.window_opacity * 100))
            self.uppdatera_opacitet()

    def minska_opacitet(self):
        """Minskar opaciteten"""
        if self.window_opacity > 0.4:
            self.window_opacity = max(0.4, self.window_opacity - 0.05)
            self.opacity_slider.setValue(int(self.window_opacity * 100))
            self.uppdatera_opacitet()

    def andrad_opacitet(self, value):
        """Hanterar ändring av opacitet via slider"""
        self.window_opacity = value / 100.0
        self.uppdatera_opacitet()

    def uppdatera_opacitet(self):
        """Uppdaterar opaciteten i gränssnittet"""
        # Uppdatera displayen
        self.opacity_display.setText(f"{int(self.window_opacity * 100)}%")

        # Tillämpa ny opacitet på fönstret
        self.setWindowOpacity(self.window_opacity)

        # Försök göra chattexten mer läsbar genom att öka kontrasten
        if self.window_opacity < 0.8:
            # När fönstret är mer genomskinligt, gör texten mer kontrastrik
            self.chat_text.setStyleSheet(f"""
                QTextEdit {{
                    background-color: #252526;
                    color: #ffffff;
                    border: 2px solid #3e3e42;
                    border-radius: 4px;
                    padding: 8px;
                    font-family: 'Segoe UI', sans-serif;
                    font-size: {self.font_size}px;
                    selection-background-color: #007acc;
                }}
            """)
        else:
            # Återställ till normal styling
            self.chat_text.setStyleSheet(f"""
                QTextEdit {{
                    background-color: #252526;
                    color: #e0e0e0;
                    border: 1px solid #3e3e42;
                    border-radius: 4px;
                    padding: 8px;
                    font-family: 'Segoe UI', sans-serif;
                    font-size: {self.font_size}px;
                    selection-background-color: #007acc;
                }}
            """)

    def uppdatera_online_anvandare(self):
        """Uppdaterar online-listan"""
        try:
            current_time = time.time()

            # Läs hela filen först
            try:
                with open(users_file, "r", encoding="utf-8") as f:
                    users = f.read().splitlines()
            except:
                users = []

            # Processera alla användare i minnet först
            updated_users = []
            seen_users = set()

            # Lägg till nuvarande användare först
            updated_users.append(f"{USERNAME}|{current_time}")
            seen_users.add(USERNAME)

            # Processa andra användare
            for user_line in users:
                try:
                    if "|" not in user_line:
                        continue

                    name, timestamp = user_line.rsplit("|", 1)

                    # Hoppa över vår egen rad (vi har redan lagt till den)
                    if name == USERNAME:
                        continue

                    # Kolla om användaren fortfarande är online (within 2 minuter)
                    if current_time - float(timestamp) < 120:
                        # Undvik dubletter och korrupta namn
                        if name and name not in seen_users:
                            updated_users.append(user_line)
                            seen_users.add(name)
                except (ValueError, IndexError):
                    # Skip corrupt lines
                    continue

            # Skriv tillbaka hela listan på en gång
            try:
                with open(users_file, "w", encoding="utf-8") as f:
                    for user_line in updated_users:
                        f.write(user_line + "\n")
            except:
                pass

            # Bygg online-listan i minnet först
            online_users = []
            for user_line in updated_users:
                try:
                    if "|" not in user_line:
                        continue
                    name, timestamp = user_line.rsplit("|", 1)
                    # Ytterligare kontroll för att vara säker
                    if current_time - float(timestamp) < 120 and name and len(name) > 1:  # Lägg till längdkontroll
                        online_users.append(name)
                except (ValueError, IndexError):
                    continue

            # Sortera och ta bort eventuella dubletter
            online_users = sorted(list(set(online_users)))

            # Uppdatera UI på en gång
            current_items = []
            for i in range(self.online_list.count()):
                current_items.append(self.online_list.item(i).text())

            if current_items != online_users:
                self.online_list.clear()
                for user in online_users:
                    if user and len(user) > 1:  # Filtrera bort förkortade namn
                        self.online_list.addItem(user)

        except Exception as e:
            print(f"Fel vid uppdatering av online-användare: {e}")

    def kolla_mentions_fran_fil(self):
        """Kollar mentions.txt efter nya mentions för denna användare"""
        try:
            with open(mentions_file, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()

            current_unseen_mentions = set()

            for line in lines:
                line = line.strip()
                if line and "|" in line:
                    user_room, message_id = line.rsplit("|", 1)
                    if ":" in user_room:
                        mentioned_user, room = user_room.split(":", 1)

                        # Om detta är en mention för denna användare
                        if mentioned_user == USERNAME:
                            mention_key = f"{room}|{message_id}"

                            # Kolla om denna mention redan är läst
                            if mention_key not in self.seen_mentions:
                                current_unseen_mentions.add(room)

            # Uppdatera bara om det finns ändringar
            if current_unseen_mentions != self.unseen_mentions:
                self.unseen_mentions = current_unseen_mentions
                self.uppdatera_notice_indikatorer()

        except Exception as e:
            print(f"Fel vid läsning av mentions: {e}")

    def uppdatera_chatt(self):
        """Uppdaterar chatten"""
        path = self.room_file()
        with open(path, "r", encoding="utf-8") as f:
            current_content = f.read()

        if current_content == self.last_seen_content:
            return

        scrollbar = self.chat_text.verticalScrollBar()
        old_scroll_position = scrollbar.value()
        at_bottom = old_scroll_position == scrollbar.maximum()

        # Use the current font size for all text elements
        content_size = self.font_size
        username_size = self.font_size + 1
        timestamp_size = self.font_size - 1
        system_size = self.font_size - 1

        html_content = f"""
        <html>
        <head>
        <style>
            body {{
                font-family: 'Segoe UI', sans-serif;
                font-size: {content_size}px;
                color: #e0e0e0;
                background-color: #252526;
                margin: 0;
                padding: 0;
                line-height: 1.4;
            }}
            .message {{
                margin: 8px 0;
                padding: 6px 0;
            }}
            .timestamp {{
                color: #6a9955;
                font-size: {timestamp_size}px;
                font-weight: bold;
                margin-right: 8px;
            }}
            .username {{
                color: #569cd6;
                font-weight: bold;
                font-size: {username_size}px;
                margin-right: 6px;
            }}
            .content {{
                color: #e0e0e0;
                word-wrap: break-word;
                font-size: {content_size}px;
                display: inline;
            }}
            .mention {{
                background-color: #3c3c3c;
                color: #ffd700;
                padding: 2px 4px;
                border-radius: 3px;
                font-weight: bold;
            }}
            .system {{
                color: #ce9178;
                font-style: italic;
                font-size: {system_size}px;
                margin: 8px 0;
                padding: 6px 0;
            }}
        </style>
        </head>
        <body>
        """

        lines = current_content.splitlines()
        for line in lines:
            if "skapades" in line or "rensades" in line:
                html_content += f'<div class="system">{line}</div>'
                continue

            if line.startswith('[') and ']' in line:
                timestamp_end = line.find(']')
                timestamp = line[1:timestamp_end]
                rest = line[timestamp_end+2:]

                if ': ' in rest:
                    username_end = rest.find(': ')
                    username_part = rest[:username_end]
                    message = rest[username_end+2:]

                    if f"@{USERNAME}" in message:
                        message = message.replace(f"@{USERNAME}", f'<span class="mention">@{USERNAME}</span>')

                    html_content += f'''
                    <div class="message">
                        <span class="timestamp">[{timestamp}]</span>
                        <span class="username">{username_part}:</span>
                        <span class="content">{message}</span>
                    </div>
                    '''
                else:
                    html_content += f'<div class="system">{line}</div>'
            else:
                html_content += f'<div class="system">{line}</div>'

        html_content += "</body></html>"

        self.chat_text.setHtml(html_content)

        if at_bottom:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(old_scroll_position)

        self.last_seen_content = current_content

    def closeEvent(self, event):
        self.chat_timer.stop()
        self.users_timer.stop()
        self.mention_timer.stop()
        self.blink_timer.stop()
        self.room_timer.stop()
        try:
            with open(users_file, "r", encoding="utf-8") as f:
                users = f.read().splitlines()
            users = [u for u in users if not u.startswith(USERNAME + "|")]
            with open(users_file, "w", encoding="utf-8") as f:
                f.write("\n".join(users) + "\n")
        except:
            pass
        event.accept()

# --- Starta app ---
window = ChatWindow()
window.show()
sys.exit(app.exec_())

