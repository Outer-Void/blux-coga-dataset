# Platform Notes

## General guidance

- Use `python -m pip`, never raw `pip`.
- The dataset harness expects the real `blux-coga` engine's canonical file-based invocation: `blux-coga run --input ... --output-dir ...`.
- Prefer running against a local checkout via `BLUX_COGA_REPO=/path/to/blux-coga python ./scripts/run_harness.py`.
- If `BLUX_COGA_REPO` points at a source checkout, the harness automatically adds `<repo>/src` to `PYTHONPATH` so you do not need an editable install just to verify fixtures.

## Linux / macOS

Install Python and any shell tooling you need with your system package manager, then run:

```sh
python -m pip install -e /path/to/blux-coga
BLUX_COGA_REPO=/path/to/blux-coga python ./scripts/run_harness.py
```

## Termux native

Use native Termux packages directly:

```sh
pkg update
pkg install python3 git jq
python -m pip install -e /data/data/com.termux/files/home/blux-coga
BLUX_COGA_REPO=/data/data/com.termux/files/home/blux-coga python ./scripts/run_harness.py
```

## Termux + proot Debian inside Debian

From Termux:

```sh
pkg update
pkg install proot-distro
proot-distro install debian
proot-distro login debian
```

Inside Debian:

```sh
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip jq
python -m pip install -e /path/to/blux-coga
BLUX_COGA_REPO=/path/to/blux-coga python ./scripts/run_harness.py
```
