import sqlite3,json
db=sqlite3.connect(r"D:\dsh-proj\Roll\.scratch\r13real\roll.sqlite3")
table=db.execute("SELECT name FROM sqlite_master WHERE name='financial_document_parses'").fetchone()
print("table",bool(table))
if table:
    rows=[json.loads(r[0]) for r in db.execute("SELECT value FROM financial_document_parses")]
    print(len(rows),[(r["status"],r["first_page"],r["last_page"],bool(r.get("artifact"))) for r in rows])
