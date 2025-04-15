import subprocess
import time
import logging
import os
import sys
import json
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define helper functions for executing shell commands
def run_command(command, timeout=300):
    """Run a shell command and return the output"""
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return result.stdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with error: {e.stderr.decode('utf-8')}")
        sys.exit(1)

def start_minikube():
    """Ensure Minikube is running"""
    try:
        logger.info("Checking if Minikube is running...")
        minikube_status = run_command("minikube status")
        if "Running" not in minikube_status:
            logger.info("Minikube not running; starting with Docker driver...")
            run_command("minikube start --driver=docker")
        else:
            logger.info("Minikube is already running.")
    except Exception as e:
        logger.error(f"Error starting Minikube: {str(e)}")
        sys.exit(1)

def create_namespace(namespace="atlas"):
    """Create a Kubernetes namespace"""
    try:
        logger.info(f"Creating namespace '{namespace}'...")
        run_command(f"kubectl create namespace {namespace} --dry-run=client -o yaml | kubectl apply -f -")
    except ApiException as e:
        logger.error(f"Error creating namespace: {e}")
        sys.exit(1)

def apply_kubernetes_manifest(manifest_path):
    """Apply the Kubernetes manifest"""
    try:
        logger.info(f"Applying manifest from {manifest_path}...")
        run_command(f"kubectl apply -f {manifest_path}")
    except ApiException as e:
        logger.error(f"Error applying manifest: {e}")
        sys.exit(1)

def check_service_status(service_name, namespace="atlas", retries=5, delay=10):
    """Check the status of the service"""
    try:
        for attempt in range(retries):
            logger.info(f"Checking status of service '{service_name}' (attempt {attempt + 1}/{retries})...")
            service_status = run_command(f"kubectl get svc {service_name} -n {namespace}")
            if service_status:
                logger.info(f"Service {service_name} is ready.")
                return True
            time.sleep(delay)
        logger.error(f"Service {service_name} is not available after {retries} attempts.")
        return False
    except ApiException as e:
        logger.error(f"Error checking service status: {e}")
        return False

def main():
    # Initialize Minikube
    start_minikube()

    # Set the namespace and manifest path
    namespace = "atlas"
    deployment_manifest = "k8s/atlas-deployment.yaml"
    service_manifest = "k8s/atlas-service-nodeport.yaml"

    # Create namespace
    create_namespace(namespace)

    # Apply deployment and service manifests
    apply_kubernetes_manifest(deployment_manifest)
    apply_kubernetes_manifest(service_manifest)

    # Wait for the service to be up and check its status
    if check_service_status("atlas-svc", namespace):
        logger.info("Deployment successful, health checks passed.")
    else:
        logger.error("Health checks failed, check logs for details.")

if __name__ == "__main__":
    main()
