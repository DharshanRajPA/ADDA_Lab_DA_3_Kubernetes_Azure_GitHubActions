#!/usr/bin/env python3
"""
atlas_pipeline.py — Orchestrates Minikube deployment and GitHub CI for atlas-app.
"""

import os
import subprocess
import time

# Configurable variables
NAMESPACE = "atlas"
NODE_PORT = 30080
IMAGE_LOCAL = "atlas-app:latest"
GITHUB_WORKFLOW = ".github/workflows/ci-atlas.yaml"

def run(cmd, **kwargs):
    """Run a shell command and handle errors clearly."""
    print(f"$ {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, **kwargs)
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {cmd}")
        raise

def setup_minikube():
    """Start Minikube if not running."""
    try:
        status = subprocess.check_output("minikube status --format '{{.Host}}'", shell=True).decode().strip()
        if status.lower() != 'running':
            raise Exception("Minikube not running")
    except:
        print("ℹ️  Minikube not running; starting with Docker driver...")
        run("minikube start --driver=docker")

    run("kubectl config use-context minikube")
    run("kubectl get nodes")

def deploy_minikube():
    """Deploy to Minikube using Kubernetes YAMLs."""
    print("👉 Ensuring namespace exists...")
    try:
        run(f"kubectl create namespace {NAMESPACE}")
    except:
        print(f"ℹ️  Namespace '{NAMESPACE}' already exists; continuing.")

    print("👉 Applying Deployment manifest...")
    run(f"kubectl apply -n {NAMESPACE} -f k8s/atlas-deployment.yaml")

    print("👉 Applying Service manifest...")
    run(f"kubectl apply -n {NAMESPACE} -f k8s/atlas-service-nodeport.yaml")

def healthcheck_minikube():
    """Check if the Minikube app is responding at /health."""
    ip = subprocess.check_output("minikube ip", shell=True).decode().strip()
    url = f"http://{ip}:{NODE_PORT}/health"
    for i in range(5):
        print(f"⏳ Health check attempt {i+1}/5: GET {url}")
        try:
            subprocess.run(f"curl -sf {url}", shell=True, check=True)
            print("✅ Minikube app is healthy!")
            return
        except subprocess.CalledProcessError:
            time.sleep(3)
    print("❌ Health check failed.")
    raise SystemExit("Health check failed after 5 attempts.")

def generate_github_actions():
    """Generate GitHub Actions workflow for CI."""
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
      - name: Build image
        run: docker build -t {IMAGE_LOCAL} .
      - name: Load into Minikube
        run: minikube image load {IMAGE_LOCAL}
      - name: Deploy
        run: |
          kubectl create namespace {NAMESPACE} || true
          kubectl apply -n {NAMESPACE} -f k8s/atlas-deployment.yaml
          kubectl apply -n {NAMESPACE} -f k8s/atlas-service-nodeport.yaml
      - name: Smoke test
        run: |
          IP=$(minikube ip)
          for i in {{1..5}}; do curl -sf http://$IP:{NODE_PORT}/health && exit 0 || sleep 3; done
          exit 1
""")
    print("✅ GitHub Actions workflow generated.")

if __name__ == "__main__":
    setup_minikube()
    deploy_minikube()
    healthcheck_minikube()
    generate_github_actions()
