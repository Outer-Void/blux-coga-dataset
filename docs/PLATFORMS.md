# Platform Notes

## Termux (native)
Use Termux directly on Android when you want the lightest footprint and direct
package management via `pkg`.

```sh
pkg update -y
pkg install -y git python openssh
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
apt install -y git python3 python3-venv
```
