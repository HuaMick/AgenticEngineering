import subprocess
try:
    result = subprocess.run(
        ["agentic", "session", "orchestrate", "--mode", "planning", "--no-tmux"],
        capture_output=True,
        text=True,
        timeout=15,
        input="/exit\n",
    )
    print("RETURN CODE:", result.returncode)
    print("STDERR length:", len(result.stderr))
except subprocess.TimeoutExpired as e:
    print("TIMEOUT!")
