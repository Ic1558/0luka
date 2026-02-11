#!/bin/bash

timestamp=$(date "+%Y-%m-%dT%H:%M:00+07:00")

curl -s -X POST https://9d9f9a73-de5a-4cb9-8d16-e0261a59b193-00-3zzaiqanqjq2.kirk.replit.dev/time \
-H "Content-Type: application/json" \
-d "{\"time\":\"$timestamp\",\"sender\":\"LaunchdBeacon\",\"channel\":\"launchd\"}" \
>> /tmp/launchd-beacon.log 2>> /tmp/launchd-beacon.err

