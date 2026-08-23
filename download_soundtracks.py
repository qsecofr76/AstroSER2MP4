import os
import urllib.request
import json
import subprocess

os.makedirs("colonne_sonore", exist_ok=True)
headers = {'User-Agent': 'AstroSer2Mp4/1.2 (https://github.com/qsecofr76/AstroSER2MP4)'}

# 1. Fetch exact Wikimedia links
api_url = "https://commons.wikimedia.org/w/api.php?action=query&titles=File:Moonlight_Sonata.ogg|File:Ludwig_van_Beethoven_-_symphony_no._5_in_c_minor,_op._67_-_i._allegro_con_brio.ogg&prop=imageinfo&iiprop=url&format=json"

req = urllib.request.Request(api_url, headers=headers)
data = json.loads(urllib.request.urlopen(req).read())
pages = data['query']['pages']

audio_urls = {}
for p in pages.values():
    if 'imageinfo' in p:
        title = p['title']
        raw_url = p['imageinfo'][0]['url'].split('?')[0]
        if 'Moonlight' in title:
            audio_urls['Moonlight'] = raw_url
        elif 'symphony_no._5' in title:
            audio_urls['5th'] = raw_url

print("Resolved URLs:", audio_urls)

# Download Beethoven - Moonlight Sonata
if 'Moonlight' in audio_urls:
    print("Downloading Beethoven - Moonlight Sonata (Adagio sostenuto)...")
    req = urllib.request.Request(audio_urls['Moonlight'], headers=headers)
    ogg_data = urllib.request.urlopen(req).read()
    dest_path = os.path.join("colonne_sonore", "Beethoven_Moonlight_Sonata.ogg")
    with open(dest_path, "wb") as f:
        f.write(ogg_data)
    print(f"Saved {dest_path} ({len(ogg_data)} bytes)")

# Download Beethoven - 5th Symphony
if '5th' in audio_urls:
    print("Downloading Beethoven - 5th Symphony (Allegro con brio)...")
    req = urllib.request.Request(audio_urls['5th'], headers=headers)
    ogg_data = urllib.request.urlopen(req).read()
    dest_path = os.path.join("colonne_sonore", "Beethoven_5th_Symphony.ogg")
    with open(dest_path, "wb") as f:
        f.write(ogg_data)
    print(f"Saved {dest_path} ({len(ogg_data)} bytes)")

