#!/usr/bin/env python -tt
#  -*- coding: utf-8 -*-
 
################################################################################
# This is the confidential unpublished intellectual property of Dell Corporation,
# and includes without limitation exclusive copyright and trade secret rights
# of Dell throughout the world.
################################################################################
 
"""This Pytest local plugin creates some basic objects for testing purposes"""
 
from __future__ import unicode_literals, absolute_import
import pytest
from mock import patch
from .. import HostUnderTest
from ..interface import PublicInterface
import subprocess
import time

@pytest.fixture(scope="module")
def kubeflow_pods_status():
    """
    Run 'kubectl get pods -A | grep kubeflow' to get the status of Kubeflow pods.
    Returns a list of tuples containing pod names and their statuses.
    """
    try:
        # Execute the command to get pod details in the kubeflow namespace
        command = "kubectl get pods -A | grep kubeflow"
        result = subprocess.check_output(command, shell=True, text=True)

        # Process the result into a list of (pod_name, status) tuples
        pods = []
        for line in result.strip().split("\n"):
            columns = line.split()
            if len(columns) >= 4:  # Ensure the output has enough columns
                pods.append((columns[1], columns[3]))  # (pod_name, status)
        return pods

    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to execute kubectl command. Error: {e}")

def test_kubeflow_pods_running_or_completed(kubeflow_pods_status):
    """
    Validate that all pods in the Kubeflow namespace are either running or completed.
    """
    failed_pods = [
        pod for pod, status in kubeflow_pods_status
        if status not in ("Running", "Completed")
    ]

    # Assert no failed pods and print success message if all are running
    if not failed_pods:
        print("All Kubeflow pods are either in Running or Completed state.")
    assert not failed_pods, f"Some Kubeflow pods are not in Running or Completed state: {failed_pods}"

def test_create_kubeflow_job():
    """
    Create a job in Kubeflow and validate the pod associated with it.
    """
    # Apply the job YAML to create the job
    command = "kubectl apply -f /home/mystic/validate-kubeflow-job.yaml"
    try:
        subprocess.check_call(command, shell=True)
        print("Job 'validate-kubeflow-installation' created successfully.")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to create Kubeflow job. Error: {e}")

    # Wait for the pod to appear and be in the Running state
    pod_running = False
    timeout = 120  # Timeout in seconds
    start_time = time.time()

    while time.time() - start_time < timeout:
        # Use grep to find the pod associated with the job
        command = "kubectl get pods -n kubeflow | grep validate-kubeflow-installation"
        try:
            result = subprocess.check_output(command, shell=True, text=True)
            pods = result.strip().split("\n")
            pod_running = any("Running" in pod for pod in pods)
            if pod_running:
                print("Pod associated with the job is in the Running state.")
                break
        except subprocess.CalledProcessError:
            # Pod not yet available, wait and retry
            time.sleep(5)

    assert pod_running, "The pod associated with the job is not running within the timeout."

    # Collect logs of the pod
    pod_name = None
    command = "kubectl get pods -n kubeflow | grep validate-kubeflow-installation"
    try:
        result = subprocess.check_output(command, shell=True, text=True)
        pods = result.strip().split("\n")
        for pod in pods:
            if "Running" in pod:
                pod_name = pod.split()[0]  # Extract pod name
                break
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to retrieve pod name. Error: {e}")

    if pod_name:
        log_file_path = f"/home/mystic/{pod_name}_logs.txt"
        try:
            # Collect the logs and save them to a file
            log_command = f"kubectl logs -n kubeflow {pod_name} > {log_file_path}"
            subprocess.check_call(log_command, shell=True)
            print(f"Logs collected for pod {pod_name} and saved to {log_file_path}.")
        except subprocess.CalledProcessError as e:
            pytest.fail(f"Failed to collect logs for pod {pod_name}. Error: {e}")

    # Cleanup: Delete the job after verification
    cleanup_command = "kubectl delete -f /home/mystic/validate-kubeflow-job.yaml"
    try:
        subprocess.check_call(cleanup_command, shell=True)
        print("Job and associated pod cleaned up successfully.")
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to delete Kubeflow job. Error: {e}")

