#!/usr/bin/env bash
set -euo pipefail

ip route | awk '/^default via / {print $3; exit}'
