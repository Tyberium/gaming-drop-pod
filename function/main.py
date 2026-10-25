import base64
import json
import os
import functions_framework
from google.cloud import compute_v1


@functions_framework.cloud_event
def stop_gaming_vm(cloud_event):
    pubsub_data = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
    budget_notification = json.loads(pubsub_data)

    cost_amount = budget_notification.get("costAmount", 0)
    budget_amount = budget_notification.get("budgetAmount", 0)

    print(f"Budget check: Current spend £{cost_amount} / £{budget_amount}")

    if cost_amount >= budget_amount:
        project = os.environ["GCP_PROJECT"]
        zone = os.environ["COMPUTE_ZONE"]
        instance_name = os.environ["INSTANCE_NAME"]

        print(f"LIMIT EXCEEDED! Stopping instance {instance_name} in {zone}...")
        instances_client = compute_v1.InstancesClient()
        operation = instances_client.stop(
            project=project, zone=zone, instance=instance_name
        )
        print(f"Stop command issued successfully: {operation.name}")
    else:
        print("Spend is still below 100% threshold. No action taken.")