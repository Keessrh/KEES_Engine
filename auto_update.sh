#!/bin/bash
cd /root/master_kees/
echo "Backup run - $(date)" >> /root/backup.log  # Log outside repo
git add .  # Grab everything (new folders too)
git commit -m "Auto-backup - $(date)" || echo "Nothing new" >> /root/backup.log
git push origin HEAD:main  # Push current branch to main
