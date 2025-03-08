#!/bin/bash
cd /root/master_kees/
git add .
# Alleen committen en pushen als er wijzigingen zijn
if ! git diff-index --quiet HEAD --; then
    git commit -m "Automatische update vanaf server - $(date '+%Y-%m-%d %H:%M:%S')"
    git push origin main
fi
