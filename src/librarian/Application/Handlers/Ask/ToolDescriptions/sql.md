Run single-statement SQL queries against the library database and read the rows.

What you can see (the columns and the most used keys of `fields` are in your instructions):
- documents(id, kind, validity_start, validity_end, validity_as_written, description, created_at)
- fields(id, document_id, name, value, as_written, verified)
- sections(id, document_id, position, heading, created_at)

`fields` is a table, one row per field: read a value with
`fields.value`, it needs the document join: `JOIN fields f ON f.document_id = d.id AND f.name = 'total_amount'`.
`validity_start` and `validity_end` are ISO dates as text ('YYYY-MM-DD'), `validity_end` is the
last day the document covers. A document with no validity has both null. A document covers
May 2025 when `validity_start <= '2025-05-31' AND (validity_end IS NULL OR validity_end >= '2025-05-01')`.

Only a query runs: SELECT, WITH ... SELECT, VALUES or TABLE. Writes, SET, SHOW and
EXPLAIN fail at the database.

Limits: the connection is read-only, writes fail at the database; each statement stops
after 5 seconds; a query returning more than 200 rows is an error, aggregate in SQL or
add a LIMIT.

Examples, from simple to hard:

```sql
SELECT 1
```

```sql
SELECT kind, count(*) AS documents
FROM documents
GROUP BY kind
ORDER BY documents DESC
```

```sql
SELECT d.id, d.kind, f.value AS total_amount
FROM documents d
JOIN fields f ON f.document_id = d.id AND f.name = 'total_amount'
WHERE d.kind = 'invoice' AND d.validity_start <= '2025-12-31' AND d.validity_end >= '2025-10-01'
ORDER BY d.validity_end DESC
LIMIT 1
```

```sql
SELECT sum(CAST(f.value AS numeric)) AS spent_2025
FROM documents d
JOIN fields f ON f.document_id = d.id AND f.name = 'total_amount'
WHERE f.name = 'total_amount'
  AND d.validity_start <= '2025-12-31'
  AND (d.validity_end IS NULL OR d.validity_end >= '2025-01-01')
```

```sql
SELECT d.id, CAST(f.value AS numeric) AS total_amount
FROM documents d
JOIN fields f ON f.document_id = d.id AND f.name = 'total_amount'
ORDER BY d.validity_end DESC
LIMIT 10
```
