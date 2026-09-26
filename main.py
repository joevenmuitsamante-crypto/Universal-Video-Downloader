
import os, sys, json, re, subprocess, threading, urllib.request, tempfile, hashlib, shutil, zipfile, base64, webbrowser, datetime, time
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QIcon
from embedded_assets import GCASH_QR_B64, PAYPAL_QR_B64, WISE_QR_B64, LOGO_PNG_B64

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QProgressBar,
    QFileDialog, QCheckBox, QListWidget, QFrame, QMessageBox,
    QStackedWidget, QFormLayout, QSizePolicy, QScrollArea
)

APP_VERSION = os.environ.get("UMD_BUILD_VERSION", "4.3.2")
BUILD_YEAR = "2026"
# Set this to your GitHub repository, for example "leo123/UniversalMediaDownloader".
# Releases published there are checked from Settings so users can download new installers.
GITHUB_REPO = "joevenmuitsamante-crypto/Universal-Video-Downloader"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"

APP_DIR = Path(sys.argv[0]).resolve().parent
APP_EXE = APP_DIR / "UniversalMediaDownloader.exe"
HISTORY = Path.home() / "UniversalMediaDownloader_history.json"
LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "UniversalMediaDownloader"
LOCAL_APPDATA.mkdir(parents=True, exist_ok=True)
COMPONENT_DIR = LOCAL_APPDATA / "bin"
COMPONENT_DIR.mkdir(parents=True, exist_ok=True)
# Installed builds keep helper binaries in per-user app data so automatic updates
# do not require administrator rights. Portable builds still work with binaries
# placed beside the EXE.
YTDLP = COMPONENT_DIR / "yt-dlp.exe"
FFMPEG = COMPONENT_DIR / "ffmpeg.exe"
if not YTDLP.exists() and (APP_DIR / "yt-dlp.exe").exists():
    YTDLP = APP_DIR / "yt-dlp.exe"
if not FFMPEG.exists() and (APP_DIR / "ffmpeg.exe").exists():
    FFMPEG = APP_DIR / "ffmpeg.exe"
UPDATE_CACHE = LOCAL_APPDATA / "update_cache.json"
YTDLP_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
FFMPEG_API = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"

def hidden_run(cmd, **kwargs):
    startup = None
    creation = 0
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        creation = subprocess.CREATE_NO_WINDOW
    return subprocess.run(cmd, startupinfo=startup, creationflags=creation, **kwargs)

def desktop_dir():
    if os.name == "nt":
        try:
            r = hidden_run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "[Environment]::GetFolderPath('Desktop')"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            if r.returncode == 0 and r.stdout.strip():
                return Path(r.stdout.strip())
        except Exception:
            pass
    return Path.home() / "Desktop"


