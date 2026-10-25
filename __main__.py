import pulumi
import pulumi_gcp as gcp

# 1. Configuration
config = pulumi.Config()
gcp_config = pulumi.Config("gcp")

project_id = gcp_config.require("project")
region = gcp_config.get("region") or "europe-west1"
zone = gcp_config.get("zone") or "europe-west1-b"
billing_account = gcp_config.require("billingAccount")

disk_size = config.get_int("diskSize") or 220  # 220GB gives plenty of room for Windows + Aion 2
max_spend_gbp = config.get_int("maxSpend") or 10
max_session_hours = config.get_int("maxSessionHours") or 6
# Generate an ephemeral/reusable Auth Key in your Tailscale Admin Console -> Settings -> Keys
tailscale_auth_key = config.require_secret("tailscaleAuthKey")

# 2. Networking (Zero public ports exposed; IAP only for fallback RDP)
vpc = gcp.compute.Network("gaming-vpc", auto_create_subnetworks=False)

subnet = gcp.compute.Subnetwork(
    "gaming-subnet",
    ip_cidr_range="10.0.1.0/24",
    region=region,
    network=vpc.id,
)

# Allow RDP ONLY via Google's Identity-Aware Proxy (IAP)
iap_firewall = gcp.compute.Firewall(
    "allow-iap-rdp",
    network=vpc.id,
    allows=[gcp.compute.FirewallAllowArgs(protocol="tcp", ports=["3389"])],
    source_ranges=["35.235.240.0/20"],
    target_tags=["gaming-pc"],
)

# 3. Windows Automated Startup Script (Drivers + Tailscale + Sunshine + 6h Kill Timer)
startup_script = tailscale_auth_key.apply(
    lambda ts_key: f"""
$ErrorActionPreference = "Continue"
$LogFile = "C:\\setup_log.txt"
function Log($msg) {{ Add-Content -Path $LogFile -Value "$(Get-Date -Format 'HH:mm:ss') - $msg" }}

if (Test-Path "C:\\setup_complete.flag") {{
    Log "Setup already completed on previous boot. Setting 6-hour safety shutdown timer."
    shutdown.exe /s /f /t {max_session_hours * 3600} /c "Scheduled safety shutdown ({max_session_hours}h limit). Run 'shutdown /a' in CMD to cancel."
    exit 0
}}

Log "Starting automated Cloud Gaming Rig configuration..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# 1. Schedule immediate OS-level safety shutdown timer ({max_session_hours} hours)
shutdown.exe /s /f /t {max_session_hours * 3600} /c "Scheduled safety shutdown ({max_session_hours}h limit). Run 'shutdown /a' in CMD to cancel."
Log "Safety shutdown timer set for {max_session_hours} hours."

# 2. Install Tailscale & auto-join tailnet
Log "Downloading and installing Tailscale..."
Invoke-WebRequest -Uri "https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.msi" -OutFile "C:\\tailscale.msi"
Start-Process msiexec.exe -ArgumentList "/i C:\\tailscale.msi /quiet /norestart" -Wait
& "C:\\Program Files\\Tailscale\\tailscale.exe" up --authkey="{ts_key}" --unattended --accept-routes
Log "Tailscale connected!"

# 3. Install Virtual Audio Driver (VB-Cable) so Moonlight has sound
Log "Installing VB-Cable Virtual Audio..."
Invoke-WebRequest -Uri "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack43.zip" -OutFile "C:\\vbcable.zip"
Expand-Archive -Path "C:\\vbcable.zip" -DestinationPath "C:\\vbcable" -Force
Start-Process -FilePath "C:\\vbcable\\VBCABLE_Setup_x64.exe" -ArgumentList "-i -h" -Wait

# 4. Download & Install Latest Sunshine Streaming Server
Log "Installing Sunshine..."
$sunshineRelease = Invoke-RestMethod -Uri "https://api.github.com/repos/LizardByte/Sunshine/releases/latest"
$installerAsset = $sunshineRelease.assets | Where-Object {{ $_.name -like "*windows-installer.exe" }} | Select-Object -First 1
Invoke-WebRequest -Uri $installerAsset.browser_download_url -OutFile "C:\\sunshine-setup.exe"
Start-Process -FilePath "C:\\sunshine-setup.exe" -ArgumentList "/S" -Wait

# 5. Disable Windows Firewall on Tailscale interface so Moonlight pairs seamlessly
Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled False

# 6. Install GCP NVIDIA L4 GRID Virtual Workstation Driver
Log "Installing NVIDIA GRID Driver via GCP gsutil..."
$driverList = & gsutil ls "gs://nvidia-drivers-us-public/GRID/vGPU*/*server2022*64bit*.exe"
$latestDriver = $driverList | Select-Object -Last 1
& gsutil cp $latestDriver "C:\\nvidia_grid_driver.exe"
Start-Process -FilePath "C:\\nvidia_grid_driver.exe" -ArgumentList "-s -noreboot" -Wait
Log "NVIDIA GRID Driver installed."

New-Item -ItemType File -Path "C:\\setup_complete.flag" -Force
Log "Rebooting to activate GPU and Virtual Display..."
Restart-Computer -Force
"""
)

