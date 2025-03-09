import os
import subprocess

with open("/root/master_kees/agent_report.txt", "w") as report:
    report.write("=== Directory Contents ===\n")
    report.write(subprocess.getoutput("ls -la /root/master_kees/") + "\n\n")
    report.write("=== Running Processes ===\n")
    report.write(subprocess.getoutput("ps aux | grep -E 'python3|flask|mqtt'") + "\n\n")
    report.write("=== Last 20 Log Lines ===\n")
    report.write(subprocess.getoutput("tail -n 20 /root/master_kees/main.log") + "\n\n")
    report.write("=== Port Status (80, 1883) ===\n")
    report.write(subprocess.getoutput("netstat -tuln | grep -E '80|1883'") + "\n")
print("Report written to /root/master_kees/agent_report.txt")
