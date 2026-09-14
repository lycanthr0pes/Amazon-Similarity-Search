"""Local build selection; no provider credentials or implicit CPU fallback."""

from pathlib import Path
import tomllib

from tools.bonsai_live_e2e import BonsaiLiveE2EConfig, BonsaiLiveE2EError


CONFIG_PATH = Path(__file__).resolve().parents[1] / "bonsai-runtime.toml"
PROFILE_NAMES = {"original", "optimized", "igpu"}
CONFIG_ERROR = "Bonsai runtime configuration is invalid"


def _absolute_path(value):
    if type(value) is not str or not value or ":" in value or "\x00" in value:
        raise ValueError(CONFIG_ERROR)
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(CONFIG_ERROR)
    return path


def load_bonsai_config(model_path, port, *, path=CONFIG_PATH):
    try:
        with Path(path).open("rb") as source:
            body = source.read(16_385)
        if len(body) > 16_384:
            raise ValueError
        data = tomllib.loads(body.decode("utf-8"))
        if set(data) != {"version", "active", "profiles"}:
            raise ValueError
        if type(data["version"]) is not int or data["version"] != 1:
            raise ValueError
        active = data["active"]
        if type(active) is not str or active not in PROFILE_NAMES:
            raise ValueError
        profiles = data["profiles"]
        if type(profiles) is not dict or set(profiles) != PROFILE_NAMES:
            raise ValueError
        for name, profile in profiles.items():
            expected = {"server_binary"}
            if name == "igpu":
                expected |= {"device", "device_name", "vulkan_driver", "library_paths"}
            if type(profile) is not dict or set(profile) != expected:
                raise ValueError
        profile = profiles[active]
        binary = _absolute_path(profile["server_binary"])
        options = {"library_paths": (binary.parent,)}
        if active == "igpu":
            paths = profile["library_paths"]
            if type(paths) is not list or len(paths) > 4:
                raise ValueError
            options.update(
                device=profile["device"],
                device_name=profile["device_name"],
                vulkan_driver=_absolute_path(profile["vulkan_driver"]),
                library_paths=(binary.parent, *(_absolute_path(p) for p in paths)),
            )
        return BonsaiLiveE2EConfig(binary, model_path, port, **options)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, BonsaiLiveE2EError):
        raise ValueError(CONFIG_ERROR) from None
