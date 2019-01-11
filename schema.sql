-- To create the database, start psql interactive terminal, then
--
--   pairing=# CREATE DATABASE installations;

CREATE TABLE installation (
    id SERIAL PRIMARY KEY,
    install_id INT NOT NULL,
    sub_id INT,
    api_key VARCHAR(100)
);

CREATE INDEX ON installation (install_id);