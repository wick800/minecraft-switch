
#!/usr/bin/env python3
"""Baixa os arquivos do Minecraft para ./game."""
import concurrent.futures
import hashlib
import json
import os
import sys
import tempfile
import urllib.request

V = sys.argv[1] if len(sys.argv) > 1 else "1.12.2"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game")


def get(url, path=None, sha1=None):
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            existing = f.read()
        if not sha1 or hashlib.sha1(existing).hexdigest() == sha1:
            return existing

    req = urllib.request.Request(
        url, headers={"User-Agent": "SwitchCraftLauncher/1.0"}
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        data = response.read()

    if sha1 and hashlib.sha1(data).hexdigest() != sha1:
        raise RuntimeError("SHA-1 incorreto: " + url)

    if path:
        folder = os.path.dirname(path)
        os.makedirs(folder, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            prefix=".download-", dir=folder
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            if sha1 and hashlib.sha1(
                open(temp_path, "rb").read()
            ).hexdigest() != sha1:
                raise RuntimeError("Arquivo temporário inválido: " + path)
            os.replace(temp_path, path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    return data


manifest_url = (
    "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
)
manifest = json.loads(get(manifest_url))
version_url = next(
    item["url"] for item in manifest["versions"]
    if item["id"] == V
)
ver = json.loads(get(version_url, f"{OUT}/{V}.json"))

client = ver["downloads"]["client"]
get(client["url"], f"{OUT}/{V}.jar", client["sha1"])

libraries = []
for lib in ver["libraries"]:
    artifact = lib.get("downloads", {}).get("artifact")
    rules = lib.get("rules", [])
    allowed = all(
        rule.get("action") == "allow"
        and rule.get("os", {}).get("name", "linux") == "linux"
        for rule in rules
    )
    if artifact and "natives" not in lib and allowed:
        libraries.append((
            artifact["url"],
            f'{OUT}/libraries/{artifact["path"]}',
            artifact.get("sha1")
        ))

asset_index = ver["assetIndex"]
index = json.loads(get(
    asset_index["url"],
    f'{OUT}/assets/indexes/{asset_index["id"]}.json',
    asset_index["sha1"]
))

objects = [
    (
        f'https://resources.download.minecraft.net/{obj["hash"][:2]}/{obj["hash"]}',
        f'{OUT}/assets/objects/{obj["hash"][:2]}/{obj["hash"]}',
        obj["hash"]
    )
    for obj in index["objects"].values()
]

tasks = libraries + objects
errors = []

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    futures = {executor.submit(get, *task): task[1] for task in tasks}
    for future in concurrent.futures.as_completed(futures):
        try:
            future.result()
        except Exception as exc:
            errors.append((futures[future], str(exc)))
            print("ERRO:", futures[future], exc)

if errors:
    raise SystemExit(f"{len(errors)} downloads falharam.")

print(
    f'{V}: {len(libraries)} bibliotecas, '
    f'{len(objects)} objetos de assets; '
    f'classe principal: {ver["mainClass"]}'
)
print("Download concluído com sucesso.")
print("Argumentos:", ver.get("minecraftArguments"))
