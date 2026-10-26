# Ephemeral Cloud Gaming PC on GCP with Pulumi

A zero-maintenance, on-demand Windows Server 2022 cloud gaming rig deployed on Google Cloud Platform using Spot VMs with NVIDIA L4 GPU. Features automated setup, Tailscale zero-trust networking, Sunshine/Moonlight streaming, and dual fail-safe cost controls.

## Architecture Overview

- **Compute**: `g2-standard-4` Spot VM (4 vCPUs, 16GB RAM, 1x NVIDIA L4 24GB GPU)
- **Zone**: `europe-west1-b` (configurable)
- **Storage**: 220GB ephemeral boot disk (auto-deletes on destroy, zero idle storage costs)
- **Networking**: Custom VPC with IAP-only RDP access + Tailscale private mesh for Sunshine streaming
- **Egress**: Standard Network Tier (200GB/month free outbound bandwidth for video streaming)
- **Setup**: Fully automated PowerShell script installs NVIDIA GRID driver, VB-Cable audio, Sunshine, and Tailscale
- **Cost Control**: Dual fail-safe (6-hour OS timer + £10 billing budget with Cloud Function kill-switch)

## Prerequisites

### Required Tools
- [Pulumi CLI](https://www.pulumi.com/docs/install/)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- Python 3.9+ with pip
- [Tailscale](https://tailscale.com/download) installed on your Mac
- [Moonlight](https://moonlight-stream.org/) installed on your Mac

### GCP Requirements
- GCP Project with billing enabled
- GCP Billing Account ID
- IAM permissions for:
  - Compute Engine Admin
  - Cloud Functions Admin
  - Cloud Build
  - Pub/Sub Admin
  - Cloud Billing Budgets
- Enabled APIs:
  - Compute Engine
  - Cloud Functions
  - Cloud Build
  - Eventarc
  - Pub/Sub
  - Cloud Billing Budgets

### Tailscale Setup
1. Log in to [Tailscale Admin Console](https://login.tailscale.com/admin)
2. Navigate to Settings → Keys
3. Generate an Auth Key with:
   - ✅ Reusable
   - ✅ Ephemeral
4. Copy the key (format: `tskey-auth-xxxxx`)

## One-Time Setup

### 1. Clone and Initialize
```bash
cd gaming-drop-pod
pulumi login
pulumi stack init gaming
```

### 2. Configure GCP Authentication
```bash
gcloud auth application-default login
```

### 3. Set Pulumi Configuration
```bash
# Required
pulumi config set gcp:project YOUR_PROJECT_ID
pulumi config set gaming:billingAccount YOUR_BILLING_ACCOUNT_ID
pulumi config set --secret gaming:tailscaleAuthKey tskey-auth-xxxxx

# Optional (defaults shown)
pulumi config set gcp:region europe-west1
pulumi config set gcp:zone europe-west1-b
pulumi config set gaming:diskSize 220
pulumi config set gaming:maxSpend 10
pulumi config set gaming:maxSessionHours 6
```

### 4. Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Game-Day Workflow

### Start Gaming Rig (~20 minutes before playing)
```bash
pulumi up --yes
```

The deployment takes about 6 minutes for:
- VM provisioning and boot
- Automated installation of Tailscale, VB-Cable, Sunshine, and NVIDIA GRID driver
- Automatic reboot to activate GPU

### Verify Setup
1. Check your Mac's Tailscale menu bar - `cloud-gaming-rig` should appear with a `100.x.y.z` IP
2. Open `https://100.x.y.z:47990` in your browser (accept self-signed cert warning)
3. Set your Sunshine username and password
4. Open Moonlight on your Mac - the PC should auto-discover
5. Enter the 4-digit PIN from the Sunshine web UI
6. Launch the Desktop stream in Moonlight

### Download Games
Download games from within the Moonlight stream - they download at 2+ Gbps with £0.00 ingress cost.

### End Gaming Session
```bash
pulumi destroy --yes
```

This completely deletes the VM and disk, so you pay £0.00 until your next session.

**Tip for consecutive days**: If you plan to play Saturday and Sunday, don't run `pulumi destroy` on Saturday. Just shut down Windows from inside Moonlight (`Stop-Computer`). Your game stays installed, compute billing stops immediately, and keeping the 220GB disk for 24 hours costs less than £0.55. Run `pulumi destroy --yes` on Sunday night.

## Multi-Machine Workflow

**Development (PC):**
- Initial project setup and code changes
- Commit to repository

**Operations (Mac):**
- Clone repository
- Run `gcloud auth application-default login`
- Run `pulumi login` (same Pulumi Cloud account as PC)
- Run `pulumi up` to start gaming
- Run `pulumi destroy` to stop gaming

Configuration and secrets sync automatically via Pulumi Cloud.

## Configuration Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `gcp:project` | required | - | GCP Project ID |
| `gcp:region` | optional | `europe-west1` | GCP region |
| `gcp:zone` | optional | `europe-west1-b` | GCP zone |
| `gcp:billingAccount` | required | - | GCP Billing Account ID |
| `gaming:tailscaleAuthKey` | secret | - | Tailscale Auth Key (reusable, ephemeral) |
| `gaming:diskSize` | optional | `220` | Boot disk size in GB |
| `gaming:maxSpend` | optional | `10` | Monthly spend limit in GBP |
| `gaming:maxSessionHours` | optional | `6` | OS-level auto-shutdown timer in hours |

## Cost Control

### Layer 1: OS-Level Session Timer (Zero Latency)
The Windows startup script sets a 6-hour countdown timer (`shutdown.exe /s /f /t 21600`). When Windows shuts down, the GCP instance stops (not terminates), stopping compute, GPU, and Windows licensing charges immediately.

**To cancel the timer** (if needed):
```cmd
shutdown /a
```

**To re-arm the timer**:
```cmd
shutdown /s /f /t 21600
```

### Layer 2: GCP Billing Budget + Cloud Function
A £10 monthly budget triggers a Cloud Function that stops the VM when exceeded. The function checks budget notifications via Pub/Sub and calls the Compute Engine API to stop the instance.

**Budget thresholds**: 50%, 90%, and 100% alerts

**To increase the budget** (if you play more in a month):
```bash
pulumi config set gaming:maxSpend 20
pulumi up
```

## Outputs

After `pulumi up`, the following outputs are provided:

- `instance_name` - Name of the deployed VM (`cloud-gaming-rig`)
- `zone` - Deployment zone
- `reset_password_cmd` - Command to reset Windows password if needed
- `iap_tunnel_cmd` - Command to create IAP tunnel for RDP (fallback)

## Fallback RDP via IAP

If Tailscale has issues, you can use Google's Identity-Aware Proxy for RDP:

```bash
# Run the exported iap_tunnel_cmd from pulumi outputs
gcloud compute start-iap-tunnel cloud-gaming-rig 3389 --local-host-port=localhost:3389 --zone=europe-west1-b
```

Then connect via Microsoft Remote Desktop to `localhost:3389`.

## Troubleshooting

### VM Not Appearing in Tailscale
1. Check the VM is running in GCP Console
2. Check `C:\setup_log.txt` on the VM (via RDP if needed)
3. Verify Tailscale Auth Key is valid and not expired (max 90 days)

### GPU Not Detected
1. Check `C:\setup_log.txt` for driver installation errors
2. Run `nvidia-smi` in PowerShell on the VM
3. Ensure the VM has `enable_display=True` (default in code)

### Sunshine Not Starting
1. Check Windows Firewall is disabled on Tailscale interface (script does this)
2. Verify Sunshine installation completed in `C:\setup_log.txt`
3. Access Sunshine web UI at `https://100.x.y.z:47990`

### Budget Kill-Switch Not Working
1. Verify budget is created in Cloud Billing console
2. Check Cloud Function logs in GCP Console
3. Test the function manually:
   ```bash
   gcloud pubsub topics publish $(gcloud pubsub topics list --format="value(name)" --filter="budget-alert-topic") \
     --message='{"costAmount": 12.0, "budgetAmount": 10.0}'
   ```

## Risks and Considerations

### Spot VM Preemption
GCP can reclaim Spot VMs at any time if capacity is tight. If preempted mid-session:
- Switch to a different zone: `pulumi config set gcp:zone europe-west1-c`
- Re-run: `pulumi up`

### Tailscale Key Expiry
Auth Keys expire after up to 90 days. Every 3 months:
- Generate a fresh key in Tailscale console
- Update: `pulumi config set --secret gaming:tailscaleAuthKey NEW_KEY`
- Run: `pulumi up`

### Windows KMS Activation
Windows Server 2022 activates automatically against `kms.windows.googlecloud.com` (35.190.247.13/32) via standard outbound NAT.

### Monthly Budget Reset
GCP Budgets track cumulative monthly spend. If you exceed £10 in a calendar month, raise `gaming:maxSpend` to prevent the Cloud Function from stopping new sessions.

### Ephemeral Disk
Since the disk is ephemeral (`autoDelete: true`), all game data is lost when you run `pulumi destroy`. To preserve games between sessions:
- Keep the VM running (just shut down Windows) instead of destroying
- Or increase disk size to hold multiple games

## Cost Estimates

### Compute (Spot VM)
- `g2-standard-4` with L4 GPU: ~£0.26/hour
- 6-hour session: ~£1.56

### Storage
- 220GB `pd-balanced`: ~£15/month (only when VM is running)
- Ephemeral: £0.00 when destroyed

### Egress
- Standard Tier: 200GB/month free
- Moonlight streaming (5 Mbps): ~2.2GB/hour
- 6-hour session: ~13GB (well within free tier)

### Windows Licensing
- Windows Server 2022: Included in compute pricing

**Total per 6-hour session**: ~£1.56 (plus egress if you exceed 200GB/month)

## File Structure

```
cloud-gaming-pc/
├── Pulumi.yaml           # Pulumi project configuration
├── requirements.txt      # Python dependencies
├── __main__.py          # Main infrastructure code
├── README.md            # This file
└── function/
    ├── main.py          # Cloud Function for billing kill-switch
    └── requirements.txt # Cloud Function dependencies
```

## License

This project is provided as-is for personal cloud gaming use.
