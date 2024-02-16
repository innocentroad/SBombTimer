import sys
import time
import keyboard
import math
import configparser
import os
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QMenu
from PyQt5.QtGui import QFont, QColor, QPalette, QPainter, QPen, QIcon
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

class TimerThread(QThread):
    timer_updated = pyqtSignal(float)

    def __init__(self, initial_time, reset_callback):
        super().__init__()
        self.initial_time = initial_time
        self.current_time = initial_time
        self.running = False
        self.reset_callback = reset_callback

    def run(self):
        start_time = time.time()
        while self.running and self.current_time > 0:
            elapsed_time = time.time() - start_time
            self.current_time = self.initial_time - elapsed_time
            if self.current_time < 0:
                self.current_time = 0
            self.timer_updated.emit(self.current_time)
            time.sleep(0.1)

        if self.current_time <= 0:
            self.running = False
            self.reset_callback()

    def start_timer(self):
        self.running = True
        self.start()

    def stop(self):
        self.running = False

class TransparentWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.key_repeat_delay = 0.4
        self.last_key_press_time = 0

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.loadConfig()
        self.setupUIElements()
        self.setupEvents()
        self.setupLogs()
        self.setupMediaPlayer()

    def loadConfig(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.font_color = config.get('Settings', 'font_color')
        self.font_color_while_running = config.get('Settings', 'font_color_while_running')
        self.outline_color = config.get('Settings', 'outline_color')
        self.font_size = config.getint('Settings', 'font_size')
        self.initial_time = config.get('Settings', 'initial_time')
        self.window_x = config.getint('Settings', 'window_x')
        self.window_y = config.getint('Settings', 'window_y')
        self.start_key = config.get('Settings', 'start_key')
        self.log_key_a = config.get('Settings', 'log_key_a')
        self.log_key_b = config.get('Settings', 'log_key_b')
        self.increment_key = config.get('Settings', 'increment_key')
        self.decrement_key = config.get('Settings', 'decrement_key')
        self.boom_time = config.getint('Settings', 'boom_time') / 1000
        self.scramble_time = config.getint('Settings', 'scramble_time') / 1000
        self.brilliant_time = config.getint('Settings', 'brilliant_time') / 1000
        self.play_start_sound = config.getboolean('Settings', 'play_start_sound')
        self.play_bomb_sound = config.getboolean('Settings', 'play_bomb_sound')
        self.play_record_sound = config.getboolean('Settings', 'play_record_sound')
        self.sound_delay = config.getint('Settings', 'sound_delay') / 1000
        self.sound_volume = config.getint('Settings', 'sound_volume')

    def setupUIElements(self):
        self.setupTimer()
        self.setupMediaPlayer()
        self.setupLabel()
        self.setupContextMenu()
        self.setupUpdateTimer()

    def setupEvents(self):
        keyboard.on_press_key(self.start_key, self.start_countdown)
        keyboard.on_press_key(self.log_key_a, self.log_time_a)
        keyboard.on_press_key(self.log_key_b, self.log_time_b)
        keyboard.on_press_key(self.increment_key, self.increment_counters)
        keyboard.on_press_key(self.decrement_key, self.decrement_counters)

    def setupTimer(self):
        self.timer = QTimer(self)
        self.timer_thread = TimerThread(self.time_to_seconds(self.initial_time), self.reset_timer_and_logs)
        self.timer_thread.timer_updated.connect(self.update_time)

    def setupMediaPlayer(self):
        self.start_player = QMediaPlayer()
        self.start_player.setMedia(QMediaContent(QUrl.fromLocalFile("start.mp3")))
        self.bomb_player = QMediaPlayer()
        self.bomb_player.setMedia(QMediaContent(QUrl.fromLocalFile("bomb.mp3")))
        self.record_player = QMediaPlayer()
        self.record_player.setMedia(QMediaContent(QUrl.fromLocalFile("record.mp3")))
    
    def playStartSound(self):
        self.stopAllSounds()
        self.start_player.setVolume(self.sound_volume)
        self.start_player.play()

    def playBombSound(self):
        self.stopAllSounds()
        self.bomb_player.setVolume(self.sound_volume)
        self.bomb_player.play()

    def playRecordSound(self):
        self.stopAllSounds()
        self.record_player.setVolume(self.sound_volume)
        self.record_player.play()

    def stopAllSounds(self):
        self.start_player.stop()
        self.bomb_player.stop()
        self.record_player.stop()

    def setupLabel(self):
        self.label = QLabel(self.initial_time, self)
        self.label.setFont(QFont('Meiryo', self.font_size))
        self.label.setAlignment(Qt.AlignCenter)
        palette = self.label.palette()
        palette.setColor(QPalette.WindowText, QColor(self.font_color))
        self.label.setPalette(palette)
        
        self.label.setContentsMargins(10, 10, 10, 10)

    def setupContextMenu(self):
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)

    def showContextMenu(self, pos):
        menu = QMenu(self)
        exit_action = menu.addAction("終了")
        exit_action.triggered.connect(self.closeApplication)
        return_action = menu.addAction("戻る")
        return_action.triggered.connect(menu.close)
        menu.setStyleSheet("QMenu { color: white; background-color: rgba(50, 50, 50, 150); }" 
                           "QMenu::item:selected { background-color: rgba(100, 100, 100, 150); }")
        menu.exec_(self.mapToGlobal(pos))

    def closeApplication(self):
        QApplication.instance().quit()

    def setupUpdateTimer(self):
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_logs)
        self.update_timer.start(1000)

    def setupLogs(self):
        self.time_logs_a = []
        self.time_logs_b = []
        self.combined_logs = []
        self.log_time_b_counter = 0

    def start_countdown(self, event):
        if self.timer_thread.isRunning():
            self.reset_timer_and_logs()
        else:
            self.countdown_started = True
            self.timer_thread.initial_time = self.time_to_seconds(self.initial_time)
            self.reset_timer_and_logs()
            self.timer_thread.start_timer()
            self.setRunningFontColor()
            self.update_time(self.timer_thread.current_time)
            if self.play_start_sound:
                self.playStartSound()

    def log_time_a(self, event):
        if self.timer_thread.isRunning():
            recorded_time = self.timer_thread.current_time - self.boom_time
            self.time_logs_a.append(recorded_time)
            self.combined_logs.append(recorded_time)
            if self.play_record_sound:
                self.playRecordSound()

    def log_time_b(self, event):
        if self.timer_thread.isRunning():
            self.log_time_b_counter += 1
            if self.log_time_b_counter == 1:
                self.log_time_b_sc(event)
            elif self.log_time_b_counter == 2:
                self.log_time_b_br(event)
            
            if self.log_time_b_counter <= 2:
                if self.play_record_sound:
                    self.playRecordSound()

    def log_time_b_sc(self, event):
        recorded_time = self.timer_thread.current_time - self.boom_time
        self.time_logs_b.append(recorded_time)
        current_sc_time = recorded_time
        while current_sc_time > 0:
            self.combined_logs.append(current_sc_time)
            current_sc_time -= self.scramble_time

    def log_time_b_br(self, event):
        recorded_time = self.timer_thread.current_time - self.boom_time
        self.time_logs_b.append(recorded_time)
        current_br_time = recorded_time
        br_times = []
        while current_br_time > 0:
            br_times.append(current_br_time)
            current_br_time -= self.brilliant_time
        self.combined_logs = [x for x in self.combined_logs if x > (recorded_time - self.boom_time)]
        self.combined_logs.extend(br_times)

    def increment_counters(self, event):
        current_time = time.time()
        if not self.timer_thread.isRunning() and current_time - self.last_key_press_time > self.key_repeat_delay:
            new_time_seconds = self.time_to_seconds(self.initial_time) + 10
            self.initial_time = self.seconds_to_time(new_time_seconds)
            self.label.setText(self.initial_time)
            self.label.repaint()
            self.last_key_press_time = current_time
        elif self.timer_thread.isRunning() and current_time - self.last_key_press_time > self.key_repeat_delay:
            self.last_key_press_time = current_time
            for i in range(len(self.combined_logs)):
                self.combined_logs[i] += 1
            self.update_time(self.timer_thread.current_time)

    def decrement_counters(self, event):
        current_time = time.time()
        if not self.timer_thread.isRunning() and current_time - self.last_key_press_time > self.key_repeat_delay:
            new_time_seconds = max(0, self.time_to_seconds(self.initial_time) - 10)
            self.initial_time = self.seconds_to_time(new_time_seconds)
            self.label.setText(self.initial_time)
            self.label.repaint()
            self.last_key_press_time = current_time
        elif self.timer_thread.isRunning() and current_time - self.last_key_press_time > self.key_repeat_delay:
            self.last_key_press_time = current_time
            for i in range(len(self.combined_logs)):
                if self.combined_logs[i] > 0:
                    self.combined_logs[i] -= 1
            self.update_time(self.timer_thread.current_time)

    def time_to_seconds(self, time_str):
        minutes, seconds = map(int, time_str.split(':'))
        return minutes * 60 + seconds

    def seconds_to_time(self, seconds):
        minutes, seconds = divmod(seconds, 60)
        return f'{minutes:02d}:{seconds:02d}'

    def mousePressEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(self.label.font())
        rect = self.label.geometry()
        for dx in [-2, 0, 2]:
            for dy in [-2, 0, 2]:
                painter.setPen(QPen(QColor(self.outline_color)))
                painter.drawText(rect.translated(dx, dy), Qt.AlignCenter, self.label.text())
        painter.setPen(self.label.palette().color(QPalette.WindowText))
        painter.drawText(rect, Qt.AlignCenter, self.label.text())
        painter.end()

    def update_time(self, current_time):
        if self.combined_logs:
            if self.combined_logs[0] < current_time:
                seconds = int(self.combined_logs[0])
                minutes = seconds // 60
                seconds %= 60
                self.label_text = f"{minutes:02d}:{seconds:02d}"
                self.label.setText(self.label_text)
                self.label.repaint()
                
                if current_time - self.combined_logs[0] <= self.sound_delay:
                    if self.play_bomb_sound:
                        self.bomb_player.setVolume(self.sound_volume)
                        self.bomb_player.play()
            elif self.combined_logs[0] > current_time:
                self.combined_logs.pop(0)
                self.update_time(current_time)
        else:
            minutes = math.ceil(self.time_to_seconds(self.initial_time) / 60)
            seconds = self.time_to_seconds(self.initial_time) % 60
            self.label_text = f"{minutes:02d}:{seconds:02d}"
            if not self.timer_thread.isRunning():
                self.label.setText(self.label_text)
                self.label.repaint() 

    def setRunningFontColor(self):
        palette = self.label.palette()
        palette.setColor(QPalette.WindowText, QColor(self.font_color_while_running))
        self.label.setPalette(palette)

    def update_logs(self):
        self.combined_logs.sort(reverse=True)
        print("Combined logs:", self.combined_logs)

    def reset_timer_and_logs(self):
        if self.timer_thread.isRunning():
            self.timer_thread.stop()
            self.timer_thread.wait()
        self.timer_thread.current_time = self.time_to_seconds(self.initial_time)
        self.label.setText(self.initial_time)
        self.combined_logs.clear()
        self.time_logs_a.clear()
        self.time_logs_b.clear()
        self.log_time_b_counter = 0
        palette = self.label.palette()
        palette.setColor(QPalette.WindowText, QColor(self.font_color))
        self.label.setPalette(palette)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TransparentWindow()
    window.setGeometry(window.window_x, window.window_y, 200, 50)
    window.show()

    if getattr(sys, 'frozen', False):
        icon_path = os.path.join(sys._MEIPASS, "SBombTimer128.ico")
    else:
        icon_path = "SBombTimer128.ico"

    app.setWindowIcon(QIcon(icon_path))

    sys.exit(app.exec_())
