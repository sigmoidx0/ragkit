# Incident Response Playbook

## Severity Levels

- **SEV-1**: Complete outage or data corruption risk
- **SEV-2**: Major functionality degraded
- **SEV-3**: Minor bug with workaround available

## First 15 Minutes

1. Acknowledge the alert.
2. Create an incident channel.
3. Assign commander, communicator, and investigator roles.
4. Capture current impact and affected users.

## Communication Template

> We are investigating elevated error rates in the document search API.
> Next update in 15 minutes.

## Recovery Checklist

- Roll back the latest deployment if needed
- Verify DB and vector store health
- Confirm login, upload, and search paths are functional
- Post a summary and action items

## Postmortem Questions

- What was the trigger?
- Why did detection happen late (if applicable)?
- Which guardrails should be automated?
