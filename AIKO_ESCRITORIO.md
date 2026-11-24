# Aiko por voz en Windows

Arranca desde una terminal interactiva de Windows con `pymanager exec -3.11 main.py` o `start_backend.bat`. En cada inicio puedes habilitar el micrófono local y, por separado, la apertura de apps y la consulta de Gmail. Aunque rechaces el micrófono, el backend normal inicia. Si lo habilitas, cierra la consola de escucha o presiona Ctrl+C para detenerla. El arranque ASGI (por ejemplo, `uvicorn main:app`) no abre el micrófono.

## Preparación local

1. En PowerShell, dentro del backend, instala los complementos con `.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt`.
2. Descarga el [modelo español pequeño de Vosk](https://alphacephei.com/vosk/models) y extrae su contenido a `%LOCALAPPDATA%\Aiko\modelo-es`. Las carpetas internas del modelo deben quedar directamente allí.
3. Verifica que Windows permita el micrófono para aplicaciones de escritorio. Aiko transcribe localmente, no guarda audio y solo procesa órdenes que empiecen por «Aiko» o lleguen dentro de los ocho segundos posteriores a la activación.

## Aplicaciones y juegos

Coloca accesos directos de Windows en `%LOCALAPPDATA%\Aiko\accesos`. Usa el acceso oficial de cada juego o el acceso de instancia que exporte tu launcher de Minecraft.

| Orden después de «Aiko» | Acceso directo |
| --- | --- |
| Abre Valorant | Valorant.lnk |
| Abre Fortnite | Fortnite.lnk |
| Abre Minecraft | Minecraft.lnk |
| Abre Minecraft Prueba | Minecraft Prueba.lnk |
| Abre Minecraft Parásitos | Minecraft Parasitos.lnk |
| Abre Minecraft Prueba y abre el primer mundo | Minecraft Prueba Mundo.lnk |
| Abre Minecraft Parásitos y abre el primer mundo | Minecraft Parasitos Mundo.lnk |

Para las órdenes de mundo, configura un acceso que ya sepa iniciar el mundo concreto. El soporte depende del launcher y de la versión del modpack. Aiko no inspecciona ni elige automáticamente el primer mundo de la lista.

«Abre Google» y «Abre YouTube» abren el navegador predeterminado. Para «Abre Google y pon YouTube el video más reciente de Aquino», guarda en `%LOCALAPPDATA%\Aiko\settings.json` un objeto con `aquino_channel_id` y el ID del canal de YouTube. Aiko abre la publicación más reciente devuelta por el feed público de ese canal. La reproducción automática depende del navegador.

## Gmail

Habilita Gmail API en tu proyecto de Google Cloud y descarga el [cliente OAuth de escritorio](https://developers.google.com/workspace/gmail/api/quickstart/python?hl=es-419) como `%LOCALAPPDATA%\Aiko\gmail-client.json`. Si la app OAuth está en pruebas, agrega tu cuenta como usuario de prueba.

Al autorizar Gmail en el inicio, el navegador permite aprobar el acceso de solo lectura. «Aiko, revisa mi correo» muestra en la consola hasta cinco asuntos de la bandeja de entrada. El cliente y el token quedan fuera del repositorio, en la carpeta local de Aiko. Para quitar el acceso, revócalo en tu cuenta de Google y elimina `gmail-token.json`.

Si escribes esa orden de Aquino en el chat, recibirás un enlace al video verificado o a la pestaña Videos del canal si falta la configuración o falla el feed. El chat no abre aplicaciones de la PC desde el servidor.
