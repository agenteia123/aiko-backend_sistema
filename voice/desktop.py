"""Local, opt-in desktop commands. This module exposes no HTTP endpoints."""
import hashlib
import json
import logging
import os
from pathlib import Path
import queue
import re
import sys
import subprocess
import tempfile
import time
import unicodedata
from urllib.parse import quote, urlencode
from urllib.request import urlopen
import webbrowser
from xml.etree import ElementTree

logger = logging.getLogger(__name__)

DESKTOP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Aiko"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
AQUINO_CHANNEL_ID = "UCKuufKpyTISGU1TGj9n0q2A"
AQUINO_VIDEOS = "https://www.youtube.com/@aquino_/videos"
SHORTCUTS = {
    "riot": "Riot Client",
    "riot client": "Riot Client",
    "steam": "Steam",
    "epic": "Epic Games Launcher",
    "epic games": "Epic Games Launcher",
    "epic games launcher": "Epic Games Launcher",
    "valorant": "Valorant",
    "valoran": "Valorant",
    "fortnite": "Fortnite",
    "fornite": "Fortnite",
    "minecraft": "Minecraft",
    "minecraft prueba": "Minecraft Prueba",
    "minecraft parasitos": "Minecraft Parasitos",
    "minecraft prueba primer mundo": "Minecraft Prueba Mundo",
    "minecraft parasitos primer mundo": "Minecraft Parasitos Mundo",
}


