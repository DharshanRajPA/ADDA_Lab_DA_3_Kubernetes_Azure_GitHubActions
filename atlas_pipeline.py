#!/usr/bin/env python3
"""
atlas_pipeline.py — Orchestrate Minikube and GitHub CI for atlas-app.
"""

import os
import sys
import subprocess
import time

# Configurable parameters
NAMESPACE = "atlas"
NODE_PORT = 30080
IMAGE_LOCAL = "atlas-app:latest"
GITHUB_WORKFLOW = ".github/workflows/ci-atlas.yaml"

def run(cmd, **kwargs):
    """Run shell command, exit on failure."""
    print(f"$ {cmd}")
    subprocess.run(cmd, shell=True, check=True, **kwargs)

def setup_minikube():
    """
    1. Check if Minikube is running.
    2. If not, start Minikube with Docker driver.
    3. Switch kubectl context to minikube.
    4. Verify node status.
    """
    try:
        run("minikube status")
    except subprocess.CalledProcessError:
        run("minikube start --driver=docker")
    run("kubectl config use-context minikube")
    run("kubectl get nodes")

def deploy_minikube():
    """
    1. Create 'atlas' namespace if it doesn't exist.
    2. Apply Deployment manifest.
    3. Apply NodePort Service manifest.
    """
    run(f"kubectl create namespace {NAMESPACE} || true")
    run(f"kubectl apply -n {NAMESPACE} -f k8s/atlas-deployment.yaml")
    run(f"kubectl apply -n {NAMESPACE} -f k8s/atlas-service-nodeport.yaml")

def healthcheck_minikube():
    """
    1. Retrieve Minikube IP.
    2. Poll the /health endpoint on the NodePort.
    3. Exit with error if it never becomes healthy.
    """
    ip = subprocess.check_output("minikube ip", shell=True).decode().strip()
    url = f"http://{ip}:{NODE_PORT}/health"
    for i in range(1, 6):
        try:
            run(f"curl -sf {url}")
            print("✅ Minikube health check passed.")
            return
        except subprocess.CalledProcessError:
            print(f"⏳ Retry {i}/5...")
            time.sleep(2)
    sys.exit("❌ Minikube health check failed after 5 attempts.")

def generate_github_actions():
    """
    Write a GitHub Actions workflow that:
    - Checks out the code.
    - Starts Minikube.
    - Builds the Docker image.
    - Loads it into Minikube.
    - Deploys the app.
    - Performs a smoke-test.
    """
    os.makedirs(os.path.dirname(GITHUB_WORKFLOW), exist_ok=True)
    with open(GITHUB_WORKFLOW, "w") as f:
        f.write(f"""\
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
""")
    print(f"✔ Generated GitHub Actions workflow at {GITHUB_WORKFLOW}")

def cleanup_minikube():
    """Optional: delete Minikube cluster to free resources."""
    run("minikube delete")

if __name__ == "__main__":
    # 1. Local cluster setup
    setup_minikube()

    # 2. Deploy application to Minikube
    deploy_minikube()

    # 3. Health-check the deployed service
    healthcheck_minikube()

    # 4. Generate CI workflow for GitHub Actions
    generate_github_actions()

    # Uncomment below to destroy the local cluster after testing
    # cleanup_minikube()
