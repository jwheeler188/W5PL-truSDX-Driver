#!/bin/zsh
# W5PL Driver for DL2MAN (tr)uSDX - double-click to start the driver in a Terminal window (macOS).
# Extra options: edit the last line, e.g.  ... trusdx.sh --cat-tcp 4542
# The first time, macOS may ask to confirm opening it: right-click > Open.
exec "${0:A:h}/trusdx.sh"
