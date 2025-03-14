# K.E.E.S. Vision - Last Updated: 2025-03-08

## Who I Am
- **Kees**: Not a programmer, big dreamer—building a future energy company from scratch at EcoKees.
- **Skills**: Vision, grit, pasting Grok’s code into VS Code like a champ.
- **Struggles**: Forgetting stuff, indent errors, repeating myself to Grok.
- **Learning**: SSH, Git basics, VS Code + SFTP workflow.

## The Big Goal
- K.E.E.S.: Kalibrerend Energie Efficiency Systeem—cloud platform to optimize ANY Wi-Fi device (heat pumps, EVs, solar, etc.) for max cost-efficiency. Targets 15–30% savings with dynamic pricing (Tibber, ENTSO-E), solar opwek, saldering, and thermal buffers—keeps comfort at 20–22°C. Scales from julianalaan_39 to 1000s via a $10/€10 subscription model, with a no-code UI like a mixing board.

## Current State
- **Server**: 159.223.10.31, Ubuntu 22.04.5 LTS, 16% disk (3.7GB/25GB), €7/month DigitalOcean Droplet.
- **GitHub**: https://github.com/Keessrh/KEES_Engine, auto-updates every 5 mins via `auto_update.sh`.
- **Files**: 
  - `main.py` (central hub—MQTT on 159.223.10.31:1883, Flask on port 80, splitting soon).
  - `clients/julianalaan_39/warmtepomp.py` (processes MQTT data, optimizes state: 2-8).
  - `prices.json` (Tibber/ENTSO-E pricing data).
  - `.gitignore` (blocks logs, pyc files).
  - `auto_update.sh` (Git sync script).
- **Logging**: `/root/main.log` (live data, debug—e.g., "Received: julianalaan_39/telemetry").
- **Dashboard**: http://159.223.10.31—shows live data (e.g., "Temp In: 26.7°C", "State: 4") for julianalaan_39/warmtepomp, updates every 5 secs.
- **Local Setup**: `/home/kees/Projects/master_kees/` on Chromebook, syncs via SFTP (`.vscode/sftp.json`, `uploadOnSave: true`).
- **Crontab**: 
  - `*/5 * * * * /root/master_kees/auto_update.sh` (Git push).
  - `@reboot /usr/bin/python3 /root/master_kees/main.py > /root/main.log 2>&1` (auto-start).
- **Home Assistant**: Local machine, bridges LG Therma V heat pump (Modbus TCP, 192.168.86.47:502, ~12 kWh buffer) to server via MQTT (`julianalaan_39/telemetry`). Manages state (1-8) and DHW via price/solar—runs until K.E.E.S. takes over.

## Recent Wins
- **2025-03-08**: GitHub was messy with logs—cleaned it with `.gitignore` and `git rm`, now lean.
- **Earlier**: Server live, MQTT syncing julianalaan_39, dashboard up, SFTP/Git sync solid.

## Next Up
- Split `main.py` into modules (`prices_tibber.py` started)—data, pricing, optimization.
- Fix state mismatch (telemetry says 2, `force_state` sets 4—timing?).
- Shift HA control to server—phase out HA, own state/DHW logic.

## Chat Summaries
- **2025-03-08**: Fixed GitHub log clutter with git rm and .gitignore, built README system for vision tracking. Added HA bridge and early K.E.E.S. vision—price-driven, scalable, subscription-based.

## Random Thoughts (Throw Stuff Here!)
- EV chargers—solar/saldering optimization?
- Solar prediction—blend history and forecasts?
- Thermal buffer—charge low, discharge high?
- UI sliders—price and comfort controls?

