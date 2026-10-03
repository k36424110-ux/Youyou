"""Studio Les Mini-Gardiens : histoire -> images 3D -> voix -> animation -> episode + short."""
import asyncio, html, json, os, pathlib, shutil, subprocess, time, urllib.parse
import requests, edge_tts
from google import genai

OUT = pathlib.Path("output"); OUT.mkdir(exist_ok=True)
WORK = pathlib.Path("work"); WORK.mkdir(exist_ok=True)
MEM = pathlib.Path("episodes.json")
TEXT_MODEL = "gemini-2.5-flash"
VOICE = "fr-FR-DeniseNeural"
SEED = 1234

STYLE = "stylized 3D animated family movie style, vibrant colors, soft lighting, expressive faces, highly detailed, consistent characters"
CHARACTERS = {
 "Léo":   "Leo, a 4-year-old boy toddler with short curly brown hair, big green eyes, red cape, blue hero suit with a yellow lightning logo",
 "Maya":  "Maya, a 5-year-old girl with two black pigtails, brown skin, bright smile, orange cape, purple hero suit with a white wing logo",
 "Noah":  "Noah, a chubby 3-year-old boy with blond hair and freckles, green cape, grey hero suit with a rock logo",
 "Grumbo":"Grumbo, a funny grumpy giant grey fog-cat with big yellow eyes, cartoonish but fluffy",
}
WORLD = ("Les Mini-Gardiens sont des bébés héros de Bambouville (Léo: vitesse, Maya: vol, Noah: force) "
         "qui protègent la ville de Grumbo, le chat de brouillard qui vole les rires. "
         "Aventure, humour tendre, amitié, avec un mystère qui avance d'épisode en épisode.")

def write_episode(n, idee, scenes, memory):
    recap = "\n".join(f"Ép.{e['n']} {e['title']}: {e['summary']}" for e in memory[-5:]) or "Aucun (premier épisode)."
    sujet = idee or "Invente la suite logique de la série."
    prompt = f"""Scénariste de série pour enfants (3-8 ans) avec une intrigue solide qui avance.
UNIVERS: {WORLD}
Clés personnages autorisées: {list(CHARACTERS)}
ÉPISODES PRÉCÉDENTS: {recap}
Épisode {n}. Idée: {sujet}
Écris {scenes} scènes (accroche, mission, obstacles, retournement, climax, fin avec cliffhanger doux).
La narration raconte l'histoire (2 phrases, max 35 mots par scène).
JSON uniquement: {{"title":"...","summary":"résumé en 3 phrases","scenes":[{{"characters":["Léo"],"visual":"UNE image fixe, en ANGLAIS: cadrage + action + décor, sans texte","narration":"narration française"}}]}}"""
    r = genai.Client().models.generate_content(
        model=TEXT_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(r.text)

def image(scene, path, essais=4):
    who = " ".join(CHARACTERS[c] + "." for c in scene.get("characters", []) if c in CHARACTERS)
    p = f"{STYLE}. {who} {scene['visual']}"
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(p) +
           f"?width=1280&height=720&seed={SEED}&nologo=true&model=flux")
    for _ in range(essais):
        try:
            r = requests.get(url, timeout=180)
            if r.ok and r.headers.get("content-type", "").startswith("image"):
                path.write_bytes(r.content)
                time.sleep(16)
                return
        except Exception as e:
            print("  erreur image:", e)
        time.sleep(20)
    raise RuntimeError("Image non générée (service occupé). Relance.")

def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)

def animer(img, audio, out, i):
    d = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(audio)
    ])) + 0.6
    z = "min(zoom+0.0007,1.25)" if i % 2 == 0 else "if(eq(on,1),1.25,max(zoom-0.0007,1.0))"
    vf = (
        "scale=2560:1440:force_original_aspect_ratio=increase,crop=2560:1440,"
        f"zoompan=z='{z}':d={int(d*24)}:"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        "s=1280x720:fps=24,format=yuv420p"
    )
    run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(audio),
        "-t", f"{d:.2f}", "-vf", vf, "-c:v", "libx264", "-crf", "28",
        "-preset", "veryfast", "-c:a", "aac", "-shortest", str(out)
    ])

