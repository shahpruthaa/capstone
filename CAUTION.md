# ⚠️ CRITICAL: File Corruption Risk

## THE BUG

DO NOT run this pattern:
```bash
docker compose exec api bash -c "cat /app/file" > ~/hostfile.py
```

This **WILL truncate and corrupt the file**. Here's why:

### Why It Happens (Technical)

The shell (zsh/bash) executes redirection BEFORE running the command:
```
1. zsh parses: docker exec ... > file.py
2. zsh opens file.py in WRITE mode (truncates to 0 bytes) ← FILE NOW EMPTY
3. zsh runs: docker compose exec ... (outputs to the now-empty file)
4. Result: Original content lost, file corrupted
```

Since `~/hostfile.py` is volume-mounted into the container at `/app/file`, they're the **same inode**. Truncating on the host truncates in the container too.

### The Fix (Always Use This Pattern)
```bash
# 1. ALWAYS restore from git first
git checkout HEAD -- apps/api/app/services/db_quant_engine.py

# 2. Apply patches as Python (modifies host file only)
python3 << 'PYEOF'
with open("apps/api/app/services/db_quant_engine.py", s f:
    content = f.read()

# YOUR PATCHES HERE
content = content.replace("old", "new")

with open("apps/api/app/services/db_quant_engine.py", "w") as f:
    f.write(content)

print("✅ Patched safely on host")
PYEOF

# 3. Restart container
docker compose restart api && sleep 5

# 4. Verify (read from container to confirm)
docker compose exec api bash -c "grep -c 'def estimate_expected_returns' /app/app/services/db_quant_engine.py"
```

### Why This Works

- `git checkout` restores from `.git/objects` (atomic, safe)
- Python read→modify→write is atomic on most filesystems
- No shell redirection, no race condition
- Container sees the changes via volume mount (one-way, after file is written)

### Git State Safety

Always check before patching:
```bash
git status
# Should show: "On branch kairavee-platform\nnothing to commit, working tree clean"

git log --oneline -3
# Your commits should appear, not teammates' commits
```

If working tree is dirty:
```bash
git stash  # Safely save uncommitted changes
gckout HEAD -- <file>  # Restore
git stash pop  # Restore your changes (may need merge)
```

### Emergency Recovery (If File Is Already Corrupted)
```bash
# Check the damage
wc -l apps/api/app/services/db_quant_engine.py
# If < 500 lines, file is corrupted

# Restore from git
git checkout HEAD -- apps/api/app/services/db_quant_engine.py

# Verify
wc -l apps/api/app/services/db_quant_engine.py
# Should be ~1878 lines

# If still broken, restore from a specific commit
git show HEAD:apps/api/app/services/db_quant_engine.py > apps/api/app/services/db_quant_engine.py

# Or from previous commits
git log --oneline apps/api/app/services/db_quant_engine.py | head -5
git checkout <commit-hash> -- apps/api/app/services/db_quant_engine.py
```

### Collaborative Safety

**Do NOT:**
- Force push to main/origin
- Delete branches that teammates are using
- Commit directly to main (use your feature branch)
- Share uncommitted changes via copy-paste

**Do:**
- Work on your feature branch (`kairavee-platform`)
- Commit frequently with clear messages: `git commit -am "Fix: Ensemble scorer integration"`
- Push to your branch: `git push origin kairavee-platform`
- Create PRs for merging to main
- Communicate with teammates before patching shared files

### Testing Pattern
```bash
# After any patch, always test locally first
docker compose restart api && sleep 10

# Verify syntax
docker compose exec api python -c "from app.services.db_quant_engine import generate_portfolio; print('✅ Imports OK')"

# Verify functionality
curl -s -X POST http://localhost:8000/api/v1/portfolio/generate \
  -H "Content-Type: application/json" \
  -d '{"investment_amount": 500000, "risk_mode": "MODERATE"}' | python3 -m json.tool | head -20

# Only after local verification, commit
git add apps/api/app/services/db_quant_engine.py
git commit -m "Integration: Ensemble scorer in portfolio generator"
```