def normalize(text):
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return " ".join(re.findall(r"[a-z0-9]+", "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )))


def youtube_channel_handle(name):
    if re.fullmatch(r"@[A-Za-z0-9_.-]{1,30}", name):
        return name
    return {"aquisi": "@AQUISI_", "aquino": "@AQUINO_"}.get(normalize(name))


def parse_command(text):
    text_original = text
    text = normalize(text)
    text = re.sub(r"^aiko ", "", text)
    if re.fullmatch(
        r"(?:(?:abre|entra a) google y )?(?:abre youtube y )?"
        r"(?:pon(?:(?: en)? youtube)?|reproduce|abre|busca) "
        r"(?:en youtube )?el video mas (?:reciente|nuevo) de aquino",
        text,
    ):
        return "youtube", ""
    raw = re.sub(r"^(?:aiko[, ]+|por favor[, ]+)", "", text_original.strip(), flags=re.IGNORECASE)
    if re.fullmatch(r"(?:abre|inicia) spotify y (?:pon|reproduce) musica(?: por favor)?", text):
        return "spotify_music", "Spotify"

    if re.match(r"(?:abre|pon|reproduce) ", text) and re.search(r"\b(?:playlist[s]?|lista de reproduccion)\b", text):
        playlist = re.search(r"[?&]list=([A-Za-z0-9_-]{12,80})(?=[&#\s]|$)", raw)
        position = re.search(r"\b(?:pon|reproduce) (?:la |el )?(?:pista |cancion )?(\d{1,3})\b", text)
        if not playlist:
            return "playlist_clarify", ""
        index = int(position[1]) if position else 1
        if 1 <= index <= 500:
            return "youtube_playlist", f"{playlist[1]}:{index}"
        return "playlist_clarify", ""
    latest = re.fullmatch(
        r"(?:abre|busca|pon|reproduce) (?:el )?(?:ultimo video|video mas (?:nuevo|reciente)) "
        r"(?:del canal )?de (.+?)(?: por favor)?",
        raw.replace("último", "ultimo").replace("más", "mas"), re.IGNORECASE,
    )
    compound = re.fullmatch(
        r"(?:abre|busca) (?:el )?canal (?:de )?(.+?) y (?:pon|abre|reproduce) "
        r"(?:el )?(?:ultimo(?: video)?|video mas (?:nuevo|reciente))(?: por favor)?",
        raw.replace("último", "ultimo").replace("más", "mas"), re.IGNORECASE,
    )
    if latest or compound:
        name = (latest or compound)[1]
        handle = youtube_channel_handle(name)
        return ("youtube_latest", handle) if handle else ("youtube_channel_clarify", name)
    if re.fullmatch(
        r"(?:miralo(?: tu)?(?: entonces)? y )?(?:pon|abre|reproduce) "
        r"(?:el )?ultimo(?: video)?(?: por favor)?",
        text,
    ):
        return "youtube_followup", ""
    channel = re.fullmatch(
        r"(?:abre|busca(?:me)?|entra a) (?:el )?canal (?:de )?(.+?)(?: en youtube)?(?: por favor)?",
        raw, re.IGNORECASE,
    )
    if channel:
        handle = youtube_channel_handle(channel[1])
        if handle:
            return "youtube_channel", handle
        return "web_url", youtube_search(channel[1] + " canal oficial")
    google = re.fullmatch(r"(?:abre|entra a) en google (.+?)(?: por favor)?", text)
    if google:
        return "web_url", "https://www.google.com/search?" + urlencode({"q": google[1]})
    search = re.fullmatch(
        r"(?:abre youtube y )?(?:busca(?:me)?|haz una busqueda de) (.+)", text
    )
    if search:
        query = search[1]
        if query.startswith("en youtube "):
            return "web_url", youtube_search(query.removeprefix("en youtube "))
        if query.endswith(" en youtube"):
            return "web_url", youtube_search(query.removesuffix(" en youtube"))
        if query.startswith("en google ") or query.endswith(" en google"):
            query = query.removeprefix("en google ").removesuffix(" en google")
            return "web_url", "https://www.google.com/search?" + urlencode({"q": query})
        return None
    music = re.fullmatch(r"(?:pon(?:me)?|reproduce)(?: en youtube)? (.+)", text)
    if music:
        return "youtube_play", music[1].removesuffix(" en youtube").removesuffix(" por favor")
    if text in ("lee mis ultimos correos", "revisa mi correo", "revisa mis correos"):
        return "gmail", ""
    command = re.fullmatch(
        r"(?:(?:no )?solo tu |no )?(?:abre|inicia|ejecuta) (?:el |la )?(.+)", text
    )
    if command is None:
        return None
    text = re.sub(r" por favor$", "", command[1])
    text = re.sub(r"^juego ins?talado en mi pc llamado ", "", text)
    if re.fullmatch(r"(?:riot|riot client) y (?:abre|inicia) (?:el )?valoran[t]?", text):
        text = "valorant"
    text = re.sub(r"^minecraft (?:el )?paquete de mods (?:de )?", "minecraft ", text)
    text = re.sub(r" y (?:inicia|abre) el primer mundo(?: que (?:esta|este) (?:hay|ahi))?$", " primer mundo", text)
    if text in SHORTCUTS:
        return "shortcut", SHORTCUTS[text]
    if text in ("google", "youtube"):
        return "web_url", "https://www." + text + ".com/"
    if not text or len(text) > 100:
        return None
    if re.search(r"\b(?:que hago|como lo|que puedo|desde cuando)\b", text):
        return None
    if normalize(command[0]).startswith("no abre ") and not command[1].startswith("juego "):
        return None
    return "shortcut", text


def youtube_search(query):
    return "https://www.youtube.com/results?" + urlencode({"search_query": query})


def find_youtube_video(query, *, channel=False, playlist_index=None):
    if channel and query.casefold() == "@aquisi_":
        try:
            return latest_channel_feed_video("UC7jtSuXXamDt0eKFfYfGLDQ")
        except (OSError, ValueError, SyntaxError):
            pass
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    try:
        with YoutubeDL({
            "quiet": True, "no_warnings": True, "extract_flat": True,
            "socket_timeout": 5, "extractor_retries": 0, "retries": 0,
            "playlist_items": str(playlist_index or 1),
        }) as youtube:
            if playlist_index:
                source = "https://www.youtube.com/playlist?" + urlencode({"list": query})
            elif channel:
                source = "https://www.youtube.com/" + query + "/videos"
            else:
                source = "ytsearch1:" + query
            results = youtube.extract_info(source, download=False)
    except DownloadError:
        return None
    for entry in (results or {}).get("entries", []):
        if entry and re.fullmatch(r"[A-Za-z0-9_-]{11}", entry.get("id") or ""):
            params = {"v": entry["id"]}
            if playlist_index:
                params.update(list=query, index=playlist_index)
            return "https://www.youtube.com/watch?" + urlencode(params)
    return None


def open_web_url(url):
    if sys.platform == "win32":
        import winreg

        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                    path = Path(winreg.QueryValue(key, None))
                if path.is_absolute() and path.is_file():
                    subprocess.Popen([str(path), url])
                    return True
            except OSError:
                continue
        for key in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            if location := os.environ.get(key):
                chrome = Path(location) / "Google" / "Chrome" / "Application" / "chrome.exe"
                if chrome.is_file():
                    subprocess.Popen([str(chrome), url])
                    return True
    return webbrowser.open(url)


def read_settings():
    path = DESKTOP_DIR / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    if not isinstance(settings, dict):
        raise ValueError("settings.json debe contener un objeto JSON.")
    return settings


def latest_aquino_video(settings):
    channel_id = settings.get("aquino_channel_id", AQUINO_CHANNEL_ID)
    if not isinstance(channel_id, str) or not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", channel_id):
        raise ValueError("Configura aquino_channel_id en settings.json.")
    return latest_channel_feed_video(channel_id)


def latest_channel_feed_video(channel_id):
    feed = "https://www.youtube.com/feeds/videos.xml?" + urlencode({"channel_id": channel_id})
    ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    with urlopen(feed, timeout=8) as response:
        root = ElementTree.fromstring(response.read(512_000))
    videos = []
    for entry in root.findall("atom:entry", ns):
        video_id = entry.findtext("yt:videoId", "", ns)
        published = entry.findtext("atom:published", "", ns)
        if published and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            videos.append((published, video_id))
    if not videos:
        raise ValueError("El canal no devolvió videos.")
    return "https://www.youtube.com/watch?v=" + max(videos)[1]


def connect_gmail():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token = DESKTOP_DIR / "gmail-token.json"
    if token.exists():
        credentials = Credentials.from_authorized_user_file(str(token), scopes=GMAIL_SCOPES)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
    else:
        client = DESKTOP_DIR / "gmail-client.json"
        if not client.is_file():
            raise ValueError("Agrega gmail-client.json a la carpeta local de Aiko.")
        flow = InstalledAppFlow.from_client_secrets_file(str(client), GMAIL_SCOPES)
        credentials = flow.run_local_server(host="127.0.0.1", port=0, timeout_seconds=120)
    if not credentials.valid:
        raise ValueError("Token Gmail inválido. Elimina gmail-token.json y vuelve a autorizar.")
    temp = token.with_suffix(".tmp")
    temp.write_text(credentials.to_json(), encoding="utf-8")
    temp.replace(token)
    return credentials


def list_mail(credentials):
    from googleapiclient.discovery import build

    with build("gmail", "v1", credentials=credentials, cache_discovery=False) as gmail:
        messages = gmail.users().messages()
        result = messages.list(userId="me", labelIds=["INBOX"], maxResults=5).execute()
        print("Últimos asuntos de Gmail:", flush=True)
        for item in result.get("messages", []):
            message = messages.get(
                userId="me", id=item["id"], format="metadata", metadataHeaders=["Subject"]
            ).execute()
            subject = next((header["value"] for header in message["payload"]["headers"]
                            if header["name"].lower() == "subject"), "(sin asunto)")
            print(" - " + "".join(char for char in subject if char.isprintable()), flush=True)


def installed_shortcuts(target):
    """Look in Windows' usual launcher and desktop shortcut folders."""
    names = {normalize(target)}
    if normalize(target) == "minecraft":
        names.add("minecraft launcher")

    desktop_folders = [Path.home() / "Desktop"]
    for env_key in ("OneDrive", "PUBLIC"):
        if location := os.environ.get(env_key):
            desktop_folders.append(Path(location) / "Desktop")
    menu_folders = [
        Path(os.environ[key]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        for key in ("APPDATA", "PROGRAMDATA") if os.environ.get(key)
    ]
    for folder in [DESKTOP_DIR / "accesos", *desktop_folders, *menu_folders]:
        matches = folder.rglob("*") if folder in menu_folders else folder.glob("*")
        for path in matches:
            if (
                normalize(path.stem) in names
                and path.suffix.casefold() in {".lnk", ".url"}
                and path.is_file()
            ):
                yield path


def riot_client_path():
    program_data = os.environ.get("PROGRAMDATA")
    if program_data:
        registration = Path(program_data) / "Riot Games" / "RiotClientInstalls.json"
        try:
            data = json.loads(registration.read_text(encoding="utf-8-sig"))
            candidates = [data.get("rc_live")] if isinstance(data, dict) else []
            associated = data.get("associated_client") if isinstance(data, dict) else None
            if isinstance(associated, dict):
                candidates = [
                    client for game, client in associated.items()
                    if "valorant" in game.casefold()
                ] + candidates
            for candidate in candidates:
                if isinstance(candidate, str):
                    path = Path(candidate)
                    if path.is_absolute() and path.name.casefold() == "riotclientservices.exe" and path.is_file():
                        return path
        except (OSError, ValueError):
            pass

    drive = os.environ.get("SystemDrive", "C:")
    default = Path(drive + "/Riot Games/Riot Client/RiotClientServices.exe")
    return default if default.is_file() else None


def _manifest_fields(path):
    try:
        content = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return {}
    return dict(re.findall(r'^\s*"([^"]+)"\s+"((?:\\.|[^"\\])*)"', content, re.MULTILINE))


def steam_launch_uris(target):
    if sys.platform != "win32":
        return
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            location, _ = winreg.QueryValueEx(key, "SteamPath")
    except OSError:
        return
    root = Path(location)
    library_list = root / "steamapps" / "libraryfolders.vdf"
    libraries = [root]
    try:
        content = library_list.read_text(encoding="utf-8-sig", errors="replace")
        libraries.extend(
            Path(value.replace("\\\\", "\\"))
            for value in re.findall(r'^\s*"path"\s+"([^"]+)"', content, re.MULTILINE)
        )
    except OSError:
        pass
    for library in dict.fromkeys(libraries):
        for manifest in (library / "steamapps").glob("appmanifest_*.acf"):
            fields = _manifest_fields(manifest)
            app_id = fields.get("appid", "")
            if (
                normalize(fields.get("name", "")) == target
                and re.fullmatch(r"[0-9]{1,10}", app_id)
                and manifest.stem == "appmanifest_" + app_id
            ):
                yield "steam://rungameid/" + app_id


def epic_launch_uris(target):
    if not (program_data := os.environ.get("PROGRAMDATA")):
        return
    folder = Path(program_data) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    for manifest in folder.glob("*.item"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("bIsIncompleteInstall"):
            continue
        name = data.get("DisplayName")
        if not isinstance(name, str) or normalize(name) != target:
            continue
        launch_id = [data.get(key) for key in ("CatalogNamespace", "CatalogItemId", "AppName")]
        if all(isinstance(part, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in launch_id):
            yield "com.epicgames.launcher://apps/" + quote(":".join(launch_id), safe="") + "?action=launch&silent=true"


def riot_shortcut_target(shortcut):
    """Read a Riot shortcut without triggering Windows' repair dialog."""
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    powershell = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    try:
        result = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command",
             "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
             "(New-Object -ComObject WScript.Shell).CreateShortcut($env:AIKO_RIOT_LINK).TargetPath"],
            env={**os.environ, "AIKO_RIOT_LINK": str(shortcut)},
            capture_output=True, check=True, timeout=6,
            encoding="utf-8-sig", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        target = Path(result.stdout.strip())
        if target.is_absolute() and target.name.casefold() == "riotclientservices.exe" and target.is_file():
            return target
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def start_menu_app_uris(target):
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    powershell = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    try:
        result = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command",
             "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
             "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"],
            capture_output=True, check=True, timeout=6, encoding="utf-8-sig", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        apps = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return
    for app in apps if isinstance(apps, list) else [apps]:
        if not isinstance(app, dict):
            continue
        name, app_id = app.get("Name"), app.get("AppID")
        if isinstance(name, str) and (normalize(name) == target or (target == "minecraft" and normalize(name) == "minecraft launcher")) and isinstance(app_id, str):
            if re.fullmatch(r"[\w.{}!@+ -]{1,256}", app_id):
                yield "shell:AppsFolder\\" + app_id


def open_game_shortcut(target):
    name = normalize(target)
    if not name or len(name) > 100:
        raise ValueError("Nombre de aplicación inválido.")
    is_riot_game = target in {"Valorant", "Riot Client"}

    def destinations():
        if is_riot_game:
            arguments = "--launch-product=valorant --launch-patchline=live" if target == "Valorant" else ""
            if client := riot_client_path():
                yield str(client), arguments
            for shortcut in installed_shortcuts(target):
                if shortcut.suffix.casefold() == ".lnk" and (client := riot_shortcut_target(shortcut)):
                    yield str(client), arguments
            return
        yield from ((str(path), "") for path in installed_shortcuts(target))
        for source in (steam_launch_uris, epic_launch_uris, start_menu_app_uris):
            yield from ((uri, "") for uri in source(name))

    failures = []
    for path, arguments in destinations():
        try:
            if path.casefold().endswith(".exe"):
                os.startfile(path, "open", arguments, str(Path(path).parent))
            else:
                os.startfile(path)
        except OSError as exc:
            code = getattr(exc, "winerror", None) or exc.errno
            reason = f"error de Windows {code}" if code is not None else type(exc).__name__
            logger.warning("No se pudo abrir %s desde %s: %s", target, path, exc)
            failures.append(f"{Path(path).name}: {reason}")
        else:
            logger.info("Windows recibió la orden de abrir %s desde %s", target, path)
            return

    if not failures and is_riot_game:
        raise FileNotFoundError(
            "No encontré un RiotClientServices.exe válido en el registro de instalación "
            "de Riot ni en los accesos directos. Comprueba si Riot abre desde Inicio."
        )
    if not failures:
        raise FileNotFoundError(f"No encontré «{target}» en Inicio, el escritorio, Steam ni Epic.")
    raise OSError(f"Windows no pudo iniciar {target}. " + " · ".join(dict.fromkeys(failures)))


def execute(command, allow_apps, gmail, settings):
    if command is None:
        print("Orden no disponible.", flush=True)
        return
    action, target = command
    if action == "gmail":
        if gmail is None:
            print("Gmail está desactivado.", flush=True)
            return
        list_mail(gmail)
        return
    if not allow_apps:
        print("Apertura de aplicaciones desactivada.", flush=True)
        return
    if action in {"shortcut", "spotify_music"}:
        open_game_shortcut(target)
        if action == "spotify_music":
            print("Envié la orden de abrir Spotify. Inicia la reproducción desde Spotify.", flush=True)
    elif action == "playlist_clarify":
        print("Indica el enlace de la playlist de YouTube y el número de pista.", flush=True)
    elif action == "youtube_playlist":
        playlist, index = target.split(":")
        try:
            video = find_youtube_video(playlist, playlist_index=int(index))
        except ImportError:
            video = None
        if video:
            open_web_url(video)
        else:
            print("No pude verificar esa pista de la playlist.", flush=True)
    elif action == "youtube":
        open_web_url(latest_aquino_video(settings))
    elif action == "web_url":
        open_web_url(target)
    elif action == "youtube_channel":
        open_web_url("https://www.youtube.com/" + target)
    elif action == "youtube_latest":
        try:
            video = find_youtube_video(target, channel=True)
        except ImportError:
            video = None
        open_web_url(video or "https://www.youtube.com/" + target)
    elif action in {"youtube_followup", "youtube_channel_clarify"}:
        print("Indica el nombre o @usuario del canal para abrir su último video.", flush=True)
    elif action == "youtube_play":
        try:
            video = find_youtube_video(target)
        except ImportError:
            video = None
        open_web_url(video or youtube_search(target))


def listen(model_path, process):
    import sounddevice as sd
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)
    rate = int(sd.query_devices(kind="input")["default_samplerate"])
    recognizer = KaldiRecognizer(Model(str(model_path)), rate)
    audio = queue.Queue(maxsize=16)

    def on_audio(indata, frames, audio_time, status):
        try:
            audio.put_nowait(bytes(indata))
        except queue.Full:
            pass

    wake_deadline = 0
    with sd.RawInputStream(samplerate=rate, blocksize=rate // 10, dtype="int16",
                           channels=1, callback=on_audio):
        print('Micrófono activo. Di «Aiko» y luego la orden. Ctrl+C pausa la escucha.', flush=True)
        while True:
            if not recognizer.AcceptWaveform(audio.get()):
                continue
            phrase = normalize(json.loads(recognizer.Result()).get("text", ""))
            if phrase in ("aiko", "ayko"):
                wake_deadline = time.monotonic() + 8
                print("Escuchando orden…", flush=True)
                continue
            wake, _, remainder = phrase.partition(" ")
            if wake in ("aiko", "ayko"):
                phrase = remainder
            elif not phrase or time.monotonic() > wake_deadline:
                continue
            wake_deadline = 0
            process(parse_command(phrase))
            while True:
                try:
                    audio.get_nowait()
                except queue.Empty:
                    break
            recognizer.Reset()


def run(allow_apps, allow_gmail):
    if sys.platform != "win32":
        print("El asistente de escritorio requiere Windows.")
        return
    settings = read_settings()
    model_path = DESKTOP_DIR / "modelo-es"
    if not model_path.is_dir():
        raise ValueError(f"Falta el modelo de voz en {model_path}.")
    gmail = None

    def process(command):
        nonlocal gmail
        try:
            if command and command[0] == "gmail" and allow_gmail and gmail is None:
                gmail = connect_gmail()
            execute(command, allow_apps, gmail, settings)
        except (ValueError, OSError) as exc:
            print(str(exc), flush=True)
        except Exception as exc:
            print(f"No se completó la orden ({type(exc).__name__}).", flush=True)


    listen(model_path, process)


class DesktopPermissions:
    def __init__(self, reset=False):
        self.path = DESKTOP_DIR / "permisos.json"
        self.device = None
        self.choices = {}
        if sys.platform != "win32":
            return

        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                                access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            self.device = hashlib.sha256(machine_guid.encode("utf-8")).hexdigest()
        except (OSError, AttributeError) as exc:
            logger.warning("No se pudo identificar esta instalación de Windows: %s", exc)
        if reset:
            self.path.unlink(missing_ok=True)
        if self.device:
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(saved, dict) and saved.get("device") == self.device:
                    choices = saved.get("choices")
                    if isinstance(choices, dict):
                        self.choices = {key: value for key, value in choices.items() if type(value) is bool}
            except FileNotFoundError:
                pass
            except (OSError, ValueError) as exc:
                logger.warning("No se pudieron leer los permisos de Aiko: %s", exc)

    def allow(self, key, question):
        if sys.platform != "win32":
            return False
        if key in self.choices:
            return self.choices[key]
        if not sys.stdin.isatty():
            return False
        while True:
            try:
                answer = normalize(input(question + " [s/N] "))
            except EOFError:
                return False
            if answer in ("s", "si", "n", "no", ""):
                break
        allowed = answer in ("s", "si")
        self.choices[key] = allowed
        if self.device:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self.path.parent, delete=False
                ) as stream:
                    temporary = Path(stream.name)
                    try:
                        json.dump({"device": self.device, "choices": self.choices}, stream)
                    except OSError:
                        stream.close()
                        temporary.unlink(missing_ok=True)
                        raise
                try:
                    temporary.replace(self.path)
                finally:
                    temporary.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("No se pudieron guardar los permisos de Aiko: %s", exc)
        return allowed


def start_listener(permissions):
    try:
        if not permissions.allow("microphone", "¿Permitir que Aiko escuche el micrófono localmente?"):
            return None
        args = [sys.executable, "-m", "voice.desktop"]
        if permissions.allow("voice_apps", "¿Permitir que Aiko abra aplicaciones y páginas por voz?"):
            args.append("--apps")
        if permissions.allow("voice_gmail", "¿Permitir que Aiko consulte Gmail por voz?"):
            args.append("--gmail")
        model_path = DESKTOP_DIR / "modelo-es"
        if not model_path.is_dir():
            print(f"Escucha desactivada. Falta el modelo de voz en {model_path}.", flush=True)
            return None
        print("Iniciando la escucha local de Aiko en una consola aparte. No necesitas abrir la página.", flush=True)
        return subprocess.Popen(
            args,
            cwd=Path(__file__).resolve().parents[1],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    except (EOFError, OSError) as exc:
        print(f"Escucha desactivada ({type(exc).__name__}).")
        return None


if __name__ == "__main__":
    try:
        run("--apps" in sys.argv[1:], "--gmail" in sys.argv[1:])
    except KeyboardInterrupt:
        print("\nEscucha detenida.")
    except (ValueError, ImportError, OSError, RuntimeError) as exc:
        print(f"Escucha desactivada. {exc}")
    except Exception as exc:
        print(f"Escucha desactivada ({type(exc).__name__}).")
