#!/bin/bash
cd /root/master_kees/
git add .
if ! git diff-index --quiet HEAD --; then
    git commit -m "Code update - $(date '+%Y-%m-%d %H:%M:%S')"
    git push origin main 2>/root/master_kees/git_errors.log
    if [ $? -eq 0 ]; then
        echo "Git push succesvol: $(date)" >> /root/master_kees/git.log
    else
        echo "Git push mislukt: $(date)" >> /root/master_kees/git.log
    fi
fi