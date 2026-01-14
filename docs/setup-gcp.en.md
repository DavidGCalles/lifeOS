# Google Cloud Platform (GCP) Setup Guide for LifeOS

This guide describes the necessary steps to configure the GCP services required by LifeOS, specifically Firestore and authentication via a service account.

## 1. Enable the Firestore API

Firestore is used as the backend for persistent memory management (sessions and long-term memory).

1.  **Go to the GCP Console:** Access [https://console.cloud.google.com/](https://console.cloud.google.com/).
2.  **Select your project:** Make sure you have the correct project selected at the top of the console.
3.  **Enable the API:**
    *   In the navigation menu, go to **APIs & Services > Library**.
    *   Search for "Cloud Firestore API".
    *   Select it and click **Enable**.
4.  **Create a Firestore database:**
    *   Once the API is enabled, go to the **Firestore** section in the navigation menu.
    *   Click **Create database**.
    *   Choose **Native Mode**.
    *   Select a location close to your users (e.g., `europe-west1`).
    *   Click **Create**.

## 2. Create a Service Account

A service account allows the application to securely authenticate with GCP services without using personal user credentials.

1.  **Go to IAM & Admin:** In the navigation menu, go to **IAM & Admin > Service Accounts**.
2.  **Create the account:**
    *   Click **+ CREATE SERVICE ACCOUNT**.
    *   **Service account name:** `lifeos-firestore-sa` (or a descriptive name).
    *   **Service account ID:** It will be generated automatically.
    *   **Description:** "Service account for LifeOS to access Firestore".
    *   Click **CREATE AND CONTINUE**.
3.  **Assign roles:**
    *   In the "Grant this service account access to project" section, search for and add the following role:
        *   `Cloud Datastore User` (This role provides full permissions for Firestore in Native Mode).
    *   Click **CONTINUE**.
4.  **Generate the key (JSON):**
    *   In the last step ("Grant users access to this service account"), you can skip it and click **DONE**.
    *   Find the newly created account in the list, click the three dots (Actions), and select **Manage keys**.
    *   Click **ADD KEY > Create new key**.
    *   Select **JSON** as the key type and click **CREATE**.
    *   A JSON file will be downloaded. **Rename it to `credentials.json`** and save it in a safe place. **Do not commit it to the Git repository!**

## 3. Local Setup for Firestore Testing

For your local development environment to connect to Firestore using the credentials you just created, you need to "mount" them so the application can find them.

The standard way is by using the `GOOGLE_APPLICATION_CREDENTIALS` environment variable.

### Option A: Using `docker-compose.yml` (Recommended)

> **[WIP]** This section is pending an update. Credential injection will be managed through Docker secrets or a similar solution in the future.

For now, please use "Option B" for local development.

### Option B: Local Execution (without Docker)

If you run the `main.py` script directly on your machine:

1.  **Place `credentials.json`** in the project root.
2.  **Set the environment variable** in your terminal before running the script.

    **On Windows (PowerShell):**
    ```powershell
    $env:GOOGLE_APPLICATION_CREDENTIALS="c:\full\path\to\your\project\lifeOS\credentials.json"
    python main.py
    ```

    **On macOS/Linux:**
    ```bash
    export GOOGLE_APPLICATION_CREDENTIALS="/full/path/to/your/project/lifeOS/credentials.json"
    python main.py
    ```
This variable will only persist for the duration of your terminal session. To make it permanent, you should add it to your shell profile (`.bashrc`, `.zshrc`, etc.) or your system's environment variables.
