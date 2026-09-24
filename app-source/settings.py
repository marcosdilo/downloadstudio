"""Configurações persistentes e validação das regras de organização."""
import json
import math
import re
from pathlib import Path
from core import CATEGORIAS, TEMPORARIOS, downloads_padrao


def defaults():
    return {
        "folder": str(downloads_padrao()), "stability": 2.0,
        "quarantine": False, "auto_start": False, "close_to_tray": True,
        "theme": "Dark",
        "categories": [{"name": name, "extensions": ", ".join(sorted(ext)),
                        "enabled": True} for name, ext in CATEGORIAS.items()],
    }


def validate(config):
    if not isinstance(config, dict):
        raise ValueError("Configuração inválida")
    folder = Path(config["folder"]).expanduser().resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("Selecione uma pasta existente")
    delay = float(config["stability"])
    if not math.isfinite(delay) or not 1 <= delay <= 60:
        raise ValueError("A estabilidade deve estar entre 1 e 60 segundos")
    if config["theme"] not in {"Dark", "Light", "System"}:
        raise ValueError("Tema inválido")
    mapping, names = {}, set()
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10))}
    for category in config["categories"]:
        name = category["name"].strip()
        if (not name or len(name) > 80 or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
                or name.endswith((".", " ")) or name in {".", ".."}
                or name.split(".")[0].upper() in reserved
                or name.casefold() == "quarentena_corrompidos"):
            raise ValueError(f"Nome de categoria inválido: {name!r}")
        if name.casefold() in names:
            raise ValueError(f"Categoria repetida: {name}")
        names.add(name.casefold())
        # Evita saídas redirecionadas por junctions/symlinks.
        target = folder / name
        if target.is_symlink() or target.is_junction():
            raise ValueError(f"A categoria {name} é um link/junção; escolha outra pasta")
        if target.exists() and not target.is_dir():
            raise ValueError(f"Já existe um arquivo com o nome {name}")
        if not category["enabled"]:
            continue
        extensions = re.split(r"[,;\s]+", category["extensions"].strip().lower())
        if not extensions or not extensions[0]:
            raise ValueError(f"Informe extensões para {name}")
        for ext in extensions:
            ext = ext if ext.startswith(".") else "." + ext
            if not re.fullmatch(r"\.[a-z0-9]{1,16}", ext) or ext in TEMPORARIOS:
                raise ValueError(f"Extensão inválida ou temporária: {ext}")
            if ext in mapping:
                raise ValueError(f"Extensão repetida: {ext}")
            mapping[ext] = name
    if not mapping:
        raise ValueError("Ative pelo menos uma categoria")
    quarantine = folder / "Quarentena_Corrompidos"
    if config["quarantine"] and (quarantine.is_symlink() or quarantine.is_junction()
                                or (quarantine.exists() and not quarantine.is_dir())):
        raise ValueError("O destino de quarentena não é uma pasta comum")
    return folder, delay, mapping


def save(path, config):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load(path):
    path = Path(path)
    if not path.exists():
        return defaults()
    data = json.loads(path.read_text(encoding="utf-8"))
    validate(data)
    return data
