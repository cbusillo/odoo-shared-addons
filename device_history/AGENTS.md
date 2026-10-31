# Historical Device Information

Own only the transition from stored parsed device attributes to native raw
User-Agent telemetry. Keep native request logging, queries, access rules and
retention behavior. Never synthesize raw agents or grant access for a reader.

The install hook admits existing missing-agent rows before field reflection.
Do not run it on upgrades or call it from request handling. The conditional
database constraint keeps new inserts subject to the raw-agent requirement.
Session fallbacks must follow native current/latest device selection.

Run the complete addon test module for changes here. Native installation and
base-update ownership proof belong in the consuming migration's existing run.
See [README.md](README.md) for the same-run installation contract.
