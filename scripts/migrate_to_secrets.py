import os
import subprocess
from pathlib import Path

def create_secret(name, value):
    """Create a GCP secret and add a version with the provided value."""
    project_id = "election-assistant-494615"
    
    # Check if secret exists
    check_cmd = ["gcloud", "secrets", "list", f"--filter=name~{name}", "--format=value(name)", f"--project={project_id}"]
    exists = subprocess.run(check_cmd, capture_output=True, text=True, shell=True).stdout.strip()
    
    if not exists:
        print(f"Creating secret: {name}")
        create_cmd = ["gcloud", "secrets", "create", name, "--replication-policy=automatic", f"--project={project_id}"]
        subprocess.run(create_cmd, check=True, shell=True)
    
    # Add version
    print(f"Adding version to: {name}")
    add_cmd = ["gcloud", "secrets", "versions", "add", name, f"--data-file=-", f"--project={project_id}"]
    subprocess.run(add_cmd, input=value.encode(), check=True, shell=True)

def main():
    # Load .env manually to avoid dependency issues in this script
    env_path = Path(".env")
    if not env_path.exists():
        print("Error: .env file not found.")
        return

    secrets_to_migrate = [
        "GOOGLE_API_KEY",
        "FIREBASE_PROJECT_ID",
        "SECRET_KEY",
        "GOOGLE_CSE_ID",
        "GOOGLE_CSE_API_KEY"
    ]

    with open(env_path, "r") as f:
        lines = f.readlines()

    for line in lines:
        if "=" in line and not line.startswith("#"):
            key, value = line.strip().split("=", 1)
            if key in secrets_to_migrate:
                create_secret(key, value)

if __name__ == "__main__":
    main()
