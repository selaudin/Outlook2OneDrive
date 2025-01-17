# Email Attachment Downloader and OneDrive Uploader

Automate the process of fetching your latest emails, downloading their attachments, and uploading them to OneDrive seamlessly. This Python script leverages the Microsoft Graph API to interact with your Outlook and OneDrive accounts, ensuring secure and efficient email and file management.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
<!-- - [Installation](#installation)
- [Configuration](#configuration)
  - [1. Azure App Registration](#1-azure-app-registration)
  - [2. Environment Variables](#2-environment-variables)
- [Usage](#usage)
- [Scheduling the Script](#scheduling-the-script)
  - [Using `cron` on macOS/Linux](#using-cron-on-macoslinux)
- [Logging](#logging)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)
- [License](#license)
- [Contact](#contact) -->

## Features

- **Fetch Emails**: Retrieves the latest 10 emails from your Outlook inbox.
- **Download Attachments**: Identifies and downloads attachments from fetched emails.
- **Upload to OneDrive**: Automatically uploads downloaded attachments to a specified OneDrive folder.
- **Handle Large Files**: Supports uploading large files (>4MB) using upload sessions.
- **Token Caching**: Implements persistent token caching to avoid repeated authentication prompts.
- **Automated Scheduling**: Easily schedule the script to run every 10 minutes using `cron`.
- **Logging**: Maintains detailed logs for monitoring and troubleshooting.

## Prerequisites

Before setting up the script, ensure you have the following:

- **Python 3.12+**: Ensure Python is installed on your system. You can download it from [python.org](https://www.python.org/downloads/).
- **Microsoft Account**: An Outlook.com or Office 365 account with access to OneDrive.
- **Azure App Registration**: Access to the Azure Portal to register your application and configure permissions.

<!-- ## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/selaudin/Outlook2OneDrive.git
   cd Outlook2OneDrive -->
