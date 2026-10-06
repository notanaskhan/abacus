-- Local and test passwords only (never staging or production). Runs after bootstrap.sql.
ALTER ROLE abacus_owner PASSWORD 'abacusowner';
ALTER ROLE abacus_app PASSWORD 'abacusapp';
