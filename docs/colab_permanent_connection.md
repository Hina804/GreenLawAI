# How to Make Colab Connection "Permanent"

Google Colab disconnects every 12 hours (Free Tier). You cannot change this.
**HOWEVER**, you can make the **URL** permanent so you don't have to update `rag_config.yaml` every time!

## The Solution: Static ngrok Domain (Free)

ngrok now offers **1 free static domain** for everyone.

### Step 1: Get Your Static Domain
1.  Log in to [dashboard.ngrok.com](https://dashboard.ngrok.com).
2.  Go to **Cloud Edge** -> **Domains**.
3.  Click **+ Create Domain**.
4.  Copy your domain (e.g., `funny-cat-123.ngrok-free.app`).

### Step 2: Update Colab Notebook
In `colab/llm_server.ipynb`, change the ngrok cell to:

```python
# Start ngrok with STATIC DOMAIN
ngrok.set_auth_token("YOUR_TOKEN")
public_url = ngrok.connect(5000, domain="funny-cat-123.ngrok-free.app")  # <-- YOUR DOMAIN HERE
```

### Step 3: Update Local Config (Once)
In `config/rag_config.yaml`:

```yaml
llm:
  provider: "colab"
  colab_url: "https://funny-cat-123.ngrok-free.app"  # <-- NEVER CHANGE THIS AGAIN!
```

### Result
Now, whenever you start Colab:
1.  Run the notebook.
2.  **Done!** Your local system automatically connects. No copy-pasting URLs!

---

## To See The Answer NOW

Since your local PC is struggling (11+ mins), do this **one-time setup**:

1.  Open **Colab**.
2.  Run the notebook.
3.  Copy the URL.
4.  Run: `python scripts/update_colab_url.py <URL>`
5.  Run: `python scripts/show_answer.py`

**You will see the answer in 10 seconds.**
