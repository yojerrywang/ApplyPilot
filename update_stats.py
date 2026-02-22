import re

with open("src/applypilot/database.py", "r") as f:
    text = f.read()

# Make get_stats accept session_id
text = re.sub(
    r"def get_stats\(conn: sqlite3\.Connection \| None = None\) -> dict:",
    "def get_stats(conn: sqlite3.Connection | None = None, session_id: str | None = None) -> dict:",
    text
)

# Helper replace inside get_stats
def replace_query(match):
    prefix = match.group(1)
    query_str = match.group(2)
    # E.g. "SELECT COUNT(*) FROM jobs" -> "SELECT COUNT(*) FROM jobs{where_prefix}"
    if "WHERE" in query_str:
        query_str = query_str.replace("WHERE", "WHERE{where_and}")
    else:
        query_str += "{where_clause}"
        
    return f'{prefix}conn.execute(\n        f"{query_str}", params\n    )'

stats_pattern = r'conn\.execute\(\s*"([^"]+)"\s*\)'
# We will just manually inject the `where_clause` stuff at the top of get_stats
text = re.sub(
    r'(stats: dict = {})\n',
    r'\1\n\n    where_clause = " WHERE session_id = ?" if session_id else ""\n    where_and = " session_id = ? AND " if session_id else ""\n    params = (session_id,) if session_id else ()\n',
    text
)

# Replace all execute calls inside get_stats
def replacer(match):
    return "conn.execute(f\"" + match.group(1).replace("WHERE ", "WHERE {where_and}") + "{where_clause}\", params)"
text = re.sub(r'conn\.execute\(\s*"([^"]*FROM jobs[^"]*)"\s*\)', replacer, text)
text = text.replace('{where_clause}{where_clause}', '{where_clause}')
text = text.replace('{where_and}{where_clause}', '{where_and}')

with open("src/applypilot/database.py", "w") as f:
    f.write(text)
