# TRACE-Fin Synthetic Data Directory

> **Safety & Ethics Notice:** Every record stored in this directory is **100% synthetic** and generated deterministically by [`scripts/seed_demo_data.py`](../scripts/seed_demo_data.py). None of the users, companies, IP addresses, devices, beneficiaries, or threat-intelligence indicators represent real individuals or live threat feeds.

## Files
- `trace_fin.db` — Local SQLite database created when you run `python3 -m scripts.seed_demo_data`. (Ignored by Git via `.gitignore` so you can reset it anytime.)

## Commands

```bash
# Reset and seed the database with deterministic synthetic data (SEED = 42)
.venv/bin/python -m scripts.seed_demo_data

# Inspect database summary, profile distribution, and sample linked records
.venv/bin/python -m scripts.seed_demo_data --inspect-only
```
