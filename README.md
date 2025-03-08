# K.E.E.S. Vision - Last Updated: 2025-03-08

## Who I Am
- **Kees**: Not a programmer, big dreamer—building a future energy company from scratch.
- **Skills**: Vision, grit, pasting Grok’s code into VS Code like a champ.
- **Struggles**: Forgetting stuff, indent screw-ups, repeating myself to Grok.
- **Learning**: SSH, Git basics, VS Code + SFTP workflow.

## The Big Goal
- K.E.E.S.: Kees’ Energy Efficiency System—cloud platform to optimize ANY Wi-Fi device (heat pumps, EVs, fridges, whatever!) for customers. Uses dynamic pricing (Tibber, ENTSO-E) and solar to save money and energy. Start small (julianalaan_39), scale big!

## Current State
- **Server**: 159.223.10.31, Ubuntu 22.04, 16% disk (3.7GB/25GB).
- **GitHub**: https://github.com/Keessrh/KEES_Engine, auto-updates every 5 mins via `auto_update.sh`.
- **Files**: 
  - `main.py` (big, splitting soon—runs MQTT, Flask, pricing).
  - `clients/julianalaan_39/warmtepomp.py` (heat pump logic).
  - `prices.json` (Tibber/ENTSO-E data).
  - `.gitignore` (blocks logs, pyc files).
- **Logging**: `/root/main.log` (outside Git).

## Recent Wins
- **2025-03-08**: GitHub was a mess with logs (main.log, git.log, git_errors.log)—cleaned it with `.gitignore` and `git rm`, now sleek.

## Next Up
- Split `main.py` into modules (started `prices_tibber.py`).
- Fix state mismatch (telemetry says 2, `force_state` sets 4—timing?).

## Chat Summaries
- **2025-03-08**: GitHub had log clutter, fixed it with git rm and .gitignore, planned a README system to track my vision like a Google Doc—live, editable, always open.

## Random Thoughts (Throw Stuff Here!)
- Maybe add EV chargers next?
- Solar tracking could be tighter—more data?