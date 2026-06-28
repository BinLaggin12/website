#!/bin/bash

# drop everything in cas1 (docker)
docker exec -it cas1 cqlsh -e "DROP KEYSPACE IF EXISTS house_rental;"
