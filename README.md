# Free Games Explorer

An independent Steam-style browser for free games listed on the Steam Store.

The catalog is rebuilt from Steam search results every six hours. Steam tag IDs provide game categories; Online includes multiplayer, online co-op, MMO, PvP and related Steam tags.

```bash
python scripts/update_games.py
```

For a quick local sample:

```bash
MAX_PAGES=5 python scripts/update_games.py
```
