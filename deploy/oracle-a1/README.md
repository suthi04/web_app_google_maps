# Deploy InsightReview on Oracle Cloud Always Free A1

This guide uses an **Ubuntu Arm (Ampere A1)** VM, one Waitress process, SQLite on
the VM's persistent boot volume, and Tailscale Funnel for a public HTTPS URL.
It does not require a paid domain or opening ports 80/443 on the VM. Funnel is
public: anyone with the URL can use the site and consume configured Apify/Gemini
quotas. Keep the app's rate limit enabled and monitor those services' usage.
The `deploy/oracle-a1` files must be committed/pushed before a new VM can fetch
them with `git clone`; creating this local guide does not publish it to GitHub.

## 1. Create the VM in your own Oracle account

In the Oracle Cloud Console, choose **Compute > Instances > Create instance**.
Use the tenancy's **home region**, an **Always Free Eligible Ubuntu image**, and
**VM.Standard.A1.Flex** marked Always Free, with **2 OCPU / 12 GB RAM** (provided
the tenancy has the full free allowance available). Use a boot volume within the
Always Free storage allowance; the default 50 GB is enough to start. Assign a
public IPv4 address for SSH and download the generated private SSH key to your
computer. Never send that private key, an Oracle password, or API tokens in chat.

If Oracle reports "Out of host capacity", do not select a paid shape. Try another
availability domain in the home region or wait and retry. Before creating the
instance, verify the final screen still says **Always Free Eligible**.

For SSH, permit inbound TCP 22 from **your own public IP** where possible. Do
not add inbound rules for 5000, 80, or 443: Funnel only needs outbound access.

From PowerShell on your computer, connect using the key and public IP shown in
the Oracle Console (substitute the actual values):

```powershell
ssh -i C:\path\to\your-oracle-key.key ubuntu@YOUR_VM_PUBLIC_IP
```

The remaining commands run **inside the Ubuntu VM**, not in PowerShell.

## 2. Install the app and check Arm dependencies

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
git clone https://github.com/suthi04/web_app_google_maps.git ~/insightreview
cd ~/insightreview
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-model.txt
.venv/bin/python -c 'import platform, torch; print(platform.machine(), torch.__version__)'
```

The last command should print `aarch64` and a PyTorch version. If installation
fails on Arm, stop here and capture the error; do not switch to a paid VM.
Model weights download on first use, so the first WangchanBERTa analysis may
take longer. The app can still run with Lexicon/Rule-based if the model is not
available.

## 3. Configure secrets and conservative concurrency

```bash
cd ~/insightreview
cp .env.example .env
chmod 600 .env
.venv/bin/python -c 'import secrets; print(secrets.token_hex(32))'
nano .env
```

In `.env`, paste the generated random string as `SECRET_KEY`. Set the following
values (and add your own Apify/Gemini keys **only on the VM**, if wanted):

```dotenv
HOST=127.0.0.1
PORT=5000
FLASK_DEBUG=0
SESSION_COOKIE_SECURE=1
USE_MODEL=1
ANALYZE_MAX_CONCURRENT=1
WANGCHAN_MAX_CONCURRENT=1
ANALYZE_MAX_QUEUED=3
ANALYZE_MAX_REQUESTS=10
```

`APIFY_TOKEN` is required for real Google Maps reviews. Without it, the app
uses sample reviews. `GEMINI_API_KEY` is optional; without it, use Rule-based.
Both services have separate quotas/possible costs outside Oracle's free VM.

## 4. Run as one auto-starting process

```bash
cd ~/insightreview
sudo cp deploy/oracle-a1/insightreview.service /etc/systemd/system/insightreview.service
sudo systemctl daemon-reload
sudo systemctl enable --now insightreview.service
systemctl status insightreview.service --no-pager
curl -fsS http://127.0.0.1:5000/healthz
```

The health check must return JSON with a healthy database. If it fails, read
`journalctl -u insightreview.service -n 100 --no-pager` before proceeding.
Keep **one process**: the background analysis queue lives inside that process.

## 5. Publish HTTPS using the existing Tailscale account

Follow Tailscale's official [Linux installation guide](https://tailscale.com/docs/install/linux)
for Ubuntu on the VM, then:

```bash
sudo tailscale up
sudo tailscale funnel --bg http://127.0.0.1:5000
tailscale funnel status
```

Complete the `tailscale up` login in your own browser. If Tailscale asks to
enable Funnel for this tailnet/device, enable it in the admin console as you
did for your Windows computer. The status command prints the **new VM's**
`https://...ts.net/` URL; the old laptop's URL does not move automatically.
Because `--bg` is used, Funnel resumes after a VM/Tailscale restart.

Open the URL from another device. Check `/healthz`, then test one analysis in
Lexicon/Rule-based mode, then one with WangchanBERTa. Only after those work,
try Gemini and a real Apify scrape. Never expose port 5000 publicly.

## 6. Updates and backup

Before updating, make a backup of `insightreview.db` on a separate device or
volume. A VM loss or free-tier reclamation can still lose data even though the
boot volume normally persists. To update code after the current jobs finish:

```bash
cd ~/insightreview
git pull --ff-only
.venv/bin/python -m pip install -r requirements-model.txt
sudo systemctl restart insightreview.service
curl -fsS http://127.0.0.1:5000/healthz
```

Restarting during an analysis interrupts that job; the app marks interrupted
jobs as failed at next startup. To stop public access, run
`sudo tailscale funnel --https=443 off` on the VM.

Official references: [Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm),
[Oracle first Linux instance](https://docs.oracle.com/en-us/iaas/Content/Compute/tutorials/first-linux-instance/overview.htm),
[Tailscale Funnel CLI](https://tailscale.com/docs/reference/tailscale-cli/funnel).
