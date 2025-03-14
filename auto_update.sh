#!/bin/bash
cd /root/master_kees/
echo "Backup run - $(date)" >> /root/master_kees/backup.log
git checkout main
git add .
git commit -m "Auto-backup - $(date)" || echo "Nothing new" >> /root/master_kees/backup.log
git push origin main