def build_site(memory, garder=40):
    site = pathlib.Path("site")
    (site / "videos").mkdir(parents=True, exist_ok=True)

    for e in memory[:-garder]:
        for f in (f"episode_{e['n']}.mp4", f"short_{e['n']}.mp4"):
            (site / "videos" / f).unlink(missing_ok=True)

    cartes = ""
    for e in reversed(memory[-garder:]):
        n = e["n"]
        cartes += (
            f'<article><h2>Épisode {n} — {html.escape(e["title"])}</h2>'
            f'<video controls preload="metadata" playsinline src="videos/episode_{n}.mp4"></video>'
            f'<p>{html.escape(e["summary"])}</p>'
            f'<p><a href="videos/episode_{n}.mp4" download>⬇ Télécharger l\'épisode</a> &nbsp; '
            f'<a href="videos/short_{n}.mp4" download>⬇ Télécharger le short (TikTok / Reels / Shorts)</a></p>'
            f'</article>'
        )

    page = (
        "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Les Mini-Gardiens</title>"
        "<style>body{margin:0;background:#101015;color:#f2f2f5;font-family:system-ui,sans-serif}"
        "main{max-width:760px;margin:auto;padding:20px 14px}h1{margin:0 0 4px}.s{color:#9a9aa8}"
        "article{background:#1c1c24;border-radius:14px;padding:14px;margin-top:18px}"
        "video{width:100%;border-radius:10px;background:#000}a{color:#ff6b61}</style>"
        "</head><body><main><h1>🦸 Les Mini-Gardiens</h1>"
        "<p class='s'>Un nouvel épisode chaque jour.</p>" + cartes +
        "</main></body></html>"
    )
    (site / "index.html").write_text(page, encoding="utf-8")

if __name__ == "__main__":
    memory = json.loads(MEM.read_text()) if MEM.exists() else []
    n = len(memory) + 1
    idee = os.getenv("IDEE", "").strip()
    scenes = int(os.getenv("SCENES", "12") or 12)

    ep = write_episode(n, idee, scenes, memory)
    print(f"Épisode {n} : {ep['title']} ({len(ep['scenes'])} scènes)")

    segs = []
    for i, s in enumerate(ep["scenes"]):
        print(f"Scène {i+1}/{len(ep['scenes'])}")
        im, au, seg = WORK / f"s{i}.jpg", WORK / f"s{i}.mp3", WORK / f"s{i}.mp4"
        image(s, im)
        asyncio.run(edge_tts.Communicate(s["narration"], VOICE).save(str(au)))
        animer(im, au, seg, i)
        segs.append(seg)

    (WORK / "list.txt").write_text(
        "".join(f"file '{p.name}'\n" for p in segs)
    )

    full = OUT / f"episode_{n}.mp4"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(WORK / "list.txt"), "-c", "copy", str(full)
    ])

    run([
        "ffmpeg", "-y", "-i", str(full), "-t", "58",
        "-vf", "crop=ih*9/16:ih,scale=1080:1920",
        "-c:a", "aac", str(OUT / f"short_{n}.mp4")
    ])

    memory.append({
        "n": n,
        "title": ep["title"],
        "summary": ep["summary"]
    })
    MEM.write_text(json.dumps(memory, ensure_ascii=False, indent=2))

    (pathlib.Path("site") / "videos").mkdir(parents=True, exist_ok=True)
    shutil.copy(full, pathlib.Path("site/videos") / full.name)
    shutil.copy(
        OUT / f"short_{n}.mp4",
        pathlib.Path("site/videos") / f"short_{n}.mp4"
    )

    build_site(memory)
    print("Terminé :", full)
