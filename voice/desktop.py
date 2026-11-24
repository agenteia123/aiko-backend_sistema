"""Local, opt-in desktop commands. This module exposes no HTTP endpoints."""
import json
import os
from pathlib import Path
import queue
import re
import sys
import subprocess
import time
import unicodedata
from urllib.parse import urlencode
from urllib.request import urlopen
import webbrowser
from xml.etree import ElementTree

DESKTOP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Aiko"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
AQUINO_VIDEOS = "https://www.youtube.com/@aquino_/videos"
SHORTCUTS = {
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


def parse_command(text):
    text = normalize(text)
    text = re.sub(r"^aiko ", "", text)
    if re.fullmatch(
        r"(?:(?:abre|entra a) google y )?(?:abre youtube y )?"
        r"(?:pon(?:(?: en)? youtube)?|reproduce|abre|busca) "
        r"(?:en youtube )?el video mas (?:reciente|nuevo) de aquino",
        text,
    ):
        return "youtube", ""
    if text in ("lee mis ultimos correos", "revisa mi correo", "revisa mis correos"):
        return "gmail", ""
    text = re.sub(r"^abre (?:el )?", "", text) if text.startswith("abre ") else ""
    text = re.sub(r"^minecraft (?:el )?paquete de mods (?:de )?", "minecraft ", text)
    text = re.sub(r" y (?:inicia|abre) el primer mundo(?: que (?:esta|este) (?:hay|ahi))?$", " primer mundo", text)
    if text in SHORTCUTS:
        return "shortcut", SHORTCUTS[text]
    if text in ("google", "youtube"):
        return "web", text
    return None


def read_settings():
    path = DESKTOP_DIR / "settings.json"
    settings = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    if not isinstance(settings, dict):
        raise ValueError("settings.json debe contener un objeto JSON.")
    return settings


def latest_aquino_video(settings):
    channel_id = settings.get("aquino_channel_id", "")
    if not isinstance(channel_id, str) or not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", channel_id):
        raise ValueError("Configura aquino_channel_id en settings.json.")
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
    if action == "shortcut":
        shortcut = DESKTOP_DIR / "accesos" / (target + ".lnk")
        if not shortcut.is_file():
            raise ValueError(f"Falta configurar el acceso directo {shortcut.name}.")
        os.startfile(shortcut)
    elif action == "youtube":
        webbrowser.open(latest_aquino_video(settings))
    elif action == "web":
        webbrowser.open("https://www." + target + ".com/")


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
    if allow_gmail:
        try:
            gmail = connect_gmail()
        except ValueError as exc:
            print(f"Gmail desactivado. {exc}")
        except Exception as exc:
            print(f"Gmail desactivado. Error de autorización ({type(exc).__name__}).")

    def process(command):
        try:
            execute(command, allow_apps, gmail, settings)
        except ValueError as exc:
            print(str(exc), flush=True)
        except Exception as exc:
            print(f"No se completó la orden ({type(exc).__name__}).", flush=True)

    listen(model_path, process)


def start_listener():
    if sys.platform != "win32" or not sys.stdin.isatty():
        return None

    def ask(question):
        return normalize(input(question + " [s/N] ")) in ("s", "si")

    try:
        if not ask("¿Permitir que Aiko escuche el micrófono localmente?"):
            return None
        args = [sys.executable, "-m", "voice.desktop"]
        if ask("¿Permitir que Aiko abra aplicaciones y páginas por voz?"):
            args.append("--apps")
        if ask("¿Permitir que Aiko consulte Gmail por voz?"):
            args.append("--gmail")
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
