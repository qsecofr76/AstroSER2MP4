# AstroSER to MP4 Converter (v1.0.0)

AstroSER to MP4 Converter è un'applicazione desktop leggera e potente progettata specificamente per gli astrofotografi. Consente di visualizzare, ottimizzare e convertire i filmati astronomici non compressi in formato `.ser` in video `.mp4` ad alta compatibilità o in animazioni `.gif`.

## Caratteristiche principali

*   **Drag & Drop**: Trascina semplicemente il file `.ser` all'interno dell'applicazione per caricarlo istantaneamente.
*   **Anteprima Fotogrammi**: Slider integrato per scorrere i fotogrammi e verificare le regolazioni in tempo reale.
*   **Qualità Visiva e Stretching**:
    *   **Auto-Stretch**: Ottimizzazione del contrasto dei dettagli scuri per i sensori astronomici a 12/14/16 bit.
    *   **Stiramento Gamma**: Regolazione non lineare dei toni medi per far risaltare i dettagli dell'oggetto (es. ISS, Giove, Luna) senza bruciare le luci o compromettere il fondo cielo.
    *   **Auto White Balance (AWB)**: Rimozione istantanea della dominante verde o rossa tipica dei sensori raw a colori.
*   **Debayerizzazione ad Alta Fedeltà**:
    *   Supporta gli algoritmi **Edge-Aware** (che rimuove gli artefatti e le righe orizzontali) e **VNG**, oltre a quello bilineare.
    *   Override del pattern Bayer manuale (`RGGB`, `BGGR`, `GRBG`, `GBRG`, `MONO`, `RGB/BGR`) se l'header del file contiene dati di offset errati.
*   **Regolazione della Velocità**: Modifica del frame rate (FPS) del video o applicazione di moltiplicatori di velocità (es. 0.5x, 2.0x, ecc.).
*   **Massima Qualità (Compression-free)**: Controllo della qualità/bitrate del video H.264 fino al 100% per evitare la comparsa di blocchi di compressione su video a bassa risoluzione.
*   **Supporto GIF**: Generazione diretta di animazioni GIF ottimizzate per la condivisione sui social.

## Come usare l'eseguibile (.exe)

1.  Avvia `AstroSer2Mp4.exe`.
2.  Trascina un file `.ser` sull'interfaccia (o fai clic sull'area tratteggiata per cercarlo sul computer).
3.  Usa l'anteprima e gli slider per regolare il contrasto, la gamma e per verificare la correttezza dei colori.
4.  Seleziona il percorso e il nome del file di salvataggio.
5.  Fai clic su **Converti / Esporta**.

## Requisiti di sistema

*   Windows 10 o 11 (64-bit).
*   Non richiede installazione (eseguibile portabile standalone).

---
Sviluppato per gli appassionati di astrofotografia planetaria e ISS.
