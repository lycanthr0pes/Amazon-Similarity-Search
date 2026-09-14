from types import SimpleNamespace

import pytest

from tools.bonsai_profiles import load_bonsai_config
from tools import bonsai_live_e2e as runtime


def config_file(tmp_path):
    for name in ("original", "optimized", "igpu"):
        binary = tmp_path / name / "llama-server"
        binary.parent.mkdir()
        binary.write_bytes(b"fixture")
        binary.chmod(0o700)
    model = tmp_path / "model.gguf"
    model.write_bytes(b"fixture")
    driver = tmp_path / "vulkan.json"
    driver.write_text("{}")
    config = tmp_path / "runtime.toml"
    config.write_text(
        'version = 1\nactive = "igpu"\n'
        + "\n".join(
            f'[profiles.{name}]\nserver_binary = "{tmp_path / name / "llama-server"}"\n'
            for name in ("original", "optimized", "igpu")
        )
        + 'device = "Vulkan0"\ndevice_name = "Intel Arc fixture"\n'
        + f'vulkan_driver = "{driver}"\nlibrary_paths = ["{tmp_path}"]\n'
    )
    return config, model


def test_default_igpu_preserves_model_context_and_requires_gpu(tmp_path):
    config_path, model = config_file(tmp_path)
    config = load_bonsai_config(model, 18080, path=config_path)
    command = runtime.build_llama_server_command(config)
    assert command[0] == str(tmp_path / "igpu" / "llama-server")
    assert command[command.index("-m") + 1] == str(model)
    assert command[command.index("-c") + 1] == "8192"
    assert command[command.index("--device") + 1] == "Vulkan0"
    assert command[command.index("--n-gpu-layers") + 1] == "99"
    assert command[command.index("--fit") + 1] == "off"


@pytest.mark.parametrize("profile", ["original", "optimized"])
def test_explicit_cpu_selection_only_changes_binary(tmp_path, profile):
    path, model = config_file(tmp_path)
    path.write_text(path.read_text().replace('active = "igpu"', f'active = "{profile}"'))
    config = load_bonsai_config(model, 18080, path=path)
    assert config.server_binary == tmp_path / profile / "llama-server"
    assert config.device is None
    assert "--device" not in runtime.build_llama_server_command(config)


@pytest.mark.parametrize(
    "old,new",
    [
        ('active = "igpu"', 'active = "missing"'),
        ("version = 1", "version = true"),
        ('device = "Vulkan0"', 'device = "CPU"'),
        ('device_name = "Intel Arc fixture"', 'device_name = "llvmpipe"'),
        ('device = "Vulkan0"', "gpu_layers = 0"),
    ],
)
def test_invalid_profile_is_not_replaced_with_cpu(tmp_path, old, new):
    path, model = config_file(tmp_path)
    path.write_text(path.read_text().replace(old, new))
    with pytest.raises(ValueError, match="Bonsai runtime configuration"):
        load_bonsai_config(model, 18080, path=path)


def test_gpu_missing_stops_before_model_launch(tmp_path, monkeypatch):
    path, model = config_file(tmp_path)
    config = load_bonsai_config(model, 18080, path=path)
    monkeypatch.setattr(runtime, "_port_is_listening", lambda _: False)
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *_, **__: SimpleNamespace(returncode=0, stdout=b"Available devices:\n"),
    )
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *_, **__: pytest.fail("CPU fallback"))
    with pytest.raises(runtime.BonsaiLiveE2EError, match="configured GPU"):
        runtime._launch_server(config)


def test_profile_environment_does_not_inherit_credentials(tmp_path, monkeypatch):
    path, model = config_file(tmp_path)
    config = load_bonsai_config(model, 18080, path=path)
    calls = []
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "private-fixture")
    monkeypatch.setattr(runtime, "_port_is_listening", lambda _: False)

    def devices(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            returncode=0, stdout=b"  Vulkan0: Intel Arc fixture (16384 MiB, 12000 MiB free)\n"
        )

    monkeypatch.setattr(runtime.subprocess, "run", devices)
    monkeypatch.setattr(runtime.subprocess, "Popen", lambda *args, **kwargs: calls.append(kwargs))
    runtime._launch_server(config)
    assert len(calls) == 2
    expected = {
        "LC_ALL": "C",
        "LD_LIBRARY_PATH": f"{tmp_path / 'igpu'}:{tmp_path}",
        "VK_DRIVER_FILES": str(tmp_path / "vulkan.json"),
        "GGML_VK_DISABLE_F16": "1",
        "GGML_VK_DISABLE_ASYNC": "1",
    }
    assert all(call["env"] == expected for call in calls)
