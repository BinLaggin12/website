# House rental system

Big Data Project

Authors: Maciej Zygmanowski, Sofiyan Mohammed

## How to run

```sh
docker compose up -d     # cassandra
python -m house_rental   # backend
```

Stress tests (Requires running cassandra)

```sh
python -m house_rental.stress_tests
```

## API

See ![API examples](./api_examples.http)
