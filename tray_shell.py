"""Native system tray lifecycle; explicit Exit is the only background shutdown."""
from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu


class TrayShell(QObject):
    def __init__(self, app, window, manager):
        super().__init__(window)
        self.app, self.window, self.manager = app, window, manager
        self.tray = QSystemTrayIcon(app.windowIcon(), self)
        self.menu = QMenu()
        self.open_action = self.menu.addAction('')
        self.stop_action = self.menu.addAction('')
        self.menu.addSeparator()
        self.exit_action = self.menu.addAction('')
        self.open_action.triggered.connect(self.restore)
        self.stop_action.triggered.connect(manager.stopAll)
        self.exit_action.triggered.connect(self.exit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.activated)
        manager.backgroundRequested.connect(self.hide)
        manager.changed.connect(self.update)
        app.aboutToQuit.connect(self.tray.hide)
        self.update()
        if QSystemTrayIcon.isSystemTrayAvailable(): self.tray.show()

    def update(self):
        tr = self.manager.tr_text
        self.open_action.setText(tr('打开窗口'))
        self.stop_action.setText(tr('全部停止'))
        self.exit_action.setText(tr('退出'))
        count = sum(s.active for s in self.manager.sessions.values())
        self.stop_action.setEnabled(count > 0)
        self.tray.setToolTip('Elysia Tunnel · ' + str(count) + ' ' + tr('运行中'))

    def hide(self):
        if self.manager.closing: return
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
            self.window.hide()
        else:
            self.window.showMinimized()

    def restore(self):
        if self.manager.closing: return
        self.window.showNormal()
        self.window.raise_()
        self.window.requestActivate()

    def activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick): self.restore()

    def exit(self):
        self.manager.close()
        self.tray.hide()
        self.window.close()
        self.app.quit()
