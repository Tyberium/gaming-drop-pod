# Cloud Gaming PC - Complete Setup Guide

Copy and paste these commands to set up your cloud gaming rig.

## Prerequisites

### 1. Generate Tailscale Auth Key

Before running the setup commands, you need to generate a Tailscale Auth Key:

1. Go to [Tailscale Admin Console](https://login.tailscale.com/admin)
2. Log in with your Tailscale account
3. Navigate to **Settings** → **Keys** (in the left sidebar)
4. Click **Generate auth key**
5. Configure the key with:
   - ✅ **Reusable** (check this box)
   - ✅ **Ephemeral** (check this box)
   - Leave other options as default
6. Click **Generate key**
7. Copy the key (it will look like: `tskey-auth-xxxxx-xxxxx-xxxxx`)
8. **Save this key** - you'll need it in the setup commands below

### 2. Install Prerequisites

On your PC:
```bash
# Install Pulumi CLI (if not already installed)
# Windows: Download from https://www.pulumi.com/docs/install/
# Or use Chocolatey: choco install pulumi

# Install Google Cloud SDK (if not already installed)
# Windows: Download from https://cloud.google.com/sdk/docs/install
# Or use Chocolatey: choco install gcloudsdk

# Install Python 3.9+ (if not already installed)
# Windows: Download from https://www.python.org/downloads/
```

## Setup Commands (PC)

Run these commands on your PC to configure the project:

```bash
# Navigate to project directory
cd D:\code\tyberium\github\repositories\gaming-drop-pod

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Login to Pulumi Cloud
pulumi login

# Initialize Pulumi stack
pulumi stack init gaming

# Authenticate with Google Cloud
gcloud auth application-default login

# Configure Pulumi with your project details
pulumi config set gcp:project roboto-guilliman
pulumi config set gaming:billingAccount 01ACB6-920C66-B01CAE
pulumi config set gcp:region europe-west1
pulumi config set gcp:zone europe-west1-b
pulumi config set gaming:diskSize 220
pulumi config set gaming:maxSpend 10
pulumi config set gaming:maxSessionHours 6

# Set Tailscale Auth Key (REPLACE WITH YOUR ACTUAL KEY)
pulumi config set --secret gaming:tailscaleAuthKey tskey-auth-REPLACE-WITH-YOUR-KEY
```

**Important**: Replace `tskey-auth-REPLACE-WITH-YOUR-KEY` with your actual Tailscale Auth Key from step 1.

## Verify Configuration

After running the setup commands, verify your configuration:

```bash
pulumi config
```

You should see output similar to:
```
Current stack is gaming:

gcp:billingAccount: 01ACB6-920C66-B01CAE
gcp:project: roboto-guilliman
gcp:region: europe-west1
gcp:zone: europe-west1-b
gaming:diskSize: 220
gaming:maxSessionHours: 6
gaming:maxSpend: 10
gaming:tailscaleAuthKey: [secret]
```

## Test Deployment (Optional - on PC)

You can test the deployment on your PC to verify everything works:

```bash
pulumi up
```

This will create all the resources. Review the plan and confirm with `yes`.

If successful, you can destroy it:
```bash
pulumi destroy
```

## Setup on Mac (for Gaming)

When you're ready to game from your Mac:

```bash
# Clone the repository (if not already done)
git clone https://github.com/Tyberium/gaming-drop-pod.git
cd gaming-drop-pod

# Install Python dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Authenticate with Google Cloud
gcloud auth application-default login

# Login to Pulumi Cloud (use same account as PC)
pulumi login

# Select the gaming stack
pulumi stack select gaming

# Deploy the gaming rig
pulumi up --yes
```

## Quick Reference

### Start Gaming (Mac)
```bash
cd gaming-drop-pod
source venv/bin/activate
pulumi up --yes
```

### Stop Gaming (Mac)
```bash
cd gaming-drop-pod
source venv/bin/activate
pulumi destroy --yes
```

### Update Tailscale Key (if expired)
```bash
pulumi config set --secret gaming:tailscaleAuthKey tskey-auth-NEW-KEY
pulumi up
```

### Change Budget Limit
```bash
pulumi config set gaming:maxSpend 20
pulumi up
```

## Troubleshooting

### Pulumi Login Issues
If you have trouble logging in to Pulumi:
```bash
pulumi logout
pulumi login
```

### GCP Authentication Issues
If you have GCP authentication issues:
```bash
gcloud auth revoke
gcloud auth application-default login
```

### Tailscale Key Expired
Tailscale Auth Keys expire after up to 90 days. To generate a new one:
1. Go to [Tailscale Admin Console](https://login.tailscale.com/admin/settings/keys)
2. Generate a new key with Reusable and Ephemeral checked
3. Update it:
   ```bash
   pulumi config set --secret gaming:tailscaleAuthKey tskey-auth-NEW-KEY
   pulumi up
   ```

## Cost Information

- **Compute**: ~£0.26/hour (Spot VM with L4 GPU)
- **6-hour session**: ~£1.56
- **Storage**: £0.00 when destroyed (ephemeral disk)
- **Egress**: 200GB/month free (Standard Network Tier)

Estimated cost per 6-hour gaming session: **~£1.56**
