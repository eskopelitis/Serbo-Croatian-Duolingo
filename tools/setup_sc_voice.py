"""Install the reviewed Serbian Marko model outside the project tree.

Run after installing requirements.txt. With --from-dir, copy previously downloaded
model files instead of fetching them. Existing mismatched files are never replaced.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sc_piper

BASE = "https://huggingface.co/phantom9623/piper-serbian-tts/resolve/main/"
FILES = {
    "sr_Marko_medium.onnx": sc_piper._MODEL_SHA256,
    "sr_Marko_medium.onnx.json": sc_piper._CONFIG_SHA256,
}


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def install(source_dir=None):
    destination = sc_piper.default_model_path().parent
    destination.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        target = destination / name
        if target.exists():
            if not target.is_file() or digest(target) != expected:
                raise RuntimeError(f"Existing file does not match the reviewed model: {target}")
            print(f"Already installed: {target}")
            continue
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination, prefix=".marko-", delete=False) as out:
                temporary = Path(out.name)
                if source_dir:
                    with (Path(source_dir) / name).open("rb") as source:
                        shutil.copyfileobj(source, out)
                else:
                    with urlopen(BASE + name, timeout=60) as source:
                        shutil.copyfileobj(source, out)
            if digest(temporary) != expected:
                raise RuntimeError(f"Downloaded file did not match the reviewed hash: {name}")
            # Creating a link is atomic and cannot overwrite a concurrent installation.
            try:
                os.link(temporary, target)
            except FileExistsError:
                if not target.is_file() or digest(target) != expected:
                    raise RuntimeError(f"Existing file does not match the reviewed model: {target}")
            print(f"Installed: {target}")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    print("Serbian Marko is installed. Restart the learning app to use it.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-dir", help="Copy the reviewed model and config from this directory")
    args = parser.parse_args()
    try:
        install(args.from_dir)
    except (OSError, RuntimeError) as error:
        parser.exit(1, f"Voice installation failed: {error}\n")
