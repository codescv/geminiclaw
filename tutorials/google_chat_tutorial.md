# How to Configure the Google Chat Bot

This tutorial explains how to configure the Google Chat bot for Gemini Claw.

## Prerequisites

1.  A Google Cloud project.
2.  Google Chat API enabled in your project.
3.  Authentication configured (either ADC for local testing or a Service Account).

## Authentication & Permissions

Google Chat bot requires specific permissions for receiving and sending messages via Pub/Sub and the REST API.

### 1. Receiving Messages (Pub/Sub)
Google Chat sends events to a Pub/Sub topic. 

1.  **Create a Topic** (e.g., `google-chat-messages`).
2.  **Create a Subscription** (specifically a **Pull** subscription) for that topic (e.g., `geminiclaw-chat-messages-sub`).
3.  **Grant Publisher Role**: Google Chat needs permission to publish to your topic. You must grant the **Pub/Sub Publisher** role on your topic to both:
    *   `chat-api-push@system.gserviceaccount.com`
    *   The Chat app service account (which usually looks like `service-PROJECT_NUMBER@gcp-sa-gsuiteaddons.iam.gserviceaccount.com` and can be found in the Chat API configuration page).

### 2. Running the Bot (Pulling Messages)
The bot needs to pull messages from the subscription. The account running the bot (either your user account via ADC or a specific Service Account) needs the **Pub/Sub Subscriber** role on that subscription.

### 3. Sending Messages (REST API)
The bot sends replies using the Google Chat REST API.

#### Option A: Local Testing with ADC (No Service Account Needed)
If you are testing locally, you can use your user credentials instead of a service account:
1. Run `gcloud auth application-default login` with the specific scope required for Google Chat:
   ```bash
   gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/chat.messages.create
   ```
2. Ensure you set a quota project:
   ```bash
   gcloud auth application-default set-quota-project YOUR_PROJECT_ID
   ```

#### Option B: Production with Service Account
For production or if ADC issues persist:
1. Create a Service Account in your project.
2. Download the JSON key file.
3. Set the environment variable:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
   ```

## Configuration

Add the following section to your `config.toml`:

```toml
[google_chat]
enabled = true
google_cloud_project = "your-project-id"
google_chat_subscription = "your-subscription-id"
```

## Running the Bot

Ensure your configuration is correct and run:
```bash
uv run geminiclaw start
```
