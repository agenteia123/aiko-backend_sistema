# Aiko por voz en Windows

Arranca desde una terminal interactiva de Windows con `pymanager exec -3.11 main.py` o `start_backend.bat`. Aiko pregunta una vez por cada permiso y guarda tanto las respuestas afirmativas como las negativas para el usuario y la instalación de Windows actuales. En otra PC vuelve a preguntar.

Para cambiar las decisiones, inicia con `pymanager exec -3.11 main.py --reset-desktop-permissions`. El permiso de Gmail de Aiko es independiente de la autorización de Google.

Si autorizaste el micrófono y el modelo de voz está instalado, Aiko inicia la escucha en una consola separada al arrancar el backend. Puedes usarla con la página cerrada, incluso sin iniciar el frontend. Espera el mensaje «Micrófono activo» en esa consola. Cierra la consola de escucha o detén el backend para detenerla. El arranque ASGI (por ejemplo, `uvicorn main:app`) no inicia la escucha.

## Preparación local

1. En PowerShell, dentro del backend, instala los complementos con `.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt`.
2. Descarga el [modelo español pequeño de Vosk](https://alphacephei.com/vosk/models) y extrae su contenido a `%LOCALAPPDATA%\Aiko\modelo-es`. Las carpetas internas del modelo deben quedar directamente allí.
3. Verifica que Windows permita el micrófono para aplicaciones de escritorio. Aiko transcribe localmente, no guarda audio y solo procesa órdenes que empiecen por «Aiko» o lleguen dentro de los ocho segundos posteriores a la activación.

## Aplicaciones y juegos

Aiko busca accesos existentes en Inicio y el escritorio. Puedes indicar uno específico colocando un acceso directo de Windows en `%LOCALAPPDATA%\Aiko\accesos`. Usa el acceso oficial de cada juego o el acceso de instancia que exporte tu launcher de Minecraft.

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

«Abre Google» y «Abre YouTube» abren el navegador predeterminado. Para «Abre Google y pon YouTube el video más reciente de Aquino», Aiko usa el canal oficial @AQUINO_ por defecto. Puedes cambiarlo con `aquino_channel_id` en `%LOCALAPPDATA%\Aiko\settings.json`. Aiko abre la publicación más reciente devuelta por el feed público de ese canal. La reproducción automática depende del navegador.

## Gmail

Habilita Gmail API en tu proyecto de Google Cloud y descarga el [cliente OAuth de escritorio](https://developers.google.com/workspace/gmail/api/quickstart/python?hl=es-419) como `%LOCALAPPDATA%\Aiko\gmail-client.json`. Si la app OAuth está en pruebas, agrega tu cuenta como usuario de prueba.

Tras permitir Gmail en Aiko, la primera orden de correo abre el navegador para aprobar el acceso de solo lectura si todavía falta la autorización de Google. «Aiko, revisa mi correo» muestra en la consola hasta cinco asuntos de la bandeja de entrada. El cliente y el token quedan fuera del repositorio, en la carpeta local de Aiko. Para quitar el acceso, revócalo en tu cuenta de Google y elimina `gmail-token.json`.

Si escribes esa orden de Aquino en el chat, recibirás un enlace al video verificado o a la pestaña Videos del canal si falta la configuración o falla el feed. Para abrir automáticamente el video verificado al enviarlo por el chat local, acepta el permiso de YouTube en la terminal al iniciar el backend en Windows. Esta opción requiere que el backend esté enlazado a loopback y se recibe solo desde loopback. La reproducción automática depende del navegador.

Para abrir juegos desde el chat local de Windows, acepta el permiso correspondiente al arrancar el backend. Escribe «abre Valorant», «abre Fortnite» o los nombres de las instancias de Minecraft definidos arriba. Se usan los mismos accesos directos que por voz.

Puedes pedir «abre Riot Client», «abre Steam» y «abre Epic Games». Para Valorant, si no hay acceso directo, Aiko busca el cliente registrado por Riot y le pide abrir Valorant. Para Fortnite y Minecraft se usan los accesos de Windows que haya instalado el launcher. Por voz y en el chat local, Aiko también busca nombres en Inicio y en los registros locales de juegos instalados en Steam y Epic. Para programas portables, puedes agregar un acceso directo con el nombre que quieras usar.