# 4. Ephemeral Spot Gaming VM (Destroyed cleanly on `pulumi destroy`)
gaming_vm = gcp.compute.Instance(
    "gaming-vm",
    name="cloud-gaming-rig",
    machine_type="g2-standard-4",  # 4 vCPUs, 16GB RAM, 1x NVIDIA L4 (24GB VRAM)
    zone=zone,
    tags=["gaming-pc"],
    # Enables virtual monitor so Sunshine works headless without RDP connected
    enable_display=True,
    boot_disk=gcp.compute.InstanceBootDiskArgs(
        auto_delete=True,  # Wipes cleanly when you run `pulumi destroy`
        initialize_params=gcp.compute.InstanceBootDiskInitializeParamsArgs(
            image="windows-cloud/windows-2022",
            size=disk_size,
            type="pd-balanced",
        ),
    ),
    network_interfaces=[
        gcp.compute.InstanceNetworkInterfaceArgs(
            network=vpc.id,
            subnetwork=subnet.id,
            # STANDARD tier gives 200GB/month of FREE outbound video streaming traffic!
            access_configs=[
                gcp.compute.InstanceNetworkInterfaceAccessConfigArgs(
                    network_tier="STANDARD"
                )
            ],
        )
    ],
    scheduling=gcp.compute.InstanceSchedulingArgs(
        provisioning_model="SPOT",
        preemptible=True,
        automatic_restart=False,
        instance_termination_action="STOP",
    ),
    metadata={
        "windows-startup-script-ps1": startup_script,
    },
    # Required so the VM can pull the official NVIDIA GRID driver from Google's public bucket
    service_account=gcp.compute.InstanceServiceAccountArgs(
        scopes=["https://www.googleapis.com/auth/devstorage.read_only"]
    ),
)

# 5. Billing Fail-Safe Infrastructure (Pub/Sub + Gen2 Cloud Function + £10 Budget)
budget_topic = gcp.pubsub.Topic("budget-alert-topic")

# Dedicated Service Account for the Kill-Switch Cloud Function
fn_sa = gcp.serviceaccount.Account(
    "killswitch-sa",
    account_id="gaming-killswitch-sa",
    display_name="Cloud Gaming Billing Kill-Switch SA",
)

# Grant permission to stop Compute Engine instances
sa_compute_admin = gcp.projects.IAMMember(
    "killswitch-compute-admin",
    project=project_id,
    role="roles/compute.instanceAdmin.v1",
    member=fn_sa.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Bucket to store the Cloud Function source archive
fn_bucket = gcp.storage.Bucket(
    "killswitch-code-bucket",
    location=region,
    force_destroy=True,
    uniform_bucket_level_access=True,
)

fn_archive = gcp.storage.BucketObject(
    "killswitch-zip",
    bucket=fn_bucket.name,
    source=pulumi.FileArchive("./function"),
)

killswitch_fn = gcp.cloudfunctionsv2.Function(
    "billing-killswitch-fn",
    location=region,
    build_config=gcp.cloudfunctionsv2.FunctionBuildConfigArgs(
        runtime="python312",
        entry_point="stop_gaming_vm",
        source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceArgs(
            storage_source=gcp.cloudfunctionsv2.FunctionBuildConfigSourceStorageSourceArgs(
                bucket=fn_bucket.name,
                object=fn_archive.name,
            )
        ),
    ),
    service_config=gcp.cloudfunctionsv2.FunctionServiceConfigArgs(
        max_instance_count=1,
        available_memory="256M",
        timeout_seconds=60,
        service_account_email=fn_sa.email,
        environment_variables={
            "GCP_PROJECT": project_id,
            "COMPUTE_ZONE": zone,
            "INSTANCE_NAME": gaming_vm.name,
        },
    ),
    event_trigger=gcp.cloudfunctionsv2.FunctionEventTriggerArgs(
        trigger_region=region,
        event_type="google.cloud.pubsub.topic.v1.messagePublished",
        pubsub_topic=budget_topic.id,
        retry_policy="RETRY_POLICY_DO_NOT_RETRY",
    ),
)

budget = gcp.billing.Budget(
    "gaming-monthly-budget",
    billing_account=billing_account,
    display_name="Cloud Gaming £10 Fail-Safe",
    budget_filter=gcp.billing.BudgetBudgetFilterArgs(
        projects=[f"projects/{project_id}"],
    ),
    amount=gcp.billing.BudgetAmountArgs(
        specified_amount=gcp.billing.BudgetAmountSpecifiedAmountArgs(
            currency_code="GBP",
            units=str(max_spend_gbp),
        )
    ),
    threshold_rules=[
        gcp.billing.BudgetThresholdRuleArgs(threshold_percent=0.5),
        gcp.billing.BudgetThresholdRuleArgs(threshold_percent=0.9),
        gcp.billing.BudgetThresholdRuleArgs(threshold_percent=1.0),
    ],
    all_updates_rule=gcp.billing.BudgetAllUpdatesRuleArgs(
        pubsub_topic=budget_topic.id,
        schema_version="1.0",
    ),
)

# 6. Outputs
pulumi.export("instance_name", gaming_vm.name)
pulumi.export("zone", zone)
pulumi.export(
    "reset_password_cmd",
    pulumi.Output.concat(
        "gcloud compute reset-windows-password ", gaming_vm.name, " --zone=", zone
    ),
)
pulumi.export(
    "iap_tunnel_cmd",
    pulumi.Output.concat(
        "gcloud compute start-iap-tunnel ",
        gaming_vm.name,
        " 3389 --local-host-port=localhost:3389 --zone=",
        zone,
    ),
)