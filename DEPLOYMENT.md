# Deploy CampusConnect

The repository includes a Render Blueprint for a Python web service, managed PostgreSQL and a pre-deploy migration command. The declared web and database plans are paid. Check the plan prices before creating services. Create the S3 bucket and SMTP sender before opening the marketplace to users.

## Put the source on GitHub

Run these commands in the directory that contains `manage.py`. Create an empty GitHub repository under your account first.

```bash
git init -b main
git add .
git status --short
git commit -m "Build CampusConnect marketplace"
git remote add origin https://github.com/YOUR-ACCOUNT/campusconnect.git
git push -u origin main
```

Check the staged list before committing. The repository ignores `.env`, development databases, uploaded media and collected static files. If you place CampusConnect inside a larger repository, configure Render to use the CampusConnect directory as the service root.

## Configure persistent media and SMTP

1. Create an S3 bucket with Block Public Access enabled. Allow the application credential to read, write and delete objects under `images/*` only. Use TLS for your endpoint. For S3-compatible storage add `AWS_S3_ENDPOINT_URL` and use the provider's recommended region.
2. Verify a sender with your SMTP provider. Use port 587 with STARTTLS, or match your provider's settings. Supply the SMTP host, application credentials and verified from address in Render.
3. Set the access keys and SMTP credentials in the Render environment. Store and rotate them in the providers' dashboards.

## Create the Render services

1. In Render choose **New → Blueprint**, connect the GitHub repository and select the branch containing `render.yaml`.
2. Enter all requested environment variables. In `DJANGO_ALLOWED_HOSTS` use the exact Render hostname and any custom domain, with no scheme. In `CSRF_TRUSTED_ORIGINS` include their full HTTPS origins. Set `PUBLIC_BASE_URL` to the canonical HTTPS origin used in emails.
3. The Blueprint generates the Django secret, links the database's internal `DATABASE_URL` and denies public database network access. Keep PostgreSQL TLS enabled. Render terminates HTTPS and controls `X-Forwarded-Proto`; keep `TRUST_HTTPS_PROXY=1` for this topology.
4. The build installs the Python dependencies and collects static assets. The pre-deploy command applies migrations. Gunicorn then serves the web application. Render checks PostgreSQL reachability through `/health/`.
5. From a Render shell or a one-off job, run `python manage.py createsuperuser`. Add supported colleges in Django Admin and give moderators the required listing and report permissions. Schedule `python manage.py prune_rate_limits` periodically if traffic warrants it.

## Verify the deployment

- Confirm `/health/` returns HTTP 200 and the homepage loads over HTTPS with CSS, icons and images.
- In a Render shell, run `python manage.py check --deploy --fail-level WARNING` and `python manage.py migrate --check`.
- Register using an inbox you can access. Confirm the address, then request and complete a password reset.
- Publish a listing with two images, redeploy and confirm both images still load from the media bucket.
- Use separate accounts to confirm wishlist, messaging and moderation. Confirm a logged-out browser cannot open a private draft and a third account cannot read a conversation.
- Verify PostgreSQL backup and recovery settings in Render before storing real user data.

## Common deployment errors

| Symptom | Check |
| --- | --- |
| Bad Request or `DisallowedHost` | Include the exact hostname in `DJANGO_ALLOWED_HOSTS` with no scheme. |
| HTTPS redirect loop | Confirm Render terminates HTTPS and passes the trusted scheme header. |
| CSRF verification fails | Add the current HTTPS origin to `CSRF_TRUSTED_ORIGINS` and confirm proxy TLS settings. |
| Styles show as 404 | Check that the build finished `collectstatic` and that the manifest is present with the build. |
| PostgreSQL connection fails | Check the linked database, internal connection string, region and SSL configuration. |
| Upload fails or photo is blank | Check bucket endpoint, object permissions, signing region and persistent bucket configuration. |
| Password email does not arrive | Check SMTP credentials, sender verification, logs, port and TLS settings. |
| No colleges appear at registration | Add supported colleges in Django Admin. The demo command is development-only. |