class UpdateWorker(QThread):
    result = Signal(dict)
    error = Signal(str)

    def run(self):
        try:
            results = {"app": self.app_release(), "yt-dlp": self.ytdlp(), "ffmpeg": self.ffmpeg()}
            self.result.emit(results)
        except Exception as e:
            self.error.emit(str(e))

    def api_json(self, url):
        req=urllib.request.Request(url, headers={"User-Agent":f"UniversalMediaDownloader/{APP_VERSION}","Accept":"application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))

    def app_release(self):
        if GITHUB_REPO.startswith("YOUR_GITHUB_"):
            return {"configured": False, "updated": False}
        d = self.api_json(GITHUB_RELEASES_API)
        latest = str(d.get("tag_name") or "").lstrip("v")
        asset = next((a for a in d.get("assets", []) if a.get("name", "").lower().endswith(".exe")), None)
        return {
            "kind": "app", "configured": True, "latest": latest,
            "release": d.get("id"), "url": d.get("html_url") or GITHUB_RELEASES_PAGE,
            "asset": asset.get("browser_download_url") if asset else "",
            "asset_name": asset.get("name") if asset else "",
            "updated": self.version_newer(latest, APP_VERSION)
        }

    def version_newer(self, latest, current):
        def nums(x):
            return tuple(int(n) for n in re.findall(r"\d+", str(x))[:4])
        return nums(latest) > nums(current)

    def ytdlp(self):
        d=self.api_json(YTDLP_API)
        latest=d.get("tag_name", "")
        current=self.local_ytdlp()
        asset=next((a for a in d.get("assets",[]) if a.get("name")=="yt-dlp.exe"), None)
        return {"kind":"yt-dlp","current":current or "Not installed","latest":latest,"release":d.get("id"),"asset":asset.get("browser_download_url") if asset else "","asset_name":"yt-dlp.exe","updated":self.newer(latest,current)}

    def ffmpeg(self):
        d=self.api_json(FFMPEG_API)
        latest=d.get("name") or d.get("tag_name") or "Latest Auto-Build"
        asset=next((a for a in d.get("assets",[]) if a.get("name")=="ffmpeg-master-latest-win64-gpl.zip"), None)
        checksum=next((a for a in d.get("assets",[]) if a.get("name")=="checksums.sha256"), None)
        expected=None
        if checksum:
            try:
                req=urllib.request.Request(checksum["browser_download_url"], headers={"User-Agent":f"UniversalMediaDownloader/{APP_VERSION}"})
                with urllib.request.urlopen(req, timeout=20) as r: txt=r.read().decode("utf-8",errors="replace")
                for line in txt.splitlines():
                    if "ffmpeg-master-latest-win64-gpl.zip" in line:
                        expected=line.split()[0].strip(); break
            except Exception: pass
        current=self.local_ffmpeg_hash()
        changed = bool(asset) and (expected is None or current != expected)
        return {"kind":"ffmpeg","current":self.local_ffmpeg_version() or "Not installed","latest":latest,"release":d.get("id"),"asset":asset.get("browser_download_url") if asset else "","asset_name":asset.get("name") if asset else "","expected_hash":expected,"updated":changed}

    def newer(self, latest,current):
        if not current: return True
        def nums(x): return tuple(int(n) for n in re.findall(r"\d+",x)[:5])
        return nums(latest)>nums(current)

    def local_ytdlp(self):
        if not YTDLP.exists(): return None
        try:
            r=hidden_run([str(YTDLP),"--version"],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=10)
            return r.stdout.strip()
        except Exception:return None

    def local_ffmpeg_version(self):
        if not FFMPEG.exists(): return None
        try:
            r=hidden_run([str(FFMPEG),"-version"],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=10)
            m=re.search(r"ffmpeg version\s+([^\s]+)",r.stdout)
            return m.group(1) if m else None
        except Exception:return None

    def local_ffmpeg_hash(self):
        if not FFMPEG.exists(): return None
        try:
            h=hashlib.sha256()
            with open(FFMPEG,"rb") as f:
                for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
            return h.hexdigest()
        except Exception:return None

class ComponentUpdateWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    completed = Signal(bool, str, str)

    def __init__(self, item):
        super().__init__()
        self.item = item

    def replace_file(self, source, target):
        backup = target.with_suffix(target.suffix + ".old")
        if target.exists():
            shutil.copy2(source, backup)
        try:
            shutil.copy2(source, target)
            if backup.exists():
                backup.unlink(missing_ok=True)
        except Exception:
            if backup.exists():
                shutil.copy2(backup, target)
            raise

    def run(self):
        kind = self.item.get("kind", "")
        td = None
        try:
            if not self.item.get("asset"):
                raise RuntimeError("No Windows update package was found.")

            label = "yt-dlp" if kind == "yt-dlp" else "FFmpeg"
            self.status.emit(f"Downloading {label} update…")
            td = Path(tempfile.mkdtemp(prefix="umd_update_"))
            pkg = td / self.item["asset_name"]

            req = urllib.request.Request(
                self.item["asset"],
                headers={
                    "User-Agent": f"UniversalMediaDownloader/{APP_VERSION}",
                    "Accept": "*/*"
                }
            )

            with urllib.request.urlopen(req, timeout=180) as r:
                total = int(r.headers.get("Content-Length") or 0)
                downloaded = 0
                with open(pkg, "wb") as f:
                    while True:
                        chunk = r.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.progress.emit(max(0, min(100, int(downloaded * 100 / total))))

            self.progress.emit(100)
            self.status.emit(f"Installing {label} update…")

            if kind == "yt-dlp":
                self.replace_file(pkg, YTDLP)
            else:
                with zipfile.ZipFile(pkg) as z:
                    z.extractall(td)
                candidate = next(td.rglob("ffmpeg.exe"), None)
                if not candidate:
                    raise RuntimeError("ffmpeg.exe was not found in the update package.")
                self.replace_file(candidate, FFMPEG)

            self.completed.emit(True, kind, str(self.item.get("release") or self.item.get("latest")))
        except Exception as e:
            self.completed.emit(False, kind, str(e))
        finally:
            if td:
                shutil.rmtree(td, ignore_errors=True)


class InfoWorker(QThread):
    success = Signal(dict)
    failure = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        if not YTDLP.exists():
            self.failure.emit("yt-dlp is not installed. Re-run the installer or check for updates.")
            return
        try:
            r = hidden_run(
                [str(YTDLP), "--dump-single-json", "--no-playlist",
                 "--skip-download", self.url],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60
            )
            if r.returncode != 0:
                self.failure.emit((r.stderr or r.stdout or "Preview unavailable")[-800:])
                return
            self.success.emit(json.loads(r.stdout))
        except Exception as e:
            self.failure.emit(str(e))

class DownloadWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        startup = None
        creation = 0
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = subprocess.SW_HIDE
            creation = subprocess.CREATE_NO_WINDOW
        try:
            p = subprocess.Popen(
                self.command,
                cwd=str(APP_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                startupinfo=startup,
                creationflags=creation
            )
            for line in p.stdout:
                line = line.strip()
                if not line:
                    continue
                m = re.search(r"(\d+(?:\.\d+)?)%", line)
                if m:
                    self.progress.emit(max(0, min(100, int(float(m.group(1))))))
                if len(line) > 220:
                    line = line[-220:]
                self.status.emit(line)
            code = p.wait()
            self.finished.emit(code == 0, "Download complete." if code == 0 else "Download failed.")
        except Exception as e:
            self.finished.emit(False, str(e))

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Media Downloader")
        self.resize(1120, 780)
        # Keep the minimum window small enough for 14-inch/high-DPI laptops.
        # The page itself is taller and scrollable, so controls are never forced
        # outside the visible screen.
        self.setMinimumSize(780, 520)
        logo_pix = QPixmap()
        logo_pix.loadFromData(base64.b64decode(LOGO_PNG_B64))
        if not logo_pix.isNull():
            self.setWindowIcon(QIcon(logo_pix))

        self.dark = True
        self.info_worker = None
        self.download_worker = None
        self.metadata = {}
        self.update_worker = None
        self.component_update_worker = None
        self.update_results = {}
        self.download_queue = []
        self.settings_path = LOCAL_APPDATA / "settings.json"

        self.build_ui()
        self.load_history()
        self.load_settings()
        self.apply_theme()
        # Do not contact update servers on first launch. Components are bundled by the installer;
        # users can manually check for updates from Settings.

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header: centered brand, no colored text box.
        header = QWidget()
        header.setObjectName("Header")
        hv = QVBoxLayout(header)
        hv.setContentsMargins(20, 18, 20, 14)
        hv.setSpacing(3)

        brand_row = QHBoxLayout()
        brand_row.addStretch()

        logo = QLabel()
        logo.setFixedSize(52, 52)
        logo.setAlignment(Qt.AlignCenter)
        pix = QPixmap()
        pix.loadFromData(base64.b64decode(LOGO_PNG_B64))
        if not pix.isNull():
            logo.setPixmap(pix.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        brand_row.addWidget(logo)

        title = QLabel("Universal Media Downloader")
        title.setObjectName("BrandTitle")
        brand_row.addWidget(title)
        brand_row.addStretch()
        hv.addLayout(brand_row)

        build = QLabel(f"Version {APP_VERSION}  •  Build {BUILD_YEAR}")
        build.setObjectName("BuildInfo")
        build.setAlignment(Qt.AlignCenter)
        hv.addWidget(build)
        outer.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(20, 16, 20, 20)
        body.setSpacing(18)
        outer.addLayout(body, 1)

        nav = QFrame()
        nav.setObjectName("Nav")
        nav.setFixedWidth(170)
        nv = QVBoxLayout(nav)
        nv.setContentsMargins(10, 14, 10, 12)
        nv.setSpacing(5)

        menu = QLabel("MENU")
        menu.setObjectName("NavLabel")
        nv.addWidget(menu)

        self.home_btn = self.nav_button("Home", True)
        self.history_btn = self.nav_button("History")
        self.settings_btn = self.nav_button("Settings")
        self.important_btn = self.nav_button("Important")
        self.support_btn = self.nav_button("Support")
        self.home_btn.clicked.connect(lambda: self.page(0))
        self.history_btn.clicked.connect(lambda: self.page(1))
        self.settings_btn.clicked.connect(lambda: self.page(2))
        self.important_btn.clicked.connect(lambda: self.page(3))
        self.support_btn.clicked.connect(lambda: self.page(4))

        nv.addWidget(self.home_btn)
        nv.addWidget(self.history_btn)
        nv.addWidget(self.settings_btn)
        nv.addWidget(self.important_btn)
        nv.addWidget(self.support_btn)
        nv.addStretch()

        self.theme_btn = QPushButton("☀  Appearance")
        self.theme_btn.setObjectName("ThemeButton")
        self.theme_btn.clicked.connect(self.toggle_theme)
        nv.addWidget(self.theme_btn)

        small = QLabel(f"v{APP_VERSION}")
        small.setObjectName("SmallInfo")
        small.setAlignment(Qt.AlignCenter)
        nv.addWidget(small)

        body.addWidget(nav)

        self.pages = QStackedWidget()
        self.pages.setObjectName("Pages")
        # Keep a content height large enough that compact/high-DPI screens use
        # the scroll bar instead of shrinking/clipping the preview controls.
        self.pages.setMinimumHeight(560)
        self.pages.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # Put the entire content area inside a vertical scroll area. This keeps
        # the layout intact on smaller laptops and high-DPI displays instead of
        # allowing the bottom of the preview/download controls to be clipped.
        self.page_scroll = QScrollArea()
        self.page_scroll.setObjectName("PageScroll")
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.page_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.page_scroll.setWidget(self.pages)
        body.addWidget(self.page_scroll, 1)

        self.pages.addWidget(self.make_home())
        self.pages.addWidget(self.make_history())
        self.pages.addWidget(self.make_settings())
        self.pages.addWidget(self.make_important())
        self.pages.addWidget(self.make_support())

    def nav_button(self, text, checked=False):
        b = QPushButton(text)
        b.setCheckable(True)
        b.setChecked(checked)
        b.setObjectName("NavButton")
        return b

    def page(self, i):
        self.pages.setCurrentIndex(i)
        for n, b in enumerate([self.home_btn, self.history_btn, self.settings_btn, self.important_btn, self.support_btn]):
            b.setChecked(n == i)

    def make_important(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(14)
        title = QLabel("Important")
        title.setObjectName("BigPageTitle")
        v.addWidget(title)
        card = QFrame()
        card.setObjectName("PreviewCard")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(24, 24, 24, 24)
        message = QLabel(
            "<b>IMPORTANT</b><br><br>"
            "Use Universal Media Downloader only for media you own, have permission to use, "
            "or are otherwise legally allowed to download.<br><br>"
            "<b>Users are responsible for complying with copyright laws and each platform's Terms of Service.</b>"
        )
        message.setObjectName("ImportantText")
        message.setWordWrap(True)
        message.setTextFormat(Qt.RichText)
        message.setTextInteractionFlags(Qt.TextSelectableByMouse)
        cv.addWidget(message)
        v.addWidget(card)
        v.addStretch()
        return w

    def make_support(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(14)
        title = QLabel("Support")
        title.setObjectName("BigPageTitle")
        v.addWidget(title)

        card = QFrame()
        card.setObjectName("SupportCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        headline = QLabel("100% FREE • SUPPORT IS OPTIONAL")
        headline.setObjectName("SupportHeadline")
        headline.setAlignment(Qt.AlignCenter)
        layout.addWidget(headline)

        msg = QLabel(
            "<b>This app is 100% free to use.</b><br><br>"
            "Support is completely optional. If Universal Media Downloader saves you time "
            "and you would like to help with future development, you can leave a small tip."
        )
        msg.setObjectName("SupportMessage")
        msg.setWordWrap(True)
        msg.setAlignment(Qt.AlignCenter)
        layout.addWidget(msg)

        qr_row = QHBoxLayout()
        for b64, name in (
            (GCASH_QR_B64, "GCash"),
            (PAYPAL_QR_B64, "PayPal"),
            (WISE_QR_B64, "Wise"),
        ):
            box = QVBoxLayout()
            qr = QLabel()
            qr.setObjectName("SupportQR")
            qr.setAlignment(Qt.AlignCenter)
            qr.setFixedSize(210, 210)
            pix = QPixmap()
            pix.loadFromData(base64.b64decode(b64))
            if not pix.isNull():
                qr.setPixmap(pix.scaled(198, 198, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            box.addWidget(qr, alignment=Qt.AlignCenter)
            label = QLabel(f"{name} • Optional support")
            label.setObjectName("SupportQRLabel")
            label.setAlignment(Qt.AlignCenter)
            box.addWidget(label)
            qr_row.addLayout(box)
        layout.addLayout(qr_row)

        note = QLabel("No payment is required to use any feature. Thank you for supporting the project! ❤️")
        note.setObjectName("SupportNote")
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignCenter)
        layout.addWidget(note)
        v.addWidget(card)
        v.addStretch()
        return w

    def make_home(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        row = QHBoxLayout()
        self.url = QLineEdit()
        self.url.setMinimumHeight(44)
        self.url.setPlaceholderText("Paste a YouTube, TikTok, Instagram, Facebook or supported URL…")
        self.url.setClearButtonEnabled(True)
        row.addWidget(self.url, 1)
        paste = QPushButton("Paste")
        paste.setMinimumHeight(44)
        paste.clicked.connect(lambda: self.url.setText(QApplication.clipboard().text().strip()))
        row.addWidget(paste)
        add = QPushButton("＋ Add URL")
        add.setMinimumHeight(44)
        add.clicked.connect(self.add_queue_url)
        row.addWidget(add)
        v.addLayout(row)

        self.detect = QLabel("Paste a URL to preview the media")
        self.detect.setObjectName("Muted")
        v.addWidget(self.detect)

        preview = QFrame()
        preview.setObjectName("PreviewCard")
        preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        preview.setFixedHeight(250)
        pv = QHBoxLayout(preview)
        pv.setContentsMargins(14, 14, 14, 14)
        pv.setSpacing(14)

        self.thumb = QLabel("Preview")
        self.thumb.setObjectName("Thumb")
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setFixedSize(300, 190)
        self.thumb.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        pv.addWidget(self.thumb)

        info = QVBoxLayout()
        self.vtitle = QLabel("No media selected")
        self.vtitle.setObjectName("VideoTitle")
        self.vtitle.setStyleSheet("background: transparent;")
        self.vtitle.setWordWrap(True)
        self.uploader = QLabel("")
        self.duration = QLabel("")
        self.resolutions = QLabel("")
        for x in [self.uploader, self.duration, self.resolutions]:
            x.setObjectName("Muted")
            x.setStyleSheet("background: transparent;")
            x.setWordWrap(True)
        info.addWidget(self.vtitle)
        info.addWidget(self.uploader)
        info.addWidget(self.duration)
        info.addWidget(self.resolutions)
        info.addStretch()
        pv.addLayout(info, 1)
        v.addWidget(preview)

        form = QFormLayout()
        form.setSpacing(8)
        self.quality = QComboBox()
        self.quality.addItems([
            "Video • Best", "Video • 2160p 4K", "Video • 1440p 2K",
            "Video • 1080p Full HD", "Video • 720p HD", "Video • 480p", "Video • 360p",
            "Audio • Best", "Audio • 320 kbps", "Audio • 256 kbps", "Audio • 128 kbps"
        ])
        self.update_quality_options(set(), set())
        form.addRow("Quality", self.quality)

        self.speed = QComboBox()
        self.speed.addItems(["Auto (4 connections)", "Fast (8 connections)", "Maximum (16 connections)"])
        form.addRow("Download speed", self.speed)

        folder_row = QHBoxLayout()
        self.folder = QLineEdit(str(Path.home() / "Downloads"))
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse)
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(browse)
        form.addRow("Save to", folder_row)
        v.addLayout(form)

        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(120)
        self.queue_list.setVisible(False)
        v.addWidget(self.queue_list)

        self.download = QPushButton("↓  Download")
        self.download.setObjectName("DownloadButton")
        self.download.setMinimumHeight(46)
        self.download.clicked.connect(self.start_download)
        v.addWidget(self.download)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        v.addWidget(self.progress)
        self.status = QLabel("Ready")
        self.status.setObjectName("Muted")
        v.addWidget(self.status)

        self.url.textChanged.connect(self.url_changed)
        return w

    def make_history(self):
        w = QWidget()
        v = QVBoxLayout(w)
        t = QLabel("Download History")
        t.setObjectName("PageTitle")
        v.addWidget(t)
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self.history_action_menu)
        v.addWidget(self.history_list, 1)
        hint = QLabel("Double-click an item for Open File, Open Folder, or Download Again.")
        hint.setObjectName("Muted")
        v.addWidget(hint)
        return w

    def make_settings(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(12)
        t = QLabel("Settings")
        t.setObjectName("PageTitle")
        v.addWidget(t)

        general = QFrame(); general.setObjectName("PreviewCard")
        gv = QVBoxLayout(general)
        gt = QLabel("General"); gt.setObjectName("SectionTitle"); gv.addWidget(gt)
        self.auto_paste = QCheckBox("Automatically paste URLs")
        self.auto_start = QCheckBox("Start download automatically")
        self.remember_folder = QCheckBox("Remember download folder")
        self.remember_folder.setChecked(True)
        for c in (self.auto_paste, self.auto_start, self.remember_folder): gv.addWidget(c)
        v.addWidget(general)

        downloads = QFrame(); downloads.setObjectName("PreviewCard")
        dv = QVBoxLayout(downloads)
        dt = QLabel("Downloads"); dt.setObjectName("SectionTitle"); dv.addWidget(dt)
        dr = QHBoxLayout(); dr.addWidget(QLabel("Download folder"))
        self.settings_folder = QLineEdit(self.folder.text())
        dr.addWidget(self.settings_folder, 1)
        choose = QPushButton("Browse")
        choose.clicked.connect(lambda: self.settings_folder.setText(QFileDialog.getExistingDirectory(self, "Choose download folder", self.settings_folder.text()) or self.settings_folder.text()))
        dr.addWidget(choose)
        dv.addLayout(dr)
        self.shortcut = QCheckBox("Create a desktop shortcut")
        self.shortcut.setChecked((desktop_dir() / "Universal Media Downloader.lnk").exists())
        dv.addWidget(self.shortcut)
        apply_btn = QPushButton("Apply Shortcut Setting")
        apply_btn.clicked.connect(self.apply_shortcut)
        dv.addWidget(apply_btn)
        v.addWidget(downloads)

        appearance = QFrame(); appearance.setObjectName("PreviewCard")
        av = QVBoxLayout(appearance)
        at = QLabel("Appearance"); at.setObjectName("SectionTitle"); av.addWidget(at)
        av.addWidget(QLabel("Theme"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light", "System"])
        self.theme_combo.currentTextChanged.connect(self.set_theme_from_settings)
        av.addWidget(self.theme_combo)
        v.addWidget(appearance)

        behavior = QFrame(); behavior.setObjectName("PreviewCard")
        bv = QVBoxLayout(behavior)
        bt = QLabel("Behavior"); bt.setObjectName("SectionTitle"); bv.addWidget(bt)
        self.keep_open = QCheckBox("Keep app open after download"); self.keep_open.setChecked(True)
        self.notifications = QCheckBox("Show notifications"); self.notifications.setChecked(True)
        bv.addWidget(self.keep_open); bv.addWidget(self.notifications)
        v.addWidget(behavior)

        update_card = QFrame(); update_card.setObjectName("PreviewCard")
        uv = QVBoxLayout(update_card)
        ut = QLabel("Updates"); ut.setObjectName("SectionTitle"); uv.addWidget(ut)
        self.update_info = QLabel(f"Universal Media Downloader\nVersion {APP_VERSION} • Build {BUILD_YEAR}")
        self.update_info.setObjectName("Muted"); self.update_info.setWordWrap(True); uv.addWidget(self.update_info)
        self.update_btn = QPushButton("Check GitHub for New Version")
        self.update_btn.clicked.connect(self.check_updates)
        uv.addWidget(self.update_btn)

        self.update_progress = QProgressBar()
        self.update_progress.setRange(0, 100)
        self.update_progress.setValue(0)
        self.update_progress.setTextVisible(False)
        self.update_progress.setVisible(False)
        uv.addWidget(self.update_progress)

        self.update_status = QLabel("")
        self.update_status.setObjectName("Muted")
        self.update_status.setWordWrap(True)
        uv.addWidget(self.update_status)

        v.addWidget(update_card)
        v.addStretch()
        return w

    def load_settings(self):
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8")) if self.settings_path.exists() else {}
            self.keep_open.setChecked(bool(data.get("keep_open", True)))
            self.notifications.setChecked(bool(data.get("notifications", True)))
            if hasattr(self, "auto_paste"): self.auto_paste.setChecked(bool(data.get("auto_paste", False)))
            if hasattr(self, "auto_start"): self.auto_start.setChecked(bool(data.get("auto_start", False)))
            if hasattr(self, "remember_folder"): self.remember_folder.setChecked(bool(data.get("remember_folder", True)))
        except Exception:
            pass

    def save_settings(self):
        try:
            data = {
                "keep_open": self.keep_open.isChecked(),
                "notifications": self.notifications.isChecked(),
                "auto_paste": self.auto_paste.isChecked() if hasattr(self, "auto_paste") else False,
                "auto_start": self.auto_start.isChecked() if hasattr(self, "auto_start") else False,
                "remember_folder": self.remember_folder.isChecked() if hasattr(self, "remember_folder") else True,
            }
            self.settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def apply_behavior_settings(self):
        self.save_settings()
        QApplication.beep()
        QMessageBox.information(self, "Settings Applied",
                                "Behavior settings have been applied successfully.")

    def notify_user(self, title, message):
        if not self.notifications.isChecked():
            return
        QApplication.beep()
        QMessageBox.information(self, title, message)

    def set_theme_from_settings(self, value=None):
        value = value or self.theme_combo.currentText()
        if value == "System":
            self.dark = QApplication.styleHints().colorScheme().name.lower() != "light"
        else:
            self.dark = value == "Dark"
        self.apply_theme()

    def load_update_cache(self):
        try: return json.loads(UPDATE_CACHE.read_text(encoding="utf-8"))
        except Exception: return {}

    def save_update_cache(self, data):
        try: UPDATE_CACHE.write_text(json.dumps(data,indent=2),encoding="utf-8")
        except Exception: pass

    def set_update_checking(self, checking):
        if hasattr(self, "update_btn"):
            self.update_btn.setEnabled(not checking)
            self.update_btn.setText(
                "Checking for new version…" if checking else "Check GitHub for New Version"
            )
        if hasattr(self, "update_status"):
            self.update_status.setText(
                "Checking GitHub for the latest app and component versions…" if checking else ""
            )

    def check_updates(self):
        if self.update_worker is not None and self.update_worker.isRunning():
            return
        self.status.setText("Checking for updates…")
        self.set_update_checking(True)
        self.update_worker = UpdateWorker()
        self.update_worker.result.connect(self.show_updates)
        self.update_worker.error.connect(self.update_check_failed)
        self.update_worker.finished.connect(lambda: self.set_update_checking(False))
        self.update_worker.start()

    def update_check_failed(self, error):
        self.status.setText("Update check failed")
        self.set_update_checking(False)
        msg = str(error)
        if "403" in msg or "rate" in msg.lower() or "limit" in msg.lower():
            msg = (
                "GitHub temporarily rate-limited the update check.\n\n"
                "Please wait a while before checking again. "
                "This does not mean your app or GitHub release is broken."
            )
        QMessageBox.warning(self, "Update check failed", msg)

    def show_updates(self, results):
        self.update_results = results
        app = results.get("app", {})

        if app.get("configured") and app.get("updated"):
            box = QMessageBox(self)
            box.setWindowTitle("New version available")
            box.setText(f"🚀 Universal Media Downloader v{app.get('latest')} is available")
            box.setInformativeText(
                "A new installer is available on GitHub. Download it to update the application."
            )
            btn = box.addButton("Download Update", QMessageBox.AcceptRole)
            box.addButton("Later", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is btn:
                webbrowser.open(app.get("asset") or app.get("url") or GITHUB_RELEASES_PAGE)

        # Component updates remain separate because they can be replaced without
        # reinstalling the whole application.
        cache = self.load_update_cache()
        for kind in ("yt-dlp", "ffmpeg"):
            item = results.get(kind, {})
            release = str(item.get("release") or item.get("latest"))
            if not item.get("updated") or cache.get(kind) == release:
                continue

            label = "yt-dlp" if kind == "yt-dlp" else "FFmpeg"
            box = QMessageBox(self)
            box.setWindowTitle(f"{label} update available")
            box.setText(f"🔄 {label} update available")
            box.setInformativeText(
                f"Current: {item.get('current')}\nLatest: {item.get('latest')}\n\n"
                "Would you like to update now?"
            )
            now = box.addButton("Update Now", QMessageBox.AcceptRole)
            box.addButton("Later", QMessageBox.RejectRole)
            box.exec()

            if box.clickedButton() is now:
                self.install_component_update(item)
            else:
                cache[kind] = release
                self.save_update_cache(cache)

        if not app.get("updated"):
            self.status.setText(
                "✓ No new app version found" if app.get("configured")
                else "GitHub app updates are not configured yet."
            )

        self.set_update_checking(False)

    def install_component_update(self, item):
        if self.component_update_worker is not None and self.component_update_worker.isRunning():
            return

        kind = item.get("kind", "")
        label = "yt-dlp" if kind == "yt-dlp" else "FFmpeg"

        self.update_progress.setValue(0)
        self.update_progress.setVisible(True)
        self.update_status.setText(f"Downloading {label} update…")
        self.status.setText(f"Updating {label}…")

        self.component_update_worker = ComponentUpdateWorker(item)
        self.component_update_worker.progress.connect(self.update_progress.setValue)
        self.component_update_worker.status.connect(self.update_status.setText)
        self.component_update_worker.completed.connect(self.component_update_finished)
        self.component_update_worker.start()

    def component_update_finished(self, ok, kind, result):
        label = "yt-dlp" if kind == "yt-dlp" else "FFmpeg"
        self.update_progress.setVisible(False)

        if ok:
            cache = self.load_update_cache()
            cache[kind] = result
            self.save_update_cache(cache)
            self.status.setText(f"✓ {label} updated")
            self.update_status.setText(f"✓ {label} updated successfully.")
            self.notify_user("Update Complete", f"{label} was updated successfully.")
        else:
            self.status.setText("Update failed")
            self.update_status.setText(f"✕ {label} update failed")
            QMessageBox.critical(
                self,
                "Update failed",
                f"Could not update {label}.\n\n{result}"
            )

    def replace_file(self, source, target):
        backup = target.with_suffix(target.suffix + ".old")
        if target.exists():
            shutil.copy2(target, backup)
        try:
            shutil.copy2(source, target)
            if backup.exists():
                backup.unlink(missing_ok=True)
        except Exception:
            if backup.exists():
                shutil.copy2(backup, target)
            raise

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose download folder", self.folder.text())
        if folder:
            self.folder.setText(folder)

    def url_changed(self, url):
        if not url.startswith("http"):
            return
        self.detect.setText("Reading media information…")
        self.info_worker = InfoWorker(url.strip())
        self.info_worker.success.connect(self.show_metadata)
        self.info_worker.failure.connect(lambda _: self.detect.setText("Preview unavailable"))
        self.info_worker.start()

    def update_quality_options(self, heights, bitrates):
        heights = {int(h) for h in heights if h}
        bitrates = {int(round(float(b))) for b in bitrates if b}
        targets = {
            "Video • 2160p 4K": 2160, "Video • 1440p 2K": 1440,
            "Video • 1080p Full HD": 1080, "Video • 720p HD": 720,
            "Video • 480p": 480, "Video • 360p": 360
        }
        for i in range(self.quality.count()):
            text = self.quality.itemText(i)
            item = self.quality.model().item(i)
            if not item: continue
            enabled = text in ("Video • Best", "Audio • Best")
            if text in targets:
                enabled = any(h >= targets[text] for h in heights)
            elif text.startswith("Audio • "):
                if text == "Audio • 320 kbps": enabled = any(b >= 320 for b in bitrates)
                elif text == "Audio • 256 kbps": enabled = any(b >= 256 for b in bitrates)
                elif text == "Audio • 128 kbps": enabled = any(b >= 128 for b in bitrates)
            item.setEnabled(enabled)
        if not self.quality.model().item(self.quality.currentIndex()).isEnabled():
            self.quality.setCurrentIndex(0)

    def show_metadata(self, d):
        self.metadata = d
        self.detect.setText("✓ " + str(d.get("extractor_key") or d.get("extractor") or "Supported site"))
        self.vtitle.setText(d.get("title") or "Untitled")
        self.uploader.setText(d.get("uploader") or d.get("channel") or "")
        duration = d.get("duration")
        self.duration.setText(self.fmt_time(duration) if duration else "")
        formats = d.get("formats", [])
        heights = sorted({int(f.get("height")) for f in formats if f.get("height")}, reverse=True)
        bitrates = []
        for f in formats:
            abr = f.get("abr")
            if abr:
                try: bitrates.append(float(abr))
                except Exception: pass
        self.update_quality_options(heights, bitrates)
        video = ", ".join(f"{h}p" for h in heights[:8]) or "None"
        audio = ", ".join(f"{int(b)} kbps" for b in sorted(set(bitrates), reverse=True)[:8]) or "Best available"
        self.resolutions.setText(f"Video: {video}\nAudio: {audio}")
        thumb = d.get("thumbnail")
        if thumb:
            threading.Thread(target=self.load_thumb, args=(thumb,), daemon=True).start()

    def load_thumb(self, url):
        try:
            data = urllib.request.urlopen(url, timeout=10).read()
            pix = QPixmap()
            pix.loadFromData(data)
            target = self.thumb.contentsRect().size()
            if target.width() < 10 or target.height() < 10:
                target = self.thumb.minimumSize()
            pix = pix.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumb.setPixmap(pix)
        except Exception:
            pass

    def fmt_time(self, seconds):
        s = int(seconds)
        if s >= 3600:
            return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"
        return f"{s//60:02d}:{s%60:02d}"

    def add_queue_url(self):
        url = self.url.text().strip()
        if not url.startswith("http"):
            QMessageBox.warning(self, "URL needed", "Paste a media URL first.")
            return
        self.download_queue.append(url)
        self.queue_list.setVisible(True)
        self.queue_list.addItem(url)
        self.url.clear()
        self.status.setText(f"Queued {len(self.download_queue)} URL(s)")

    def start_next_queue_item(self):
        if not self.download_queue:
            self.download.setEnabled(True)
            self.status.setText("✓ Queue complete")
            return
        url = self.download_queue.pop(0)
        if self.queue_list.count():
            self.queue_list.takeItem(0)
        self.url.blockSignals(True)
        self.url.setText(url)
        self.url.blockSignals(False)
        self.detect.setText("Reading queued media information…")
        self.info_worker = InfoWorker(url)
        self.info_worker.success.connect(lambda d, u=url: (self.show_metadata(d), self.process_download(u)))
        self.info_worker.failure.connect(lambda _, u=url: self.process_download(u))
        self.info_worker.start()

    def process_download(self, url):
        folder = self.folder.text().strip()
        if not url.startswith("http"):
            QMessageBox.warning(self, "URL needed", "Paste a media URL first.")
            self.download.setEnabled(True)
            return
        if not YTDLP.exists() or not FFMPEG.exists():
            QMessageBox.critical(self, "Missing files",
                                 "The downloader components are missing. Re-run the installer or use Settings → Check for Updates.")
            self.download.setEnabled(True)
            return
        Path(folder).mkdir(parents=True, exist_ok=True)
        q = self.quality.currentText()
        if q == "Video • Best":
            fmt = "bestvideo+bestaudio/best"
        elif q.startswith("Video • "):
            h = re.search(r"(\d+)p", q).group(1)
            fmt = f"bestvideo[height<={h}]+bestaudio/best"
        elif q == "Audio • Best":
            fmt = "bestaudio/best"
        else:
            b = re.search(r"(\d+)", q).group(1)
            fmt = f"bestaudio[abr<={b}]/bestaudio/best"

        output = str(Path(folder) / "%(title)s.%(ext)s")
        concurrent = {"Auto (4 connections)": "4", "Fast (8 connections)": "8",
                      "Maximum (16 connections)": "16"}.get(self.speed.currentText(), "4")
        cmd = [str(YTDLP), "--newline", "--no-playlist", "--concurrent-fragments", concurrent,
               "--ffmpeg-location", str(FFMPEG.parent), "-f", fmt]
        if q.startswith("Audio • "):
            cmd += ["-x", "--audio-format", "mp3"]
        else:
            cmd += ["--merge-output-format", "mp4"]
        cmd += ["-o", output, url]

        self.download.setEnabled(False)
        self.progress.setValue(0)
        self.status.setText("Starting…")
        self.download_worker = DownloadWorker(cmd)
        self.download_worker.progress.connect(self.progress.setValue)
        self.download_worker.status.connect(self.status.setText)
        self.download_worker.finished.connect(self.download_finished)
        self.download_worker.start()

    def start_download(self):
        if self.download_queue:
            self.start_next_queue_item()
        else:
            self.process_download(self.url.text().strip())

    def download_finished(self, ok, msg):
        if ok:
            self.progress.setValue(100)
            self.status.setText("✓ " + msg)
            self.save_history()
            if self.download_queue:
                self.start_next_queue_item()
                return
            self.download.setEnabled(True)
            self.notify_user("Download Complete", "Your media has been downloaded successfully.")
            if not self.keep_open.isChecked():
                self.close()
        else:
            self.status.setText("✕ " + msg)
            self.download.setEnabled(True)
            self.notify_user("Download Failed", msg)
            if not self.keep_open.isChecked():
                self.close()

    def save_history(self):
        try:
            data = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
        except Exception:
            data = []
        title = self.metadata.get("title", "Downloaded media")
        folder = Path(self.folder.text())
        candidates = []
        if folder.exists():
            try:
                candidates = sorted((p for p in folder.iterdir() if p.is_file()),
                                    key=lambda p: p.stat().st_mtime, reverse=True)
            except Exception:
                candidates = []
        actual = candidates[0] if candidates else None
        item = {
            "title": title,
            "url": self.url.text(),
            "folder": str(folder),
            "file": str(actual) if actual else "",
            "quality": self.quality.currentText(),
            "resolution": next((f"{f.get('height')}p" for f in self.metadata.get("formats", [])
                                if f.get("height")), ""),
            "size": self.format_bytes(actual.stat().st_size) if actual else "",
            "date": datetime.datetime.now().isoformat(timespec="seconds")
        }
        data.insert(0, item)
        try: HISTORY.write_text(json.dumps(data[:50], indent=2), encoding="utf-8")
        except Exception: pass
        self.load_history()

    def format_bytes(self, n):
        n = float(n)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    def load_history(self):
        if not hasattr(self, "history_list"): return
        self.history_list.clear()
        try: data = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
        except Exception: data = []
        for x in data:
            date = x.get("date", "")
            day = date[:10] if date else ""
            quality = x.get("quality", "")
            size = x.get("size", "")
            detail = " • ".join(v for v in (x.get("resolution"), quality, size) if v)
            text = f"✓ {x.get('title', 'Downloaded media')}"
            if detail: text += f"\n   {detail}"
            if day: text += f"   •   {day}"
            item = self.history_list.addItem(text)
            # store complete history item on the QListWidget item
            self.history_list.item(self.history_list.count()-1).setData(Qt.UserRole, x)

    def history_action_menu(self, item):
        data = item.data(Qt.UserRole) or {}
        menu = QMessageBox(self)
        menu.setWindowTitle("Download History")
        menu.setText(data.get("title", "Downloaded media"))
        open_file = menu.addButton("Open File", QMessageBox.AcceptRole)
        open_folder = menu.addButton("Open Folder", QMessageBox.ActionRole)
        again = menu.addButton("Download Again", QMessageBox.ActionRole)
        menu.addButton("Cancel", QMessageBox.RejectRole)
        menu.exec()
        clicked = menu.clickedButton()
        folder = Path(data.get("folder", ""))
        if clicked is open_file:
            saved = Path(data.get("file", ""))
            if saved.exists():
                os.startfile(str(saved))
            else: QMessageBox.information(self, "File not found", "The downloaded file could not be located.")
        elif clicked is open_folder:
            if folder.exists(): os.startfile(str(folder))
            else: QMessageBox.information(self, "Folder not found", "The saved download folder no longer exists.")
        elif clicked is again:
            self.url.setText(data.get("url", ""))
            self.page(0)
            self.start_download()

    def apply_shortcut(self):
        shortcut = desktop_dir() / "Universal Media Downloader.lnk"
        if self.shortcut.isChecked():
            def quote(s):
                return str(s).replace("'", "''")
            command = (
                "$w=New-Object -ComObject WScript.Shell;"
                f"$s=$w.CreateShortcut('{quote(shortcut)}');"
                f"$s.TargetPath='{quote(APP_EXE)}';"
                f"$s.WorkingDirectory='{quote(APP_DIR)}';"
                f"$s.IconLocation='{quote(APP_EXE)},0';"
                "$s.Save()"
            )
            r = hidden_run(["powershell.exe", "-NoProfile", "-NonInteractive",
                            "-ExecutionPolicy", "Bypass", "-Command", command],
                           capture_output=True, text=True)
            if r.returncode:
                QMessageBox.critical(self, "Shortcut error", r.stderr or "Could not create shortcut.")
                return
            QApplication.beep()
            QMessageBox.information(self, "Shortcut Applied",
                                    "The desktop shortcut has been created successfully.")
        else:
            try:
                shortcut.unlink(missing_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Shortcut error", str(e))
                return
            QApplication.beep()
            QMessageBox.information(self, "Shortcut Setting Applied",
                                    "The desktop shortcut has been removed successfully.")
        self.save_settings()

    def toggle_theme(self):
        self.dark = not self.dark
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet(DARK if self.dark else LIGHT)
        self.theme_btn.setText("☀  Appearance" if self.dark else "☾  Appearance")

DARK = """
QMainWindow,QWidget{background:#151515;color:#ECECEC;font-family:"Segoe UI";font-size:10pt}
#Header{background:transparent}
#BrandTitle{background:transparent;color:#F4F4F4;font-size:21pt;font-weight:700}
#BuildInfo,#SmallInfo{background:transparent;color:#858585}
#Nav{background:#1D1D1D;border:1px solid #2D2D2D;border-radius:16px}
#NavLabel{color:#777;padding:5px;font-size:8pt;font-weight:700}
#NavButton{background:transparent;border:0;text-align:left;padding:11px;border-radius:9px}
#NavButton:checked{background:#2B2B2B;color:#FFF}
#ThemeButton{background:transparent;border:1px solid #333;border-radius:9px;padding:8px;color:#CCC}
QLineEdit,QComboBox{background:#202020;color:#EEE;border:1px solid #363636;border-radius:10px;padding:9px}
QPushButton{background:#292929;color:#EEE;border:1px solid #3A3A3A;border-radius:10px;padding:9px 14px}
QPushButton:hover{background:#343434}
#PageScroll{background:transparent;border:0}
#PreviewCard{background:#1C1C1C;border:1px solid #2D2D2D;border-radius:18px}
#Thumb{background:#101010;border-radius:13px;color:#777}
#VideoTitle{color:#F4F4F4;font-size:16pt;font-weight:700;background:transparent}
#PageTitle{color:#F4F4F4;font-size:18pt;font-weight:700}
#BigPageTitle{color:#F4F4F4;font-size:23pt;font-weight:800}
#ImportantText{color:#F4F4F4;font-size:13pt;font-weight:600;background:transparent}
#SupportHeadline{color:#F4F4F4;font-size:18pt;font-weight:800;background:transparent}
#SupportMessage{color:#F4F4F4;font-size:12pt;background:transparent}
#SupportNote{color:#999;font-size:10pt;background:transparent}
#SupportQR{background:#FFF;border-radius:10px}
#SupportQRLabel{color:#F4F4F4;font-weight:700;background:transparent}
#SectionTitle{color:#F4F4F4;font-size:12pt;font-weight:700}
#SupportCard{background:#1C1C1C;border:1px solid #2D2D2D;border-radius:18px}
#GcashQR,#PaypalQR{background:#FFF;border-radius:10px}
#GcashLabel,#PaypalLabel{color:#F4F4F4;font-weight:700;background:transparent}
#Muted{color:#929292;background:transparent}
#DownloadButton{background:#F2F2F2;color:#111;border:0;border-radius:12px;font-size:11pt;font-weight:700}
QProgressBar{background:#252525;border:0;border-radius:5px;height:8px}
QProgressBar::chunk{background:#EDEDED;border-radius:5px}
QListWidget{background:#1C1C1C;color:#EEE;border:1px solid #2D2D2D;border-radius:12px;padding:8px}
QListWidget::item{padding:11px;border-radius:8px}
QListWidget::item:selected{background:#2B2B2B}
"""

LIGHT = """
QMainWindow,QWidget{background:#F5F5F7;color:#202020;font-family:"Segoe UI";font-size:10pt}
#Header{background:transparent}
#BrandTitle{background:transparent;color:#171717;font-size:21pt;font-weight:700}
#BuildInfo,#SmallInfo{background:transparent;color:#888}
#Nav{background:#FFF;border:1px solid #E4E4E4;border-radius:16px}
#NavLabel{color:#999;padding:5px;font-size:8pt;font-weight:700}
#NavButton{background:transparent;border:0;text-align:left;padding:11px;border-radius:9px}
#NavButton:checked{background:#ECECEC;color:#111}
#ThemeButton{background:transparent;border:1px solid #DDD;border-radius:9px;padding:8px;color:#555}
QLineEdit,QComboBox{background:#FFF;color:#202020;border:1px solid #DCDCDC;border-radius:10px;padding:9px}
QPushButton{background:#FFF;color:#222;border:1px solid #DCDCDC;border-radius:10px;padding:9px 14px}
QPushButton:hover{background:#EEEEEE}
#PageScroll{background:transparent;border:0}
#PreviewCard{background:#FFF;border:1px solid #E3E3E3;border-radius:18px}
#Thumb{background:#ECECEC;border-radius:13px;color:#888}
#VideoTitle{color:#171717;font-size:16pt;font-weight:700;background:transparent}
#PageTitle{color:#171717;font-size:18pt;font-weight:700}
#BigPageTitle{color:#171717;font-size:23pt;font-weight:800}
#ImportantText{color:#171717;font-size:13pt;font-weight:600;background:transparent}
#SupportHeadline{color:#171717;font-size:18pt;font-weight:800;background:transparent}
#SupportMessage{color:#171717;font-size:12pt;background:transparent}
#SupportNote{color:#777;font-size:10pt;background:transparent}
#SupportQR{background:#FFF;border-radius:10px}
#SupportQRLabel{color:#171717;font-weight:700;background:transparent}
#SectionTitle{color:#171717;font-size:12pt;font-weight:700}
#SupportCard{background:#FFF;border:1px solid #E3E3E3;border-radius:18px}
#GcashQR,#PaypalQR{background:#FFF;border-radius:10px}
#GcashLabel,#PaypalLabel{color:#171717;font-weight:700;background:transparent}
#Muted{color:#777;background:transparent}
#DownloadButton{background:#171717;color:#FFF;border:0;border-radius:12px;font-size:11pt;font-weight:700}
QProgressBar{background:#E2E2E2;border:0;border-radius:5px;height:8px}
QProgressBar::chunk{background:#222;border-radius:5px}
QListWidget{background:#FFF;color:#222;border:1px solid #E0E0E0;border-radius:12px;padding:8px}
QListWidget::item{padding:11px;border-radius:8px}
QListWidget::item:selected{background:#EEEEEE}
"""

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = App()
    win.show()
    sys.exit(app.exec())
