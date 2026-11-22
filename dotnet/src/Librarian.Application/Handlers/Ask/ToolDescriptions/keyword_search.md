Search the document texts with the keyword index (websearch_to_tsquery): finds the
sections where the words of the question appear as written, without synonyms. Returns
the sections ranked best by the index, each with its document; a section already
returned comes back only as its id. With `limit` (1 to 50, default 10) choose how many
sections to fetch. With `document_ids` it searches only inside those documents; with
`from`/`to` (ISO dates, inclusive) it searches only the documents whose period
touches them.
