# Platform Notes

## Linux/macOS
Use your system package manager to install dependencies like `jq` if you want to
run the harness script locally.

```sh
MODEL_VERSION=coga-1.0 REASONING_PACK=default COGA_CMD=coga ./scripts/run_harness.sh
```

## Termux (native)
Use Termux directly on Android when you want the lightest footprint and direct
package management via `pkg`.

```sh
pkg update -y
pkg install -y git python openssh jq
MODEL_VERSION=coga-1.0 REASONING_PACK=default COGA_CMD=coga ./scripts/run_harness.sh
```

## Termux + proot Debian
Use a proot Debian environment when you need a closer match to Debian/Ubuntu
tooling while still running on Android.

```sh
pkg update -y
pkg install -y proot-distro
proot-distro install debian
proot-distro login debian
```

Inside the Debian shell:

```sh
apt update
apt install -y git python3 python3-venv jq
MODEL_VERSION=coga-1.0 REASONING_PACK=default COGA_CMD=coga ./scripts/run_harness.sh
```
