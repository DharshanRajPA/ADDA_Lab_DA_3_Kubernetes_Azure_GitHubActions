#!/usr/bin/env python3
"""
atlas_pipeline.py — Cross‑platform orchestration of Minikube + GitHub Actions CI for atlas-app.

Features:
  1. Start Minikube (Docker driver).
  2. Deploy Deployment + NodePort Service.
  3. Poll /health endpoint to verify.
  4. Generate .github/workflows/ci-atlas.yaml for CI.
  5. (Optional) Cleanup Minikube cluster.
"""

import os
import sys
import subprocess
import time

# === Configurable parameters ===
NAMESPACE = "atlas"
NODE_PORT = 30080
IMAGE_LOCAL = "atlas-app:latest"
GITHUB_WORKFLOW = ".github/workflows/ci-atlas.yaml"

# === Helper to run shell commands ===
def run(cmd: str, **kwargs):
    """Run a shell command; exit if it fails."""
    print(f"$ {cmd}")
    try:
        subprocess.run(cmd, shell=True, check=True, **kwargs)
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e.cmd}")
        raise

# === Step 1: Setup Minikube ===
def setup_minikube():
    """
    1. Check if Minikube is running.
    2. If not, start it with Docker driver.
    3. Switch kubectl context to Minikube.
    4. Verify node status.
    """
    try:
        run("minikube status --format '{{.Host}}'")
    except subprocess.CalledProcessError:
        print("ℹ️  Minikube not running; starting with Docker driver...")
        run("minikube start --driver=docker")
    run("kubectl config use-context minikube")
    run("kubectl get nodes")

# === Step 2: Deploy to Minikube ===
def deploy_minikube():
    """
    1. Create the 'atlas' namespace (ignore if exists).
    2. Apply Deployment manifest.
    3. Apply NodePort Service manifest.
    """
    try:
        run(f"kubectl create namespace {NAMESPACE}")
    except subprocess.CalledProcessError:
        print(f"ℹ️  Namespace '{NAMESPACE}' already exists; continuing.")

    print("👉 Applying Deployment manifest...")
    run(f"kubectl apply -n {NAMESPACE} -f k8s/atlas-deployment.yaml")

    print("👉 Applying Service manifest...")
    run(f"kubectl apply -n {NAMESPACE} -f k8s/atlas-service-nodeport.yaml")

# === Step 3: Health‑check the service ===
def healthcheck_minikube():
    """
    Poll the /health endpoint on the NodePort service up to 5 times.
    Exit if still unhealthy.
    """
    try:
        ip = subprocess.check_output("minikube ip", shell=True).decode().strip()
    except subprocess.CalledProcessError:
        sys.exit("❌ Failed to get Minikube IP.")

    url = f"http://{ip}:{NODE_PORT}/health"
    for attempt in range(1, 6):
        print(f"⏳ Health check attempt {attempt}/5: GET {url}")
        try:
            run(f"curl -sf {url}")
            print("✅ Health check passed!")
            return
        except subprocess.CalledProcessError:
            time.sleep(2)

    sys.exit("❌ Minikube health check failed after 5 attempts.")

# === Step 4: Generate GitHub Actions workflow ===
def generate_github_actions():
    """
    Create .github/workflows/ci-atlas.yaml that:
      - Checks out code
      - Starts Minikube
      - Builds and loads Docker image
      - Deploys to Minikube
      - Smoke‑tests the /health endpoint
    """
    os.makedirs(os.path.dirname(GITHUB_WORKFLOW), exist_ok=True)
    content = f"""\
name: CI – atlas-app
on:
  push:
    branches: [ main ]

jobs:
  minikube-ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start Minikube
        uses: medyagh/setup-minikube@latest

      - name: Build Docker image
        run: docker build -t {IMAGE_LOCAL} .

      - name: Load image into Minikube
        run: minikube image load {IMAGE_LOCAL}

      - name: Deploy to Minikube
        run: |
          kubectl create namespace {NAMESPACE} || true
          kubectl apply -n {NAMESPACE} -f k8s/atlas-deployment.yaml
          kubectl apply -n {NAMESPACE} -f k8s/atlas-service-nodeport.yaml

      - name: Smoke-test the service
        run: |
          IP=$(minikube ip)
          curl --retry 5 http://$IP:{NODE_PORT}/health
"""
    with open(GITHUB_WORKFLOW, "w", encoding="utf-8") as wf:
        wf.write(content)
    print(f"✔ Generated GitHub Actions workflow: {GITHUB_WORKFLOW}")

# === Step 5: (Optional) Cleanup Minikube ===
def cleanup_minikube():
    """Delete the Minikube cluster to free local resources."""
    run("minikube delete")

# === Main execution flow ===
if __name__ == "__main__":
    try:
        setup_minikube()
        deploy_minikube()
        healthcheck_minikube()
        generate_github_actions()
        print("\n🎉 All steps completed successfully!")
        print("→ Commit & push .github/workflows/ci-atlas.yaml to trigger CI.")
    except Exception as e:
        print(f"\n❗️ Pipeline failed: {e}")
        sys.exit(1)
    # Uncomment to auto-cleanup:
    # cleanup_minikube()
