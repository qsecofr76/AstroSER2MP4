# AstroSER to MP4 Converter (v1.2.0)

**AstroSER to MP4 Converter** è un'applicazione desktop leggera e potente progettata specificamente per gli astrofotografi. Consente di visualizzare, ottimizzare, colorizzare e convertire i filmati astronomici non compressi in formato `.ser` in video `.mp4` ad alta compatibilità o in animazioni `.gif`.

---

## Caratteristiche principali

* **Drag & Drop Compatto**: Trascina il file `.ser` nell'area superiore per caricarlo istantaneamente.
* **Layout a Schede (Tabbed UI)**: Interfaccia organizzata in 4 schede tematiche (*Immagine & Colore*, *Velocità & Taglio*, *Colorizzazione HSL*, *Logo & Titoli*) che garantisce la massima chiarezza e accessibilità su qualsiasi risoluzione.
* **Anteprima con Segnalibri di Crop Visivi**: Slider di anteprima avanzato (`BookmarkSlider`) con visualizzazione in tempo reale, salto automatico al fotogramma e **segnalibri visivi colorati (🟢 Inizio Crop, 🔴 Fine Crop)** tracciati direttamente sulla barra.

### 📷 Immagine & Colore
* **Supporto File SER Già Debayerizzati (RGB/BGR)**: Rilevamento automatico di file a 3 canali o modalità esplicita *"Disattivato (Già a Colori / RGB)"* per preservare fedelmente la resa cromatica originale registrata dalla camera.
* **Debayerizzazione ad Alta Fedeltà**: Supporta gli algoritmi **Edge-Aware** (anti-righe e artefatti), **VNG** e Bilineare Standard, con override del pattern Bayer (`RGGB`, `BGGR`, `GRBG`, `GBRG`, `MONO`, `RGB`, `RGB_PLANAR`).
* **Auto-Stretch & Stiramento Gamma**: Ottimizzazione del contrasto dei dettagli scuri (12/14/16 bit) e stiramento gamma non lineare dei toni medi.
* **Auto White Balance (AWB)**: Bilanciamento automatico del bianco (con disattivazione automatica di default per file già debayerizzati).

### ⏱️ Velocità & Taglio (Trim)
* **Regolazione della Velocità & Slow Motion**: Selezione manuale dei FPS o moltiplicatori rapidi di velocità, inclusi rallentamenti a **0.5x (1/2)**, **0.33x (1/3)**, **0.25x (1/4)**, **0.1x** ed accelerazioni fino a **10x**.
* **Taglio Fotogrammi (Trim Range)**: Definizione esplicita del fotogramma di partenza e di arrivo per esportare solo una porzione del video. Pulsanti *"Da Anteprima"* per catturare la posizione corrente.

### 🎨 Colorizzazione Solare & HSL
* **Motore LUT per Colorizzazione Solare**: Trasforma le riprese monocromatiche in bianco e nero in immagini colorate astronomicamente accurate, eliminando al 100% qualsiasi alone o inversione al bordo del disco solare.
* **Preset Astronomici Nativi**:
  * **Rosso Solare H-alpha (656nm - Rubino)**: Rosso rubino profondo con calde sfumature sulle zone di forte intensità.
  * **Arancione Solare (Prominenze / Luce Solare)**
  * **Giallo Solare (Continuum / Luce Bianca)**
  * **Oro Solare**
  * **Calcio-K / CaK (393nm - Violetto)**
  * **Blu (Deep Sky)**
  * **Inferno & Plasma (Falso Colore)**
* **Regolazione HSL Personalizzata**: Cursori in tempo reale per **Tonalità / Hue (0-360°)**, **Saturazione (0-200%)** e **Luminosità (-100..+100)**.

### 🏷️ Logo & Titoli (Intro / Outro)
* **Sovrapposizione Logo / Filigrana PNG**: Inserimento di marchi d'acqua o loghi PNG trasparenti (canale alfa) con posizionamento nei 4 angoli o al centro, dimensione regolabile (%) ed opacità (%) in anteprima live.
* **Schede Titolo Iniziale e Finale (Intro / Outro)**: Aggiunta automatica di titoli iniziali e finali con durata in secondi personalizzabile. Supporta sia formati grafici standard (`.png`, `.jpg`, `.bmp`, `.tif`) sia formati astronomici natii (**FITS / `.fit` / `.fits`**) gestiti via `astropy`.

### 🎬 Esportazione
* **Video MP4 H.264 & GIF Animati**: Controllo diretto della qualità e del bitrate del video.
* **Multi-Codec Fallback**: Supporto automatico per encoder `avc1`, `H264` e `mp4v`.

---

## Come usare l'applicazione

1. Avvia `AstroSer2Mp4.exe` o esegui `python app.py`.
2. Trascina un file `.ser` sull'area superiore o fai clic per selezionarlo.
3. Utilizza le schede a sinistra per regolare colore, velocità, taglio fotogrammi, colorizzazione ed eventuali loghi/titoli.
4. Verifica il risultato in tempo reale nell'anteprima a destra.
5. Seleziona il formato di destinazione (`.mp4` o `.gif`) e fai clic su **Converti / Esporta**.

---

## Requisiti di sistema e dipendenze

* Windows 10 o 11 (64-bit).
* Python 3.9+ (se eseguito da sorgente) con i pacchetti: `PyQt6`, `opencv-python`, `numpy`, `pillow`, `astropy`.

---
*Sviluppato per gli appassionati di astrofotografia solare, planetaria e ISS.*
