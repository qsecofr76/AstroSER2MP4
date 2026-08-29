# AstroSER to MP4 Converter (v1.4.0)

**AstroSER to MP4 Converter** è un'applicazione desktop professionale, leggera e potente progettata specificamente per gli astrofotografi. Consente di visualizzare, ottimizzare, ridurre il rumore termico/elettronico, colorizzare e convertire i filmati astronomici non compressi in formato `.ser` (o video `.avi`, `.mp4`, `.mov`) in video `.mp4` ad alta compatibilità e massima fluidità (con supporto per colonne sonore audio) o in animazioni `.gif`.

---

## Caratteristiche principali

* **Drag & Drop Intuitivo**: Trascina qualsiasi file `.ser` o video supportato nell'area superiore per caricarlo istantaneamente.
* **Layout a Schede Tematiche**: Interfaccia organizzata in schede (*Immagine & Colore*, *Velocità & Taglio*, *Colorizzazione HSL*, *Logo, Titoli & Audio*).
* **Anteprima Interattiva con Zoom & Pan**:
  * Pulsanti di **Zoom In (`🔍+`)**, **Zoom Out (`🔍-`)**, **Risoluzione Reale 1:1 (`1:1 Pixel Reali`)** e **Adatta alla Finestra (`↔️ Adatta`)**.
  * Supporto per **rotella del mouse** e **trascinamento (Click & Drag)** per navigare agilmente tra i dettagli a pieno ingrandimento.
* **Segnalibri di Crop Visivi**: Slider di anteprima avanzato (`BookmarkSlider`) con **segnalibri visivi colorati (🟢 Inizio Crop, 🔴 Fine Crop)** tracciati direttamente sulla barra.

### 📷 Immagine, Colore & Riduzione Rumore (Denoise)
* **Riduzione del Rumore Fotogramma per Fotogramma (Denoise)**:
  * **Bilateral Edge-Aware (Consigliato)**: Filtro bilaterale sulla luminanza con filtraggio della crominanza, elimina la grana e le macchie di colore nel cielo scuro preservando con precisione i bordi netti (fulmini, rami, tetti, dettagli planetari/solari).
  * **Non-Local Means (Alta Qualità)**: Denoising avanzato ad alta fedeltà.
  * **Solo Crominanza**: Rimuove le macchie di colore lasciando intatta al 100% la risoluzione originale della luminanza.
  * **Filtro Mediano**: Efficace contro singoli hot-pixel / pixel caldi del sensore.
  * **Anteprima in tempo reale**: Valuta l'effetto della pulizia del rumore all'istante spostando lo slider dell'intensità.
* **Debayerizzazione ad Alta Fedeltà & Mappatura Astronomica**: Riconoscimento automatico e corretto allineamento dei pattern Bayer astronomici (`RGGB`, `BGGR`, `GRBG`, `GBRG`, `MONO`, `RGB`, `RGB_PLANAR`), con algoritmi **Edge-Aware (anti-righe)**, **VNG** e **Bilineare**.
* **Auto-Stretch & Stiramento Gamma**: Ottimizzazione dinamica del contrasto e stiramento gamma non lineare dei toni scuri/medi.
* **Auto White Balance (AWB)**: Bilanciamento automatico del bianco per colori naturali.

### ⏱️ Velocità & Taglio (Trim)
* **Regolazione della Velocità & Slow Motion**: Selezione manuale dei FPS o moltiplicatori rapidi di velocità, inclusi rallentamenti a **0.5x (1/2)**, **0.33x (1/3)**, **0.25x (1/4)**, **0.1x** ed accelerazioni fino a **10x**.
* **Taglio Fotogrammi (Trim Range)**: Definizione esplicita del fotogramma iniziale e finale con pulsanti *"Da Anteprima"*.

### 🎨 Colorizzazione Solare & HSL
* **Motore LUT per Colorizzazione Solare**: Trasforma le riprese monocromatiche in immagini colorate astronomicamente accurate senza aloni o inversioni al bordo del disco solare.
* **Preset Astronomici Nativi**: **Rosso Solare H-alpha (656nm)**, **Arancione Solare**, **Giallo Solare (Continuum)**, **Oro Solare**, **Calcio-K (393nm)**, **Blu (Deep Sky)**, **Inferno** e **Plasma**.
* **Regolazione HSL Personalizzata**: Cursori in tempo reale per **Tonalità (Hue 0-360°)**, **Saturazione** e **Luminosità**.

### 🎵 Logo, Titoli & Colonna Sonora Audio
* **Integrazione Colonna Sonora Audio nell'MP4**: Inserisci qualsiasi file audio (`.mp3`, `.wav`, `.ogg`, `.aac`, `.flac`) come sottofondo musicale con ripetizione automatica in loop.
* **Libreria Musiche Classiche Inclusa (`colonne_sonore/`)**: Include brani di musica classica in pubblico dominio (*Beethoven - Moonlight Sonata*, *Beethoven - 5ª Sinfonia*).
* **Filigrana Logo PNG**: Posizionamento logo trasparente nei 4 angoli o al centro con scala ed opacità regolabili.
* **Schede Titolo Iniziale e Finale (Intro / Outro)**: Titoli di testa e coda con supporto per immagini standard e file astronomici **FITS (`.fit` / `.fits`)**.

### 🚀 Motore di Esportazione FFmpeg Libx264 Ultra-Compatibile
* **Codifica All-Intra (`-g 1`, `-bf 0`, `-tune fastdecode`, `-movflags +faststart`)**: Assicura che i video MP4 generati (anche ad altissima risoluzione 4K / 12 Megapixel e a bassi framerate) vengano riprodotti con **fluidità istantanea e senza scartare nessun fotogramma** su **VLC**, **Foto di Windows**, **QuickTime**, smartphone e browser web.
* **Compressione Efficiente**: La rimozione del rumore casuale ad alta frequenza riduce il peso del file video compresso del **10-20%** a parità di qualità visiva.

---

## Installazione e Avvio da Sorgente

1. Clona il repository:
   ```bash
   git clone https://github.com/qsecofr76/AstroSER2MP4.git
   cd AstroSER2MP4
   ```
2. Installa le dipendenze richieste:
   ```bash
   pip install -r requirements.txt
   ```
3. Avvia l'applicazione:
   ```bash
   python app.py
   ```

---

## Requisiti di sistema

* **Sistema Operativo**: Windows 10 o Windows 11 (64-bit), Linux o macOS.
* **Python**: 3.9 o superiore.
* **Dipendenze**: `PyQt6`, `opencv-python`, `numpy`, `Pillow`, `imageio-ffmpeg`, `astropy`.

---
*Sviluppato per gli appassionati di astrofotografia planetaria, solare, lunare e fenomeni atmosferici.*
